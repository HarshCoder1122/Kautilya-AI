"""
Kautilya AI — Telephony Webhooks (Concurrency-Fix Version)
Optimized for high-speed response to prevent Vobiz retries and multiple room spawns.
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

def create_room_background(room_name, agent_id):
    """Truly background room creation without blocking Flask."""
    def _task():
        try:
            # New event loop for the thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            async def _do():
                if not db: return
                agent_doc = db.collection('agents').document(agent_id).get()
                agent_data = agent_doc.to_dict() if agent_doc.exists else {}
                room_metadata = {
                    "source": "telephony_bridge",
                    "agent_id": agent_id,
                    "welcome_message": agent_data.get("welcome_message", "")
                }
                lk_url = LIVEKIT_URL.replace("wss://", "https://").replace("ws://", "http://")
                lkapi = LiveKitAPI(url=lk_url, api_key=LIVEKIT_API_KEY, api_secret=LIVEKIT_API_SECRET)
                try:
                    await lkapi.room.create_room(CreateRoomRequest(
                        name=room_name, 
                        empty_timeout=300, 
                        metadata=json.dumps(room_metadata)
                    ))
                    print(f"[Bridge] ✅ Room {room_name} pre-created in background.")
                finally:
                    await lkapi.aclose()
            
            loop.run_until_complete(_do())
            loop.close()
        except Exception as e:
            print(f"[Bridge] ❌ Background Error: {e}")

    threading.Thread(target=_task, daemon=True).start()

@webhooks_bp.route('/api/webhooks/vobiz/answer/<agent_id>', methods=['POST', 'GET'])
def vobiz_answer(agent_id):
    # Use Vobiz unique ID if available, else random but stable
    call_sid = request.values.get('callid') or request.values.get('CallSid') or uuid.uuid4().hex[:8]
    room_name = f"voice-{agent_id}--{call_sid}"
    sip_uri = f"sip:{room_name}@{LIVEKIT_SIP_URI}"
    
    # 1. Fire and forget room creation (No blocking!)
    create_room_background(room_name, agent_id)
    
    # 2. Immediate XML Response
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>Connecting...</Say>
    <Dial timeout="30">
        <Sip>{sip_uri}</Sip>
    </Dial>
</Response>"""
    return Response(xml, mimetype='text/xml')

@webhooks_bp.route('/api/webhooks/exotel/answer/<agent_id>', methods=['POST', 'GET'])
def exotel_answer(agent_id):
    room_name = f"voice-{agent_id}--{uuid.uuid4().hex[:8]}"
    sip_uri = f"sip:{room_name}@{LIVEKIT_SIP_URI}"
    xml = f'<?xml version="1.0" encoding="UTF-8"?><Response><Say>Connecting...</Say><Dial><Sip>{sip_uri}</Sip></Dial></Response>'
    return Response(xml, mimetype='text/xml')

@webhooks_bp.route('/api/webhooks/vobiz/events', methods=['POST'])
@webhooks_bp.route('/api/webhooks/exotel/events', methods=['POST'])
def telephony_events(): return "OK", 200

@webhooks_bp.route('/api/webhooks/livekit', methods=['POST'])
def livekit_webhook(): return "OK", 200
