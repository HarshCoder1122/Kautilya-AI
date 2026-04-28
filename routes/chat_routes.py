"""
Kautilya AI — Chat Routes Blueprint
Handles /api/chat, /api/jarvis/* endpoints.
"""
import os
import re
import io
import json
import time
import uuid
import base64
import threading
import requests

from flask import Blueprint, request, jsonify, Response

from config import SYSTEM_PROMPT, CODER_SYSTEM_PROMPT, GROQ_API_KEY, SARVAM_API_KEY
from services.auth_service import verify_firebase_token
from services.memory_service import (
    get_user_chat_dir, get_user_memory, save_user_memory,
    extract_memories, build_personalized_prompt, build_cli_system_prompt,
    process_uploaded_file, record_user_session
)
from services.agent_loop_service import get_llm_response
from services.command_service import execute_cloud_commands
from services.tts_service import clean_text_for_tts, detect_tts_voice
from middleware.rate_limiter import check_message_rate_limit
from middleware.security import block_sensitive_query

chat_bp = Blueprint('chat', __name__)

# In-memory conversation store (to be replaced with Redis/Firestore later)
conversations = {}
CONVERSATION_TTL = 3600
MAX_HISTORY = 20


def _get_conversation(session_id):
    if session_id in conversations:
        conv = conversations[session_id]
        if time.time() - conv.get('last_active', 0) > CONVERSATION_TTL:
            del conversations[session_id]
            return None
        return conv
    return None


def save_to_firestore(uid, session_id, role, content):
    from extensions import db
    if not db or not uid:
        return
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
        conv_ref.set({'last_updated': firestore.SERVER_TIMESTAMP, 'preview': preview, 'session_id': session_id}, merge=True)
        saved_content = json.dumps(content) if isinstance(content, list) else content
        conv_ref.collection('messages').document().set({'role': role, 'content': saved_content, 'timestamp': firestore.SERVER_TIMESTAMP})
    except Exception as e:
        print(f"[History] Save failed: {e}")


@chat_bp.route('/api/jarvis/stream', methods=['POST'])
def jarvis_stream():
    """Main streaming chat endpoint."""
    from extensions import limit_manager, vector_store, db

    data = request.get_json() or {}
    message = data.get('message', '')
    session_id = data.get('session_id', str(uuid.uuid4()))
    model = data.get('model', 'daily')
    files = request.files.getlist('files') if request.content_type and 'multipart' in request.content_type else []

    token_data = verify_firebase_token()
    uid = token_data.get('uid') if token_data else None
    user_email = token_data.get('email') if token_data else None
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

    # Build conversation
    conv = _get_conversation(session_id)
    if not conv:
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
        else:
            sys_prompt = build_personalized_prompt(SYSTEM_PROMPT, user_email, user_memories, user_email, settings)

        conv = {
            'messages': [{"role": "system", "content": sys_prompt}],
            'last_active': time.time(),
            'uid': uid
        }
        conversations[session_id] = conv
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

    user_message = user_content_parts if len(user_content_parts) > 1 else (user_content_parts[0].get("text", "") if user_content_parts[0].get("type") == "text" else user_content_parts)

    conv['messages'].append({"role": "user", "content": user_message})
    save_to_firestore(uid, session_id, "user", user_message)

    # Trim history
    if len(conv['messages']) > MAX_HISTORY * 2:
        conv['messages'] = [conv['messages'][0]] + conv['messages'][-(MAX_HISTORY * 2):]

    def stream():
        full_response = ""
        try:
            gen = get_llm_response(conv['messages'], uid=uid, model=model, user_ip=client_ip)
            if gen is None:
                yield f"data: {json.dumps({'chunk': 'Service temporarily unavailable.'})}\n\n"
                return
            for item in gen:
                if isinstance(item, str):
                    try:
                        parsed = json.loads(item)
                        if "chunk" in parsed:
                            full_response += parsed["chunk"]
                        yield f"data: {item}\n\n"
                    except json.JSONDecodeError:
                        full_response += item
                        yield f"data: {json.dumps({'chunk': item})}\n\n"
                elif isinstance(item, dict):
                    if "chunk" in item:
                        full_response += item["chunk"]
                    yield f"data: {json.dumps(item)}\n\n"
        except Exception as e:
            print(f"[Stream] Error: {e}")
            yield f"data: {json.dumps({'chunk': f'[Error: {e}]'})}\n\n"

        # Post-processing
        if full_response:
            processed = execute_cloud_commands(full_response, uid=uid)
            if processed != full_response:
                extra = processed[len(full_response):]
                if extra:
                    yield f"data: {json.dumps({'chunk': extra})}\n\n"
                full_response = processed

            conv['messages'].append({"role": "assistant", "content": full_response})
            save_to_firestore(uid, session_id, "assistant", full_response)

            # Background memory extraction
            if uid and message:
                def bg_memory():
                    try:
                        memories = get_user_memory(uid)
                        new_facts = extract_memories(message, full_response, memories)
                        if new_facts:
                            memories.extend(new_facts)
                            save_user_memory(uid, memories)
                    except Exception as e:
                        print(f"[Memory] Background extraction failed: {e}")
                threading.Thread(target=bg_memory, daemon=True).start()

        yield "data: [DONE]\n\n"

    return Response(stream(), mimetype='text/event-stream', headers={
        'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no', 'Connection': 'keep-alive'
    })


@chat_bp.route('/api/jarvis/command', methods=['POST'])
def jarvis_command():
    """Wrapper for jarvis_stream to support the dashboard's /command endpoint."""
    return jarvis_stream()


@chat_bp.route('/api/jarvis/prewarm', methods=['POST'])
def jarvis_prewarm():
    """Pre-warm endpoint to initialize conversation state."""
    return jsonify({"status": "ok", "message": "Kautilya Brain pre-warmed."})


@chat_bp.route('/api/chat', methods=['POST'])
def chat_legacy():
    """Legacy non-streaming chat endpoint."""
    from extensions import limit_manager
    data = request.json
    message = data.get("message", "")
    uid = data.get("uid", None)
    model = data.get("model", "daily")
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


@chat_bp.route('/api/jarvis/history', methods=['GET'])
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


@chat_bp.route('/api/jarvis/history/<session_id>', methods=['GET'])
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
        for doc in docs:
            data = doc.to_dict()
            content = data.get("content")
            if isinstance(content, str):
                try:
                    if content.strip().startswith('[') and content.strip().endswith(']'):
                        content = json.loads(content)
                except:
                    pass
            messages.append({"role": data.get("role"), "content": content})
        return jsonify({"messages": messages, "session_id": session_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@chat_bp.route('/api/jarvis/history/<session_id>', methods=['DELETE'])
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
        if session_id in conversations:
            del conversations[session_id]
        return jsonify({"status": "ok", "session_id": session_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@chat_bp.route('/api/jarvis/status', methods=['GET'])
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
    return jsonify({
        "is_pro": is_pro, "role": "Pro Plan" if is_pro else "Free Plan",
        "usage": {"chats_today": current_chats, "daily_limit": limit,
                  "remaining": (limit - current_chats) if limit is not None else "Unlimited"}
    })


@chat_bp.route('/api/jarvis/make_pro', methods=['POST'])
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


@chat_bp.route('/api/chat/history', methods=['GET'])
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


@chat_bp.route('/api/chat/save', methods=['POST'])
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


@chat_bp.route('/api/chat/delete', methods=['DELETE'])
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
