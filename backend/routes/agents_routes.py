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
from services.auth_service import verify_firebase_token, record_usage, hash_api_key
from services.memory_service import process_uploaded_file, read_website
from services.embedding_service import (
    process_document_for_embedding,
    search_similar_chunks,
    embed_text,
    chunk_text,
    EMBED_MODEL,
)

agents_bp = Blueprint('agents', __name__)


def _embed_kb_fields(content, source_name, source_type="text"):
    """Build the embedding-related fields for a KB entry. Used by the upload,
    URL and crawl paths so web-indexed content gets embedded too (not just file
    uploads). Returns {} of safe defaults if embedding fails — never raises."""
    try:
        embedded_chunks = process_document_for_embedding(
            text=content, source_name=source_name, source_type=source_type
        )
    except Exception as embed_err:
        print(f"[KB] Embedding failed for {source_name}: {embed_err}", flush=True)
        embedded_chunks = []
    return {
        "embedded_chunks": embedded_chunks,
        "embedding_model": EMBED_MODEL if embedded_chunks else "none",
        "embedding_count": len(embedded_chunks),
        "has_embeddings": bool(embedded_chunks),
    }


# Firestore caps a single document at 1 MiB. Embedding vectors (1024 floats ≈
# 8 KB each) plus full document text blow past that fast, so the heavy per-file
# payload lives in a `kb_files` subcollection (one doc per file) and only slim
# metadata + semantic text chunks stay on the agent document. These caps keep a
# single file's subcollection doc safely under 1 MiB too.
KB_MAX_STORED_EMBED_CHUNKS = 60
KB_MAX_STORED_CONTENT_CHARS = 250_000


def _persist_kb(agent_ref, kb_list):
    """Save a knowledge_base list while keeping the agent doc under 1 MiB.

    For every entry: the heavy fields (`content`, `embedded_chunks`) are written
    to `agents/<id>/kb_files/<file_id>` and stripped from the array stored on the
    agent document. This also migrates older inline entries — on the next write
    an already-bloated array slims down automatically. Returns the slim list.
    """
    from firebase_admin import firestore
    slim = []
    for f in kb_list:
        fid = f.get("id")
        content = f.get("content")
        embedded = f.get("embedded_chunks")
        if fid is not None and (content is not None or embedded is not None):
            heavy = {}
            if content is not None:
                heavy["content"] = (content or "")[:KB_MAX_STORED_CONTENT_CHARS]
            if embedded is not None:
                if len(embedded) > KB_MAX_STORED_EMBED_CHUNKS:
                    print(f"[KB] {fid}: storing first {KB_MAX_STORED_EMBED_CHUNKS}/{len(embedded)} "
                          f"embedded chunks (1 MiB doc cap)", flush=True)
                heavy["embedded_chunks"] = embedded[:KB_MAX_STORED_EMBED_CHUNKS]
            try:
                agent_ref.collection("kb_files").document(fid).set(heavy, merge=True)
            except Exception as e:
                print(f"[KB] subcollection write failed for {fid}: {e}", flush=True)
        slim.append({k: v for k, v in f.items() if k not in ("content", "embedded_chunks")})
    agent_ref.update({"knowledge_base": slim, "updated_at": firestore.SERVER_TIMESTAMP})
    return slim


def _load_kb_heavy(agent_ref, file_id):
    """Fetch a file's heavy payload (content + embedded_chunks) from the
    kb_files subcollection. Returns {} if absent."""
    try:
        snap = agent_ref.collection("kb_files").document(file_id).get()
        if snap.exists:
            return snap.to_dict() or {}
    except Exception as e:
        print(f"[KB] subcollection read failed for {file_id}: {e}", flush=True)
    return {}


def _load_all_embedded_chunks(agent_ref):
    """Gather every embedded chunk ({text, embedding, ...}) across all of an
    agent's KB files (from the kb_files subcollection) for semantic search."""
    out = []
    try:
        for snap in agent_ref.collection("kb_files").stream():
            for ch in (snap.to_dict() or {}).get("embedded_chunks", []):
                if isinstance(ch, dict) and ch.get("embedding") and ch.get("text"):
                    out.append(ch)
    except Exception as e:
        print(f"[KB] embedded-chunk load failed: {e}", flush=True)
    return out


