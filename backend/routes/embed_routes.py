"""
Kautilya AI — Embed / Public Agent / Leads routes.

Lets Kautilya customers drop their agent onto any website as a chat widget
AND capture leads back into their Firestore workspace.

Endpoints:
  GET  /embed.js                              → drop-in JS snippet
  GET  /embed/<agent_id>/config               → safe public agent metadata
  POST /embed/<agent_id>/chat                 → streaming chat with a public agent
  POST /embed/<agent_id>/lead                 → create a lead record
  GET  /api/leads                             → list leads (auth)
  PATCH /api/leads/<lead_id>                  → update lead (status, notes)
  DELETE /api/leads/<lead_id>                 → delete lead
  POST /api/agents/<agent_id>/embed-token     → generate/rotate public embed token
"""
import json
import time
import uuid
import secrets
from flask import Blueprint, request, jsonify, Response, send_from_directory

from config import STATIC_FOLDER
from services.auth_service import verify_firebase_token
from services.llm_service import call_vertex_gemini

embed_bp = Blueprint('embed', __name__)


# ---------- public embed snippet ----------
@embed_bp.route('/embed.js', methods=['GET'])
def embed_js():
    return send_from_directory(STATIC_FOLDER, 'embed.js', mimetype='application/javascript')


# ---------- agent-side: generate embed token ----------
@embed_bp.route('/agents/<agent_id>/embed-token', methods=['POST'])
def rotate_embed_token(agent_id):
    from extensions import db
    from firebase_admin import firestore
    td = verify_firebase_token()
    uid = td.get('uid') if td else None
    if not uid:
        return jsonify({"error": "Authentication required"}), 401
    if not db:
        return jsonify({"error": "Database not available"}), 503
    ref = db.collection('agents').document(agent_id)
    doc = ref.get()
    if not doc.exists or doc.to_dict().get('uid') != uid:
        return jsonify({"error": "Agent not found"}), 404

    data = request.get_json(silent=True) or {}
    token = 'kte_' + secrets.token_urlsafe(20)
    allowed_origins = data.get('allowed_origins') or ['*']
    ref.update({
        'embed_token': token,
        'embed_enabled': True,
        'embed_allowed_origins': allowed_origins,
        'embed_updated_at': firestore.SERVER_TIMESTAMP,
    })
    return jsonify({
        "token": token,
        "agent_id": agent_id,
        "allowed_origins": allowed_origins,
        "script_tag": f'<script src="{request.host_url.rstrip("/")}/embed.js" data-agent="{agent_id}" data-token="{token}"></script>',
    })


# ---------- public agent metadata ----------
@embed_bp.route('/embed/<agent_id>/config', methods=['GET'])
def public_agent_config(agent_id):
    from extensions import db
    if not db:
        return jsonify({"error": "unavailable"}), 503
    token = request.args.get('token') or request.headers.get('X-Kautilya-Embed-Token', '')
    doc = db.collection('agents').document(agent_id).get()
    if not doc.exists:
        return jsonify({"error": "not found"}), 404
    data = doc.to_dict() or {}
    if not data.get('embed_enabled'):
        return jsonify({"error": "embed disabled"}), 403
    if data.get('embed_token') and data.get('embed_token') != token:
        return jsonify({"error": "invalid token"}), 403
    # Enforce origin allowlist (best effort; CORS preflight does the heavy lifting).
    allowed = data.get('embed_allowed_origins') or ['*']
    origin = request.headers.get('Origin', '')
    if origin and allowed != ['*']:
        if not any(origin == ao or origin.endswith('.' + ao.lstrip('*.')) for ao in allowed):
            return jsonify({"error": "origin not allowed"}), 403

    return _with_cors(jsonify({
        "agent_id": agent_id,
        "name": data.get('name') or 'Assistant',
        "welcome_message": data.get('welcome_message') or 'Hi! How can I help?',
        "brand_color": data.get('brand_color') or '#FF6D3F',
        "language": data.get('language') or 'en',
        "voice_enabled": bool(data.get('voice_enabled')),
        "lead_capture": data.get('lead_capture') or {
            "enabled": True,
            "fields": ["name", "email", "phone"],
        },
    }))


