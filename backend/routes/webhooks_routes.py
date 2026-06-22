"""
Kautilya AI — Telephony Webhooks (Vobiz-Compatible)
Vobiz uses Plivo XML — <Say> and <Pause> are INVALID.
Only <Dial><Sip> is supported for SIP bridging.
"""
import os
import re
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


def _clean_phone(value: str) -> str:
    """Reduce a provider-supplied phone/caller value to digits and a leading
    '+'. The `From`/`To` fields land inside the SIP XML we return to Vobiz;
    without this, a crafted value like `1"><Dial><User>sip:attacker@evil`
    could inject extra dial directives (call redirection / toll fraud)."""
    return re.sub(r'[^0-9+]', '', value or '')

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
    caller_id = _clean_phone(request.values.get('From', ''))

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
        from_number = _clean_phone(request.values.get('From', '')).lstrip('+') or 'caller'
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
    caller_id = _clean_phone(request.values.get('From', ''))
    from_number = caller_id.lstrip('+') or 'caller'
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
            
        # Analyze with NIM (now also returns lead.name/email/company/phone/score)
        analytics = nim_service.analyze_call_transcript(transcript_text)
        lead_info = analytics.get('lead') or {}

        # We ALWAYS know the customer's number on a telephony call — it's the
        # To/From on the provider payload. Prefer that verified number over
        # anything the LLM mined from the transcript (STT garbles digits).
        from_number = _clean_phone(payload.get('From', '')) or 'Unknown'
        to_number = _clean_phone(payload.get('To', '')) or 'Unknown'
        known_phone = next((p for p in (to_number, from_number)
                            if p and p != 'Unknown'), '')
        lead_phone = (known_phone or _clean_phone(lead_info.get('phone', ''))).lstrip('+')

        # Build the final log document for the dashboard
        log_data = {
            "call_id": call_uuid,
            "agent_id": agent_id,
            "created_at": firestore.SERVER_TIMESTAMP,
            "timestamp": int(time.time()),
            "duration": payload.get('Duration', 0),
            "from_number": from_number,
            "to_number": to_number,
            "status": analytics.get('outcome', payload.get('CallStatus', 'completed')),
            "transcript": transcript_text,
            "transcript_json": _structure_transcript(transcript_text),
            "summary": analytics.get('summary', ''),
            "sentiment": analytics.get('sentiment', 'neutral'),
            "intent": analytics.get('intent', ''),
            "topics": analytics.get('topics', []),
            # Surface the extracted lead fields directly on the log so the Call
            # Analytics dashboard can show name / email / company per call.
            "lead_name": lead_info.get('name', ''),
            "lead_email": lead_info.get('email', ''),
            "lead_company": lead_info.get('company', ''),
            "lead_phone": lead_phone,
            "lead_score": lead_info.get('score', 0),
            "lead_status": analytics.get('lead_status', ''),
            "actions": [],
            "channel": "voice_sip",
        }

        # ---- Post-call integration dispatch ----
        # Fire CRM note / Slack summary / calendar follow-ups / follow-up email
        # through the owner's connected integrations, and record each action on
        # the log so the dashboard can show "what happened after the call".
        actions = []
        owner_uid = None
        try:
            agent_doc = db.collection('agents').document(agent_id).get()
            owner_uid = (agent_doc.to_dict() or {}).get('uid') if agent_doc.exists else None
            if owner_uid and transcript_text:
                actions = _dispatch_post_call_integrations(
                    owner_uid, agent_id, log_data, transcript_text) or []
        except Exception as e:
            print(f"[Integrations] post-call dispatch soft-failed: {e}")
        log_data["actions"] = actions

        # Save to agents/{agent_id}/agent_logs (call_uuid as doc id → no dupes
        # even if livekit_agent already wrote a stub for this call).
        db.collection('agents').document(agent_id).collection('agent_logs').document(call_uuid).set(log_data, merge=True)
        db.collection('agents').document(agent_id).update({"call_count": firestore.Increment(1)})
        print(f"[NIM] ✅ Saved structured call log for {call_uuid} to agent_logs")

        # ---- Lead capture ----
        # Every answered call with a known number becomes a lead so the Leads
        # page is never empty and the dialed/calling number is always extracted.
        if owner_uid and (lead_phone or lead_info.get('name') or lead_info.get('email')):
            _upsert_lead_from_call(owner_uid, agent_id, log_data)

    except Exception as e:
        import traceback
        print(f"[NIM] ❌ Error in post-call processing: {e}")
        traceback.print_exc()