def _retrieve_kb_context(agent_ref, agent, query_text, top_k=5):
    """Build a KB context block for `query_text`. Prefers semantic search over
    the bge-m3 embeddings (across ALL files); falls back to keyword matching on
    the agent doc's `chunks` (also across ALL files, not just the first 10)."""
    if not query_text:
        return ""
    snippets = []
    # 1) Semantic retrieval via embeddings.
    try:
        embedded = _load_all_embedded_chunks(agent_ref)
        if embedded:
            hits = search_similar_chunks(query_text, embedded, top_k=top_k)
            snippets = [h["text"] for h in hits
                        if h.get("text") and h.get("similarity", 0) >= 0.2]
    except Exception as e:
        print(f"[KB] semantic retrieval warning: {e}", flush=True)
    # 2) Keyword fallback across every file's chunks.
    if not snippets:
        needle = [w for w in query_text.lower().split() if len(w) > 3]
        for f in (agent.get("knowledge_base") or []):
            for ch in (f.get("chunks") or []):
                if isinstance(ch, str) and any(w in ch.lower() for w in needle):
                    snippets.append(ch)
                    break
            if len(snippets) >= top_k:
                break
    if not snippets:
        return ""
    return "\n\nKNOWLEDGE BASE (use when relevant; answer from this, don't guess):\n" + \
           "\n---\n".join(snippets[:top_k])

# Integrations an agent can be allowed to use post-call. Stored on the agent as
# a {key: bool} map; missing/None = enabled (default-on, backward compatible).
INTEGRATION_KEYS = ('crm', 'google_calendar', 'gmail', 'whatsapp', 'slack')


def _sanitize_integrations(val):
    """Coerce a client-sent integrations map to {known_key: bool}. Unknown keys
    are dropped; only explicit booleans are kept so the default-on rule holds."""
    if not isinstance(val, dict):
        return {}
    return {k: bool(val[k]) for k in INTEGRATION_KEYS if k in val}


@agents_bp.route('/agents/create', methods=['POST'])
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
        'integrations': _sanitize_integrations(data.get('integrations')),
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


@agents_bp.route('/agents/list', methods=['GET'])
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


@agents_bp.route('/agents/<agent_id>/update', methods=['POST'])
def api_agent_update_alias(agent_id):
    """Dashboard-compat alias for PUT /api/agents/<id>."""
    request.environ['REQUEST_METHOD'] = 'PUT'
    return api_agent_detail(agent_id)


@agents_bp.route('/agents/<agent_id>/delete', methods=['POST'])
def api_agent_delete_alias(agent_id):
    """Dashboard-compat alias for DELETE /api/agents/<id>."""
    request.environ['REQUEST_METHOD'] = 'DELETE'
    return api_agent_delete(agent_id)


@agents_bp.route('/agents/<agent_id>', methods=['GET', 'PUT'])
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
            'call_objective', 'post_call_webhook', 'handoff_enabled', 'handoff_number', 'handoff_callback_message', 'lead_webhook_url',
            'integrations'
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
                elif field == 'integrations': val = _sanitize_integrations(val)
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


@agents_bp.route('/agents/<agent_id>', methods=['DELETE'])
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


@agents_bp.route('/agents/<agent_id>/logs', methods=['GET', 'POST'])
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
            # Firestore Timestamp isn't JSON-serialisable. Expose BOTH a numeric
            # `created_timestamp` and an ISO `created_at` string — the dashboard
            # reads `created_at` for display/sorting, so we must not drop it.
            ca = d.get('created_at')
            if ca is not None and hasattr(ca, 'timestamp'):
                d['created_timestamp'] = ca.timestamp()
                try:
                    d['created_at'] = ca.isoformat()
                except Exception:
                    d['created_at'] = None
            d['id'] = l.id
            logs.append(d)
        return jsonify({"logs": logs})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@agents_bp.route('/agents/<agent_id>/livekit-token', methods=['POST'])
