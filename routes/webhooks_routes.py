"""
Kautilya AI — Telephony Webhooks
Handles Exotel, Vobiz, and LiveKit webhook events.
"""
import os
from flask import Blueprint, request, Response

from config import LIVEKIT_SIP_URI

webhooks_bp = Blueprint('webhooks', __name__)


@webhooks_bp.route('/api/webhooks/exotel/answer/<agent_id>', methods=['POST', 'GET'])
def exotel_answer(agent_id):
    """
    Exotel calls this URL when the customer picks up.
    We return ExoML to bridge the call to LiveKit SIP.
    """
    # Create a unique room name for this call
    import uuid
    room_name = f"voice-{agent_id}--{uuid.uuid4().hex[:4]}"
    
    # LiveKit SIP URI: sip:<room_name>@<sip_domain>
    sip_uri = f"sip:{room_name}@{LIVEKIT_SIP_URI}"
    print(f"[Exotel Webhook] Bridging agent {agent_id} to {sip_uri}")
    
    exoml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Dial>
        <Sip>{sip_uri}</Sip>
    </Dial>
</Response>"""
    return Response(exoml, mimetype='text/xml')


@webhooks_bp.route('/api/webhooks/vobiz/answer/<agent_id>', methods=['POST', 'GET'])
def vobiz_answer(agent_id):
    """
    Vobiz calls this URL when the customer picks up.
    """
    import uuid
    room_name = f"voice{agent_id.replace('-', '')}{uuid.uuid4().hex[:4]}"
    sip_uri = f"sip:{room_name}@{LIVEKIT_SIP_URI}"
    print(f"[Vobiz Webhook] Bridging agent {agent_id} to {sip_uri}")
    
    vxml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Dial>
        <Sip>{sip_uri}</Sip>
    </Dial>
</Response>"""
    return Response(vxml, mimetype='text/xml')


@webhooks_bp.route('/api/webhooks/exotel/events', methods=['POST'])
@webhooks_bp.route('/api/webhooks/vobiz/events', methods=['POST'])
def telephony_events():
    """Handle status callbacks (busy, failed, completed)."""
    # For now, just log and return 200
    data = request.form or request.get_json() or {}
    print(f"[Telephony Webhook] Event received: {data}")
    return "OK", 200


@webhooks_bp.route('/api/webhooks/livekit', methods=['POST'])
def livekit_webhook():
    """Handle LiveKit server events (room started, participant joined, etc)."""
    # This can be used to trigger post-call analysis when a participant leaves
    return "OK", 200