# ---------- public chat (streaming SSE) ----------
@embed_bp.route('/embed/<agent_id>/chat', methods=['POST', 'OPTIONS'])
def public_agent_chat(agent_id):
    if request.method == 'OPTIONS':
        return _with_cors(jsonify({"ok": True}))
    from extensions import db
    if not db:
        return jsonify({"error": "unavailable"}), 503
    payload = request.get_json(silent=True) or {}
    token = payload.get('token') or request.headers.get('X-Kautilya-Embed-Token', '')
    doc = db.collection('agents').document(agent_id).get()
    if not doc.exists:
        return jsonify({"error": "not found"}), 404
    agent = doc.to_dict() or {}
    if not agent.get('embed_enabled'):
        return jsonify({"error": "embed disabled"}), 403
    if agent.get('embed_token') and agent.get('embed_token') != token:
        return jsonify({"error": "invalid token"}), 403

    history = payload.get('history') or []
    message = (payload.get('message') or '').strip()
    if not message:
        return jsonify({"error": "message required"}), 400

    system = agent.get('system_prompt') or (
        f"You are {agent.get('name', 'an assistant')} for a business. "
        f"Be concise, helpful, and on-brand. If the user expresses interest "
        f"in a product or asks to be contacted, politely ask for name + email/phone."
    )
    messages = [{"role": "system", "content": system}]
    for m in history[-10:]:
        if m.get('role') in ('user', 'assistant') and m.get('content'):
            messages.append({"role": m['role'], "content": str(m['content'])[:4000]})
    messages.append({"role": "user", "content": message[:4000]})

    model = agent.get('model') or 'kautilya-daily'
    temperature = float(agent.get('temperature') or 0.6)
    max_tokens = int(agent.get('max_tokens') or 1024)

    # Pick backend by model id
    from services.agent_loop_service import _MODEL_LABELS, FAST_MODEL
    if 'kautilya-coder' in model or 'deepseek' in model or 'kimi' in model:
        upstream_model = _MODEL_LABELS['coder'][1]
    elif 'kautilya-pro' in model or 'glm' in model:
        upstream_model = _MODEL_LABELS['pro'][1]
    elif 'kautilya-daily' in model or 'nemotron' in model:
        upstream_model = _MODEL_LABELS['daily'][1]
    else:
        upstream_model = FAST_MODEL
    gen = call_vertex_gemini(messages, stream=True, model=upstream_model,
                             temperature=temperature, max_tokens=max_tokens, expose_thinking=False)

    if gen is None:
        return _with_cors(jsonify({"error": "LLM unavailable"})), 503

    def sse():
        for item in gen:
            if isinstance(item, dict):
                c = item.get('chunk') or ''
            else:
                c = item or ''
            if c:
                yield f"data: {json.dumps({'chunk': c})}\n\n"
        yield "data: [DONE]\n\n"

    resp = Response(sse(), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})
    return _add_cors_headers(resp)


