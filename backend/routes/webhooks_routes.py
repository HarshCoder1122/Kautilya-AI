"""
Kautilya AI — Telephony Webhooks (Vobiz-Compatible)
Vobiz uses Plivo XML — <Say> and <Pause> are INVALID.
Only <Dial><Sip> is supported for SIP bridging.
"""
import os
import json
import uuid
import hmac
import hashlib
import asyncio
import threading
from flask import Blueprint, request, Response
from livekit.api import LiveKitAPI, CreateRoomRequest
from extensions import db
from config import LIVEKIT_API_KEY, LIVEKIT_API_SECRET, LIVEKIT_URL, LIVEKIT_SIP_URI
import services.nim_service as nim_service
from firebase_admin import firestore
import services.nim_service as nim_service

# ============== Firebase Initialization for Webhooks ==============
try:
    import firebase_admin
    from firebase_admin import credentials, firestore
    if not firebase_admin._apps:
        # Try to use default or service account from env
        import os
        sa_json = os.environ.get('FIREBASE_SERVICE_ACCOUNT')
        if sa_json:
            import json
            try:
                info = json.loads(sa_json)
                cred = credentials.Certificate(info)
                firebase_admin.initialize_app(cred)
            except:
                if os.path.exists(sa_json):
                    cred = credentials.Certificate(sa_json)
                    firebase_admin.initialize_app(cred)
        if not firebase_admin._apps:
            try: firebase_admin.initialize_app()
            except: pass
    db = firestore.client()
    print("[Firebase-Webhooks] Connected and Ready")
except Exception as e:
    print(f"[Firebase-Webhooks Error] {e}")
    db = None

# Strip sip: prefix if present — we add it ourselves in the URI
SIP_DOMAIN = LIVEKIT_SIP_URI.replace("sip:", "").strip()

webhooks_bp = Blueprint('webhooks', __name__)

def _build_room_metadata(agent_id):
    """Pull agent config out of Firestore and serialise into room metadata
    so livekit_agent's fast-path can skip the per-call lookup chain."""
    metadata = {"source": "telephony_bridge", "agent_id": agent_id}
    if db:
        try:
            agent_doc = db.collection('agents').document(agent_id).get()
            if agent_doc.exists:
                d = agent_doc.to_dict()
                metadata["system_prompt"] = d.get("system_prompt", "")
                metadata["welcome_message"] = d.get("welcome_message", "")
                metadata["language"] = d.get("language", "hi-IN")
                metadata["model"] = d.get("model", "kautilya-daily")
                metadata["voice"] = d.get("voice", "shubh")
        except Exception as e:
            print(f"[Bridge] metadata lookup warning: {e}")
    return metadata


def _predispatch_blocking(room_name, agent_id, agent_name):
    """Synchronously pre-create the LiveKit room AND (if an agent_name is
    configured for explicit dispatch) request the worker to join it. We
    block briefly here — typically <500ms — so by the time we return the
    SIP XML to Vobiz the agent worker is already in the room. The user's
    audio leg lands into a populated room and there is no silence.

    If anything fails we just log and return — the SIP trunk will create
    the room itself when audio arrives (existing safe fallback).
    """
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        async def _do():
            metadata = _build_room_metadata(agent_id)
            lk_url = LIVEKIT_URL.replace("wss://", "https://").replace("ws://", "http://")
            lkapi = LiveKitAPI(url=lk_url, api_key=LIVEKIT_API_KEY, api_secret=LIVEKIT_API_SECRET)
            try:
                await lkapi.room.create_room(CreateRoomRequest(
                    name=room_name, empty_timeout=120, metadata=json.dumps(metadata)
                ))
                if agent_name:
                    # Explicit dispatch — needed when worker registered with
                    # `agent_name=`. Auto-dispatch is disabled in that mode.
                    try:
                        from livekit.api import CreateAgentDispatchRequest
                        await lkapi.agent_dispatch.create_dispatch(
                            CreateAgentDispatchRequest(
                                agent_name=agent_name,
                                room=room_name,
                                metadata=json.dumps(metadata),
                            )
                        )
                        print(f"[Bridge] ✅ {room_name} created + {agent_name} dispatched")
                    except Exception as e:
                        print(f"[Bridge] explicit dispatch failed: {e}")
                else:
                    print(f"[Bridge] ✅ {room_name} created (auto-dispatch worker)")
            finally:
                await lkapi.aclose()
        loop.run_until_complete(_do())
        loop.close()
    except Exception as e:
        print(f"[Bridge] ❌ pre-dispatch error: {e}")


