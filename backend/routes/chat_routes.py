"""
Kautilya AI — Chat Routes Blueprint
Handles /api/chat, /api/jarvis/* endpoints.
"""
import os
import re
import json
import time
import uuid
import queue
import threading

from flask import Blueprint, request, jsonify, Response

from config import SYSTEM_PROMPT, CODER_SYSTEM_PROMPT, PRO_SYSTEM_PROMPT, RESEARCH_SYSTEM_PROMPT
from services.auth_service import verify_firebase_token, record_usage
from services.memory_service import (
    get_user_chat_dir, get_user_memory, save_user_memory,
    extract_memories, build_personalized_prompt, build_cli_system_prompt,
    process_uploaded_file, record_user_session
)
from services.agent_loop_service import get_llm_response, normalize_model_choice
from services.research_service import deep_research_stream
from services.fast_response_cache import (
    try_canned_reply, cache_get as fast_cache_get, cache_put as fast_cache_put,
)
from middleware.rate_limiter import check_message_rate_limit
from middleware.security import block_sensitive_query

chat_bp = Blueprint('chat', __name__)

# In-memory conversation store — user-scoped dict: conversations[uid][session_id] = conv
conversations = {}
CONVERSATION_TTL = 3600
MAX_HISTORY = 20
MAX_INMEM_CONVERSATIONS_PER_USER = 20


def _get_conversation(uid, session_id):
    user_id = uid or "guest"
    sid = session_id
    # Check in-memory first
    if user_id in conversations and sid in conversations[user_id]:
        conv = conversations[user_id][sid]
        if time.time() - conv.get('last_active', 0) > CONVERSATION_TTL:
            del conversations[user_id][sid]
        else:
            stored_uid = conv.get('uid')
            if stored_uid and uid and stored_uid != uid:
                return None
            return conv
    # Not in memory — try to restore from Firestore (survives HF Spaces restarts)
    if uid:
        try:
            from extensions import db
            if db:
                msgs_ref = (db.collection('users').document(uid)
                              .collection('conversations').document(sid)
                              .collection('messages')
                              .order_by('timestamp')
                              .limit_to_last(MAX_HISTORY * 2))
                docs = list(msgs_ref.get())
                if docs:
                    restored = []
                    for doc in docs:
                        d = doc.to_dict()
                        content = d.get('content', '')
                        try:
                            content = json.loads(content) if isinstance(content, str) and content.startswith('[') else content
                        except:
                            pass
                        restored.append({"role": d.get('role', 'user'), "content": content})
                    if restored:
                        print(f"[Conversation] Restored {len(restored)} messages for session {sid[:8]}")
                        return {"messages_to_restore": restored, "uid": uid, "session_id": sid}
        except Exception as e:
            print(f"[Conversation] Firestore restore failed: {e}")
    return None


def _cleanup_expired_conversations():
    """Periodic cleanup of expired user conversations."""
    now = time.time()
    for user_id in list(conversations.keys()):
        user_convs = conversations[user_id]
        for sid in list(user_convs.keys()):
            if now - user_convs[sid].get('last_active', 0) > CONVERSATION_TTL:
                del user_convs[sid]
        if not user_convs:
            del conversations[user_id]


def _enforce_user_limit(uid):
    """Keep only the most recent MAX_INMEM_CONVERSATIONS_PER_USER per user."""
    user_id = uid or "guest"
    if user_id not in conversations:
        return
    user_convs = conversations[user_id]
    if len(user_convs) <= MAX_INMEM_CONVERSATIONS_PER_USER:
        return
    sorted_sids = sorted(user_convs.keys(), key=lambda s: user_convs[s].get('last_active', 0), reverse=True)
    for sid in sorted_sids[MAX_INMEM_CONVERSATIONS_PER_USER:]:
        del user_convs[sid]


