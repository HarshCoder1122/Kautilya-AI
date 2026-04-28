"""
Kautilya AI — Telephony Webhooks (Vobiz-Compatible)
Vobiz uses Plivo XML — <Say> and <Pause> are INVALID.
Only <Dial><Sip> is supported for SIP bridging.
"""
import os
import json
import uuid
import asyncio
import threading
from flask import Blueprint, request, Response
from livekit.api import LiveKitAPI, CreateRoomRequest
from extensions import db
from config import LIVEKIT_API_KEY, LIVEKIT_API_SECRET, LIVEKIT_URL, LIVEKIT_SIP_URI

# Strip sip: prefix if present — we add it ourselves in the URI
SIP_DOMAIN = LIVEKIT_SIP_URI.replace("sip:", "").strip()

webhooks_bp = Blueprint('webhooks', __name__)

def create_room_fire_and_forget(room_name, agent_id):
    """Fire-and-forget room creation. Does NOT block the Flask response."""
    def _task():
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            async def _do():
                metadata = {"source": "telephony_bridge", "agent_id": agent_id}
                if db:
                    try:
                        agent_doc = db.collection('agents').document(agent_id).get()
                        if agent_doc.exists:
                            d = agent_doc.to_dict()
                            metadata["system_prompt"] = d.get("system_prompt", "")
                            metadata["welcome_message"] = d.get("welcome_message", "")
                            metadata["language"] = d.get("language", "hi-IN")
                    except: pass
                lk_url = LIVEKIT_URL.replace("wss://", "https://").replace("ws://", "http://")
                lkapi = LiveKitAPI(url=lk_url, api_key=LIVEKIT_API_KEY, api_secret=LIVEKIT_API_SECRET)
                try:
                    await lkapi.room.create_room(CreateRoomRequest(
                        name=room_name, empty_timeout=300, metadata=json.dumps(metadata)
                    ))
                    print(f"[Bridge] ✅ Room {room_name} created. Agent dispatched.")
                finally:
                    await lkapi.aclose()
            loop.run_until_complete(_do())
            loop.close()
        except Exception as e:
            print(f"[Bridge] ❌ Error: {e}")
    threading.Thread(target=_task, daemon=True).start()

@webhooks_bp.route('/api/webhooks/vobiz/answer/<agent_id>', methods=['POST', 'GET'])
def vobiz_answer(agent_id):
    print(f"[Vobiz] Incoming: {dict(request.values)}")
    
    call_uid = uuid.uuid4().hex[:4]
    room_name = f"voice-{agent_id}--{call_uid}"
    sip_uri = f"sip:{room_name}@{SIP_DOMAIN}"
    
    # Fire-and-forget room creation
    create_room_fire_and_forget(room_name, agent_id)
    
    # Vobiz requires <User> for SIP routing. 
    # Adding callerId to ensure LiveKit's Inbound Trunk doesn't reject the call as anonymous.
    caller_id = request.values.get('From', '') # The Vobiz virtual number
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Dial timeout="60" callerId="{caller_id}">
        <User>{sip_uri}</User>
    </Dial>
</Response>"""
    print(f"[Vobiz] Returning XML with SIP URI: {sip_uri}")
    return Response(xml, mimetype='text/xml')

@webhooks_bp.route('/api/webhooks/exotel/answer/<agent_id>', methods=['POST', 'GET'])
def exotel_answer(agent_id):
    call_uid = uuid.uuid4().hex[:4]
    room_name = f"voice-{agent_id}--{call_uid}"
    sip_uri = f"sip:{room_name}@{SIP_DOMAIN}"
    create_room_fire_and_forget(room_name, agent_id)
    caller_id = request.values.get('From', '')
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Dial callerId="{caller_id}">
        <User>{sip_uri}</User>
    </Dial>
</Response>"""
    return Response(xml, mimetype='text/xml')

@webhooks_bp.route('/api/webhooks/vobiz/events', methods=['POST'])
@webhooks_bp.route('/api/webhooks/exotel/events', methods=['POST'])
def telephony_events(): return "OK", 200

@webhooks_bp.route('/api/webhooks/livekit', methods=['POST'])
def livekit_webhook(): return "OK", 200
