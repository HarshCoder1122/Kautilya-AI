"""
Kautilya AI — Telephony Webhooks (Exact 090e518 Flow Restored)
Room name uses voice- prefix (matches SIP trunk config).
Room pre-created SYNCHRONOUSLY so agent is dispatched BEFORE caller connects.
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

def _run_async(coro):
    """Run async code synchronously in a thread."""
    result, error = [None], [None]
    def _target():
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result[0] = loop.run_until_complete(coro)
            loop.close()
        except Exception as e:
            error[0] = e
    t = threading.Thread(target=_target)
    t.start()
    t.join(timeout=8)
    if error[0]:
        print(f"[Bridge] ❌ Pre-create error: {error[0]}")

async def pre_create_room(room_name, agent_id):
    """Pre-create room so agent gets dispatched immediately."""
    try:
        metadata = {"source": "telephony_bridge", "agent_id": agent_id}
        if db:
            try:
                agent_doc = db.collection('agents').document(agent_id).get()
                if agent_doc.exists:
                    agent_data = agent_doc.to_dict()
                    metadata["welcome_message"] = agent_data.get("welcome_message", "")
                    metadata["system_prompt"] = agent_data.get("system_prompt", "")
                    metadata["language"] = agent_data.get("language", "hi-IN")
                    metadata["voice"] = agent_data.get("voice", "Puck")
            except:
                pass
        
        lk_url = LIVEKIT_URL.replace("wss://", "https://").replace("ws://", "http://")
        lkapi = LiveKitAPI(url=lk_url, api_key=LIVEKIT_API_KEY, api_secret=LIVEKIT_API_SECRET)
        try:
            await lkapi.room.create_room(CreateRoomRequest(
                name=room_name,
                empty_timeout=300,
                metadata=json.dumps(metadata)
            ))
            print(f"[Bridge] ✅ Room {room_name} pre-created. Agent dispatching now.")
        finally:
            await lkapi.aclose()
    except Exception as e:
        print(f"[Bridge] ❌ Error: {e}")

@webhooks_bp.route('/api/webhooks/vobiz/answer/<agent_id>', methods=['POST', 'GET'])
def vobiz_answer(agent_id):
    print(f"[Vobiz] Incoming: {dict(request.values)}")
    
    call_uid = uuid.uuid4().hex[:4]
    # CRITICAL: voice- prefix matches SIP trunk dispatch rule
    room_name = f"voice-{agent_id}--{call_uid}"
    sip_uri = f"sip:{room_name}@{LIVEKIT_SIP_URI}"
    
    # 1. Pre-create room SYNCHRONOUSLY — agent dispatched NOW
    _run_async(pre_create_room(room_name, agent_id))
    
    # 2. Long <Say> gives agent ~5 seconds to fully initialize Gemini 3.1
    # 3. By the time <Dial> runs, agent is ready in the room
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>Please hold while we connect you to Kautilya AI. This will take just a moment.</Say>
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
    _run_async(pre_create_room(room_name, agent_id))
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>Please hold while we connect you to Kautilya AI.</Say>
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