# Background-thread variant retained for the Exotel path, which is async
# (we don't have time to block on the answer webhook). Kept identical to
# the original behaviour for back-compat.
def create_room_fire_and_forget(room_name, agent_id):
    """Fire-and-forget room creation. Does NOT block the Flask response."""
    def _task():
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            async def _do():
                metadata = _build_room_metadata(agent_id)
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

def _verify_webhook_secret(provided: str) -> bool:
    """Constant-time compare against WEBHOOK_SECRET env var.
    If the env var is not set, the check is skipped for backward compatibility.
    Set WEBHOOK_SECRET in HuggingFace Space secrets to enforce validation.
    """
    expected = os.environ.get("WEBHOOK_SECRET", "").strip()
    if not expected:
        return True
    if not provided:
        return False
    return hmac.compare_digest(expected.encode(), provided.encode())


@webhooks_bp.route('/webhooks/vobiz/answer/<agent_id>', methods=['POST', 'GET'])
def vobiz_answer(agent_id):
    secret = request.values.get('secret') or request.headers.get('X-Webhook-Secret', '')
    if not _verify_webhook_secret(secret):
        print(f"[Vobiz] Rejected: invalid webhook secret for agent {agent_id}")
        return Response("Forbidden", status=403)
    print(f"[Vobiz] Incoming: {dict(request.values)}")

    event = request.values.get('Event')
    call_uuid = request.values.get('CallUUID', uuid.uuid4().hex[:8])

    if event == 'Hangup':
        # Trigger NIM post-call analytics in background
        threading.Thread(target=_process_post_call, args=(agent_id, dict(request.values), call_uuid), daemon=True).start()
        return "OK", 200

    # ----- Save lookup mappings BEFORE the SIP leg lands -----
    # The agent worker (livekit_agent._resolve_agent_doc) reads these to
    # discover which agent_id owns the call. We do NOT pre-create a LiveKit
    # room here — LiveKit's inbound SIP trunk dispatch rule creates the real
    # room (e.g. `voice-_+<phone>_<callid>`) when the customer's audio leg
    # arrives. Pre-creating a `voice-<agent>--<uid>` room caused the agent
    # worker to be dispatched TWICE (once into the empty pre-warmed room,
    # once into the real SIP room), wasting a worker slot and producing the
    # extra 5–6 sec of ringing the user reported.
    try:
        if db:
            db.collection('call_mappings').document(call_uuid).set({
                "agent_id": agent_id,
                "created_at": firestore.SERVER_TIMESTAMP
            })
            # Race-safe mappings: write each phone variant in TWO shapes —
            # `active_calls/<phone>` (legacy, latest-wins, kept for back-compat
            # readers) plus `active_calls/<phone>/pending/<call_uuid>` (FIFO
            # queue keyed by call uuid, which the agent worker claims atomi-
            # cally so two simultaneous calls to the same phone never collide).
            for who in ('From', 'To', 'CallerNumber', 'Caller'):
                raw = (request.values.get(who) or '').strip()
                if not raw:
                    continue
                clean = raw.lstrip('+')
                variants = {raw, clean, '+' + clean}
                if clean.startswith('91') and len(clean) >= 12:
                    local = clean[2:]
                    variants.update({local, '+91' + local})
                for v in variants:
                    if not v:
                        continue
                    payload_top = {
                        "agent_id": agent_id,
                        "call_uuid": call_uuid,
                        "created_at": firestore.SERVER_TIMESTAMP,
                    }
                    payload_pending = {**payload_top, "claimed": False}
                    try:
                        db.collection('active_calls').document(v).set(payload_top)
                        db.collection('active_calls').document(v) \
                          .collection('pending').document(call_uuid).set(payload_pending)
                    except Exception:
                        pass
            print(f"[Bridge] mappings saved for call {call_uuid} -> {agent_id}")
    except Exception as e:
        print(f"[Bridge] Mapping error: {e}")

    # ----- Decide SIP destination + (optional) pre-dispatch -----
    # Two modes:
    #
    # (A) "Direct dispatch" mode (LIVEKIT_SIP_DIRECT_DISPATCH=1): we
    #     generate a deterministic room name, pre-create the room and
    #     pre-dispatch the agent BEFORE replying to Vobiz. The customer's
    #     audio leg then lands into a room where the agent is already
    #     waiting — zero silence after pickup. Requires the LiveKit
    #     inbound SIP trunk dispatch rule to be in **Direct** mode so the
    #     SIP user portion is honored as the room name.
    #
    # (B) Default safe mode: no pre-warm, no pre-create. The LiveKit
    #     inbound SIP trunk creates its own canonical room
    #     (`voice-_+<phone>_<callid>`) when the audio leg arrives and
    #     auto-dispatches the agent. Single-room guarantee.
    direct_dispatch = os.environ.get("LIVEKIT_SIP_DIRECT_DISPATCH", "").strip().lower() in ("1", "true", "yes")
    agent_worker_name = os.environ.get("LIVEKIT_AGENT_NAME", "").strip()
    caller_id = request.values.get('From', '')

    if direct_dispatch:
        room_name = f"voice-{agent_id}--{call_uuid}"
        # Block briefly while we pre-create the room and (optionally)
        # explicitly dispatch the named agent. Typical wall-clock cost is
        # 200-500ms — well within Vobiz's answer-webhook timeout — and it
        # buys us a fully populated room before the audio leg lands.
        _predispatch_blocking(room_name, agent_id, agent_worker_name)
        sip_uri = f"sip:{room_name}@{SIP_DOMAIN}"
        log_suffix = "(direct dispatch, pre-warmed)"
    else:
        from_number = (request.values.get('From') or '').strip().lstrip('+') or 'caller'
        # SINGLE ROOM GUARANTEE: In standard SIP mode, we cannot predict the 
        # random suffix LiveKit will append to the room name. We stop 
        # pre-warming here to prevent "ghost rooms" from being created.
        sip_uri = f"sip:{from_number}@{SIP_DOMAIN}"
        log_suffix = "(safe mode, single-room mode)"

    xml = f"""<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<Response>
    <Dial timeout="60" callerId="{caller_id}">
        <User>{sip_uri}</User>
    </Dial>
</Response>"""
    print(f"[Vobiz] Returning XML with SIP URI: {sip_uri} {log_suffix}")
    return Response(xml, mimetype='text/xml')

