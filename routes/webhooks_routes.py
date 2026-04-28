"""
Kautilya AI — Telephony Webhooks (Restored Pre-Creation)
Pre-creates room SYNCHRONOUSLY so agent gets dispatched BEFORE the caller connects.
Room name matches exactly what SIP trunk expects (no voice- prefix).
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
            print(f"[Bridge] ✅ Room {room_name} pre-created. Agent dispatched.")
        finally:
            await lkapi.aclose()
    except Exception as e:
        print(f"[Bridge] ❌ Error: {e}")

@webhooks_bp.route('/api/webhooks/vobiz/answer/<agent_id>', methods=['POST', 'GET'])
def vobiz_answer(agent_id):
    print(f"[Vobiz] Incoming: {dict(request.values)}")
    
    call_uid = uuid.uuid4().hex[:4]
    # Room name WITHOUT voice- prefix (matches what SIP trunk expects)
    room_name = f"{agent_id}--{call_uid}"
    sip_uri = f"sip:{room_name}@{LIVEKIT_SIP_URI}"
    
    # 1. Pre-create room SYNCHRONOUSLY — agent gets dispatched NOW
    _run_async(pre_create_room(room_name, agent_id))
    
    # 2. <Say> gives agent 2-3 seconds to fully initialize
    # 3. <Dial> connects caller to room where agent is already waiting
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
    call_uid = uuid.uuid4().hex[:4]
    room_name = f"{agent_id}--{call_uid}"
    sip_uri = f"sip:{room_name}@{LIVEKIT_SIP_URI}"
    _run_async(pre_create_room(room_name, agent_id))
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>Connecting...</Say>
    <Dial timeout="30">
        <Sip>{sip_uri}</Sip>
    </Dial>
</Response>"""
    return Response(xml, mimetype='text/xml')

@webhooks_bp.route('/api/webhooks/vobiz/events', methods=['POST'])
@webhooks_bp.route('/api/webhooks/exotel/events', methods=['POST'])
def telephony_events(): return "OK", 200

@webhooks_bp.route('/api/webhooks/livekit', methods=['POST'])
def livekit_webhook(): return "OK", 200
