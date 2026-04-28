"""
Kautilya AI — Telephony Webhooks (SIP-Fix Version)
NO room pre-creation. Let LiveKit SIP Trunk handle room creation natively.
The XML just tells Vobiz where to dial — the SIP trunk creates/joins the room automatically.
"""
import os
import json
import uuid
from flask import Blueprint, request, Response
from config import LIVEKIT_SIP_URI

webhooks_bp = Blueprint('webhooks', __name__)

@webhooks_bp.route('/api/webhooks/vobiz/answer/<agent_id>', methods=['POST', 'GET'])
def vobiz_answer(agent_id):
    # Log incoming params for debugging
    print(f"[Vobiz] Incoming: {dict(request.values)}")
    
    # Short unique suffix for this call
    call_uid = uuid.uuid4().hex[:4]
    
    # Room name format: agentId--uid
    # The SIP trunk will create this room when the call connects
    room_name = f"{agent_id}--{call_uid}"
    sip_uri = f"sip:{room_name}@{LIVEKIT_SIP_URI}"
    
    print(f"[Vobiz] Dialing SIP: {sip_uri}")
    
    # Return XML immediately — NO room pre-creation, NO blocking
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Dial timeout="30">
        <Sip>{sip_uri}</Sip>
    </Dial>
</Response>"""
    return Response(xml, mimetype='text/xml')

@webhooks_bp.route('/api/webhooks/exotel/answer/<agent_id>', methods=['POST', 'GET'])
def exotel_answer(agent_id):
    call_uid = uuid.uuid4().hex[:4]
    room_name = f"{agent_id}--{call_uid}"
    sip_uri = f"sip:{room_name}@{LIVEKIT_SIP_URI}"
    xml = f'<?xml version="1.0" encoding="UTF-8"?><Response><Dial><Sip>{sip_uri}</Sip></Dial></Response>'
    return Response(xml, mimetype='text/xml')

@webhooks_bp.route('/api/webhooks/vobiz/events', methods=['POST'])
@webhooks_bp.route('/api/webhooks/exotel/events', methods=['POST'])
def telephony_events(): return "OK", 200

@webhooks_bp.route('/api/webhooks/livekit', methods=['POST'])
def livekit_webhook(): return "OK", 200