# ---------- public lead capture ----------
@embed_bp.route('/embed/<agent_id>/lead', methods=['POST', 'OPTIONS'])
def public_lead_capture(agent_id):
    if request.method == 'OPTIONS':
        return _with_cors(jsonify({"ok": True}))
    from extensions import db
    from firebase_admin import firestore
    if not db:
        return jsonify({"error": "unavailable"}), 503

    payload = request.get_json(silent=True) or {}
    token = payload.get('token') or request.headers.get('X-Kautilya-Embed-Token', '')
    doc = db.collection('agents').document(agent_id).get()
    if not doc.exists:
        return jsonify({"error": "not found"}), 404
    agent = doc.to_dict() or {}
    if not agent.get('embed_enabled'):
        return jsonify({"error": "embed disabled"}), 403
    if agent.get('embed_token') and agent.get('embed_token') != token:
        return jsonify({"error": "invalid token"}), 403

    owner_uid = agent.get('uid')
    if not owner_uid:
        return jsonify({"error": "agent owner missing"}), 500

    lead_id = 'lead_' + uuid.uuid4().hex[:20]
    lead = {
        "id": lead_id,
        "uid": owner_uid,
        "agent_id": agent_id,
        "name":    str(payload.get('name') or '')[:120],
        "email":   str(payload.get('email') or '')[:200],
        "phone":   str(payload.get('phone') or '')[:40],
        "message": str(payload.get('message') or '')[:4000],
        "source":  str(payload.get('source') or request.headers.get('Origin') or 'embed')[:200],
        "status":  "new",
        "sentiment": payload.get('sentiment'),
        "intent":  payload.get('intent'),
        "score":   int(payload.get('score') or 0),
        "created_at": firestore.SERVER_TIMESTAMP,
    }
    try:
        db.collection('leads').document(lead_id).set(lead)
    except Exception as e:
        print(f"[Embed] lead capture error: {e}")
        return _with_cors(jsonify({"error": "Could not save lead. Please try again."})), 500

    # Best-effort webhook fan-out (Slack/Zapier) if configured on the agent.
    try:
        wh = agent.get('lead_webhook_url')
        if wh:
            import requests as _rq
            _rq.post(wh, json={**lead, "created_at": int(time.time())}, timeout=5)
    except Exception:
        pass

    return _with_cors(jsonify({"status": "ok", "lead_id": lead_id}))


# ---------- authenticated lead management ----------
@embed_bp.route('/leads', methods=['GET'])
def api_leads_list():
    from extensions import db
    from firebase_admin import firestore
    td = verify_firebase_token()
    uid = td.get('uid') if td else None
    if not uid:
        return jsonify({"error": "Authentication required"}), 401
    if not db:
        return jsonify({"leads": []})
    try:
        q = db.collection('leads').where(
            filter=firestore.FieldFilter('uid', '==', uid)
        ).order_by('created_at', direction=firestore.Query.DESCENDING).limit(500)
        docs = list(q.stream())
        leads = []
        for d in docs:
            data = d.to_dict() or {}
            ca = data.get('created_at')
            if ca and hasattr(ca, 'isoformat'):
                data['created_at'] = ca.isoformat()
            leads.append(data)
        return jsonify({"leads": leads})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@embed_bp.route('/leads/<lead_id>', methods=['PATCH'])
def api_leads_update(lead_id):
    from extensions import db
    td = verify_firebase_token()
    uid = td.get('uid') if td else None
    if not uid:
        return jsonify({"error": "Authentication required"}), 401
    ref = db.collection('leads').document(lead_id)
    doc = ref.get()
    if not doc.exists or doc.to_dict().get('uid') != uid:
        return jsonify({"error": "not found"}), 404
    patch = request.get_json(silent=True) or {}
    allowed = {'status', 'notes', 'score', 'intent', 'sentiment'}
    patch = {k: v for k, v in patch.items() if k in allowed}
    if not patch:
        return jsonify({"error": "no valid fields"}), 400
    ref.update(patch)
    return jsonify({"status": "ok"})


@embed_bp.route('/leads/<lead_id>', methods=['DELETE'])
def api_leads_delete(lead_id):
    from extensions import db
    td = verify_firebase_token()
    uid = td.get('uid') if td else None
    if not uid:
        return jsonify({"error": "Authentication required"}), 401
    ref = db.collection('leads').document(lead_id)
    doc = ref.get()
    if not doc.exists or doc.to_dict().get('uid') != uid:
        return jsonify({"error": "not found"}), 404
    ref.delete()
    return jsonify({"status": "ok"})


# ---------- CORS helpers ----------
def _add_cors_headers(resp):
    origin = request.headers.get('Origin', '*')
    resp.headers['Access-Control-Allow-Origin'] = origin
    resp.headers['Access-Control-Allow-Methods'] = 'POST, GET, OPTIONS'
    resp.headers['Access-Control-Allow-Headers'] = 'Content-Type, X-Kautilya-Embed-Token'
    resp.headers['Access-Control-Allow-Credentials'] = 'false'
    resp.headers['Vary'] = 'Origin'
    return resp


def _with_cors(resp):
    return _add_cors_headers(resp)
