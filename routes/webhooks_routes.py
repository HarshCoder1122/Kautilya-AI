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
import services.nim_service as nim_service

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
    
    event = request.values.get('Event')
    call_uuid = request.values.get('CallUUID', uuid.uuid4().hex[:8])
    
    # Extract the original room_name from the SIP URI if provided, or generate a new one
    # Vobiz doesn't send the original SIP URI in the Hangup event directly,
    # but we can reconstruct the expected room name since we know the logic.
    # Wait, the room name was generated with a random uuid in the original webhook!
    # If the user's call dropped, we need the EXACT room name.
    # Actually, Vobiz doesn't give us the generated call_uid back easily unless we pass it.
    # Let's pass the call_uuid in the answer_url in telephony_routes!
    # For now, we will search Firestore for the latest transcript for this agent_id.
    
    if event == 'Hangup':
        # Trigger NIM post-call analytics in background
        threading.Thread(target=_process_post_call, args=(agent_id, dict(request.values), call_uuid), daemon=True).start()
        return "OK", 200

    # Use pre-warmed room if provided, otherwise create a new one
    room_name = request.args.get('room')
    if room_name:
        print(f"[Vobiz] Using pre-warmed room: {room_name}")
    else:
        call_uid = uuid.uuid4().hex[:4]
        room_name = f"voice-{agent_id}--{call_uid}"
        # Fire-and-forget room creation
        create_room_fire_and_forget(room_name, agent_id)
    
    sip_uri = f"sip:{room_name}@{SIP_DOMAIN}"
    
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
    # Use pre-warmed room if provided
    room_name = request.args.get('room')
    if room_name:
        print(f"[Exotel] Using pre-warmed room: {room_name}")
    else:
        call_uid = request.values.get('CallSid', uuid.uuid4().hex[:8])
        room_name = f"voice-{agent_id}--{call_uid}"
        create_room_fire_and_forget(room_name, agent_id)
        
    sip_uri = f"sip:{room_name}@{SIP_DOMAIN}"
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

def _process_post_call(agent_id, payload, call_uuid):
    """Background task to fetch transcript, run NIM, and save logs."""
    try:
        print(f"[NIM] Processing post-call for Agent: {agent_id}, Call: {call_uuid}")
        import time
        from firebase_admin import firestore
        
        # Give the agent a few seconds to finish saving the transcript
        time.sleep(5)
        
        if not db:
            return

        # Find the latest transcript for this agent
        transcripts_ref = db.collection('transcripts').where('agent_id', '==', agent_id).order_by('created_at', direction=firestore.Query.DESCENDING).limit(1).get()
        
        transcript_text = ""
        if transcripts_ref:
            doc = transcripts_ref[0]
            transcript_text = doc.to_dict().get('transcript', '')
            print(f"[NIM] Found transcript: {len(transcript_text)} chars")
        else:
            print("[NIM] No transcript found in Firestore.")
            
        # Analyze with NIM
        analytics = nim_service.analyze_call_transcript(transcript_text)
        
        # Build the final log document
        log_data = {
            "call_id": call_uuid,
            "agent_id": agent_id,
            "timestamp": firestore.SERVER_TIMESTAMP,
            "duration": payload.get('Duration', 'Unknown'),
            "from_number": payload.get('From', 'Unknown'),
            "to_number": payload.get('To', 'Unknown'),
            "status": payload.get('CallStatus', 'completed'),
            "transcript": transcript_text,
            "analysis": analytics
        }
        
        # Save to agents/{agent_id}/logs
        db.collection('agents').document(agent_id).collection('logs').document(call_uuid).set(log_data)
        print(f"[NIM] ✅ Saved structured call log for {call_uuid}")
        
    except Exception as e:
        print(f"[NIM] ❌ Error in post-call processing: {e}")
