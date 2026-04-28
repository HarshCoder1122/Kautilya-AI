"""
Kautilya AI — Telephony Webhooks (Timing-Fixed Version)
Fire-and-forget room creation + long audio buffer for Gemini 3.1 initialization.
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
    # Start in background — does NOT block the webhook response
    threading.Thread(target=_task, daemon=True).start()

@webhooks_bp.route('/api/webhooks/vobiz/answer/<agent_id>', methods=['POST', 'GET'])
def vobiz_answer(agent_id):
    print(f"[Vobiz] Incoming: {dict(request.values)}")
    
    call_uid = uuid.uuid4().hex[:4]
    room_name = f"voice-{agent_id}--{call_uid}"
    sip_uri = f"sip:{room_name}@{LIVEKIT_SIP_URI}"
    
    # 1. Fire-and-forget: room creation starts NOW, XML returns INSTANTLY
    create_room_fire_and_forget(room_name, agent_id)
    
    # 2. Long audio buffer (~10 seconds) gives agent time to:
    #    - Get dispatched by LiveKit
    #    - Initialize Firebase
    #    - Connect to Gemini 3.1 RealtimeModel
    #    - Be fully ready in the room
    # 3. By the time <Dial> runs, agent is waiting
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>Welcome to Kautilya AI. Please hold while we connect you to your AI assistant.</Say>
    <Pause length="5"/>
    <Say>Connecting now.</Say>
    <Dial timeout="60">
        <Sip>{sip_uri}</Sip>
    </Dial>
</Response>"""
    return Response(xml, mimetype='text/xml')

@webhooks_bp.route('/api/webhooks/exotel/answer/<agent_id>', methods=['POST', 'GET'])
def exotel_answer(agent_id):
    call_uid = uuid.uuid4().hex[:4]
    room_name = f"voice-{agent_id}--{call_uid}"
    sip_uri = f"sip:{room_name}@{LIVEKIT_SIP_URI}"
    create_room_fire_and_forget(room_name, agent_id)
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>Welcome to Kautilya AI. Please hold while we connect you.</Say>
    <Pause length="5"/>
    <Say>Connecting now.</Say>
    <Dial timeout="60">
        <Sip>{sip_uri}</Sip>
    </Dial>
</Response>"""
    return Response(xml, mimetype='text/xml')

@webhooks_bp.route('/api/webhooks/vobiz/events', methods=['POST'])
@webhooks_bp.route('/api/webhooks/exotel/events', methods=['POST'])
def telephony_events(): return "OK", 200

@webhooks_bp.route('/api/webhooks/livekit', methods=['POST'])
def livekit_webhook(): return "OK", 200
