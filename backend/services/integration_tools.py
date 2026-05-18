"""
Kautilya AI — Integration Tool Registry
Single source of truth for LLM-callable integration tools, shared by
chat agent (agent_loop_service) and voice agent (livekit_agent).

Each tool exposes:
  - spec: OpenAI tool-spec dict for tool_calls
  - provider: which integration must be connected for it to appear
  - handler(uid, args) -> dict: executes the action

`available_tools(uid)` returns only the tools whose provider is connected
for that user — so a user without Slack never sees post_slack as an option,
keeping the LLM's tool list short and accurate.

`execute_tool(uid, name, args)` dispatches by name. All handlers are sync
HTTP — voice-agent callers must wrap in asyncio.to_thread().
"""
from __future__ import annotations
import json
import time
from typing import Dict, List, Any, Optional

import requests


def _get_cfg(uid: str, provider: str) -> Optional[Dict[str, Any]]:
    from extensions import db
    if not db or not uid:
        return None
    try:
        doc = db.collection('users').document(uid).collection('integrations').document(provider).get()
        return doc.to_dict() if doc.exists else None
    except Exception:
        return None


def _is_connected(uid: str, provider: str) -> bool:
    cfg = _get_cfg(uid, provider) or {}
    return bool(cfg.get('access_token') or cfg.get('api_key') or cfg.get('webhook_url'))


# ---------- Handlers ----------
def _send_whatsapp(uid, args):
    cfg = _get_cfg(uid, 'whatsapp') or {}
    if not cfg.get('access_token') or not cfg.get('phone_number_id'):
        return {"ok": False, "error": "WhatsApp not configured"}
    r = requests.post(
        f"https://graph.facebook.com/v20.0/{cfg['phone_number_id']}/messages",
        headers={"Authorization": f"Bearer {cfg['access_token']}", "Content-Type": "application/json"},
        json={"messaging_product": "whatsapp", "to": args["to"],
              "type": "text", "text": {"body": args["message"]}},
        timeout=15,
    )
    return {"ok": r.ok, "status": r.status_code, "body": (r.json() if r.headers.get('content-type','').startswith('application/json') else r.text)[:500]}


def _post_slack(uid, args):
    cfg = _get_cfg(uid, 'slack') or {}
    if not cfg.get('webhook_url'):
        return {"ok": False, "error": "Slack not configured"}
    body = {"text": args["message"]}
    if cfg.get('default_channel'):
        body["channel"] = cfg['default_channel']
    r = requests.post(cfg['webhook_url'], json=body, timeout=10)
    return {"ok": r.ok, "status": r.status_code}


def _create_calendar_event(uid, args):
    cfg = _get_cfg(uid, 'google_calendar') or {}
    if not cfg.get('access_token'):
        return {"ok": False, "error": "Google Calendar not connected"}
    body = {
        "summary": args["title"],
        "description": args.get("description", ""),
        "start": {"dateTime": args["start"], "timeZone": args.get("tz", "Asia/Kolkata")},
        "end":   {"dateTime": args["end"],   "timeZone": args.get("tz", "Asia/Kolkata")},
        "attendees": [{"email": e} for e in (args.get("attendees") or []) if '@' in e],
    }
    r = requests.post(
        "https://www.googleapis.com/calendar/v3/calendars/primary/events",
        headers={"Authorization": f"Bearer {cfg['access_token']}", "Content-Type": "application/json"},
        json=body, timeout=15,
    )
    return {"ok": r.ok, "status": r.status_code, "event_id": (r.json().get('id') if r.ok else None)}


def _trigger_zapier(uid, args):
    cfg = _get_cfg(uid, 'zapier') or {}
    hook = args.get("hook_url") or cfg.get('webhook_url')
    if not hook:
        return {"ok": False, "error": "Zapier hook not configured"}
    r = requests.post(hook, json=args.get("payload") or {}, timeout=10)
    return {"ok": r.ok, "status": r.status_code}


def _lookup_crm_contact(uid, args):
    """Search HubSpot first, then Zoho. Returns first match."""
    phone = (args.get("phone") or "").lstrip('+').strip()
    email = (args.get("email") or "").strip().lower()
    if not phone and not email:
        return {"ok": False, "error": "phone or email required"}

    # HubSpot
    cfg = _get_cfg(uid, 'hubspot') or {}
    if cfg.get('access_token'):
        try:
            q = email or phone
            r = requests.post(
                "https://api.hubapi.com/crm/v3/objects/contacts/search",
                headers={"Authorization": f"Bearer {cfg['access_token']}", "Content-Type": "application/json"},
                json={"query": q, "limit": 1, "properties": ["firstname","lastname","email","phone","company","jobtitle","lifecyclestage"]},
                timeout=10,
            )
            if r.ok and r.json().get('results'):
                p = r.json()['results'][0].get('properties', {})
                return {"ok": True, "source": "hubspot", "contact": p}
        except Exception as e:
            print(f"[integration_tools] HubSpot lookup error: {e}")

    # Zoho
    cfg = _get_cfg(uid, 'zoho') or {}
    if cfg.get('access_token'):
        try:
            crit = f"(Email:equals:{email})" if email else f"(Phone:equals:{phone})"
            r = requests.get(
                f"https://www.zohoapis.in/crm/v2/Contacts/search?criteria={crit}",
                headers={"Authorization": f"Zoho-oauthtoken {cfg['access_token']}"},
                timeout=10,
            )
            if r.ok and r.json().get('data'):
                return {"ok": True, "source": "zoho", "contact": r.json()['data'][0]}
        except Exception as e:
            print(f"[integration_tools] Zoho lookup error: {e}")

    return {"ok": False, "error": "not found"}


