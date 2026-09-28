"""
Kautilya AI — Telephony Dialer Service

Extracted from `routes/telephony_routes.py` so that both the Flask outbound
endpoint AND the standalone `campaign_worker.py` can call the same code path
without each other's Flask request context.

Public entry point: `dial_outbound(...)` returns a plain dict so the caller
can shape its own HTTP/JSON response.
"""
import os
import json
import uuid
import requests
from urllib.parse import urlencode
from firebase_admin import firestore as _firestore


def _to_e164(num, default_cc="91"):
    """Best-effort E.164 normalisation for the LiveKit→SIP outbound leg.
    Indian-default: bare 10-digit → +91XXXXXXXXXX; 12-digit starting 91 → +91…;
    already-+ → unchanged. Non-India callers can pass a full +<cc> number."""
    s = str(num or "").strip().replace(" ", "").replace("-", "")
    if not s:
        return s
    if s.startswith("+"):
        return s
    s = s.lstrip("0")
    if len(s) == 10:                       # bare local mobile
        return f"+{default_cc}{s}"
    if s.startswith(default_cc) and len(s) >= (len(default_cc) + 10):
        return f"+{s}"
    return f"+{s}"


def _with_secret(url):
    """Append the WEBHOOK_SECRET as a query param when one is configured.

    The provider hits our answer webhook on pickup, and that webhook does a
    constant-time secret check (`webhooks_routes._verify_webhook_secret`). If
    WEBHOOK_SECRET is set on the server but the answer/callback URL we hand the
    provider does NOT carry it, the webhook returns 403 → the provider gets no
    <Dial> instruction → the call cuts the instant the callee answers. Passing
    the secret here keeps the dialer and the webhook in lockstep. When the env
    var is unset the URL is returned unchanged (the webhook skips validation).
    Vobiz/Exotel POST to the answer URL, but Flask's request.values merges the
    query string, so a `?secret=` param is still seen on a POST."""
    secret = (os.environ.get("WEBHOOK_SECRET") or "").strip()
    if not secret:
        return url
    sep = '&' if '?' in url else '?'
    return f"{url}{sep}{urlencode({'secret': secret})}"


def _phone_variants(raw):
    """All reasonable lookup keys for a phone number — must mirror the
    agent's `_phone_variants` so the SIP-side worker hits the same docs."""
    if not raw:
        return []
    s = str(raw).strip()
    no_plus = s.lstrip('+')
    out = []
    for v in (s, no_plus, '+' + no_plus):
        if v and v not in out:
            out.append(v)
    if no_plus.startswith('91') and len(no_plus) >= 12:
        local = no_plus[2:]
        for v in (local, '+91' + local):
            if v not in out:
                out.append(v)
    return out


def _save_active_call_mapping(db, phone_raw, agent_id, call_id):
    """Write the call → agent mapping in two shapes:

    1. `active_calls/<phone>` — legacy lookup key (latest-wins; fine for the
       common case where a phone is in flight on at most one call at a time).
    2. `active_calls/<phone>/pending/<call_id>` — race-safe FIFO subcollection
       so the agent worker can claim the OLDEST unclaimed mapping when two
       calls hit the same phone simultaneously.

    We write every reasonable phone variant so the agent's lookup chain
    matches no matter which form ends up in the SIP room name.
    """
    if not (db and phone_raw and agent_id and call_id):
        return
    payload = {
        "agent_id": agent_id,
        "call_uuid": call_id,
        "created_at": _firestore.SERVER_TIMESTAMP,
        "claimed": False,
    }
    for v in _phone_variants(phone_raw):
        try:
            # Latest-wins document (back-compat for existing lookups).
            db.collection('active_calls').document(v).set({
                "agent_id": agent_id,
                "call_uuid": call_id,
                "created_at": _firestore.SERVER_TIMESTAMP,
            })
            # FIFO pending queue — race-safe per-call entry.
            db.collection('active_calls').document(v) \
              .collection('pending').document(call_id).set(payload)
        except Exception as e:
            print(f"[Dialer] mapping write warning for {v}: {e}")


