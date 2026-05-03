"""
Kautilya AI — Agents Routes Blueprint
Handles /api/agents/* endpoints (Voice & Chat Agent config).
"""
import time
import json
import uuid
import secrets
from flask import Blueprint, request, jsonify, Response

from config import MAX_AGENTS_FREE, MAX_AGENTS_PRO
from services.auth_service import verify_firebase_token, record_usage
from services.memory_service import process_uploaded_file, generate_semantic_chunks, read_website

agents_bp = Blueprint('agents', __name__)


@agents_bp.route('/api/agents/create', methods=['POST'])
def api_agent_create():
    from extensions import db, limit_manager
    from firebase_admin import firestore
    token_data = verify_firebase_token()
    uid = token_data.get('uid') if token_data else None
    if not uid: return jsonify({"error": "Authentication required"}), 401
    if not db: return jsonify({"error": "Database not available"}), 503
    
    data = request.get_json() or {}
    name = data.get('name', 'My Agent')[:100]
    
    is_pro = limit_manager.is_pro_user(uid)
    max_agents = MAX_AGENTS_PRO if is_pro else MAX_AGENTS_FREE
    try:
        existing = db.collection('agents').where(filter=firestore.FieldFilter('uid', '==', uid)).stream()
        if sum(1 for _ in existing) >= max_agents:
            return jsonify({"error": f"Max {max_agents} agents allowed on {'Pro' if is_pro else 'Free'} plan"}), 400
    except Exception as e:
        print(f"[Agents] Count check error: {e}")
    
    agent_id = secrets.token_hex(16)
    
    agent_data = {
        'uid': uid, 'name': name,
        'system_prompt': data.get('system_prompt', 'You are a helpful AI assistant.')[:10000],
        'welcome_message': data.get('welcome_message', 'Hello! How can I help you today?')[:500],
        'fallback_message': data.get('fallback_message', "I'm sorry, I didn't catch that.")[:500],
        'model': data.get('model', 'kautilya-daily'),
        'voice': data.get('voice', 'shubh'),
        'language': data.get('language', 'hi-IN'),
        'temperature': min(max(float(data.get('temperature', 0.7)), 0.0), 2.0),
        'max_tokens': min(int(data.get('max_tokens', 4096)), 16384),
        'agent_type': data.get('agent_type', 'inbound'),
        'stt_provider': data.get('stt_provider', 'sarvam'),
        'tts_provider': data.get('tts_provider', 'cartesia'),
        'interruption_mode': data.get('interruption_mode', 'allow'),
        'silence_timeout': min(max(float(data.get('silence_timeout', 1.5)), 0.5), 10.0),
        'max_call_duration': int(data.get('max_call_duration', 300)),
        'end_on_silence': bool(data.get('end_on_silence', False)),
        'exotel_sid': data.get('exotel_sid', '')[:100],
        'exotel_api_key': data.get('exotel_api_key', '')[:100],
        'exotel_token': data.get('exotel_token', '')[:100],
        'exotel_number': data.get('exotel_number', '')[:20],
        'exotel_subdomain': data.get('exotel_subdomain', 'api.exotel.com')[:100],
        'telephony_provider': data.get('telephony_provider', 'exotel')[:20],
        'vobiz_auth_id': data.get('vobiz_auth_id', '')[:100],
        'vobiz_auth_token': data.get('vobiz_auth_token', '')[:100],
        'vobiz_number': data.get('vobiz_number', '')[:20],
        'conversational_flow': data.get('conversational_flow', []),
        'knowledge_base': data.get('knowledge_base', []),
        'status': 'active',
        'created_at': firestore.SERVER_TIMESTAMP,
        'updated_at': firestore.SERVER_TIMESTAMP,
    }
    
    linked_numbers = []
    if agent_data['exotel_number']: linked_numbers.append(agent_data['exotel_number'])
    if agent_data['vobiz_number']: linked_numbers.append(agent_data['vobiz_number'])
    extra_numbers = data.get('linked_numbers', [])
    if isinstance(extra_numbers, list):
        linked_numbers.extend([n for n in extra_numbers if n])
    agent_data['linked_numbers'] = list(set(linked_numbers))
    
    db.collection('agents').document(agent_id).set(agent_data)
    return jsonify({"agent_id": agent_id, "name": name, "message": "Agent created successfully"})