def _create_or_update_crm_contact(uid, args):
    """Create the contact if not found, otherwise patch fields (name/email/company).
    Lookup key: phone OR email — must supply at least one. Returns contact_id."""
    phone = (args.get("phone") or "").lstrip('+').strip()
    email = (args.get("email") or "").strip().lower()
    if not phone and not email:
        return {"ok": False, "error": "phone or email required as lookup key"}

    first = (args.get("first_name") or args.get("name") or "").strip()
    last  = (args.get("last_name") or "").strip()
    company = (args.get("company") or "").strip()
    title = (args.get("title") or "").strip()
    notes = (args.get("notes") or "").strip()

    # HubSpot
    cfg = _get_cfg(uid, 'hubspot') or {}
    if cfg.get('access_token'):
        try:
            existing = _lookup_crm_contact(uid, {"phone": phone, "email": email})
            props = {}
            if first: props["firstname"] = first
            if last:  props["lastname"] = last
            if email: props["email"] = email
            if phone: props["phone"] = phone
            if company: props["company"] = company
            if title: props["jobtitle"] = title

            if existing.get("ok") and existing.get("source") == "hubspot":
                cid = existing["contact"].get("vid") or existing["contact"].get("id")
                r = requests.patch(
                    f"https://api.hubapi.com/crm/v3/objects/contacts/{cid}",
                    headers={"Authorization": f"Bearer {cfg['access_token']}", "Content-Type": "application/json"},
                    json={"properties": props}, timeout=10)
                created = False
            else:
                r = requests.post(
                    "https://api.hubapi.com/crm/v3/objects/contacts",
                    headers={"Authorization": f"Bearer {cfg['access_token']}", "Content-Type": "application/json"},
                    json={"properties": props}, timeout=10)
                cid = r.json().get('id') if r.ok else None
                created = True
            out = {"ok": r.ok, "source": "hubspot", "contact_id": str(cid) if cid else None, "created": created, "status": r.status_code}
            if notes and cid and r.ok:
                _log_crm_activity(uid, {"contact_id": str(cid), "note": notes, "source": "hubspot"})
            return out
        except Exception as e:
            print(f"[integration_tools] HubSpot upsert error: {e}")

    # Zoho fallback
    cfg = _get_cfg(uid, 'zoho') or {}
    if cfg.get('access_token'):
        try:
            record = {}
            if first: record["First_Name"] = first
            if last:  record["Last_Name"] = last or first or "Unknown"
            if email: record["Email"] = email
            if phone: record["Phone"] = phone
            if company: record["Account_Name"] = company
            if title: record["Title"] = title
            r = requests.post(
                "https://www.zohoapis.in/crm/v2/Contacts/upsert",
                headers={"Authorization": f"Zoho-oauthtoken {cfg['access_token']}", "Content-Type": "application/json"},
                json={"data": [record], "duplicate_check_fields": ["Email" if email else "Phone"]},
                timeout=10,
            )
            data = r.json() if r.ok else {}
            cid = (data.get('data') or [{}])[0].get('details', {}).get('id')
            return {"ok": r.ok, "source": "zoho", "contact_id": str(cid) if cid else None, "status": r.status_code}
        except Exception as e:
            print(f"[integration_tools] Zoho upsert error: {e}")

    return {"ok": False, "error": "no CRM connected"}


