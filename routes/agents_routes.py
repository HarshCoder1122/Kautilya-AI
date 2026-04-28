"""
Kautilya AI — Agents Routes Blueprint
Handles /api/agents/* endpoints (Voice & Chat Agent config).
"""
import time
import uuid
import secrets
from flask import Blueprint, request, jsonify

from config import MAX_AGENTS_FREE, MAX_AGENTS_PRO
from services.auth_service import verify_firebase_token
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
