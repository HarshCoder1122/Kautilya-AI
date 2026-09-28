"""
Kautilya AI — Telephony & Outbound Calling
Handles /api/telephony/* and agent outbound calls.
"""
import os
import uuid
import requests
from flask import Blueprint, request, jsonify

from services.auth_service import verify_firebase_token
from services.telephony_dialer import dial_outbound, load_provider_config

telephony_bp = Blueprint('telephony', __name__)


@telephony_bp.route('/telephony/diagnostic', methods=['GET'])
def api_telephony_diagnostic():
    """Reports which env vars are set on the server + which provider creds this
    user has saved. Use this to self-diagnose 'calls fail before audio' without
    SSHing into the box. Never returns secret values — only booleans + the host."""
    from extensions import db
    token_data = verify_firebase_token()
    uid = token_data.get('uid') if token_data else None
    if not uid:
        return jsonify({"error": "Unauthorized"}), 401

    env_checks = {k: bool(os.environ.get(k)) for k in [
        "LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET", "LIVEKIT_SIP_URI",
        "VOBIZ_MASTER_USER", "VOBIZ_MASTER_PASS", "VOBIZ_MASTER_NUMBER",
        # GOOGLE_VERTEX_CREDENTIALS_JSON powers the voice agent's real-time
        # conversational LLM (livekit_agent.py's google.LLM) — required.
        # NVIDIA_API_KEY (embeddings/RAG) and GROQ_API_KEY (Whisper STT) are
        # still separate, non-chat capabilities this box may also use.
        "GOOGLE_VERTEX_CREDENTIALS_JSON", "VERTEX_PROJECT_ID",
        "NVIDIA_API_KEY", "GEMINI_API_KEY", "GROQ_API_KEY",
        "FIREBASE_SERVICE_ACCOUNT_JSON",
    ]}

    user_providers = {"exotel": {"saved": False}, "vobiz": {"saved": False}}
    try:
        doc = db.collection('users').document(uid).collection('config').document('telephony').get()
        if doc.exists:
            for p in (doc.to_dict() or {}).get('providers', []):
                pt = p.get('type')
                if pt in user_providers:
                    user_providers[pt] = {
                        "saved": True,
                        "enabled": p.get('enabled') or p.get('status') == 'available',
                        "has_caller_id": bool(p.get('caller_id') or p.get('exotel_number') or p.get('number')),
                        "has_creds": bool((p.get('api_key') and p.get('api_token')) or
                                          (p.get('username') and p.get('password'))),
                    }
    except Exception as e:
        print(f"[Diagnostic] user provider read err: {e}")

    public_url = request.host_url.rstrip('/')
    is_https = public_url.startswith('https://') or 'localhost' in public_url
    is_localhost = 'localhost' in public_url or '127.0.0.1' in public_url

    issues = []
    if not all([env_checks["LIVEKIT_URL"], env_checks["LIVEKIT_API_KEY"], env_checks["LIVEKIT_API_SECRET"]]):
        issues.append("LiveKit env vars missing — browser web-calls will fail at /api/livekit/token.")
    if is_localhost:
        issues.append("Backend reachable as localhost — SIP webhooks from Vobiz/Exotel cannot reach you. Deploy or use ngrok.")
    if not is_https and not is_localhost:
        issues.append("Backend served over plain HTTP — webhooks will be rejected by most SIP providers.")
    if not any(p.get("saved") for p in user_providers.values()) and not env_checks["VOBIZ_MASTER_USER"]:
        issues.append("No user provider configured AND no master Vobiz creds set — outbound SIP cannot dial.")

    return jsonify({
        "env": env_checks,
        "host": public_url,
        "user_providers": user_providers,
        "issues": issues,
        "status": "ok" if not issues else "degraded",
    })


@telephony_bp.route('/telephony/config', methods=['GET'])
def api_telephony_config():
    from extensions import db
    token_data = verify_firebase_token()
    uid = token_data.get('uid') if token_data else None
    if not uid: return jsonify({"error": "Unauthorized"}), 401
    
    try:
        config_ref = db.collection('users').document(uid).collection('config').document('telephony')
        doc = config_ref.get()
        data = doc.to_dict() if doc.exists else {"providers": []}
        
        # Flatten the providers list into a dict for the frontend
        # New dashboard expects: { exotel: {...}, vobiz: {...} }
        res = {
            "exotel": {"enabled": False},
            "vobiz": {"enabled": False}
        }
        
        for p in data.get('providers', []):
            ptype = p.get('type')
            if ptype in res:
                res[ptype] = p
                res[ptype]['enabled'] = p.get('status') == 'available' or p.get('enabled', False)
                
        return jsonify(res)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@telephony_bp.route('/telephony/save', methods=['POST'])