def _structure_transcript(transcript_text):
    """Turn the flat "ROLE: text" transcript into a list of {role, text} turns
    the dashboard renders as chat bubbles. Roles are normalised to
    'agent' / 'customer' (what CallAnalytics expects). Unknown shapes → []."""
    if not transcript_text or not isinstance(transcript_text, str):
        return []
    turns = []
    for line in transcript_text.splitlines():
        line = line.strip()
        if not line:
            continue
        m = re.match(r'^([A-Za-z_]+)\s*:\s*(.*)$', line)
        if not m:
            # continuation of the previous speaker's line
            if turns:
                turns[-1]["text"] += " " + line
            continue
        role_raw, text = m.group(1).lower(), m.group(2).strip()
        if role_raw in ('assistant', 'agent', 'ai', 'bot'):
            role = 'agent'
        elif role_raw in ('user', 'customer', 'caller', 'human'):
            role = 'customer'
        else:
            role = 'agent'
        if text:
            turns.append({"role": role, "text": text})
    return turns


def _upsert_lead_from_call(uid, agent_id, log_data):
    """Create (or refresh) a lead from a finished call. Keyed by phone so
    repeated calls from the same number update one lead instead of spamming."""
    try:
        phone = (log_data.get('lead_phone') or '').strip()
        score = int(log_data.get('lead_score') or 0)
        status = 'hot' if score >= 7 else ('warm' if score >= 4 else 'new')
        lead = {
            "uid": uid,
            "agent_id": agent_id,
            "name": log_data.get('lead_name', ''),
            "email": log_data.get('lead_email', ''),
            "company": log_data.get('lead_company', ''),
            "phone": phone,
            "message": log_data.get('summary', ''),
            "intent": log_data.get('intent', ''),
            "source": "voice_sip",
            "status": status,
            "sentiment": log_data.get('sentiment', 'neutral'),
            "score": score,
            "last_call_id": log_data.get('call_id', ''),
            "updated_at": firestore.SERVER_TIMESTAMP,
        }
        existing = None
        if phone:
            try:
                existing = list(db.collection('leads')
                                .where(filter=firestore.FieldFilter('uid', '==', uid))
                                .where(filter=firestore.FieldFilter('phone', '==', phone))
                                .limit(1).stream())
            except Exception as qe:
                # Missing index / transient error → just create a fresh lead
                # rather than dropping the capture entirely.
                print(f"[Lead] dedup query failed ({qe}) — creating new lead")
                existing = None
        if existing:
            db.collection('leads').document(existing[0].id).set(lead, merge=True)
            print(f"[Lead] 🔄 Updated lead for {phone}")
        else:
            lead_id = 'lead_' + uuid.uuid4().hex[:20]
            lead["id"] = lead_id
            lead["created_at"] = firestore.SERVER_TIMESTAMP
            db.collection('leads').document(lead_id).set(lead)
            print(f"[Lead] 🏆 Captured lead {lead_id} for {phone or '(no phone)'}")
    except Exception as e:
        print(f"[Lead] upsert failed: {e}")


