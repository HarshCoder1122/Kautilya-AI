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
import requests
from firebase_admin import firestore as _firestore


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


def dial_outbound(uid, agent_id, agent, telephony_config, to_number, base_url, db=None):
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
    """
    provider = (agent.get('telephony_provider') or 'exotel').lower()
    base_url = (base_url or '').rstrip('/').replace('http://', 'https://')
    if not base_url:
        return {"ok": False, "error": "base_url required for callbacks"}

    if provider == 'vobiz':
        return _dial_vobiz(uid, agent_id, telephony_config, to_number, base_url, db)
    return _dial_exotel(uid, agent_id, telephony_config, to_number, base_url, db)


def _dial_vobiz(uid, agent_id, config, to_number, base_url, db):
    auth_id = config.get('auth_id') or config.get('trunk_id')
    auth_token = config.get('auth_token')
    virtual_number = config.get('number')
    if not all([auth_id, auth_token, virtual_number]):
        return {"ok": False, "error": "Vobiz credentials incomplete"}

    answer_url = f"{base_url}/api/webhooks/vobiz/answer/{agent_id}"
    status_url = f"{base_url}/api/webhooks/vobiz/events"
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
    sid = config.get('sid')
    api_key = config.get('api_key')
    token = config.get('token_val') or config.get('token')
    subdomain = config.get('exotel_subdomain', 'api.exotel.com')
    virtual_number = config.get('exotel_number') or config.get('number')
    if not all([sid, api_key, token, virtual_number]):
        return {"ok": False, "error": "Exotel credentials incomplete"}

    callback_url = f"{base_url}/api/webhooks/exotel/answer/{agent_id}"
    status_url = f"{base_url}/api/webhooks/exotel/events"
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