def api_telephony_save():
    from extensions import db
    from firebase_admin import firestore
    token_data = verify_firebase_token()
    uid = token_data.get('uid') if token_data else None
    if not uid: return jsonify({"error": "Unauthorized"}), 401
    
    data = request.get_json() or {}
    
    # Dashboard v2 sends { exotel: {...}, vobiz: {...} }
    # We convert this to the legacy list format for backward compatibility
    
    try:
        config_ref = db.collection('users').document(uid).collection('config').document('telephony')
        
        providers_list = []
        for ptype in ['exotel', 'vobiz']:
            if ptype in data:
                pdata = data[ptype]
                pdata['type'] = ptype
                # Ensure status is set for legacy logic
                if pdata.get('enabled'):
                    pdata['status'] = 'available'
                providers_list.append(pdata)
        
        config_ref.set({"providers": providers_list}, merge=True)
        return jsonify({"status": "ok", "message": "Telephony configuration saved"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@telephony_bp.route('/telephony/inbound-url/<agent_id>', methods=['GET'])
def api_telephony_inbound_url(agent_id):
    """Return the ready-to-paste Vobiz Answer/Events URLs for INBOUND calls.

    The user pastes the answer_url into the Vobiz portal against their virtual
    number ("Answer URL", method POST). When someone calls that number, Vobiz
    hits our webhook, which bridges the call into LiveKit SIP and the mapped
    agent picks it up. The WEBHOOK_SECRET is appended server-side so the
    frontend never needs to know it."""
    from extensions import db
    token_data = verify_firebase_token()
    uid = token_data.get('uid') if token_data else None
    if not uid: return jsonify({"error": "Unauthorized"}), 401
    if not db: return jsonify({"error": "Database not available"}), 503
    try:
        doc = db.collection('agents').document(agent_id).get()
        if not doc.exists or (doc.to_dict() or {}).get('uid') != uid:
            return jsonify({"error": "Agent not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    base_url = request.host_url.rstrip('/').replace('http://', 'https://')
    answer_url = f"{base_url}/api/webhooks/vobiz/answer/{agent_id}"
    events_url = f"{base_url}/api/webhooks/vobiz/events"
    secret = (os.environ.get("WEBHOOK_SECRET") or "").strip()
    if secret:
        answer_url += f"?secret={secret}"
        events_url += f"?secret={secret}"
    return jsonify({"answer_url": answer_url, "events_url": events_url, "method": "POST"})


@telephony_bp.route('/telephony/outbound-call', methods=['POST'])
def api_agent_call_outbound():
    from extensions import db, limit_manager
    from config import FREE_OUTBOUND_CALL_LIMIT
    token_data = verify_firebase_token()
    uid = token_data.get('uid') if token_data else None
    if not uid: return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json() or {}
    agent_id = data.get('agent_id')
    to_number = data.get('to_number')
    if not agent_id: return jsonify({"error": "Agent ID required"}), 400
    if not to_number: return jsonify({"error": "Destination number required"}), 400

    # Mobile-call gate: free users get FREE_OUTBOUND_CALL_LIMIT lifetime test
    # calls, then PRO is required. (Browser/web calls stay free — different
    # route.) PRO is unlimited. Checked here but only CONSUMED after a
    # successful dial, so a failed dial doesn't burn the user's free quota.
    is_pro = bool(limit_manager.is_pro_user(uid))
    allowed, call_info = limit_manager.check_outbound_call_allowed(
        uid, is_pro=is_pro, free_limit=FREE_OUTBOUND_CALL_LIMIT)
    if not allowed:
        return jsonify({
            "error": "Free mobile-call limit reached",
            "code": "upgrade_required",
            "upgrade": True,
            "used": call_info["used"],
            "limit": call_info["limit"],
            "message": (f"You've used all {call_info['limit']} free test calls. "
                        f"Upgrade to PRO for unlimited outbound mobile calling."),
        }), 402

    try:
        agent_doc = db.collection('agents').document(agent_id).get()
        if not agent_doc.exists or agent_doc.to_dict().get('uid') != uid:
            return jsonify({"error": "Agent not found"}), 404
        agent = agent_doc.to_dict()

        # TEST CALLS: Studio "Instant Telephony" calls always prefer the MASTER
        # Vobiz creds from ENV so a brand-new agent can be dialed without the
        # user first configuring their own provider. The creds are resolved in
        # config.py across every env-var name we've ever shipped, so a name
        # mismatch no longer silently disables this path.
        from config import VOBIZ_MASTER_USER, VOBIZ_MASTER_PASS, VOBIZ_MASTER_NUMBER

        config = None
        if VOBIZ_MASTER_USER and VOBIZ_MASTER_PASS:
            provider_type = 'vobiz'
            config = {
                "username": VOBIZ_MASTER_USER,
                "password": VOBIZ_MASTER_PASS,
                "caller_id": VOBIZ_MASTER_NUMBER,
                "type": "vobiz",
            }
            print(f"[Outbound] Using MASTER Vobiz creds for test call to {to_number}")
        else:
            # Master not set → fall back to whichever provider the user saved.
            # Try the agent's preferred provider first, then the other one, so a
            # user who only saved Vobiz (or only Exotel) still gets dialed.
            preferred = (agent.get('telephony_provider') or 'exotel').lower()
            for provider_type in (preferred, 'vobiz' if preferred == 'exotel' else 'exotel'):
                config = load_provider_config(db, uid, provider_type)
                if config:
                    print(f"[Outbound] Master not set — using user '{provider_type}' provider")
                    break

        if not config:
            return jsonify({
                "error": ("Master Vobiz creds are not set on the server and you "
                          "have not saved any telephony provider. Set VOBIZ_MASTER_USER / "
                          "VOBIZ_MASTER_PASS / VOBIZ_MASTER_NUMBER in the deployment env, "
                          "or add Exotel/Vobiz credentials under Settings → Telephony."),
                "code": "telephony_not_configured",
            }), 400

        # Pre-call CRM lookup: enrich the agent's system_prompt with whatever
        # the connected CRM knows about this number. Soft-fail: missing CRM
        # or no match must not block the call.
        try:
            from services.integration_tools import _lookup_crm_contact
            crm = _lookup_crm_contact(uid, {"phone": to_number})
            if crm.get("ok") and crm.get("contact"):
                c = crm["contact"]
                name = c.get("firstname") or c.get("First_Name") or c.get("Full_Name") or ""
                last = c.get("lastname") or c.get("Last_Name") or ""
                company = c.get("company") or c.get("Account_Name") or ""
                title = c.get("jobtitle") or c.get("Title") or ""
                stage = c.get("lifecyclestage") or c.get("Lead_Status") or ""
                summary_parts = [f"{name} {last}".strip(), title, company, f"stage: {stage}" if stage else ""]
                summary = " | ".join(p for p in summary_parts if p)
                if summary:
                    extra = f"\n\nCALL CONTEXT (from {crm['source']} CRM): You are calling {summary}. Greet them by name and reference their company where relevant. Stay natural — do not read this verbatim."
                    agent = {**agent, "system_prompt": (agent.get("system_prompt") or "") + extra}
                    print(f"[Pre-call] CRM enrichment applied for {to_number}: {summary}")
        except Exception as e:
            print(f"[Pre-call] CRM lookup soft-failed: {e}")

        # Webhook callbacks MUST use a publicly-reachable URL. Behind the HF
        # Spaces proxy (and the ai.revealiq.in custom domain in front of it),
        # request.host_url can resolve to an internal/wrong host that the
        # telephony provider cannot reach — so Vobiz/Exotel never hit the
        # answer webhook, never get the <Dial> SIP instruction, and the call
        # sits in dead air until it times out (LiveKit receives nothing).
        # Prefer the configured/auto-detected PUBLIC_BASE_URL (same source the
        # campaign worker uses); fall back to request.host_url only if unset.
        from config import PUBLIC_BASE_URL
        base_url = (PUBLIC_BASE_URL or request.host_url).rstrip('/')
        # Ensure base_url is HTTPS in production
        if not base_url.startswith('http'):
            base_url = f"https://{base_url}"
        elif 'localhost' not in base_url and '127.0.0.1' not in base_url:
            base_url = base_url.replace('http://', 'https://')
        print(f"[Outbound] Using callback base_url: {base_url}")

        result = dial_outbound(uid, agent_id, agent, config, to_number, base_url, db=db,
                               provider=provider_type)
        if result.get('ok'):
            # Consume one free call only on a successful dial. PRO is unlimited
            # (increment is a no-op cost-wise but we skip it to keep the counter
            # meaningful as "free calls used").
            calls_remaining = None
            if not is_pro:
                limit_manager.increment_outbound_call_count(uid)
                calls_remaining = max(0, (call_info["remaining"] or 0) - 1)
            return jsonify({"status": "ok", "call_id": result.get('call_id'),
                            "provider": result.get('provider'),
                            "is_pro": is_pro, "calls_remaining": calls_remaining})
        return jsonify({"error": result.get('error') or "Dial failed"}), 500
    except Exception as e:
        print(f"[Outbound] Error: {e}")
        return jsonify({"error": str(e)}), 500


def trigger_exotel_call(config, to_number, agent_id):
    # Unified keys supporting both legacy and new dashboard
    sid = config.get('account_sid') or config.get('sid')
    api_key = config.get('api_key')
    token = config.get('api_token') or config.get('token_val') or config.get('token')
    subdomain = config.get('exotel_subdomain', 'api.exotel.com')
    virtual_number = config.get('caller_id') or config.get('exotel_number') or config.get('number')
    
    if not all([sid, api_key, token, virtual_number]):
        return jsonify({"error": "Exotel credentials incomplete"}), 400
        
    url = f"https://{subdomain}/v1/Accounts/{sid}/Calls/connect.json"
    
    base_url = request.host_url.rstrip('/').replace('http://', 'https://')
    callback_url = f"{base_url}/api/webhooks/exotel/answer/{agent_id}"
    
    payload = {
        'From': to_number,
        'CallerId': virtual_number,
        'Url': callback_url,
        'StatusCallback': f"{base_url}/api/webhooks/exotel/events"
    }
    
    try:
        resp = requests.post(url, data=payload, auth=(api_key, token), timeout=15)
        if resp.status_code in (200, 201):
            return jsonify({"status": "ok", "call_sid": resp.json().get('Call', {}).get('Sid')})
        return jsonify({"error": f"Exotel API Error: {resp.text}"}), resp.status_code
    except Exception as e:
        return jsonify({"error": f"Request failed: {e}"}), 500


def trigger_vobiz_call(config, to_number, agent_id):
    # Unified keys supporting both legacy and new dashboard
    auth_id = config.get('username') or config.get('auth_id') or config.get('trunk_id')
    auth_token = config.get('password') or config.get('auth_token')
    virtual_number = config.get('caller_id') or config.get('number')
    
    if not all([auth_id, auth_token, virtual_number]):
        return jsonify({"error": "Vobiz credentials incomplete"}), 400

    url = f"https://api.vobiz.ai/api/v1/Account/{auth_id}/Call/"

    base_url = request.host_url.rstrip('/').replace('http://', 'https://')
    answer_url = f"{base_url}/api/webhooks/vobiz/answer/{agent_id}"
    status_url = f"{base_url}/api/webhooks/vobiz/events"
    
    headers = {
        "X-Auth-ID": auth_id,
        "X-Auth-Token": auth_token,
        "Content-Type": "application/json"
    }
    
    payload = {
        "from": virtual_number,
        "to": to_number,
        "answer_url": answer_url,
        "answer_method": "POST",
        "status_url": status_url
    }
    
    try:
        # BULLETPROOF MAPPING: Save customer number to agent_id mapping
        from extensions import db
        from firebase_admin import firestore
        clean_to = to_number.lstrip('+')
        try:
            db.collection('active_calls').document(clean_to).set({
                "agent_id": agent_id,
                "created_at": firestore.SERVER_TIMESTAMP
            })
            print(f"[Telephony] Saved customer mapping: {clean_to} -> {agent_id}")
        except: pass
        
        resp = requests.post(url, headers=headers, json=payload, timeout=15)
        if resp.status_code in (200, 201):
            resp_data = resp.json()
            vobiz_call_id = resp_data.get('api_id')
            if vobiz_call_id and db:
                try:
                    db.collection('call_mappings').document(vobiz_call_id).set({
                        "agent_id": agent_id,
                        "created_at": firestore.SERVER_TIMESTAMP
                    })
                    print(f"[Telephony] 🎯 Mapped Vobiz Call ID: {vobiz_call_id} -> {agent_id}")
                except: pass
            return jsonify({"status": "ok", "call_id": vobiz_call_id})
        return jsonify({"error": f"Vobiz API Error: {resp.text}"}), resp.status_code
    except Exception as e:
        return jsonify({"error": f"Request failed: {e}"}), 500