def _log_crm_activity(uid, args):
    """Append a call/activity note to the contact's CRM record."""
    contact_id = args.get("contact_id")
    note = args.get("note") or ""
    if not contact_id or not note:
        return {"ok": False, "error": "contact_id and note required"}
    source = (args.get("source") or "hubspot").lower()
    if source == "hubspot":
        cfg = _get_cfg(uid, 'hubspot') or {}
        if not cfg.get('access_token'):
            return {"ok": False, "error": "HubSpot not connected"}
        r = requests.post(
            "https://api.hubapi.com/crm/v3/objects/notes",
            headers={"Authorization": f"Bearer {cfg['access_token']}", "Content-Type": "application/json"},
            json={"properties": {"hs_note_body": note, "hs_timestamp": int(time.time()*1000)},
                  "associations": [{"to": {"id": contact_id}, "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 202}]}]},
            timeout=10,
        )
        return {"ok": r.ok, "status": r.status_code}
    return {"ok": False, "error": f"source {source} not supported yet"}


# ---------- Registry ----------
# Each entry: name → {provider, spec (OpenAI tool format), handler}
REGISTRY: Dict[str, Dict[str, Any]] = {
    "send_whatsapp": {
        "provider": "whatsapp",
        "handler": _send_whatsapp,
        "spec": {"type": "function", "function": {
            "name": "send_whatsapp",
            "description": "Send a WhatsApp message via WhatsApp Business API.",
            "parameters": {"type": "object", "required": ["to", "message"], "properties": {
                "to": {"type": "string", "description": "Recipient phone in E.164 (e.g. 919876543210)"},
                "message": {"type": "string", "description": "Text body"}}}}},
    },
    "post_slack": {
        "provider": "slack",
        "handler": _post_slack,
        "spec": {"type": "function", "function": {
            "name": "post_slack",
            "description": "Post a message to the user's configured Slack channel.",
            "parameters": {"type": "object", "required": ["message"], "properties": {
                "message": {"type": "string"}}}}},
    },
    "create_calendar_event": {
        "provider": "google_calendar",
        "handler": _create_calendar_event,
        "spec": {"type": "function", "function": {
            "name": "create_calendar_event",
            "description": "Create a Google Calendar event on the user's primary calendar.",
            "parameters": {"type": "object", "required": ["title", "start", "end"], "properties": {
                "title": {"type": "string"},
                "start": {"type": "string", "description": "RFC3339 datetime"},
                "end":   {"type": "string", "description": "RFC3339 datetime"},
                "description": {"type": "string"},
                "attendees": {"type": "array", "items": {"type": "string", "description": "email"}},
                "tz": {"type": "string", "description": "IANA timezone, defaults to Asia/Kolkata"}}}}},
    },
    "trigger_zapier": {
        "provider": "zapier",
        "handler": _trigger_zapier,
        "spec": {"type": "function", "function": {
            "name": "trigger_zapier",
            "description": "Fire a Zapier webhook with an arbitrary JSON payload.",
            "parameters": {"type": "object", "required": ["payload"], "properties": {
                "hook_url": {"type": "string", "description": "Optional override of saved hook URL"},
                "payload":  {"type": "object"}}}}},
    },
    "lookup_crm_contact": {
        "provider": "hubspot",  # also covered by zoho, but at least one CRM must be connected
        "handler": _lookup_crm_contact,
        "spec": {"type": "function", "function": {
            "name": "lookup_crm_contact",
            "description": "Find a contact in the connected CRM (HubSpot or Zoho) by phone or email.",
            "parameters": {"type": "object", "properties": {
                "phone": {"type": "string"},
                "email": {"type": "string"}}}}},
    },
    "log_crm_activity": {
        "provider": "hubspot",
        "handler": _log_crm_activity,
        "spec": {"type": "function", "function": {
            "name": "log_crm_activity",
            "description": "Add a note/activity to a CRM contact's timeline.",
            "parameters": {"type": "object", "required": ["contact_id", "note"], "properties": {
                "contact_id": {"type": "string"},
                "note": {"type": "string"},
                "source": {"type": "string", "enum": ["hubspot", "zoho"], "default": "hubspot"}}}}},
    },
    "create_or_update_crm_contact": {
        "provider": "hubspot",  # zoho fallback handled inside handler
        "handler": _create_or_update_crm_contact,
        "spec": {"type": "function", "function": {
            "name": "create_or_update_crm_contact",
            "description": "Create a new CRM contact, or patch an existing one matched by phone/email. Returns contact_id you can use with log_crm_activity. Call this AS SOON as you capture name/email/company during a call.",
            "parameters": {"type": "object", "properties": {
                "phone": {"type": "string", "description": "E.164 phone (lookup key)"},
                "email": {"type": "string", "description": "Email (lookup key, preferred over phone for dedup)"},
                "first_name": {"type": "string"},
                "last_name": {"type": "string"},
                "company": {"type": "string"},
                "title": {"type": "string"},
                "notes": {"type": "string", "description": "Optional — also logged as an activity note"}}}}},
    },
}


def available_tools(uid: str) -> List[Dict[str, Any]]:
    """OpenAI-format tool specs for integrations the user has connected.
    `lookup_crm_contact` is offered if EITHER hubspot or zoho is connected."""
    if not uid:
        return []
    out = []
    hubspot_or_zoho = _is_connected(uid, 'hubspot') or _is_connected(uid, 'zoho')
    for name, entry in REGISTRY.items():
        if name in ('lookup_crm_contact', 'log_crm_activity', 'create_or_update_crm_contact'):
            if hubspot_or_zoho: out.append(entry["spec"])
        elif _is_connected(uid, entry["provider"]):
            out.append(entry["spec"])
    return out


def execute_tool(uid: str, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    entry = REGISTRY.get(name)
    if not entry:
        return {"ok": False, "error": f"unknown tool: {name}"}
    try:
        return entry["handler"](uid, args or {})
    except Exception as e:
        return {"ok": False, "error": str(e)}


def tool_names(uid: str) -> List[str]:
    return [s["function"]["name"] for s in available_tools(uid)]