def generate_external_livekit_token(agent_id):
    """External API endpoint to generate a LiveKit token using an API key."""
    import os
    from extensions import db
    try:
        from livekit import api
    except ImportError:
        return jsonify({"error": "LiveKit SDK not installed"}), 500

    # 1. Validate API Key from header
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return jsonify({"error": "Missing or invalid Authorization header. Use Bearer <api_key>"}), 401
    
    api_key = auth_header.split('Bearer ')[1].strip()

    # 2. Check key in database. Keys are stored under their SHA-256 hash (see
    # auth_service.hash_api_key / keys_routes) — looking up the RAW key as the
    # doc id (the previous behaviour) never matched, so this endpoint was dead.
    if not db:
        return jsonify({"error": "Database unavailable"}), 503

    key_doc = db.collection('api_keys').document(hash_api_key(api_key)).get()
    if not key_doc.exists:
        return jsonify({"error": "Invalid API key"}), 401

    key_data = key_doc.to_dict()
    if not key_data.get('is_active', False):
        return jsonify({"error": "API key is revoked"}), 401
    uid = key_data.get('uid')
    
    # 3. Verify agent belongs to this user
    agent_doc = db.collection('agents').document(agent_id).get()
    if not agent_doc.exists or agent_doc.to_dict().get('uid') != uid:
        return jsonify({"error": "Agent not found or access denied"}), 404
        
    agent_data = agent_doc.to_dict()

    # 4. Generate LiveKit Token
    lk_api_key = os.environ.get("LIVEKIT_API_KEY")
    lk_api_secret = os.environ.get("LIVEKIT_API_SECRET")
    if not lk_api_key or not lk_api_secret:
        return jsonify({"error": "LiveKit configuration missing on server"}), 500

    data = request.get_json(silent=True) or {}
    participant_name = data.get("participantName", "Web User")
    
    room_name = f"voice-{agent_id}--{uuid.uuid4().hex[:4]}"
    identity = f"user-{uuid.uuid4().hex[:8]}"
    
    token = api.AccessToken(lk_api_key, lk_api_secret) \
        .with_identity(identity) \
        .with_name(participant_name) \
        .with_grants(api.VideoGrants(
            room_join=True,
            room=room_name,
        ))
    
    # Add room metadata for worker routing
    import json
    token.with_metadata(json.dumps({
        "agent_id": agent_id,
        "system_prompt": agent_data.get("system_prompt", ""),
        "voice": agent_data.get("voice", "shubh"),
        "model": agent_data.get("model", "kautilya-daily"),
        "welcome_message": agent_data.get("welcome_message", "")
    }))

    from config import LIVEKIT_URL
    return jsonify({
        "token": token.to_jwt(), 
        "roomName": room_name,
        "wsUrl": LIVEKIT_URL or "wss://your-project.livekit.cloud"
    })


