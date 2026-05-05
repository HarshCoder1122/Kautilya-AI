import os
import uuid
import json
import threading
import time
import asyncio
from flask import Blueprint, request, Response
from firebase_admin import firestore
from extensions import db
from services import nim_service

webhooks_bp = Blueprint('webhooks', __name__)

SIP_DOMAIN = os.environ.get("LIVEKIT_SIP_DOMAIN", "meet-2wx5nfq3.sip.livekit.cloud")

def _empty_xml_response():
    return Response('<?xml version="1.0" encoding="UTF-8"?><Response></Response>', mimetype='text/xml')


def _claim_bridge_once(agent_id, call_uuid):
    if not (db and call_uuid):
        return True
    ref = db.collection('call_mappings').document(call_uuid)

    @firestore.transactional
    def _claim(tx, doc_ref):
        snap = doc_ref.get(transaction=tx)
        data = snap.to_dict() if snap.exists else {}
        if data.get("sip_bridge_started"):
            return False
        tx.set(doc_ref, {
            "agent_id": agent_id,
            "sip_bridge_started": True,
            "sip_bridge_started_at": firestore.SERVER_TIMESTAMP,
            "created_at": data.get("created_at") or firestore.SERVER_TIMESTAMP,
        }, merge=True)
        return True

    return _claim(db.transaction(), ref)


def _build_room_metadata(agent_id, call_uuid):
    metadata = {
        "source": "telephony_bridge",
        "agent_id": agent_id,
        "resolved_agent_id": agent_id,
        "resolved_call_id": call_uuid or "",
    }
    if db:
        try:
            agent_doc = db.collection('agents').document(agent_id).get()
            if agent_doc.exists:
                data = agent_doc.to_dict() or {}
                for key in ("system_prompt", "welcome_message", "language", "model", "voice"):
                    if data.get(key):
                        metadata[key] = data.get(key)
        except Exception as e:
            print(f"[Bridge] metadata lookup warning: {e}")
    return metadata


def _predispatch_room_blocking(room_name, agent_id, call_uuid):
    """Pre-create and optionally explicit-dispatch a LiveKit room.

    This is enabled only with LIVEKIT_SIP_DIRECT_DISPATCH=1 because the SIP
    trunk must honor the SIP user portion as the room name.
    """
    try:
        from livekit.api import LiveKitAPI, CreateRoomRequest
        from config import LIVEKIT_API_KEY, LIVEKIT_API_SECRET, LIVEKIT_URL

        if not (LIVEKIT_URL and LIVEKIT_API_KEY and LIVEKIT_API_SECRET):
            print("[Bridge] direct dispatch skipped: LiveKit credentials missing")
            return False

        agent_name = os.environ.get("LIVEKIT_AGENT_NAME", "").strip()
        metadata = _build_room_metadata(agent_id, call_uuid)
        lk_url = LIVEKIT_URL.replace("wss://", "https://").replace("ws://", "http://")

        async def _do():
            lkapi = LiveKitAPI(url=lk_url, api_key=LIVEKIT_API_KEY, api_secret=LIVEKIT_API_SECRET)
            try:
                try:
                    await lkapi.room.create_room(CreateRoomRequest(
                        name=room_name,
                        empty_timeout=120,
                        metadata=json.dumps(metadata),
                    ))
                    print(f"[Bridge] pre-created LiveKit room {room_name}")
                except Exception as e:
                    print(f"[Bridge] room pre-create warning for {room_name}: {e}")

                if agent_name:
                    try:
                        from livekit.api import CreateAgentDispatchRequest
                        await lkapi.agent_dispatch.create_dispatch(
                            CreateAgentDispatchRequest(
                                agent_name=agent_name,
                                room=room_name,
                                metadata=json.dumps(metadata),
                            )
                        )
                        print(f"[Bridge] explicit-dispatched {agent_name} to {room_name}")
                    except Exception as e:
                        print(f"[Bridge] explicit dispatch warning for {room_name}: {e}")
            finally:
                await lkapi.aclose()

        asyncio.run(_do())
        return True
    except Exception as e:
        print(f"[Bridge] pre-dispatch error: {e}")
        return False