def _generate_chat_title(uid, session_id, user_msg, assistant_msg):
    """Background job: ask a tiny LLM for a 3-5 word title and save it to the
    conversation doc so the sidebar shows something meaningful instead of the
    raw first line of the last message."""
    from extensions import db
    if not db or not uid:
        return

    def _worker():
        try:
            # Skip if a non-default title already exists for this session
            ref = db.collection('users').document(uid).collection('conversations').document(session_id)
            snap = ref.get()
            if snap.exists:
                existing = (snap.to_dict() or {}).get('title')
                if existing and len(existing) > 0 and len(existing) < 60 and not existing.startswith('New Chat'):
                    return  # leave intact

            from services.llm_service import call_groq
            um = (user_msg or '')[:600] if isinstance(user_msg, str) else str(user_msg)[:600]
            am = (assistant_msg or '')[:600]
            prompt = (
                "Summarize this conversation in 3-5 words for a chat history sidebar. "
                "No quotes, no punctuation at the end, no model names, just the topic. "
                "Examples: 'React date picker bug', 'Marketing budget Q3', 'Sanskrit grammar help'.\n\n"
                f"User: {um}\n\nAssistant: {am}\n\nTitle:"
            )
            raw = call_groq(
                [{"role": "user", "content": prompt}],
                model='llama-3.3-70b-versatile',
                temperature=0.3, max_tokens=20, stream=False,
            )
            if not raw or not isinstance(raw, str):
                return
            title = raw.strip().strip('"').strip("'").strip()
            # First line only; drop "Title:" prefix some models add
            title = title.split('\n')[0]
            if title.lower().startswith('title:'):
                title = title[6:].strip()
            # Clamp length / word count
            words = title.split()
            if len(words) > 7:
                title = ' '.join(words[:7])
            if len(title) > 60:
                title = title[:60].rsplit(' ', 1)[0]
            if not title:
                return
            ref.set({'title': title}, merge=True)
            print(f"[Title] Generated for {session_id[:8]}: {title}")
        except Exception as e:
            print(f"[Title] Generation failed: {e}")

    threading.Thread(target=_worker, daemon=True).start()


def save_to_firestore(uid, session_id, role, content, message_id=None, streaming=False, extras=None):
    """Save a chat message.
    - If `message_id` is provided, the message doc is updated (used for live
      streaming so reopening the app reveals in-progress responses).
    - `streaming=True` marks the message as still generating; the frontend
      polls until this flips false.
    - `extras` (dict) carries structured side-data so it survives reload:
        tool_results, react_steps, citations, artifact (type/title/code).
    """
    from extensions import db
    if not db or not uid:
        return None
    try:
        from firebase_admin import firestore
        conv_ref = db.collection('users').document(uid).collection('conversations').document(session_id)
        preview = ""
        if isinstance(content, str):
            preview = content[:60] + "..." if len(content) > 60 else content
        elif isinstance(content, list):
            for part in content:
                if part.get("type") == "text":
                    text = part.get("text", "")
                    preview = text[:60] + "..." if len(text) > 60 else text
                    break
            if not preview:
                preview = "[Media Message]"
        conv_ref.set({
            'last_updated': firestore.SERVER_TIMESTAMP,
            'preview': preview,
            'session_id': session_id,
            'streaming': bool(streaming),
        }, merge=True)
        saved_content = json.dumps(content) if isinstance(content, list) else content
        payload = {
            'role': role,
            'content': saved_content,
            'streaming': bool(streaming),
            'timestamp': firestore.SERVER_TIMESTAMP,
        }
        if extras and isinstance(extras, dict):
            # Firestore disallows None values; strip them, and JSON-encode
            # nested structures so we don't hit nested-array limits.
            for k in ('tool_results', 'react_steps', 'citations', 'artifact', 'agent_type'):
                v = extras.get(k)
                if v in (None, [], {}, ''):
                    continue
                if isinstance(v, (list, dict)):
                    try:
                        payload[k] = json.dumps(v)[:200_000]
                    except Exception:
                        continue
                else:
                    payload[k] = v
        msgs = conv_ref.collection('messages')
        if message_id:
            msgs.document(message_id).set(payload, merge=True)
            return message_id
        new_ref = msgs.document()
        new_ref.set(payload)
        return new_ref.id
    except Exception as e:
        print(f"[History] Save failed: {e}")
        return None