@agents_bp.route('/api/agents/list', methods=['GET'])
def api_agent_list():
    from extensions import db, limit_manager
    from firebase_admin import firestore
    token_data = verify_firebase_token()
    uid = token_data.get('uid') if token_data else None
    if not uid: return jsonify({"error": "Authentication required"}), 401
    if not db: return jsonify({"error": "Database not available"}), 503
    
    try:
        docs = db.collection('agents').where(filter=firestore.FieldFilter('uid', '==', uid)).stream()
        agents = []
        for doc in docs:
            d = doc.to_dict()
            agent = {
                "agent_id": doc.id, "name": d.get('name', 'Unnamed'), "system_prompt": d.get('system_prompt', ''),
                "welcome_message": d.get('welcome_message', ''), "fallback_message": d.get('fallback_message', ''),
                "model": d.get('model', 'kautilya-daily'), "voice": d.get('voice', 'shubh'), "language": d.get('language', 'hi-IN'),
                "temperature": d.get('temperature', 0.7), "max_tokens": d.get('max_tokens', 4096),
                "agent_type": d.get('agent_type', 'inbound'), "stt_provider": d.get('stt_provider', 'sarvam'),
                "tts_provider": d.get('tts_provider', 'cartesia'), "interruption_mode": d.get('interruption_mode', 'allow'),
                "silence_timeout": d.get('silence_timeout', 1.5), "max_call_duration": d.get('max_call_duration', 300),
                "end_on_silence": d.get('end_on_silence', False), "exotel_sid": d.get('exotel_sid', ''),
                "exotel_token": d.get('exotel_token', ''), "exotel_number": d.get('exotel_number', ''),
                "exotel_subdomain": d.get('exotel_subdomain', 'api.exotel.com'), "status": d.get('status', 'active'),
                "call_count": d.get('call_count', 0),
                "created_at": d.get('created_at').isoformat() if hasattr(d.get('created_at'), 'isoformat') else None,
                "latest_intelligence": None
            }
            try:
                latest_log = db.collection('agents').document(doc.id).collection('agent_logs')\
                               .order_by('created_at', direction=firestore.Query.DESCENDING).limit(1).get()
                if latest_log:
                    log_data = latest_log[0].to_dict()
                    agent["latest_intelligence"] = {
                        "summary": log_data.get("summary", ""), "sentiment": log_data.get("sentiment_score", "neutral"),
                        "timestamp": log_data.get("created_timestamp")
                    }
            except: pass
            agents.append(agent)
        
        is_pro = limit_manager.is_pro_user(uid)
        return jsonify({"agents": agents, "max_agents": MAX_AGENTS_PRO if is_pro else MAX_AGENTS_FREE, "tier": "pro" if is_pro else "free"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@agents_bp.route('/api/agents/<agent_id>/update', methods=['POST'])
def api_agent_update_alias(agent_id):
    """Dashboard-compat alias for PUT /api/agents/<id>."""
    request.environ['REQUEST_METHOD'] = 'PUT'
    return api_agent_detail(agent_id)


@agents_bp.route('/api/agents/<agent_id>/delete', methods=['POST'])
def api_agent_delete_alias(agent_id):
    """Dashboard-compat alias for DELETE /api/agents/<id>."""
    request.environ['REQUEST_METHOD'] = 'DELETE'
    return api_agent_delete(agent_id)


@agents_bp.route('/api/agents/<agent_id>', methods=['GET', 'PUT'])
def api_agent_detail(agent_id):
    from extensions import db
    from firebase_admin import firestore
    token_data = verify_firebase_token()
    uid = token_data.get('uid') if token_data else None
    if not uid: return jsonify({"error": "Authentication required"}), 401
    if not db: return jsonify({"error": "Database not available"}), 503
    
    try:
        doc_ref = db.collection('agents').document(agent_id)
        doc = doc_ref.get()
        if not doc.exists or doc.to_dict().get('uid') != uid: return jsonify({"error": "Agent not found"}), 404
            
        if request.method == 'GET':
            agent_data = doc.to_dict()
            agent_data['agent_id'] = doc.id
            return jsonify(agent_data)
        
        data = request.get_json() or {}
        update_fields = {'updated_at': firestore.SERVER_TIMESTAMP}
        allowed = [
            'name', 'system_prompt', 'welcome_message', 'fallback_message', 'model', 'voice', 'language', 'temperature', 
            'max_tokens', 'agent_type', 'stt_provider', 'tts_provider', 'interruption_mode', 'silence_timeout', 'max_call_duration', 
            'end_on_silence', 'exotel_sid', 'exotel_api_key', 'exotel_token', 'exotel_number', 'exotel_subdomain', 'telephony_provider', 
            'vobiz_auth_id', 'vobiz_auth_token', 'vobiz_number', 'conversational_flow', 'knowledge_base', 'status', 'linked_numbers', 
            'call_objective', 'post_call_webhook'
        ]
        for field in allowed:
            if field in data:
                val = data[field]
                if field == 'name': val = str(val)[:100]
                elif field == 'system_prompt': val = str(val)[:10000]
                elif field in ('welcome_message', 'fallback_message'): val = str(val)[:500]
                elif field == 'temperature': val = min(max(float(val), 0.0), 2.0)
                elif field == 'max_tokens': val = min(int(val), 16384)
                elif field == 'silence_timeout': val = min(max(float(val), 0.5), 10.0)
                elif field == 'max_call_duration': val = int(val)
                elif field == 'end_on_silence': val = bool(val)
                update_fields[field] = val
        
        linked_numbers = []
        existing = doc.to_dict()
        if update_fields.get('exotel_number', existing.get('exotel_number')): linked_numbers.append(update_fields.get('exotel_number', existing.get('exotel_number')))
        if update_fields.get('vobiz_number', existing.get('vobiz_number')): linked_numbers.append(update_fields.get('vobiz_number', existing.get('vobiz_number')))
        manual = update_fields.get('linked_numbers', existing.get('linked_numbers', []))
        if isinstance(manual, list): linked_numbers.extend([n for n in manual if n and n not in linked_numbers])
        update_fields['linked_numbers'] = list(set(linked_numbers))
        
        doc_ref.update(update_fields)
        return jsonify({"status": "ok", "message": "Agent updated"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@agents_bp.route('/api/agents/<agent_id>', methods=['DELETE'])
def api_agent_delete(agent_id):
    from extensions import db
    token_data = verify_firebase_token()
    uid = token_data.get('uid') if token_data else None
    if not uid: return jsonify({"error": "Authentication required"}), 401
    
    try:
        doc = db.collection('agents').document(agent_id).get()
        if not doc.exists or doc.to_dict().get('uid') != uid: return jsonify({"error": "Agent not found"}), 404
        db.collection('agents').document(agent_id).delete()
        return jsonify({"status": "ok", "message": "Agent deleted"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@agents_bp.route('/api/agents/<agent_id>/logs', methods=['GET', 'POST'])
def api_agent_logs(agent_id):
    from extensions import db
    from firebase_admin import firestore
    if request.method == 'POST':
        data = request.get_json() or {}
        try:
            log_data = {
                'agent_id': agent_id, 'duration': data.get('duration', 0), 'status': data.get('status', 'completed'),
                'messages': data.get('messages', 0), 'transcript': data.get('transcript', ''), 'analysis': data.get('analysis', ''),
                'summary': data.get('summary', ''), 'sentiment': data.get('sentiment', 'neutral'), 'outcome': data.get('outcome', False),
                'created_at': firestore.SERVER_TIMESTAMP
            }
            db.collection('agents').document(agent_id).collection('agent_logs').add(log_data)
            db.collection('agents').document(agent_id).update({"call_count": firestore.Increment(1)})
            return jsonify({"status": "ok"})
        except Exception as e:
            return jsonify({"error": str(e)}), 500
            
    token_data = verify_firebase_token()
    uid = token_data.get('uid') if token_data else None
    try:
        doc = db.collection('agents').document(agent_id).get()
        if not doc.exists or doc.to_dict().get('uid') != uid: return jsonify({"error": "Agent not found"}), 404
        try:
            logs_ref = db.collection('agents').document(agent_id).collection('agent_logs')\
                         .order_by('created_at', direction=firestore.Query.DESCENDING).limit(50).stream()
        except:
            logs_ref = db.collection('agents').document(agent_id).collection('agent_logs').limit(50).stream()
        logs = []
        for l in logs_ref:
            d = l.to_dict()
            if 'created_at' in d and hasattr(d['created_at'], 'timestamp'):
                d['created_timestamp'] = d['created_at'].timestamp()
                del d['created_at']
            d['id'] = l.id
            logs.append(d)
        return jsonify({"logs": logs})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@agents_bp.route('/api/agents/<agent_id>/kb', methods=['GET', 'POST'])
def api_agent_kb(agent_id):
    from extensions import db
    from firebase_admin import firestore
    token_data = verify_firebase_token()
    uid = token_data.get('uid') if token_data else None
    if not uid: return jsonify({"error": "Authentication required"}), 401
    
    try:
        agent_ref = db.collection('agents').document(agent_id)
        doc = agent_ref.get()
        if not doc.exists or doc.to_dict().get('uid') != uid: return jsonify({"error": "Agent not found"}), 404
        
        kb = doc.to_dict().get('knowledge_base', [])
        if request.method == 'POST':
            if 'files' not in request.files: return jsonify({"error": "No files provided"}), 400
            new_files = []
            for file in request.files.getlist('files'):
                if not file.filename: continue
                processed = process_uploaded_file(file)
                if not processed or processed.get('type') != 'text': continue
                chunks = generate_semantic_chunks(processed.get('text', ''))
                new_files.append({
                    "id": str(uuid.uuid4())[:8], "name": file.filename, "type": file.mimetype,
                    "size": len(processed.get('text', '')), "created_at": int(time.time()),
                    "chunks": chunks, "content": processed.get('text', '')
                })
            if not new_files: return jsonify({"error": "No valid documents"}), 400
            kb.extend(new_files)
            agent_ref.update({"knowledge_base": kb, "updated_at": firestore.SERVER_TIMESTAMP})
            return jsonify({"status": "ok", "message": f"{len(new_files)} files uploaded", "files": new_files})
            
        kb_meta = [{"id": f["id"], "name": f["name"], "type": f.get("type", "text/plain"), "size": f.get("size", 0), "created_at": f.get("created_at")} for f in kb]
        return jsonify({"knowledge_base": kb_meta})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@agents_bp.route('/api/agents/<agent_id>/kb-url', methods=['POST'])
def api_agent_kb_url(agent_id):
    from extensions import db
    from firebase_admin import firestore
    token_data = verify_firebase_token()
    uid = token_data.get('uid') if token_data else None
    if not uid: return jsonify({"error": "Authentication required"}), 401
    try:
        agent_ref = db.collection('agents').document(agent_id)
        doc = agent_ref.get()
        if not doc.exists or doc.to_dict().get('uid') != uid: return jsonify({"error": "Agent not found"}), 404
        url = (request.get_json() or {}).get('url')
        if not url: return jsonify({"error": "URL is required"}), 400
        text = read_website(url)
        if not text: return jsonify({"error": "Could not extract content"}), 400
        chunks = generate_semantic_chunks(text)
        kb = doc.to_dict().get('knowledge_base', [])
        file_id = str(uuid.uuid4())[:8]
        kb.append({
            "id": file_id, "name": f"Web: {url[:30]}...", "type": "text/html",
            "size": len(text), "created_at": int(time.time()), "chunks": chunks, "content": text, "url": url
        })
        agent_ref.update({"knowledge_base": kb, "updated_at": firestore.SERVER_TIMESTAMP})
        return jsonify({"status": "ok", "message": "Website indexed", "file_id": file_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@agents_bp.route('/api/agents/<agent_id>/kb/<file_id>/content', methods=['GET'])
def api_agent_kb_content(agent_id, file_id):
    from extensions import db
    token_data = verify_firebase_token()
    uid = token_data.get('uid') if token_data else None
    if not uid: return jsonify({"error": "Authentication required"}), 401
    try:
        doc = db.collection('agents').document(agent_id).get()
        if not doc.exists or doc.to_dict().get('uid') != uid: return jsonify({"error": "Agent not found"}), 404
        target_file = next((f for f in doc.to_dict().get('knowledge_base', []) if f['id'] == file_id), None)
        if not target_file: return jsonify({"error": "File not found"}), 404
        return jsonify({"name": target_file.get("name"), "content": target_file.get("content", ""), "chunks": target_file.get("chunks", []), "url": target_file.get("url")})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@agents_bp.route('/api/agents/<agent_id>/chat', methods=['POST'])
def api_agent_chat(agent_id):
    """Streaming chat with a configured agent.

    The dashboard's "Test" panel and any external API consumer hit this. We
    load the agent's saved system_prompt + (optional) knowledge-base context,
    forward the conversation to the LLM, and stream the response as
    Server-Sent Events: `data: {"content": "..."}` per chunk, `data: [DONE]`.
    """
    from extensions import db
    from services.llm_service import call_groq

    token_data = verify_firebase_token()
    uid = token_data.get('uid') if token_data else None
    if not uid:
        return jsonify({"error": "Authentication required"}), 401
    if not db:
        return jsonify({"error": "Database not available"}), 503

    body = request.get_json(silent=True) or {}
    incoming = body.get('messages') or []
    if not isinstance(incoming, list) or not incoming:
        return jsonify({"error": "messages array required"}), 400

    try:
        doc = db.collection('agents').document(agent_id).get()
        if not doc.exists:
            return jsonify({"error": "Agent not found"}), 404
        agent = doc.to_dict() or {}
        # Allow either the owner OR any caller using a valid API key (the
        # dashboard always passes a Firebase token for the owner; external
        # consumers pass an API key whose uid matches the agent's owner).
        if agent.get('uid') and agent.get('uid') != uid and not token_data.get('is_admin'):
            return jsonify({"error": "Agent not found"}), 404
    except Exception as e:
        return jsonify({"error": f"Agent lookup failed: {e}"}), 500

    system_prompt = (agent.get('system_prompt') or 'You are a helpful AI assistant.')
    welcome = agent.get('welcome_message') or ''
    model_name = (agent.get('model') or 'kautilya-daily').lower()
    temperature = float(agent.get('temperature') or 0.7)
    max_tokens = int(agent.get('max_tokens') or 4096)

    # Lightweight KB injection: take the user's last message and pull the top
    # matching chunks from the agent's stored knowledge base (if any).
    kb_context = ""
    try:
        kb = agent.get('knowledge_base') or []
        if kb and incoming:
            last_user = next((m for m in reversed(incoming) if (m.get('role') == 'user')), None)
            if last_user:
                last_text = last_user.get('content') or ''
                if isinstance(last_text, list):
                    last_text = " ".join(p.get('text', '') for p in last_text if isinstance(p, dict))
                if last_text:
                    needle = last_text.lower()
                    snippets = []
                    for f in kb[:10]:
                        for ch in (f.get('chunks') or [])[:50]:
                            if not isinstance(ch, str):
                                continue
                            if any(w for w in needle.split() if len(w) > 3 and w in ch.lower()):
                                snippets.append(ch)
                                if len(snippets) >= 4:
                                    break
                        if len(snippets) >= 4:
                            break
                    if snippets:
                        kb_context = "\n\nKNOWLEDGE BASE (use when relevant):\n" + "\n---\n".join(snippets[:4])
    except Exception as e:
        print(f"[Agent Chat] KB lookup warning: {e}")

    full_system = system_prompt + kb_context
    if welcome:
        full_system += f"\n\nIf the conversation has just started, greet the user with: \"{welcome}\""

    # Map dashboard model aliases to a real Groq model id
    groq_model = "llama-3.3-70b-versatile"
    if "pro" in model_name:
        groq_model = "llama-3.3-70b-versatile"
    elif "coder" in model_name:
        groq_model = "llama-3.3-70b-versatile"
    # Gemini Live is voice-only — fall through to Groq for chat.

    chat_messages = [{"role": "system", "content": full_system}]
    for m in incoming:
        if isinstance(m, dict) and m.get('role') in ('user', 'assistant') and m.get('content'):
            chat_messages.append({"role": m['role'], "content": m['content']})

    def stream():
        full_text = ""
        try:
            gen = call_groq(
                chat_messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
                model=groq_model,
            )
            if gen is None:
                yield f"data: {json.dumps({'content': 'Service temporarily unavailable.'})}\n\n"
                yield "data: [DONE]\n\n"
                return
            for item in gen:
                if isinstance(item, dict) and item.get('chunk'):
                    chunk = item['chunk']
                    full_text += chunk
                    # Frontend reads `d.content`
                    yield f"data: {json.dumps({'content': chunk})}\n\n"
        except Exception as e:
            print(f"[Agent Chat] Stream error: {e}")
            yield f"data: {json.dumps({'content': f'[Error: {e}]'})}\n\n"

        # Usage tracking — rough 4-chars-per-token estimate
        try:
            in_chars = sum(len(str(m.get('content') or '')) for m in chat_messages)
            est_tokens = max(1, (in_chars + len(full_text)) // 4)
            record_usage(uid, 'llm_tokens', est_tokens, model=groq_model)
        except Exception as e:
            print(f"[Agent Chat] usage record failed: {e}")

        # Persist a lightweight log entry so Studio "Recent" shows test chats too
        try:
            from firebase_admin import firestore as _fs
            db.collection('agents').document(agent_id).collection('agent_logs').add({
                'agent_id': agent_id,
                'channel': 'chat',
                'duration': 0,
                'status': 'completed',
                'messages': len(incoming) + 1,
                'transcript': "\n".join(
                    f"{(m.get('role') or '').upper()}: {m.get('content')}" for m in incoming
                ) + f"\nASSISTANT: {full_text}",
                'summary': (full_text or '').strip().splitlines()[0][:200] if full_text else 'Test chat',
                'sentiment': 'neutral',
                'outcome': bool(full_text),
                'model': groq_model,
                'created_at': _fs.SERVER_TIMESTAMP,
            })
        except Exception as e:
            print(f"[Agent Chat] log persist warning: {e}")

        yield "data: [DONE]\n\n"

    return Response(stream(), mimetype='text/event-stream', headers={
        'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no', 'Connection': 'keep-alive'
    })


@agents_bp.route('/api/agents/<agent_id>/kb/<file_id>', methods=['DELETE'])
def api_agent_kb_delete(agent_id, file_id):
    from extensions import db
    from firebase_admin import firestore
    token_data = verify_firebase_token()
    uid = token_data.get('uid') if token_data else None
    if not uid: return jsonify({"error": "Authentication required"}), 401
    try:
        agent_ref = db.collection('agents').document(agent_id)
        doc = agent_ref.get()
        if not doc.exists or doc.to_dict().get('uid') != uid: return jsonify({"error": "Agent not found"}), 404
        kb = [f for f in doc.to_dict().get('knowledge_base', []) if f['id'] != file_id]
        agent_ref.update({"knowledge_base": kb, "updated_at": firestore.SERVER_TIMESTAMP})
        return jsonify({"status": "ok", "message": "File deleted"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
