"""
Kautilya AI — Telephony Webhooks (Latent-Fix Version)
Adds a greeting in XML to keep the call alive during Agent startup.
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

def _run_async_safe(coro):
    import asyncio, threading
    result, error = [None], [None]
    def _target():
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result[0] = loop.run_until_complete(coro)
            loop.close()
        except Exception as e: error[0] = e
    t = threading.Thread(target=_target); t.start(); t.join(timeout=10)
    if error[0]: raise error[0]
    return result[0]

async def pre_create_legacy(room_name, agent_id):
    if not db: return
    try:
        agent_doc = db.collection('agents').document(agent_id).get()
        agent_data = agent_doc.to_dict() if agent_doc.exists else {}
        room_metadata = {
            "source": "telephony_bridge",
            "agent_id": agent_id,
            "system_prompt": agent_data.get("system_prompt", ""),
            "voice": agent_data.get("voice", "shubh"),
            "language": agent_data.get("language", "hi-IN"),
            "welcome_message": agent_data.get("welcome_message", ""),
            "stt_provider": agent_data.get("stt_provider", "sarvam"),
            "tts_provider": agent_data.get("tts_provider", "sarvam")
        }
        lk_url = LIVEKIT_URL.replace("wss://", "https://").replace("ws://", "http://")
        lkapi = LiveKitAPI(url=lk_url, api_key=LIVEKIT_API_KEY, api_secret=LIVEKIT_API_SECRET)
        try:
            await lkapi.room.create_room(CreateRoomRequest(name=room_name, empty_timeout=300, metadata=json.dumps(room_metadata)))
            print(f"[Bridge] ✅ Room {room_name} pre-created.")
        finally: await lkapi.aclose()
    except Exception as e: print(f"[Bridge] ❌ Error: {e}")

@webhooks_bp.route('/api/webhooks/vobiz/answer/<agent_id>', methods=['POST', 'GET'])
def vobiz_answer(agent_id):
    room_name = f"voice-{agent_id}--{uuid.uuid4().hex[:4]}"
    sip_uri = f"sip:{room_name}@{LIVEKIT_SIP_URI}"
    
    # Pre-create room in background
    try: _run_async_safe(pre_create_legacy(room_name, agent_id))
    except: pass
    
    # Add <Say> to hold the call for 2-3 seconds while HF Agent wakes up
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>Connecting your call to Kautilya AI assistant. Please wait.</Say>
    <Dial timeout="30">
        <Sip>{sip_uri}</Sip>
    </Dial>
</Response>"""
    return Response(xml, mimetype='text/xml')

@webhooks_bp.route('/api/webhooks/exotel/answer/<agent_id>', methods=['POST', 'GET'])
def exotel_answer(agent_id):
    room_name = f"voice-{agent_id}--{uuid.uuid4().hex[:4]}"
    sip_uri = f"sip:{room_name}@{LIVEKIT_SIP_URI}"
    xml = f'<?xml version="1.0" encoding="UTF-8"?><Response><Say>Connecting...</Say><Dial><Sip>{sip_uri}</Sip></Dial></Response>'
    return Response(xml, mimetype='text/xml')

@webhooks_bp.route('/api/webhooks/vobiz/events', methods=['POST'])
@webhooks_bp.route('/api/webhooks/exotel/events', methods=['POST'])
def telephony_events(): return "OK", 200

@webhooks_bp.route('/api/webhooks/livekit', methods=['POST'])
def livekit_webhook(): return "OK", 200