def _dispatch_post_call_integrations(uid, agent_id, log_data, transcript_text):
    """Fan call summary + action items into the owner's connected integrations
    and RETURN a list of recorded actions so the dashboard can show what
    happened after the call. Each action: {type, label, status, detail}.
    - Slack: post a brief outcome summary to the configured channel.
    - CRM: log a note on the matched contact (looked up by phone).
    - Calendar: any extracted action item with a due date becomes an event.
    - Email: a follow-up email to the lead (if we captured an address).
    """
    from services.integration_tools import execute_tool, _is_connected, _lookup_crm_contact
    from services.llm_service import call_groq

    actions = []
    summary = log_data.get('summary') or '(no summary)'
    sentiment = log_data.get('sentiment', 'neutral')
    phone = log_data.get('lead_phone') or log_data.get('from_number') or log_data.get('to_number') or ''

    # 1. Slack summary
    if _is_connected(uid, 'slack'):
        msg = f"*Call wrapped* — Agent `{agent_id}` | {phone} | sentiment: {sentiment}\n>{summary[:500]}"
        res = execute_tool(uid, "post_slack", {"message": msg})
        actions.append({"type": "slack", "label": "Posted call summary to Slack",
                        "status": "ok" if (res or {}).get("ok", True) else "failed",
                        "detail": summary[:140]})

    # 2. CRM note (lookup by phone, then attach activity note)
    crm = _lookup_crm_contact(uid, {"phone": phone}) if phone else {"ok": False}
    if crm.get("ok"):
        contact = crm["contact"]
        cid = contact.get("vid") or contact.get("id") or contact.get("Contact_Id") or contact.get("contact_id")
        if cid:
            note = f"Kautilya call summary ({sentiment}):\n{summary}\n\nTopics: {', '.join(log_data.get('topics', []))}"
            execute_tool(uid, "log_crm_activity", {"contact_id": str(cid), "note": note, "source": crm["source"]})
            actions.append({"type": "crm", "label": f"Logged note in {crm['source']} CRM",
                            "status": "ok", "detail": f"Contact {cid}"})

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
            lead_email = (log_data.get('lead_email') or '').strip()
            for it in items[:5]:
                due = it.get("due")
                if not due: continue
                try:
                    start = datetime.fromisoformat(due.replace('Z', '+00:00'))
                    dur = int(it.get("duration_minutes", 30))
                    # Time-aware: shift the slot forward until it no longer
                    # clashes with anything already on the calendar, so two
                    # different leads never get booked into the same slot.
                    start, end, shifted = _find_clash_free_slot(uid, start, dur)
                    invite = {
                        "title": it.get("title", "Kautilya follow-up"),
                        "start": start.isoformat(),
                        "end": end.isoformat(),
                        "description": f"Auto-created from call {log_data.get('call_id')}.\n\n{summary}",
                        "create_meet_link": True,
                    }
                    if lead_email and '@' in lead_email:
                        invite["attendees"] = [lead_email]  # sends the invite
                    res = execute_tool(uid, "create_calendar_event", invite)
                    ok = bool((res or {}).get("ok", True))
                    detail = f"{it.get('title', 'Follow-up')} @ {start.strftime('%d %b %H:%M')}"
                    if shifted:
                        detail += " (auto-shifted to avoid a clash)"
                    actions.append({"type": "calendar",
                                    "label": "Scheduled follow-up meeting",
                                    "status": "ok" if ok else "failed", "detail": detail})
                except Exception as e:
                    print(f"[Integrations] calendar item skipped: {e}")
    except Exception as e:
        print(f"[Integrations] action-item extraction failed: {e}")

    # 4. Follow-up email to the lead — sent FROM the owner's OWN connected Gmail
    #    account. This dashboard is multi-tenant, so we never send from the shared
    #    Kautilya/Resend address (that would misrepresent the user). If the owner
    #    hasn't connected Gmail, we skip and surface a "connect Gmail" hint.
    lead_email = (log_data.get('lead_email') or '').strip()
    if lead_email and '@' in lead_email:
        try:
            via, sent = _send_followup_email(uid, lead_email, log_data)
            if via == "none":
                actions.append({"type": "email", "status": "failed",
                                "label": "Follow-up email not sent — connect Gmail",
                                "detail": "Connect your Gmail under Integrations to auto-email leads from your own address."})
            else:
                actions.append({"type": "email",
                                "label": f"Follow-up email to {lead_email} (from your Gmail)",
                                "status": "ok" if sent else "failed",
                                "detail": summary[:140]})
        except Exception as e:
            print(f"[Integrations] follow-up email failed: {e}")

    return actions