@chat_bp.route('/jarvis/stream', methods=['POST'])
def jarvis_stream():
    """Main streaming chat endpoint."""
    from extensions import limit_manager, vector_store, db

    # NEW: Even more robust extraction
    data = request.get_json(silent=True) or {}
    form = request.form or {}
    args = request.args or {}
    
    # Extract message from any possible field
    message = (data.get('message') or data.get('text') or 
               form.get('text') or form.get('message') or 
               args.get('text') or args.get('message') or '').strip()
               
    session_id = data.get('session_id') or form.get('session_id') or args.get('session_id', str(uuid.uuid4()))
    model = normalize_model_choice(data.get('model') or form.get('model') or args.get('model', 'auto'))
    # Max Thinking toggle — enables reasoning_content streaming on pro/coder models.
    _mt_raw = data.get('max_thinking', form.get('max_thinking', args.get('max_thinking', False)))
    max_thinking = str(_mt_raw).lower() in ('1', 'true', 'yes', 'on')
    
    # Correctly handle files list
    files = []
    if request.files:
        try:
            files = request.files.getlist('files')
        except:
            pass
            
    print(f"[DEBUG] jarvis_stream: msg_len={len(message)}, files_count={len(files)}, session={session_id}, model={model}")

    token_data = verify_firebase_token()
    uid = token_data.get('uid') if token_data else None
    user_email = token_data.get('email') if token_data else None
    user_name = token_data.get('name') or token_data.get('display_name') if token_data else None
    client_ip = request.headers.get('X-Forwarded-For', request.remote_addr) or "unknown"
    if ',' in client_ip:
        client_ip = client_ip.split(',')[0].strip()

    # Security: banned check
    identifier = uid or client_ip
    if limit_manager.is_banned(identifier, client_ip):
        return jsonify({"error": "Access denied"}), 403

    # Prompt injection check
    block_msg = block_sensitive_query(message, uid)
    if block_msg:
        def blocked():
            yield f"data: {json.dumps({'chunk': block_msg})}\n\n"
        return Response(blocked(), mimetype='text/event-stream')

    # Rate limit check
    tier = "pro" if (uid and limit_manager.is_pro_user(uid)) else ("free" if uid else "guest")
    allowed, err_msg = check_message_rate_limit(identifier, tier)
    if not allowed:
        def rate_err():
            yield f"data: {json.dumps({'chunk': err_msg})}\n\n"
        return Response(rate_err(), mimetype='text/event-stream')

    # ───────────────────────── Fast-response cache ─────────────────────────
    # Trivial chat ("hi", "ok", "thanks", "who are you", repeated short
    # questions) bypasses the agent loop entirely and returns a canned or
    # cached reply in ~5 ms instead of ~1-2 s of LLM round-trip. Skipped
    # when files are attached or for modes that have a custom flow
    # (research has its own pipeline; coder/pro should always get real
    # model output even on small queries).
    fast_eligible = (
        message
        and not files
        and model in ('auto', 'daily')
    )
    fast_reply = None
    if fast_eligible:
        fast_reply = try_canned_reply(message) or fast_cache_get(message, model)
    if fast_reply:
        # Persist both sides of the exchange so chat history stays correct.
        try:
            save_to_firestore(uid, session_id, "user", message)
            save_to_firestore(uid, session_id, "assistant", fast_reply, streaming=False)
        except Exception as e:
            print(f"[FastCache] Firestore save failed (non-fatal): {e}")

        def fast_sse():
            # Emit as a single chunk — the frontend renders SSE chunks
            # incrementally, so a one-shot reply lands as fast as the
            # client can read the socket.
            yield f"data: {json.dumps({'chunk': fast_reply})}\n\n"
            yield "data: [DONE]\n\n"

        return Response(fast_sse(), mimetype='text/event-stream', headers={
            'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no', 'Connection': 'keep-alive',
            'X-Kautilya-Cache': 'hit',
        })

    # Build conversation (user-scoped)
    conv = _get_conversation(uid, session_id)
    restored_messages = None
    if conv and 'messages_to_restore' in conv:
        # Firestore-restored session — rebuild in-memory conv with history
        restored_messages = conv['messages_to_restore']
        conv = None  # trigger full build below

    if not conv:
        _cleanup_expired_conversations()
        user_memories = get_user_memory(uid) if uid else []
        settings = {}
        if uid and db:
            try:
                sdoc = db.collection('users').document(uid).collection('settings').document('profile').get()
                if sdoc.exists:
                    settings = sdoc.to_dict()
            except:
                pass

        if model == 'coder':
            sys_prompt = build_cli_system_prompt(CODER_SYSTEM_PROMPT)
        elif model == 'pro':
            sys_prompt = build_personalized_prompt(PRO_SYSTEM_PROMPT, user_name, user_memories, user_email, settings, uid=uid)
        elif model == 'research':
            sys_prompt = build_personalized_prompt(RESEARCH_SYSTEM_PROMPT, user_name, user_memories, user_email, settings, uid=uid)
        else:
            sys_prompt = build_personalized_prompt(SYSTEM_PROMPT, user_name, user_memories, user_email, settings, uid=uid)

        user_id = uid or "guest"
        if user_id not in conversations:
            conversations[user_id] = {}

        base_messages = [{"role": "system", "content": sys_prompt}]
        if restored_messages:
            # Re-attach Firestore history so context is preserved across restarts
            base_messages.extend(restored_messages)

        conv = {
            'messages': base_messages,
            'last_active': time.time(),
            'uid': uid,
            'created_at': time.time(),
            'model': model,
            'message_count': 0,
            'title': None
        }
        conversations[user_id][session_id] = conv
        _enforce_user_limit(uid)
    else:
        conv['last_active'] = time.time()

    # Process file uploads
    user_content_parts = []
    if files:
        for f in files:
            processed = process_uploaded_file(f)
            if processed:
                user_content_parts.append(processed)

    if message:
        user_content_parts.insert(0, {"type": "text", "text": message})

    if not user_content_parts:
        return jsonify({"error": "No message"}), 400

    if model == "research":
        research_queue = queue.Queue()
        research_content_holder = [""]
        # Save user query first so reopening shows what they asked
        save_to_firestore(uid, session_id, "user", message)
        # Streaming placeholder so reopened tabs see deep-research progress
        research_msg_id = save_to_firestore(uid, session_id, "assistant", "", streaming=True)
        research_flush_ts = [time.time()]

        def _run_research():
            try:
                for event in deep_research_stream(message):
                    if event.get("event") == "chunk":
                        research_content_holder[0] += event.get("chunk", "")
                        # Flush every 1.5s so it's visible after reopen
                        if research_msg_id and time.time() - research_flush_ts[0] >= 1.5:
                            try:
                                save_to_firestore(uid, session_id, "assistant",
                                                  research_content_holder[0],
                                                  message_id=research_msg_id, streaming=True)
                                research_flush_ts[0] = time.time()
                            except Exception:
                                pass
                    research_queue.put(json.dumps(event))
            except Exception as e:
                research_queue.put(json.dumps({'event': 'chunk', 'chunk': f'[error: {e}]'}))
            finally:
                research_queue.put(None)
                full_research = research_content_holder[0]
                if uid:
                    try:
                        save_to_firestore(uid, session_id, "assistant",
                                          full_research or "[no response]",
                                          message_id=research_msg_id, streaming=False)
                        print(f"[Research] Saved {len(full_research)} chars for session {session_id}")
                    except Exception as e:
                        print(f"[Research] Firestore save failed: {e}")

        threading.Thread(target=_run_research, daemon=True).start()

        def research_sse():
            while True:
                try:
                    item = research_queue.get(timeout=300)
                except queue.Empty:
                    break
                if item is None:
                    break
                yield f"data: {item}\n\n"
            yield "data: [DONE]\n\n"

        return Response(research_sse(), mimetype='text/event-stream', headers={
            'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no', 'Connection': 'keep-alive'
        })

    user_message = user_content_parts if len(user_content_parts) > 1 else (user_content_parts[0].get("text", "") if user_content_parts[0].get("type") == "text" else user_content_parts)

    # Real-time identity capture: scan THIS message for self-disclosed handles
    # ("my github is harshcoder1122", "my email is …", "I'm Harsh") and (a) save
    # them to long-term memory and (b) inject a system note into the current
    # turn so the model can't hallucinate a different handle on its first tool
    # call. Without this, the fact only landed via the background LLM-based
    # extraction AFTER the response — too late to prevent the wrong call.
    if uid and isinstance(user_message, str):
        try:
            from services.memory_service import extract_identity_facts_inline, merge_identity_facts_into_memory
            id_facts = extract_identity_facts_inline(user_message)
            if id_facts:
                stored = merge_identity_facts_into_memory(uid, id_facts)
                if stored:
                    inject = (
                        "[SYSTEM: The user just self-disclosed identifying info in this message — "
                        "use these EXACT values for any subsequent tool call, do NOT substitute a "
                        "similar-looking name from training data:\n  • " + "\n  • ".join(stored) + "]"
                    )
                    # Prepend to the system prompt so this turn already sees it.
                    if conv['messages'] and conv['messages'][0].get('role') == 'system':
                        conv['messages'][0]['content'] = str(conv['messages'][0].get('content', '')) + "\n\n" + inject
        except Exception as _e:
            print(f"[Memory] inline identity capture failed: {_e}")

    conv['messages'].append({"role": "user", "content": user_message})
    save_to_firestore(uid, session_id, "user", user_message)

    # Trim history
    if len(conv['messages']) > MAX_HISTORY * 2:
        conv['messages'] = [conv['messages'][0]] + conv['messages'][-(MAX_HISTORY * 2):]

    def stream():
        """
        The LLM runs in a background thread — it saves to Firestore when done,
        regardless of whether the client is still connected. The SSE generator
        here just reads from a queue. If the user navigates away mid-stream,
        the thread keeps running and the response is saved for when they return.

        A placeholder assistant message is created in Firestore at the start
        and updated every ~1.5s with the partial response so reopening the
        app reveals the in-progress generation (no more "dead UI" feeling).
        """
        chunk_queue = queue.Queue()
        full_response_holder = [""]  # list so the thread can mutate via closure
        # Collected structured side-data — persisted alongside the text so
        # tool-result cards / ReAct steps / citations don't vanish on reload.
        side_data = {
            'tool_results': [],
            'react_steps': {},  # id → step dict
            'citations': [],
            'artifact': None,
            'agent_type': None,
        }
        # Reserve a streaming-message doc id up-front; the LLM thread flushes into it.
        assistant_msg_id = save_to_firestore(uid, session_id, "assistant", "", streaming=True)
        last_flush_ts = [time.time()]
        # Tighter flush cadence so remounting the chat (route change, tab
        # switch, refresh) finds an almost-up-to-date partial in Firestore
        # — the visible "vanished output" window is bounded by this.
        FLUSH_INTERVAL_SEC = 0.5

        def _maybe_flush_partial(force=False):
            """Periodically write the current partial response back to Firestore."""
            if not assistant_msg_id or not uid:
                return
            now = time.time()
            if not force and now - last_flush_ts[0] < FLUSH_INTERVAL_SEC:
                return
            try:
                save_to_firestore(uid, session_id, "assistant",
                                  full_response_holder[0],
                                  message_id=assistant_msg_id, streaming=True)
                last_flush_ts[0] = now
            except Exception as e:
                print(f"[Stream] partial flush failed: {e}")

        def _run_llm():
            try:
                gen = get_llm_response(
                    conv['messages'], uid=uid, model=model,
                    user_ip=client_ip, max_thinking=max_thinking
                )
                if gen is None:
                    chunk_queue.put(json.dumps({'chunk': 'Service temporarily unavailable.'}))
                    return

                def _capture(parsed):
                    """Extract structured side-data from one event so it survives reload."""
                    if not isinstance(parsed, dict):
                        return
                    if "chunk" in parsed:
                        full_response_holder[0] += parsed["chunk"]
                        return
                    ev = parsed.get("event") or parsed.get("type")
                    if ev == "tool_result":
                        side_data['tool_results'].append({
                            'tool': parsed.get('tool'),
                            'data': parsed.get('data'),
                        })
                    elif ev in ("react_action", "react_action_done"):
                        sid = parsed.get('id') or f"s{len(side_data['react_steps'])}"
                        prev = side_data['react_steps'].get(sid, {})
                        prev.update({
                            'id': sid,
                            'tool': parsed.get('tool') or prev.get('tool'),
                            'input': parsed.get('input') if parsed.get('input') is not None else prev.get('input'),
                            'status': parsed.get('status') or prev.get('status'),
                            'preview': parsed.get('preview') or prev.get('preview'),
                            'sources': parsed.get('sources') or prev.get('sources'),
                        })
                        side_data['react_steps'][sid] = prev
                    elif ev == "sources":
                        side_data['citations'] = parsed.get('sources') or []
                    elif ev == "artifact":
                        side_data['artifact'] = {
                            'type': parsed.get('artifactType'),
                            'title': parsed.get('artifactTitle'),
                        }
                    elif ev == "agent":
                        side_data['agent_type'] = parsed.get('agent') or side_data['agent_type']

                for item in gen:
                    if isinstance(item, str):
                        try:
                            parsed = json.loads(item)
                            _capture(parsed)
                        except json.JSONDecodeError:
                            full_response_holder[0] += item
                        chunk_queue.put(item)
                    elif isinstance(item, dict):
                        _capture(item)
                        chunk_queue.put(json.dumps(item))
                    # Periodic Firestore flush so reopening the app shows progress
                    _maybe_flush_partial()
            except Exception as e:
                print(f"[LLM Thread] Error: {e}")
                chunk_queue.put(json.dumps({'chunk': f'[Error: {e}]'}))
            finally:
                chunk_queue.put(None)  # sentinel: stream finished

                # ---- Persist to Firestore (runs even if client disconnected) ----
                full_response = full_response_holder[0]
                if full_response:
                    try:
                        conv['messages'].append({"role": "assistant", "content": full_response})
                        conv['message_count'] = len(conv['messages'])
                        if not conv.get('title') and conv['message_count'] >= 2:
                            title = full_response.strip().split('\n')[0][:60]
                            conv['title'] = title if title else "New Chat"
                        # Final write — flip streaming flag off so the frontend stops polling.
                        save_to_firestore(
                            uid, session_id, "assistant", full_response,
                            message_id=assistant_msg_id, streaming=False,
                            extras={
                                'tool_results': side_data['tool_results'],
                                'react_steps': list(side_data['react_steps'].values()),
                                'citations': side_data['citations'],
                                'artifact': side_data['artifact'],
                                'agent_type': side_data['agent_type'],
                            },
                        )
                        print(f"[Stream] Saved response ({len(full_response)} chars) for session {session_id}")
                        # Feed the fast-response LRU: short query + short reply
                        # = a future hit. The cache itself decides whether
                        # the lengths qualify, we just hand it the pair.
                        try:
                            if message and isinstance(message, str) and model in ('auto', 'daily'):
                                fast_cache_put(message, model, full_response)
                        except Exception:
                            pass
                        # AI-generated 3-4 word title for the sidebar (background job)
                        _generate_chat_title(uid, session_id, message, full_response)
                    except Exception as e:
                        print(f"[Stream] Firestore save failed: {e}")
                else:
                    # No content produced — clear the placeholder so it doesn't loop forever
                    if assistant_msg_id and uid:
                        try:
                            save_to_firestore(uid, session_id, "assistant",
                                              "[no response]",
                                              message_id=assistant_msg_id, streaming=False)
                        except Exception:
                            pass

                # Usage tracking — runs for every completed stream so the daily
                # llm_tokens counter (and the Usage page chart) reflects real activity.
                if uid:
                    try:
                        est_tokens = max(1, (len(str(message or '')) + len(full_response)) // 4)
                        record_usage(uid, 'llm_tokens', est_tokens, model=model)
                    except Exception as e:
                        print(f"[Usage] llm_tokens record failed: {e}")

                # Background memory extraction
                if uid and message and full_response:
                    def _bg_memory(fr=full_response):
                        try:
                            memories = get_user_memory(uid)
                            new_facts = extract_memories(message, fr, memories)
                            if new_facts:
                                memories.extend(new_facts)
                                save_user_memory(uid, memories)
                        except Exception as e:
                            print(f"[Memory] Background extraction failed: {e}")
                    threading.Thread(target=_bg_memory, daemon=True).start()

        # Launch LLM thread — independent of client connection
        t = threading.Thread(target=_run_llm, daemon=True)
        t.start()

        # SSE: read from queue and forward to client
        # If client disconnects, we stop yielding but the thread keeps running
        while True:
            try:
                item = chunk_queue.get(timeout=180)  # 3-min max wait per chunk
            except queue.Empty:
                print(f"[Stream] Queue timeout for session {session_id}")
                break
            if item is None:  # sentinel — thread finished
                break
            yield f"data: {item}\n\n"

        yield "data: [DONE]\n\n"

    return Response(stream(), mimetype='text/event-stream', headers={
        'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no', 'Connection': 'keep-alive'
    })

@chat_bp.route('/jarvis/command', methods=['POST'])
def jarvis_command():
    """Wrapper for jarvis_stream to support the dashboard's /command endpoint."""
    return jarvis_stream()


@chat_bp.route('/jarvis/prewarm', methods=['POST'])
def jarvis_prewarm():
    """Pre-warm endpoint to initialize conversation state."""
    return jsonify({"status": "ok", "message": "Kautilya Brain pre-warmed."})


@chat_bp.route('/chat', methods=['POST'])
def chat_legacy():
    """Legacy non-streaming chat endpoint."""
    from extensions import limit_manager
    data = request.json
    message = data.get("message", "")
    uid = data.get("uid", None)
    model = normalize_model_choice(data.get("model", "auto"))
    client_ip = request.remote_addr
    if limit_manager.is_banned(uid, client_ip):
        return jsonify({"response": "🚫 Access Denied"}), 403
    if not message:
        return jsonify({"error": "No message provided"}), 400
    try:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": message}]
        llm_response = get_llm_response(messages, uid=uid, model=model, user_ip=client_ip)
        full_response = ""
        if isinstance(llm_response, str):
            full_response = llm_response
        else:
            for chunk in llm_response:
                if chunk and not (chunk.startswith('{') and '"type": "status"' in chunk):
                    full_response += chunk
        return jsonify({"status": "success", "response": full_response})
    except Exception as e:
        return jsonify({"status": "error", "response": f"Internal error: {str(e)}"}), 500


@chat_bp.route('/jarvis/history', methods=['GET'])
def get_all_history():
    from extensions import db
    from firebase_admin import firestore
    token_data = verify_firebase_token()
    uid = token_data.get('uid') if token_data else None
    if not uid:
        return jsonify({"error": "Unauthorized"}), 401
    if not db:
        return jsonify({"chats": []})
    try:
        docs = db.collection('users').document(uid).collection('conversations') \
                .order_by('last_updated', direction=firestore.Query.DESCENDING).limit(50).stream()
        chats = []
        for doc in docs:
            if doc.id.startswith('cli-'):
                continue
            data = doc.to_dict()
            data['session_id'] = doc.id
            if 'last_updated' in data and data['last_updated']:
                data['last_updated'] = data['last_updated'].isoformat()
            chats.append(data)
        return jsonify({"chats": chats})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@chat_bp.route('/jarvis/history/<session_id>', methods=['GET'])
def get_chat_history(session_id):
    from extensions import db
    token_data = verify_firebase_token()
    uid = token_data.get('uid') if token_data else None
    if not uid:
        return jsonify({"error": "Unauthorized"}), 401
    if not db:
        return jsonify({"messages": []})
    try:
        docs = db.collection('users').document(uid).collection('conversations').document(session_id) \
                 .collection('messages').order_by('timestamp').stream()
        messages = []
        streaming_any = False
        for doc in docs:
            data = doc.to_dict()
            content = data.get("content")
            if isinstance(content, str):
                try:
                    if content.strip().startswith('[') and content.strip().endswith(']'):
                        content = json.loads(content)
                except:
                    pass
            is_streaming = bool(data.get("streaming", False))
            if is_streaming:
                streaming_any = True

            def _unjson(val):
                if not isinstance(val, str):
                    return val
                s = val.strip()
                if not s:
                    return None
                if s[0] in '[{':
                    try:
                        return json.loads(s)
                    except Exception:
                        return val
                return val

            msg = {
                "id": doc.id,
                "role": data.get("role"),
                "content": content,
                "streaming": is_streaming,
            }
            for k in ('tool_results', 'react_steps', 'citations', 'artifact'):
                if data.get(k) is not None:
                    msg[k] = _unjson(data.get(k))
            if data.get('agent_type'):
                msg['agent_type'] = data.get('agent_type')
            messages.append(msg)
        return jsonify({
            "messages": messages,
            "session_id": session_id,
            "streaming": streaming_any,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@chat_bp.route('/jarvis/history/<session_id>', methods=['DELETE'])
def delete_chat_history(session_id):
    from extensions import db
    token_data = verify_firebase_token()
    uid = token_data.get('uid') if token_data else None
    if not uid:
        return jsonify({"error": "Unauthorized"}), 401
    if not db:
        return jsonify({"status": "ok"})
    try:
        doc_ref = db.collection('users').document(uid).collection('conversations').document(session_id)
        msgs = doc_ref.collection('messages').limit(100).stream()
        for m in msgs:
            m.reference.delete()
        doc_ref.delete()
        user_id = uid or "guest"
        if user_id in conversations and session_id in conversations[user_id]:
            del conversations[user_id][session_id]
        return jsonify({"status": "ok", "session_id": session_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@chat_bp.route('/jarvis/status', methods=['GET'])
def get_user_status():
    from extensions import limit_manager
    from config import _MESSAGE_RATE_LIMITS
    token_data = verify_firebase_token()
    uid = token_data.get('uid') if token_data else None
    if not uid:
        return jsonify({"error": "Unauthorized"}), 401
    is_pro = limit_manager.is_pro_user(uid)
    today = time.strftime("%Y-%m-%d")
    user_record = limit_manager.usage_data.get(uid, {})
    current_chats = user_record.get("chat_count", 0) if user_record.get("last_chat_date") == today else 0
    tier = "pro" if is_pro else "free"
    limit = _MESSAGE_RATE_LIMITS[tier]["per_day"]
    # Active in-memory sessions for this user
    active_sessions = []
    user_id = uid or "guest"
    if user_id in conversations:
        active_sessions = [
            {"session_id": sid, "title": c.get("title"), "model": c.get("model"), "message_count": c.get("message_count", 0)}
            for sid, c in conversations[user_id].items()
        ]
    return jsonify({
        "is_pro": is_pro, "role": "Pro Plan" if is_pro else "Free Plan",
        "usage": {"chats_today": current_chats, "daily_limit": limit,
                  "remaining": (limit - current_chats) if limit is not None else "Unlimited"},
        "sessions": {"active_count": len(active_sessions), "active": active_sessions}
    })


@chat_bp.route('/jarvis/make_pro', methods=['POST'])
def remote_make_pro():
    from extensions import limit_manager
    admin_key = os.environ.get("ADMIN_SECRET_KEY")
    if not admin_key:
        return jsonify({"error": "Admin Secret Key not configured"}), 500
    data = request.json
    if not data or data.get("admin_key") != admin_key:
        return jsonify({"error": "Unauthorized Admin Key"}), 403
    target_uid = data.get("uid")
    if not target_uid:
        return jsonify({"error": "No target UID provided"}), 400
    try:
        limit_manager.add_pro_user(target_uid)
        return jsonify({"status": "success", "message": f"User {target_uid} upgraded to Pro"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@chat_bp.route('/chat/history', methods=['GET'])
def chat_history_legacy():
    token_data = verify_firebase_token()
    uid = token_data.get('uid') if token_data else None
    if not uid:
        return jsonify({"error": "Authentication required"}), 401
    user_dir = get_user_chat_dir(uid)
    chats_file = os.path.join(user_dir, 'chats.json')
    if os.path.exists(chats_file):
        try:
            with open(chats_file, 'r', encoding='utf-8') as f:
                chats = json.load(f)
            return jsonify({"chats": {cid: d for cid, d in chats.items() if not str(cid).startswith('cli-')}})
        except Exception as e:
            return jsonify({"chats": {}, "error": str(e)})
    return jsonify({"chats": {}})


@chat_bp.route('/chat/save', methods=['POST'])
def chat_save():
    token_data = verify_firebase_token()
    uid = token_data.get('uid') if token_data else None
    if not uid:
        return jsonify({"error": "Authentication required"}), 401
    data = request.get_json()
    incoming_chats = data.get('chats', {})
    if not incoming_chats:
        return jsonify({"error": "No chats provided"}), 400
    user_dir = get_user_chat_dir(uid)
    chats_file = os.path.join(user_dir, 'chats.json')
    existing = {}
    if os.path.exists(chats_file):
        try:
            with open(chats_file, 'r', encoding='utf-8') as f:
                existing = json.load(f)
        except:
            pass
    existing.update(incoming_chats)
    with open(chats_file, 'w', encoding='utf-8') as f:
        json.dump(existing, f, ensure_ascii=False)
    return jsonify({"status": "ok", "saved": len(incoming_chats)})


@chat_bp.route('/chat/delete', methods=['DELETE'])
def chat_delete():
    token_data = verify_firebase_token()
    uid = token_data.get('uid') if token_data else None
    if not uid:
        return jsonify({"error": "Authentication required"}), 401
    data = request.get_json()
    chat_id = data.get('chat_id', '')
    if not chat_id:
        return jsonify({"error": "No chat_id provided"}), 400
    user_dir = get_user_chat_dir(uid)
    chats_file = os.path.join(user_dir, 'chats.json')
    if os.path.exists(chats_file):
        try:
            with open(chats_file, 'r', encoding='utf-8') as f:
                chats = json.load(f)
            if chat_id in chats:
                del chats[chat_id]
                with open(chats_file, 'w', encoding='utf-8') as f:
                    json.dump(chats, f, ensure_ascii=False)
                return jsonify({"status": "ok", "deleted": chat_id})
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    return jsonify({"status": "ok", "message": "Chat not found"})
