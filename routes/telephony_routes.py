"""
Kautilya AI — Telephony & Outbound Calling
Handles /api/telephony/* and agent outbound calls.
"""
import os
import uuid
import requests
from flask import Blueprint, request, jsonify

from services.auth_service import verify_firebase_token

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
        if doc.exists:
            return jsonify(doc.to_dict())
        return jsonify({
            "providers": [
                {"type": "exotel", "name": "Exotel Cloud", "status": "available"},
                {"type": "vobiz", "name": "Vobiz AI", "status": "available"}
            ]
        })
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
    provider_type = data.get('type')
    if not provider_type: return jsonify({"error": "Provider type required"}), 400
    
    try:
        config_ref = db.collection('users').document(uid).collection('config').document('telephony')
        existing = config_ref.get().to_dict() or {"providers": []}
        
        # Update or add provider
        found = False
        for p in existing['providers']:
            if p['type'] == provider_type:
                p.update(data)
                p['status'] = 'available'
                found = True
                break
        if not found:
            data['status'] = 'available'
            existing['providers'].append(data)
            
        config_ref.set(existing, merge=True)
        return jsonify({"status": "ok", "message": f"{provider_type.capitalize()} saved"})
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
        # 1. Fetch Agent Config
        agent_doc = db.collection('agents').document(agent_id).get()
        if not agent_doc.exists or agent_doc.to_dict().get('uid') != uid:
            return jsonify({"error": "Agent not found"}), 404
        agent = agent_doc.to_dict()
        
        # 2. Fetch Telephony Config
        config_doc = db.collection('users').document(uid).collection('config').document('telephony').get()
        if not config_doc.exists:
            return jsonify({"error": "Telephony not configured"}), 400
        
        providers = config_doc.to_dict().get('providers', [])
        provider_type = agent.get('telephony_provider', 'exotel')
        config = next((p for p in providers if p['type'] == provider_type), None)
        
        if not config:
            return jsonify({"error": f"Provider {provider_type} not configured"}), 400

        # 3. Trigger Call based on provider
        if provider_type == 'vobiz':
            return trigger_vobiz_call(config, to_number, agent_id)
        else:
            return trigger_exotel_call(config, to_number, agent_id)
            
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
    url = f"https://api.vobiz.ai/api/v1/Account/{auth_id}/Call/"
    
    # Force HTTPS for callbacks (Cloud providers like Koyeb/ngrok require it for telephony)
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
        import requests
        resp = requests.post(url, headers=headers, json=payload, timeout=15)
        if resp.status_code in (200, 201):
            return jsonify({"status": "ok", "call_id": resp.json().get('api_id')})
        return jsonify({"error": f"Vobiz API Error: {resp.text}"}), resp.status_code
    except Exception as e:
        return jsonify({"error": f"Request failed: {e}"}), 500