@webhooks_bp.route('/webhooks/exotel/answer/<agent_id>', methods=['POST', 'GET'])
def exotel_answer(agent_id):
    secret = request.values.get('secret') or request.headers.get('X-Webhook-Secret', '')
    if not _verify_webhook_secret(secret):
        print(f"[Exotel] Rejected: invalid webhook secret for agent {agent_id}")
        return Response("Forbidden", status=403)
    caller_id = request.values.get('From', '')
    from_number = caller_id.strip().lstrip('+') or 'caller'
    sip_uri = f"sip:{from_number}@{SIP_DOMAIN}"
    
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Dial callerId="{caller_id}">
        <User>{sip_uri}</User>
    </Dial>
</Response>"""
    return Response(xml, mimetype='text/xml')

@webhooks_bp.route('/webhooks/vobiz/events', methods=['POST'])
@webhooks_bp.route('/webhooks/exotel/events', methods=['POST'])
def telephony_events(): return "OK", 200

@webhooks_bp.route('/webhooks/livekit', methods=['POST'])
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
        transcripts_ref = db.collection('transcripts').where(filter=firestore.FieldFilter('agent_id', '==', agent_id)).order_by('created_at', direction=firestore.Query.DESCENDING).limit(1).get()
        
        transcript_text = ""
        if transcripts_ref:
            doc = transcripts_ref[0]
            transcript_text = doc.to_dict().get('transcript', '')
            print(f"[NIM] Found transcript: {len(transcript_text)} chars")
        else:
            print("[NIM] No transcript found in Firestore.")
            
        # Analyze with NIM
        analytics = nim_service.analyze_call_transcript(transcript_text)
        
        # Build the final log document for the dashboard
        log_data = {
            "call_id": call_uuid,
            "agent_id": agent_id,
            "created_at": firestore.SERVER_TIMESTAMP,
            "timestamp": int(time.time()),
            "duration": payload.get('Duration', 0),
            "from_number": payload.get('From', 'Unknown'),
            "to_number": payload.get('To', 'Unknown'),
            "status": analytics.get('outcome', payload.get('CallStatus', 'completed')),
            "transcript": transcript_text,
            "summary": analytics.get('summary', ''),
            "sentiment": analytics.get('sentiment', 'neutral'),
            "topics": analytics.get('topics', []),
            "channel": "voice_sip",
        }
        
        # Save to agents/{agent_id}/agent_logs
        # We use call_uuid as doc ID to prevent duplicates if livekit_agent already saved it
        db.collection('agents').document(agent_id).collection('agent_logs').document(call_uuid).set(log_data, merge=True)
        db.collection('agents').document(agent_id).update({"call_count": firestore.Increment(1)})
        print(f"[NIM] ✅ Saved structured call log for {call_uuid} to agent_logs")

        # ---- Post-call integration dispatch ----
        # Extract action items from transcript and fire them through the
        # owner's connected integrations (CRM note, Slack summary, calendar
        # follow-ups). Soft-fail — analytics save above must remain authoritative.
        try:
            agent_doc = db.collection('agents').document(agent_id).get()
            owner_uid = (agent_doc.to_dict() or {}).get('uid') if agent_doc.exists else None
            if owner_uid and transcript_text:
                _dispatch_post_call_integrations(owner_uid, agent_id, log_data, transcript_text)
        except Exception as e:
            print(f"[Integrations] post-call dispatch soft-failed: {e}")

    except Exception as e:
        print(f"[NIM] ❌ Error in post-call processing: {e}")


def _dispatch_post_call_integrations(uid, agent_id, log_data, transcript_text):
    """Fan call summary + action items into the owner's connected integrations.
    - Slack: post a brief outcome summary to the configured channel.
    - CRM: log a note on the matched contact (looked up by from_number).
    - Calendar: any extracted action item with a due date becomes an event.
    """
    from services.integration_tools import execute_tool, _is_connected, _lookup_crm_contact
    from services.llm_service import call_groq

    summary = log_data.get('summary') or '(no summary)'
    sentiment = log_data.get('sentiment', 'neutral')
    from_number = log_data.get('from_number') or log_data.get('to_number') or ''

    # 1. Slack summary
    if _is_connected(uid, 'slack'):
        msg = f"*Call wrapped* — Agent `{agent_id}` | {from_number} | sentiment: {sentiment}\n>{summary[:500]}"
        execute_tool(uid, "post_slack", {"message": msg})

    # 2. CRM note (lookup by phone, then attach activity note)
    crm = _lookup_crm_contact(uid, {"phone": from_number}) if from_number else {"ok": False}
    if crm.get("ok"):
        contact = crm["contact"]
        cid = contact.get("vid") or contact.get("id") or contact.get("Contact_Id") or contact.get("contact_id")
        if cid:
            note = f"Kautilya call summary ({sentiment}):\n{summary}\n\nTopics: {', '.join(log_data.get('topics', []))}"
            execute_tool(uid, "log_crm_activity", {"contact_id": str(cid), "note": note, "source": crm["source"]})

    # 3. Calendar follow-ups — extract action items with a due date
    try:
        prompt = [
            {"role": "system", "content":
             "Extract action items from this call transcript that need a calendar follow-up. "
             "Return JSON array; each item: {title, due (RFC3339), duration_minutes (int, default 30)}. "
             "Only items the agent explicitly committed to. If none, return []."},
            {"role": "user", "content": transcript_text[:6000]},
        ]
        out = call_groq(prompt, model="llama-3.3-70b-versatile",
                        temperature=0.1, max_tokens=600, stream=False)
        import re as _re
        m = _re.search(r'\[.*\]', out or "", _re.S)
        items = json.loads(m.group(0)) if m else []
        if _is_connected(uid, 'google_calendar'):
            from datetime import datetime, timedelta
            for it in items[:5]:
                due = it.get("due")
                if not due: continue
                try:
                    start = datetime.fromisoformat(due.replace('Z', '+00:00'))
                    end = start + timedelta(minutes=int(it.get("duration_minutes", 30)))
                    execute_tool(uid, "create_calendar_event", {
                        "title": it.get("title", "Kautilya follow-up"),
                        "start": start.isoformat(),
                        "end": end.isoformat(),
                        "description": f"Auto-created from call {log_data.get('call_id')}.",
                    })
                except Exception as e:
                    print(f"[Integrations] calendar item skipped: {e}")
    except Exception as e:
        print(f"[Integrations] action-item extraction failed: {e}")