@webhooks_bp.route('/api/webhooks/vobiz/answer/<agent_id>', methods=['POST', 'GET'])
def vobiz_answer(agent_id):
    print(f"[Vobiz] Incoming: {dict(request.values)}")
    
    event = request.values.get('Event')
    call_uuid = (
        request.values.get('CallUUID')
        or request.values.get('call_uuid')
        or request.values.get('RequestUUID')
        or request.values.get('request_uuid')
        or request.values.get('api_id')
        or uuid.uuid4().hex[:8]
    )

    if event == 'Hangup':
        threading.Thread(target=_process_post_call, args=(agent_id, dict(request.values), call_uuid), daemon=True).start()
        return "OK", 200

    try:
        if not _claim_bridge_once(agent_id, call_uuid):
            print(f"[Vobiz] Duplicate answer callback ignored for call {call_uuid}")
            return _empty_xml_response()
    except Exception as e:
        print(f"[Bridge] Idempotency claim warning: {e}")

    # Save lookup mapping
    try:
        if db:
            db.collection('call_mappings').document(call_uuid).set({
                "agent_id": agent_id,
                "created_at": firestore.SERVER_TIMESTAMP
            }, merge=True)
            
            # Save variants for lookup
            for who in ('From', 'To', 'CallerNumber', 'Caller'):
                raw = (request.values.get(who) or '').strip()
                if not raw: continue
                clean = raw.lstrip('+')
                variants = {raw, clean, '+' + clean}
                for v in variants:
                    if not v: continue
                    payload = {
                        "agent_id": agent_id,
                        "call_uuid": call_uuid,
                        "created_at": firestore.SERVER_TIMESTAMP,
                    }
                    db.collection('active_calls').document(v).set(payload)
                    db.collection('active_calls').document(v).collection('pending').document(call_uuid).set({**payload, "claimed": False})
    except Exception as e:
        print(f"[Bridge] Mapping error: {e}")

    from_number = (request.values.get('From') or '').strip().lstrip('+') or 'caller'
    caller_id = request.values.get('From', '')
    direct_dispatch = os.environ.get("LIVEKIT_SIP_DIRECT_DISPATCH", "").strip().lower() in ("1", "true", "yes")

    if direct_dispatch:
        room_name = f"voice-_+{from_number}_{call_uuid}"
        _predispatch_room_blocking(room_name, agent_id, call_uuid)
        sip_uri = f"sip:{room_name}@{SIP_DOMAIN}"
        print(f"[Vobiz] Direct dispatch SIP URI: {sip_uri}")
    else:
        sip_uri = f"sip:{from_number}@{SIP_DOMAIN}"

    xml = f"""<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<Response>
    <Dial timeout="60" callerId="{caller_id}">
        <User>{sip_uri}</User>
    </Dial>
</Response>"""
    print(f"[Vobiz] Returning XML: {sip_uri}")
    return Response(xml, mimetype='text/xml')

@webhooks_bp.route('/api/webhooks/exotel/answer/<agent_id>', methods=['POST', 'GET'])
def exotel_answer(agent_id):
    from_number = (request.values.get('From') or '').strip().lstrip('+') or 'caller'
    sip_uri = f"sip:{from_number}@{SIP_DOMAIN}"
    xml = f'<?xml version="1.0" encoding="UTF-8"?><Response><Dial><User>{sip_uri}</User></Dial></Response>'
    return Response(xml, mimetype='text/xml')

@webhooks_bp.route('/api/webhooks/vobiz/events', methods=['POST'])
@webhooks_bp.route('/api/webhooks/exotel/events', methods=['POST'])
def telephony_events(): return "OK", 200

@webhooks_bp.route('/api/webhooks/livekit', methods=['POST'])
def livekit_webhook(): return "OK", 200

def _process_post_call(agent_id, payload, call_uuid):
    try:
        time.sleep(5)
        if not db: return
        transcripts = db.collection('transcripts').where(filter=firestore.FieldFilter('agent_id', '==', agent_id)).order_by('created_at', direction=firestore.Query.DESCENDING).limit(1).get()
        transcript_text = transcripts[0].to_dict().get('transcript', '') if transcripts else ""
        analytics = nim_service.analyze_call_transcript(transcript_text)
        log_data = {
            "call_id": call_uuid, "agent_id": agent_id, "timestamp": firestore.SERVER_TIMESTAMP,
            "duration": payload.get('Duration', 'Unknown'), "from_number": payload.get('From', 'Unknown'),
            "to_number": payload.get('To', 'Unknown'), "status": payload.get('CallStatus', 'completed'),
            "transcript": transcript_text, "analysis": analytics
        }
        db.collection('agents').document(agent_id).collection('logs').document(call_uuid).set(log_data)
    except Exception as e:
        print(f"[NIM] Error: {e}")