def dial_outbound(uid, agent_id, agent, telephony_config, to_number, base_url, db=None, provider=None):
    """Place a single outbound call. Returns:
        {"ok": True,  "call_id": "...", "provider": "vobiz|exotel"}
        {"ok": False, "error": "..."}

    Required inputs:
      uid               — Firestore user id (used only for logging)
      agent_id          — agent doc id; baked into mappings & callback URL
      agent             — agent dict (must include `telephony_provider`)
      telephony_config  — provider config dict (sid/token/auth/etc.)
      to_number         — destination phone (E.164 preferred)
      base_url          — public https URL of THIS Flask service for callbacks
      db                — Firestore client (optional; mappings skipped if None)
      provider          — optional explicit provider override

    Provider resolution order: explicit arg → config['type'] → the agent's
    `telephony_provider` → exotel. The config's own type MUST outrank the
    agent setting: the route may have resolved master-Vobiz creds for an
    agent whose doc still says exotel, and routing a Vobiz config to the
    Exotel dialer guarantees "credentials incomplete".
    """
    # ZERO-SILENCE PATH (opt-in via LIVEKIT_OUTBOUND_TRUNK_ID):
    # If a LiveKit outbound SIP trunk is configured, dial the callee NATIVELY
    # through LiveKit instead of the Vobiz HTTP-API → answer-webhook → SIP
    # bridge. LiveKit creates ONE room, the agent is dispatched into it BEFORE
    # the phone is dialed, and the callee lands directly in the agent's room on
    # pickup — no bridge hop, no double-room, no post-pickup silence. If the
    # trunk env is unset (default) or the native dial fails, we fall through to
    # the existing provider bridge so calls keep working.
    if os.environ.get("LIVEKIT_OUTBOUND_TRUNK_ID"):
        native = _dial_livekit_native(uid, agent_id, agent, to_number, db)
        if native is not None and native.get("ok"):
            return native
        if native is not None:
            print(f"[Dialer] LiveKit-native dial failed ({native.get('error')}) — "
                  f"falling back to provider bridge")

    provider = (provider
                or (telephony_config or {}).get('type')
                or agent.get('telephony_provider')
                or 'exotel').lower()
    base_url = (base_url or '').rstrip('/').replace('http://', 'https://')
    if not base_url:
        return {"ok": False, "error": "base_url required for callbacks"}

    if provider == 'vobiz':
        return _dial_vobiz(uid, agent_id, telephony_config, to_number, base_url, db)
    return _dial_exotel(uid, agent_id, telephony_config, to_number, base_url, db)


def _dial_livekit_native(uid, agent_id, agent, to_number, db=None):
    """Dial the callee via LiveKit's outbound SIP trunk so the agent is already
    in the room at pickup (zero silence, single room).

    Flow: create room (with agent config in metadata) → dispatch the agent
    (explicit dispatch if LIVEKIT_AGENT_NAME is set, else auto) → ask LiveKit
    to dial the callee INTO that room via the outbound trunk.

    Returns {"ok": True, "provider": "livekit", "call_id": room} on success,
    {"ok": False, "error": ...} on failure, or None if not configured.
    """
    import asyncio
    trunk_id = (os.environ.get("LIVEKIT_OUTBOUND_TRUNK_ID") or "").strip()
    if not trunk_id:
        return None

    lk_url = (os.environ.get("LIVEKIT_URL") or "").strip()
    api_key = (os.environ.get("LIVEKIT_API_KEY") or "").strip()
    api_secret = (os.environ.get("LIVEKIT_API_SECRET") or "").strip()
    if not all([lk_url, api_key, api_secret]):
        return {"ok": False, "error": "LIVEKIT_URL/API_KEY/API_SECRET not set"}

    # LiveKit → Vobiz SIP termination needs an E.164 destination. A bare
    # 10-digit Indian number (what the dashboard sends) is rejected by the
    # trunk, so the PSTN leg never rings even though CreateSIPParticipant
    # returns OK. Normalise to +<cc><number> before dialing.
    dial_to = _to_e164(to_number)

    agent_name = (os.environ.get("LIVEKIT_AGENT_NAME") or "").strip()
    room_name = f"voice-{agent_id}--{uuid.uuid4().hex[:12]}"

    # Bake the agent config into room metadata so the worker's fast-path skips
    # the per-call Firestore lookup chain (mirrors webhooks_routes._build_room_metadata).
    metadata = {"source": "livekit_outbound", "agent_id": agent_id, "uid": uid,
                "to_number": to_number}
    a = agent or {}
    for k_meta, k_src, default in (
        ("system_prompt", "system_prompt", ""),
        ("welcome_message", "welcome_message", ""),
        ("language", "language", "hi-IN"),
        ("model", "model", "kautilya-daily"),
        ("voice", "voice", "shubh"),
    ):
        metadata[k_meta] = a.get(k_src, default)

    async def _go():
        from livekit.api import (LiveKitAPI, CreateRoomRequest,
                                 CreateSIPParticipantRequest)
        http_url = lk_url.replace("wss://", "https://").replace("ws://", "http://")
        lk = LiveKitAPI(url=http_url, api_key=api_key, api_secret=api_secret)
        try:
            await lk.room.create_room(CreateRoomRequest(
                name=room_name, empty_timeout=120, metadata=json.dumps(metadata)))
            if agent_name:
                from livekit.api import CreateAgentDispatchRequest
                await lk.agent_dispatch.create_dispatch(CreateAgentDispatchRequest(
                    agent_name=agent_name, room=room_name,
                    metadata=json.dumps(metadata)))
            # Dial the callee straight into the agent's room.
            await lk.sip.create_sip_participant(CreateSIPParticipantRequest(
                sip_trunk_id=trunk_id,
                sip_call_to=dial_to,
                room_name=room_name,
                participant_identity=f"sip-{dial_to}",
                participant_name="Customer",
                wait_until_answered=False,
            ))
        finally:
            await lk.aclose()

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_go())
        finally:
            loop.close()
        # Map the room as the call so post-call analytics can find the agent.
        if db:
            try:
                db.collection('call_mappings').document(room_name).set({
                    "agent_id": agent_id, "uid": uid, "to_number": to_number,
                    "created_at": _firestore.SERVER_TIMESTAMP,
                })
            except Exception:
                pass
        print(f"[Dialer] ✅ LiveKit-native outbound: dialing {dial_to} "
              f"(trunk {trunk_id}) -> room {room_name}")
        return {"ok": True, "provider": "livekit", "call_id": room_name}
    except Exception as e:
        return {"ok": False, "error": f"LiveKit native dial failed: {e}"}