@agents_bp.route('/agents/<agent_id>/kb', methods=['GET', 'POST'])
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
                if not processed:
                    continue
                # Agent KB is text-only (semantic chunks for RAG). If the
                # processor returned a multi-block list (PDF with page images),
                # concatenate the text blocks and ignore image blocks here —
                # vision-augmented PDFs only matter for live chat, not KB.
                if isinstance(processed, list):
                    text_only = "\n".join(b.get('text', '') for b in processed
                                          if isinstance(b, dict) and b.get('type') == 'text').strip()
                    if not text_only:
                        continue
                    content = text_only
                else:
                    if processed.get('type') != 'text':
                        continue
                    content = processed.get('text', '')
                
                # Local fixed-size chunks (keyword retrieval) + vector embeddings (RAG).
                # No LLM here — semantic chunking made one Groq call PER file/page,
                # which rate-limited Groq during multi-file uploads / site crawls.
                chunks = chunk_text(content)
                src_type = ("pdf" if file.filename.lower().endswith('.pdf')
                            else "docx" if file.filename.lower().endswith('.docx') else "text")
                new_files.append({
                    "id": str(uuid.uuid4())[:8], "name": file.filename, "type": file.mimetype,
                    "size": len(content), "created_at": int(time.time()),
                    "chunks": chunks, "content": content,
                    **_embed_kb_fields(content, file.filename, src_type),
                })
            if not new_files: return jsonify({"error": "No valid documents"}), 400
            kb.extend(new_files)
            _persist_kb(agent_ref, kb)
            # Don't echo full content / vectors back to the client.
            resp_files = [{k: v for k, v in f.items() if k not in ("content", "embedded_chunks")} for f in new_files]
            return jsonify({"status": "ok", "message": f"{len(new_files)} files uploaded", "files": resp_files})
            
        # Return KB metadata with embedding info
        kb_meta = []
        for f in kb:
            meta = {
                "id": f["id"], 
                "name": f["name"], 
                "type": f.get("type", "text/plain"), 
                "size": f.get("size", 0), 
                "created_at": f.get("created_at"),
                "embedding_model": f.get("embedding_model", "none"),
                "embedding_count": f.get("embedding_count", 0),
                "has_embeddings": f.get("has_embeddings", f.get("embedding_count", 0) > 0)
            }
            kb_meta.append(meta)
        
        return jsonify({
            "knowledge_base": kb_meta,
            "total_files": len(kb),
            "total_embeddings": sum(f.get("embedding_count", 0) for f in kb)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@agents_bp.route('/agents/<agent_id>/kb-url', methods=['POST'])
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
        chunks = chunk_text(text)
        kb = doc.to_dict().get('knowledge_base', [])
        file_id = str(uuid.uuid4())[:8]
        kb.append({
            "id": file_id, "name": f"Web: {url[:30]}...", "type": "text/html",
            "size": len(text), "created_at": int(time.time()), "chunks": chunks, "content": text, "url": url,
            **_embed_kb_fields(text, f"Web: {url[:30]}", "website"),
        })
        _persist_kb(agent_ref, kb)
        return jsonify({"status": "ok", "message": "Website indexed", "file_id": file_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@agents_bp.route('/agents/<agent_id>/kb-crawl', methods=['POST'])
def api_agent_kb_crawl(agent_id):
    """BFS crawl up to N pages from a start URL, same-origin only.
    Each page becomes its own KB entry so retrieval can score them independently."""
    from extensions import db
    from firebase_admin import firestore
    from urllib.parse import urlparse, urljoin
    from collections import deque
    import re as _re
    token_data = verify_firebase_token()
    uid = token_data.get('uid') if token_data else None
    if not uid: return jsonify({"error": "Authentication required"}), 401
    try:
        agent_ref = db.collection('agents').document(agent_id)
        doc = agent_ref.get()
        if not doc.exists or doc.to_dict().get('uid') != uid:
            return jsonify({"error": "Agent not found"}), 404
        payload = request.get_json() or {}
        start_url = payload.get('url')
        max_pages = min(int(payload.get('max_pages', 50)), 50)
        if not start_url:
            return jsonify({"error": "URL required"}), 400
        if not start_url.startswith(('http://', 'https://')):
            start_url = 'https://' + start_url
        origin = urlparse(start_url).netloc

        seen, queue = set(), deque([start_url])
        kb = doc.to_dict().get('knowledge_base', [])
        added, errors = 0, 0
        link_pat = _re.compile(r'href=["\']([^"\']+)["\']', _re.I)
        import requests as _rq

        # Seed from sitemap.xml — the most reliable way to enumerate a site and
        # essential for SPA/JS sites whose internal links aren't in server HTML.
        try:
            sm = _rq.get(f"https://{origin}/sitemap.xml", timeout=10,
                         headers={"User-Agent": "KautilyaKBCrawler/1.0"})
            if sm.status_code == 200 and '<loc>' in sm.text:
                locs = _re.findall(r'<loc>\s*([^<\s]+)\s*</loc>', sm.text)
                page_locs = []
                for loc in locs:
                    if loc.endswith('.xml'):  # sitemap index → expand one level
                        try:
                            sub = _rq.get(loc, timeout=10, headers={"User-Agent": "KautilyaKBCrawler/1.0"})
                            if sub.status_code == 200:
                                page_locs += _re.findall(r'<loc>\s*([^<\s]+)\s*</loc>', sub.text)
                        except Exception:
                            pass
                    else:
                        page_locs.append(loc)
                for loc in page_locs:
                    loc = loc.split('#')[0]
                    if urlparse(loc).netloc == origin and not loc.endswith('.xml'):
                        queue.append(loc)
                print(f"[KB-Crawl] sitemap seeded {len(page_locs)} urls", flush=True)
        except Exception as _e:
            print(f"[KB-Crawl] sitemap: {_e}", flush=True)

        while queue and len(seen) < max_pages:
            url = queue.popleft()
            if url in seen: continue
            seen.add(url)
            try:
                # Content via Jina (renders JS / SPAs); don't gate on a raw GET.
                text = read_website(url)
                if not text or text.startswith("Error:") or len(text) < 200:
                    continue
                chunks = chunk_text(text)
                page_name = f"Web: {urlparse(url).path[:40] or '/'}"
                kb.append({
                    "id": str(uuid.uuid4())[:8],
                    "name": page_name,
                    "type": "text/html",
                    "size": len(text),
                    "created_at": int(time.time()),
                    "chunks": chunks,
                    "content": text,
                    "url": url,
                    **_embed_kb_fields(text, page_name, "website"),
                })
                added += 1
                # Discover same-origin links from the rendered markdown AND (best
                # effort) the raw HTML — SPA links only show up in the former.
                links = _re.findall(r'\]\((https?://[^)\s]+)\)', text)
                try:
                    raw = _rq.get(url, timeout=8, headers={"User-Agent": "KautilyaKBCrawler/1.0"})
                    if raw.status_code == 200 and 'html' in raw.headers.get('content-type', ''):
                        links += [urljoin(url, h) for h in link_pat.findall(raw.text)]
                except Exception:
                    pass
                for nxt in links[:80]:
                    nxt = urljoin(url, nxt).split('#')[0]
                    if (urlparse(nxt).netloc == origin and nxt not in seen
                            and len(queue) < max_pages * 4):
                        queue.append(nxt)
            except Exception as e:
                errors += 1
                print(f"[KB-Crawl] {url}: {e}")
        _persist_kb(agent_ref, kb)
        return jsonify({"status": "ok", "pages_added": added, "pages_attempted": len(seen), "errors": errors})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@agents_bp.route('/agents/<agent_id>/kb/<file_id>/content', methods=['GET'])
def api_agent_kb_content(agent_id, file_id):
    from extensions import db
    token_data = verify_firebase_token()
    uid = token_data.get('uid') if token_data else None
    if not uid: return jsonify({"error": "Authentication required"}), 401
    try:
        agent_ref = db.collection('agents').document(agent_id)
        doc = agent_ref.get()
        if not doc.exists or doc.to_dict().get('uid') != uid: return jsonify({"error": "Agent not found"}), 404
        target_file = next((f for f in doc.to_dict().get('knowledge_base', []) if f['id'] == file_id), None)
        if not target_file: return jsonify({"error": "File not found"}), 404

        # Heavy payload (full content + vectors) lives in the kb_files subcollection;
        # fall back to inline fields for any not-yet-migrated legacy entry.
        heavy = _load_kb_heavy(agent_ref, file_id)
        embedded_chunks = heavy.get("embedded_chunks", target_file.get("embedded_chunks", []))
        content = heavy.get("content", target_file.get("content", ""))

        chunks_preview = []
        for chunk in embedded_chunks[:10]:  # Limit to first 10 chunks for preview
            chunks_preview.append({
                "id": chunk.get("id"),
                "text_preview": chunk.get("text", "")[:200] + "..." if len(chunk.get("text", "")) > 200 else chunk.get("text", ""),
                "source": chunk.get("source"),
                "chunk_index": chunk.get("chunk_index")
            })

        return jsonify({
            "name": target_file.get("name"),
            "content": content,
            "chunks": target_file.get("chunks", []),
            "url": target_file.get("url"),
            "embedding_model": target_file.get("embedding_model", "none"),
            "embedding_count": target_file.get("embedding_count", len(embedded_chunks)),
            "embedded_chunks": chunks_preview,
            "has_embeddings": len(embedded_chunks) > 0
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@agents_bp.route('/agents/<agent_id>/kb/<file_id>/embeddings', methods=['GET'])
def api_agent_kb_embeddings(agent_id, file_id):
    """Get all embeddings for a specific KB file (eye view)."""
    from extensions import db
    token_data = verify_firebase_token()
    uid = token_data.get('uid') if token_data else None
    if not uid: return jsonify({"error": "Authentication required"}), 401
    try:
        agent_ref = db.collection('agents').document(agent_id)
        doc = agent_ref.get()
        if not doc.exists or doc.to_dict().get('uid') != uid: return jsonify({"error": "Agent not found"}), 404
        target_file = next((f for f in doc.to_dict().get('knowledge_base', []) if f['id'] == file_id), None)
        if not target_file: return jsonify({"error": "File not found"}), 404

        # Embeddings live in the kb_files subcollection (fall back to inline legacy).
        embedded_chunks = _load_kb_heavy(agent_ref, file_id).get(
            "embedded_chunks", target_file.get("embedded_chunks", []))
        return jsonify({
            "file_id": file_id,
            "file_name": target_file.get("name"),
            "embedding_model": target_file.get("embedding_model", "none"),
            "total_chunks": len(embedded_chunks),
            "chunks": [
                {
                    "id": chunk.get("id"),
                    "text": chunk.get("text", ""),
                    "source": chunk.get("source"),
                    "source_type": chunk.get("source_type"),
                    "chunk_index": chunk.get("chunk_index"),
                    "created_at": chunk.get("created_at")
                }
                for chunk in embedded_chunks
            ]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@agents_bp.route('/agents/<agent_id>/chat', methods=['POST'])
def api_agent_chat(agent_id):
    """Streaming chat with a configured agent.

    The dashboard's "Test" panel and any external API consumer hit this. We
    load the agent's saved system_prompt + (optional) knowledge-base context,
    forward the conversation to the LLM, and stream the response as
    Server-Sent Events: `data: {"content": "..."}` per chunk, `data: [DONE]`.
    """
    from extensions import db
    from services.agent_loop_service import normalize_model_choice
    from services.llm_service import call_groq, call_nvidia

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
        agent_ref = db.collection('agents').document(agent_id)
        doc = agent_ref.get()
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

    # KB injection: embed the user's last message and pull the most relevant
    # chunks (semantic search over bge-m3 embeddings across ALL files, keyword
    # fallback). Previously this keyword-scanned only the first 10 files and
    # never used the embeddings — so content on later pages was invisible.
    kb_context = ""
    try:
        if (agent.get('knowledge_base') or []) and incoming:
            last_user = next((m for m in reversed(incoming) if (m.get('role') == 'user')), None)
            last_text = (last_user or {}).get('content') or ''
            if isinstance(last_text, list):
                last_text = " ".join(p.get('text', '') for p in last_text if isinstance(p, dict))
            kb_context = _retrieve_kb_context(agent_ref, agent, last_text, top_k=5)
    except Exception as e:
        print(f"[Agent Chat] KB lookup warning: {e}")

    full_system = system_prompt + kb_context
    if welcome:
        full_system += f"\n\nIf the conversation has just started, greet the user with: \"{welcome}\""

    # Map dashboard model aliases to a real Groq model id
    model_choice = normalize_model_choice(model_name, default="daily")
    upstream_model = "llama-3.3-70b-versatile"
    if model_choice == "pro":
        upstream_model = "z-ai/glm-5.1"   # GLM-5.1 on NVIDIA NIM (nemotron retired)
    elif model_choice == "coder":
        upstream_model = "moonshotai/kimi-k2.6"
    # Gemini Live is voice-only — fall through to Groq for chat.

    chat_messages = [{"role": "system", "content": full_system}]
    for m in incoming:
        if isinstance(m, dict) and m.get('role') in ('user', 'assistant') and m.get('content'):
            chat_messages.append({"role": m['role'], "content": m['content']})

    def stream():
        full_text = ""
        try:
            if model_choice in ("pro", "coder"):
                gen = call_nvidia(
                    chat_messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=True,
                    model=upstream_model,
                    expose_thinking=False,
                )
                if gen is None:
                    gen = call_groq(
                        chat_messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        stream=True,
                        model="llama-3.3-70b-versatile",
                    )
            else:
                gen = call_groq(
                    chat_messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=True,
                    model=upstream_model,
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
            record_usage(uid, 'llm_tokens', est_tokens, model=upstream_model)
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
                'model': upstream_model,
                'created_at': _fs.SERVER_TIMESTAMP,
            })
        except Exception as e:
            print(f"[Agent Chat] log persist warning: {e}")

        yield "data: [DONE]\n\n"

    return Response(stream(), mimetype='text/event-stream', headers={
        'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no', 'Connection': 'keep-alive'
    })


@agents_bp.route('/agents/<agent_id>/kb/<file_id>', methods=['DELETE'])
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
        try:
            agent_ref.collection('kb_files').document(file_id).delete()
        except Exception as _e:
            print(f"[KB] subcollection delete warning for {file_id}: {_e}", flush=True)
        return jsonify({"status": "ok", "message": "File deleted"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