def _followup_email_html(log_data):
    """Clean, UN-branded follow-up email body. It's sent from the dashboard
    user's own Gmail to their lead, so it must NOT carry Kautilya/RevealIQ
    branding or footers — it should read like the user wrote it."""
    name = (log_data.get('lead_name') or '').split(' ')[0] or 'there'
    summary = (log_data.get('summary') or 'It was great speaking with you.')
    return f"""<!doctype html><html><body style="margin:0;background:#f6f7f9;">
<div style="max-width:560px;margin:24px auto;padding:24px;background:#fff;border:1px solid #e6e8eb;border-radius:12px;font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;color:#1a1a1a;">
  <p style="font-size:16px;margin:0 0 14px;">Hi {name},</p>
  <p style="font-size:15px;line-height:1.6;margin:0 0 14px;">Thanks for your time on the call today. Here's a quick recap:</p>
  <p style="font-size:15px;line-height:1.6;margin:0 0 18px;color:#333;">{summary}</p>
  <p style="font-size:15px;line-height:1.6;margin:0;">If anything's unclear or you'd like to take the next step, just reply to this email — happy to help.</p>
</div></body></html>"""


def _send_followup_email(uid, to_email, log_data):
    """Send the post-call follow-up FROM the owner's own connected Gmail account.
    No Resend/Kautilya fallback — multi-tenant users must email from their own
    address. Returns (channel, ok): 'Gmail' if connected, else 'none'."""
    from services.integration_tools import execute_tool, _is_connected
    if not _is_connected(uid, 'gmail'):
        return "none", False
    res = execute_tool(uid, "send_gmail", {
        "to": to_email,
        "subject": "Following up on our call",
        "body": _followup_email_html(log_data),
    })
    if (res or {}).get("ok"):
        return "Gmail", True
    print(f"[Integrations] Gmail send failed ({(res or {}).get('error')})")
    return "Gmail", False


def _find_clash_free_slot(uid, start, duration_minutes, tz="Asia/Kolkata"):
    """Return (start, end, shifted) for a follow-up that doesn't overlap any
    existing calendar event. Queries Google's freeBusy API and, if the desired
    slot is busy, advances by the slot length (keeping it inside 09:00–19:00
    local working hours) until a free window is found. This is what stops the
    agent from booking the same time with many different people.

    Soft-fail: on any error it returns the original slot so we still book
    something rather than dropping the follow-up."""
    from datetime import timedelta
    import requests
    end = start + timedelta(minutes=duration_minutes)
    try:
        from services.integration_tools import _get_valid_google_token
        token = _get_valid_google_token(uid, 'google_calendar')
    except Exception:
        return start, end, False

    def _busy(s, e):
        try:
            r = requests.post(
                "https://www.googleapis.com/calendar/v3/freeBusy",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json={"timeMin": s.isoformat(), "timeMax": e.isoformat(),
                      "timeZone": tz, "items": [{"id": "primary"}]},
                timeout=12)
            if not r.ok:
                return False  # can't tell → treat as free
            cals = (r.json() or {}).get("calendars", {})
            return bool(cals.get("primary", {}).get("busy"))
        except Exception:
            return False

    shifted = False
    for _ in range(12):  # cap the search
        # Keep follow-ups inside working hours; otherwise jump to 09:00 next day.
        if start.hour < 9:
            start = start.replace(hour=9, minute=0, second=0, microsecond=0)
            end = start + timedelta(minutes=duration_minutes)
            shifted = True
        if end.hour >= 19 or (end.hour == 19 and end.minute > 0):
            start = (start + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
            end = start + timedelta(minutes=duration_minutes)
            shifted = True
        if not _busy(start, end):
            return start, end, shifted
        start = end
        end = start + timedelta(minutes=duration_minutes)
        shifted = True
    return start, end, shifted