def _dial_vobiz(uid, agent_id, config, to_number, base_url, db):
    # Accept every key shape in circulation: master config uses
    # username/password/caller_id, legacy saved configs use
    # auth_id/auth_token/number, trunk-style uses trunk_id.
    auth_id = config.get('username') or config.get('auth_id') or config.get('trunk_id')
    auth_token = config.get('password') or config.get('auth_token')
    virtual_number = config.get('caller_id') or config.get('number')
    if not all([auth_id, auth_token, virtual_number]):
        return {"ok": False, "error": "Vobiz credentials incomplete"}

    answer_url = _with_secret(f"{base_url}/api/webhooks/vobiz/answer/{agent_id}")
    status_url = _with_secret(f"{base_url}/api/webhooks/vobiz/events")
    url = f"https://api.vobiz.ai/api/v1/Account/{auth_id}/Call/"
    headers = {
        "X-Auth-ID": auth_id,
        "X-Auth-Token": auth_token,
        "Content-Type": "application/json",
    }
    payload = {
        "from": virtual_number,
        "to": to_number,
        "answer_url": answer_url,
        "answer_method": "POST",
        "status_url": status_url,
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=15)
        if resp.status_code not in (200, 201):
            return {"ok": False, "error": f"Vobiz API {resp.status_code}: {resp.text[:200]}"}
        data = resp.json()
        call_id = data.get('api_id') or data.get('call_uuid') or data.get('request_uuid')

        # Persist ONLY the call ID mapping so that when Vobiz hits the answer webhook,
        # we can look up which agent_id this call belongs to.
        # We intentionally do NOT write to active_calls/<phone> here, because that would 
        # prematurely trigger the agent worker before the SIP room is actually created.
        if db and call_id:
            try:
                db.collection('call_mappings').document(call_id).set({
                    "agent_id": agent_id,
                    "uid": uid,
                    "to_number": to_number,
                    "created_at": _firestore.SERVER_TIMESTAMP,
                })
            except Exception as e:
                print(f"[Dialer] call_mappings write warning: {e}")

        return {"ok": True, "provider": "vobiz", "call_id": call_id}
    except Exception as e:
        return {"ok": False, "error": f"Vobiz request failed: {e}"}


def _dial_exotel(uid, agent_id, config, to_number, base_url, db):
    # Accept both the new dashboard's keys (account_sid/api_token/caller_id)
    # and the legacy ones (sid/token_val/exotel_number).
    sid = config.get('account_sid') or config.get('sid')
    api_key = config.get('api_key')
    token = config.get('api_token') or config.get('token_val') or config.get('token')
    subdomain = config.get('exotel_subdomain', 'api.exotel.com')
    virtual_number = config.get('caller_id') or config.get('exotel_number') or config.get('number')
    if not all([sid, api_key, token, virtual_number]):
        return {"ok": False, "error": "Exotel credentials incomplete"}

    callback_url = _with_secret(f"{base_url}/api/webhooks/exotel/answer/{agent_id}")
    status_url = _with_secret(f"{base_url}/api/webhooks/exotel/events")
    url = f"https://{subdomain}/v1/Accounts/{sid}/Calls/connect.json"
    payload = {
        'From': to_number,
        'CallerId': virtual_number,
        'Url': callback_url,
        'StatusCallback': status_url,
    }
    try:
        resp = requests.post(url, data=payload, auth=(api_key, token), timeout=15)
        if resp.status_code not in (200, 201):
            return {"ok": False, "error": f"Exotel API {resp.status_code}: {resp.text[:200]}"}
        call_sid = resp.json().get('Call', {}).get('Sid')
        _save_active_call_mapping(db, to_number, agent_id, call_sid or '')
        if db and call_sid:
            try:
                db.collection('call_mappings').document(call_sid).set({
                    "agent_id": agent_id,
                    "uid": uid,
                    "to_number": to_number,
                    "created_at": _firestore.SERVER_TIMESTAMP,
                })
            except Exception:
                pass
        return {"ok": True, "provider": "exotel", "call_id": call_sid}
    except Exception as e:
        return {"ok": False, "error": f"Exotel request failed: {e}"}


def load_provider_config(db, uid, provider_type):
    """Read the user's saved telephony provider config. Returns the
    matching provider dict or None."""
    if not db:
        return None
    try:
        doc = db.collection('users').document(uid).collection('config').document('telephony').get()
        if not doc.exists:
            return None
        for p in (doc.to_dict() or {}).get('providers', []):
            if (p.get('type') or '').lower() == provider_type.lower():
                return p
    except Exception as e:
        print(f"[Dialer] provider config load failed for {uid}: {e}")
    return None
