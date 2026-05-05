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


@telephony_bp.route('/api/telephony/config', methods=['GET'])
def api_telephony_config():
    from extensions import db
    token_data = verify_firebase_token()
    uid = token_data.get('uid') if token_data else None
    if not uid: return jsonify({"error": "Unauthorized"}), 401
    
    try:
        config_ref = db.collection('users').document(uid).collection('config').document('telephony')
        doc = config_ref.get()
        data = doc.to_dict() if doc.exists else {"providers": []}
        
        # If the frontend is expecting { exotel: {...}, vobiz: {...} }, we need to format it
        formatted_providers = {
            "exotel": {"status": "available", "name": "Exotel Cloud"},
            "vobiz": {"status": "available", "name": "Vobiz AI"}
        }
        
        for p in data.get('providers', []):
            ptype = p.get('type')
            if ptype in formatted_providers:
                formatted_providers[ptype].update(p)
                
        # Send the formatted providers directly under the main object
        return jsonify({"providers": formatted_providers})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@telephony_bp.route('/api/telephony/save', methods=['POST'])
def api_telephony_save():
    from extensions import db
    from firebase_admin import firestore
    token_data = verify_firebase_token()
    uid = token_data.get('uid') if token_data else None
    if not uid: return jsonify({"error": "Unauthorized"}), 401
    
    data = request.get_json() or {}
    
    # Handle two possible structures:
    # 1. Frontend sends flat object { exotel: {...}, vobiz: {...} } under 'providers'
    # 2. Frontend sends single provider payload with 'type'
    
    updates_to_make = []
    
    if 'providers' in data and isinstance(data['providers'], dict):
        for ptype, pdata in data['providers'].items():
            if not pdata: continue
            pdata_copy = pdata.copy()
            pdata_copy['type'] = ptype
            updates_to_make.append(pdata_copy)
    elif 'type' in data:
        updates_to_make.append(data)
    else:
        return jsonify({"error": "Invalid payload format"}), 400
    
    try:
        config_ref = db.collection('users').document(uid).collection('config').document('telephony')
        existing = config_ref.get().to_dict() or {"providers": []}
        
        # Update or add provider
        for pdata in updates_to_make:
            provider_type = pdata.get('type')
            found = False
            for p in existing.get('providers', []):
                if p.get('type') == provider_type:
                    p.update(pdata)
                    p['status'] = 'available'
                    found = True
                    break
            if not found:
                pdata['status'] = 'available'
                if 'providers' not in existing:
                    existing['providers'] = []
                existing['providers'].append(pdata)
            
        config_ref.set(existing, merge=True)
        return jsonify({"status": "ok", "message": "Telephony configuration saved"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@telephony_bp.route('/api/agents/<agent_id>/call-outbound', methods=['POST'])
def api_agent_call_outbound(agent_id):
    from extensions import db
    token_data = verify_firebase_token()
    uid = token_data.get('uid') if token_data else None
    if not uid: return jsonify({"error": "Unauthorized"}), 401
    
    data = request.get_json() or {}
    to_number = data.get('to_number')
    if not to_number: return jsonify({"error": "Destination number required"}), 400
    
    try:
        agent_doc = db.collection('agents').document(agent_id).get()
        if not agent_doc.exists or agent_doc.to_dict().get('uid') != uid:
            return jsonify({"error": "Agent not found"}), 404
        agent = agent_doc.to_dict()

        provider_type = (agent.get('telephony_provider') or 'exotel').lower()
        config = load_provider_config(db, uid, provider_type)
        if not config:
            return jsonify({"error": f"Provider {provider_type} not configured"}), 400

        base_url = request.host_url.rstrip('/')
        result = dial_outbound(uid, agent_id, agent, config, to_number, base_url, db=db)
        if result.get('ok'):
            return jsonify({"status": "ok", "call_id": result.get('call_id'), "provider": result.get('provider')})
        return jsonify({"error": result.get('error') or "Dial failed"}), 500
    except Exception as e:
        print(f"[Outbound] Error: {e}")
        return jsonify({"error": str(e)}), 500


def trigger_exotel_call(config, to_number, agent_id):
    sid = config.get('sid')
    api_key = config.get('api_key')
    token = config.get('token_val') or config.get('token')
    subdomain = config.get('exotel_subdomain', 'api.exotel.com')
    virtual_number = config.get('exotel_number') or config.get('number')
    
    if not all([sid, api_key, token, virtual_number]):
        return jsonify({"error": "Exotel credentials incomplete"}), 400
        
    url = f"https://{subdomain}/v1/Accounts/{sid}/Calls/connect.json"
    
    # The URL that Exotel will hit when call is answered to get instructions
    # We point it to our webhook which will return ExoML to connect to LiveKit SIP
    base_url = request.host_url.rstrip('/')
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
    auth_id = config.get('auth_id') or config.get('trunk_id')
    auth_token = config.get('auth_token')
    virtual_number = config.get('number')
    
    if not all([auth_id, auth_token, virtual_number]):
        return jsonify({"error": "Vobiz credentials incomplete"}), 400

    # NOTE: We intentionally do NOT pre-warm a `voice-<agent>--<hex>` room here.
    # LiveKit's SIP inbound trunk creates its own room of the form
    # `voice-_+<phone>_<call_id>` when the SIP leg lands. Pre-warming a
    # web-format room caused the agent worker to spawn TWICE per call (one in
    # the empty pre-warm room, one in the real SIP room) — wasting compute and
    # producing the "received server content but no active generation"
    # warning. The real-time agent dispatch happens via `active_calls/<phone>`
    # mapping (written below) which `_resolve_agent_doc` consults.

    url = f"https://api.vobiz.ai/api/v1/Account/{auth_id}/Call/"

    # Force HTTPS for callbacks
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
        
        import requests
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
