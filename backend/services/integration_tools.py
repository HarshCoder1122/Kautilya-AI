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


def _refresh_google_oauth_token(uid: str, provider: str) -> Dict[str, Any]:
    cfg = _get_cfg(uid, provider) or {}
    refresh_token = cfg.get("refresh_token")
    client_id = cfg.get("client_id")
    client_secret = cfg.get("client_secret")
    if not refresh_token or not client_id or not client_secret:
        raise Exception(f"{provider} not connected or missing refresh credentials")

    r = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
        },
        timeout=15,
    )
    if not r.ok:
        raise Exception(f"{provider} token refresh failed: {r.text[:200]}")

    data = r.json()
    access_token = data.get("access_token")
    if not access_token:
        raise Exception(f"{provider} refresh returned no access_token")

    from extensions import db
    db.collection('users').document(uid).collection('integrations').document(provider).set({
        "access_token": access_token,
        "obtained_at": int(time.time()),
        "expires_in": data.get("expires_in", 3600),
    }, merge=True)
    cfg["access_token"] = access_token
    cfg["obtained_at"] = int(time.time())
    cfg["expires_in"] = data.get("expires_in", 3600)
    return cfg


_GOOGLE_API_LABELS = {
    "docs.googleapis.com": "Google Docs API",
    "sheets.googleapis.com": "Google Sheets API",
    "drive.googleapis.com": "Google Drive API",
    "calendar-json.googleapis.com": "Google Calendar API",
    "gmail.googleapis.com": "Gmail API",
    "people.googleapis.com": "People (Contacts) API",
    "youtube.googleapis.com": "YouTube Data API",
    "tasks.googleapis.com": "Google Tasks API",
}


def _google_api_error(resp) -> Optional[Dict[str, Any]]:
    """If a Google API response is a `SERVICE_DISABLED` 403, return a dict
    the frontend can render as a one-click "Enable API" prompt. Otherwise
    return None and let the caller surface the generic error.

    We can't enable APIs on the user's behalf (only the project owner can in
    their own Cloud Console), but Google's error payload includes the exact
    deeplink that takes them straight to the Enable button — we just need
    to lift it out and present it nicely instead of dumping raw JSON.
    """
    if resp.status_code != 403:
        return None
    try:
        body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
    except Exception:
        return None
    err = (body or {}).get("error") or {}
    if err.get("status") != "PERMISSION_DENIED":
        return None
    details = err.get("details") or []
    service = None
    project = None
    for d in details:
        if d.get("reason") == "SERVICE_DISABLED":
            meta = d.get("metadata") or {}
            service = meta.get("service")
            consumer = meta.get("consumer") or ""
            if consumer.startswith("projects/"):
                project = consumer.split("/", 1)[1]
            break
    if not service:
        # Fall back to scraping the URL out of the message text.
        msg = err.get("message") or ""
        import re as _re
        m = _re.search(r"https://console\.developers\.google\.com/apis/api/([^/]+)/overview\?project=(\d+)", msg)
        if m:
            service = m.group(1)
            project = m.group(2)
    if not service:
        return None
    api_label = _GOOGLE_API_LABELS.get(service, service)
    enable_url = f"https://console.developers.google.com/apis/api/{service}/overview"
    if project:
        enable_url += f"?project={project}"
    return {
        "ok": False,
        "error_kind": "google_api_disabled",
        "service": service,
        "api_label": api_label,
        "enable_url": enable_url,
        "error": (
            f"{api_label} is not enabled on your Google Cloud project yet. "
            f"Open this link to enable it (one click, then wait ~30s and retry): {enable_url}"
        ),
    }


def _get_valid_google_token(uid: str, provider: str) -> str:
    cfg = _get_cfg(uid, provider) or {}
    access_token = cfg.get("access_token")
    if not access_token:
        raise Exception(f"{provider} not connected")

    obtained_at = int(cfg.get("obtained_at") or 0)
    expires_in = int(cfg.get("expires_in") or 3600)
    if time.time() > obtained_at + expires_in - 300:
        try:
            cfg = _refresh_google_oauth_token(uid, provider)
            access_token = cfg.get("access_token") or access_token
        except Exception:
            pass
    return access_token


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
    try:
        token = _get_valid_google_token(uid, 'google_calendar')
    except Exception as e:
        return {"ok": False, "error": str(e)}
    
    body = {
        "summary": args["title"],
        "description": args.get("description", ""),
        "start": {"dateTime": args["start"], "timeZone": args.get("tz", "Asia/Kolkata")},
        "end":   {"dateTime": args["end"],   "timeZone": args.get("tz", "Asia/Kolkata")},
        "attendees": [{"email": e} for e in (args.get("attendees") or []) if '@' in e],
    }

    url = "https://www.googleapis.com/calendar/v3/calendars/primary/events"
    params = {}
    
    if args.get("create_meet_link"):
        params["conferenceDataVersion"] = 1
        body["conferenceData"] = {
            "createRequest": {
                "requestId": f"meet_{int(time.time())}",
                "conferenceSolutionKey": {"type": "eventHangout"}
            }
        }

    r = requests.post(
        url,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        params=params,
        json=body,
        timeout=15,
    )
    if not r.ok:
        return _google_api_error(r) or {"ok": False, "status": r.status_code, "error": r.text[:300]}

    res = r.json()
    return {
        "ok": True,
        "status": r.status_code,
        "event_id": res.get("id"),
        "meet_link": res.get("hangoutLink")
    }


def _append_sheet_row(uid, args):
    try:
        token = _get_valid_google_token(uid, 'google_sheets')
    except Exception as e:
        return {"ok": False, "error": str(e)}

    spreadsheet_id = (args.get("spreadsheet_id") or "").strip()
    if not spreadsheet_id:
        return {"ok": False, "error": "spreadsheet_id is required"}

    values = args.get("values")
    if not isinstance(values, list):
        return {"ok": False, "error": "values must be a list of cell values"}

    sheet_name = (args.get("sheet_name") or "Sheet1").strip()
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/{sheet_name}:append"
    params = {
        "valueInputOption": "USER_ENTERED",
        "insertDataOption": "INSERT_ROWS"
    }
    body = {
        "values": [values]
    }
    r = requests.post(
        url,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        params=params,
        json=body,
        timeout=15,
    )
    if not r.ok:
        return _google_api_error(r) or {"ok": False, "status": r.status_code, "error": r.text[:300]}
    
    return {"ok": True, "status": r.status_code, "response": r.json()}


def _create_google_task(uid, args):
    try:
        token = _get_valid_google_token(uid, 'google_tasks')
    except Exception as e:
        return {"ok": False, "error": str(e)}

    title = (args.get("title") or "").strip()
    if not title:
        return {"ok": False, "error": "title is required"}

    notes = args.get("notes") or ""
    due = args.get("due")

    body = {
        "title": title,
    }
    if notes:
        body["notes"] = notes
    if due:
        body["due"] = due

    r = requests.post(
        "https://tasks.googleapis.com/v1/users/@default/lists/@default/tasks",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=body,
        timeout=15,
    )
    if not r.ok:
        return _google_api_error(r) or {"ok": False, "status": r.status_code, "error": r.text[:300]}

    data = r.json()
    return {"ok": True, "status": r.status_code, "task_id": data.get("id"), "self_link": data.get("selfLink")}


def _list_drive_files(uid, args):
    try:
        token = _get_valid_google_token(uid, 'google_drive')
    except Exception as e:
        return {"ok": False, "error": str(e)}

    query = (args.get("query") or "").strip()
    page_size = max(1, min(int(args.get("page_size") or 10), 50))
    params = {
        "pageSize": page_size,
        "fields": "files(id,name,mimeType,modifiedTime,webViewLink,iconLink,size),nextPageToken",
        "orderBy": "modifiedTime desc",
        "supportsAllDrives": "true",
        "includeItemsFromAllDrives": "true",
    }
    if query:
        safe_query = query.replace("'", "\\'")
        params["q"] = f"name contains '{safe_query}' and trashed = false"
    else:
        params["q"] = "trashed = false"

    r = requests.get(
        "https://www.googleapis.com/drive/v3/files",
        headers={"Authorization": f"Bearer {token}"},
        params=params,
        timeout=20,
    )
    if not r.ok:
        return _google_api_error(r) or {"ok": False, "status": r.status_code, "error": r.text[:300]}
    data = r.json()
    return {"ok": True, "files": data.get("files", []), "next_page_token": data.get("nextPageToken")}


def _read_drive_file(uid, args):
    try:
        token = _get_valid_google_token(uid, 'google_drive')
    except Exception as e:
        return {"ok": False, "error": str(e)}

    file_id = (args.get("file_id") or "").strip()
    if not file_id:
        return {"ok": False, "error": "file_id is required"}

    meta = requests.get(
        f"https://www.googleapis.com/drive/v3/files/{file_id}",
        headers={"Authorization": f"Bearer {token}"},
        params={
            "fields": "id,name,mimeType,modifiedTime,webViewLink,webContentLink,size,exportLinks",
            "supportsAllDrives": "true",
        },
        timeout=20,
    )
    if not meta.ok:
        return _google_api_error(meta) or {"ok": False, "status": meta.status_code, "error": meta.text[:300]}

    info = meta.json()
    return {"ok": True, "file": info}


def _create_google_doc(uid, args):
    try:
        token = _get_valid_google_token(uid, 'google_docs')
    except Exception as e:
        return {"ok": False, "error": str(e)}
    title = (args.get("title") or "Untitled Document").strip()
    content = args.get("content") or ""
    r = requests.post(
        "https://docs.googleapis.com/v1/documents",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"title": title},
        timeout=15,
    )
    if not r.ok:
        return _google_api_error(r) or {"ok": False, "status": r.status_code, "error": r.text[:300]}
    doc = r.json()
    doc_id = doc.get("documentId")
    insert_warning = None
    inserted_chars = 0
    if content and doc_id:
        try:
            ins = requests.post(
                f"https://docs.googleapis.com/v1/documents/{doc_id}:batchUpdate",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json={"requests": [{"insertText": {"location": {"index": 1}, "text": content}}]},
                timeout=30,
            )
            if ins.ok:
                inserted_chars = len(content)
            else:
                err = _google_api_error(ins) or {}
                insert_warning = err.get("error") or f"insertText failed: HTTP {ins.status_code} {ins.text[:200]}"
        except Exception as e:
            insert_warning = f"insertText failed: {e}"
    return {
        "ok": True,
        "document_id": doc_id,
        "title": title,
        "inserted_chars": inserted_chars,
        "insert_warning": insert_warning,
        "url": f"https://docs.google.com/document/d/{doc_id}/edit" if doc_id else None,
    }


def _read_google_doc(uid, args):
    try:
        token = _get_valid_google_token(uid, 'google_docs')
    except Exception as e:
        return {"ok": False, "error": str(e)}
    doc_id = (args.get("document_id") or "").strip()
    if not doc_id:
        return {"ok": False, "error": "document_id is required"}
    r = requests.get(
        f"https://docs.googleapis.com/v1/documents/{doc_id}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=20,
    )
    if not r.ok:
        return _google_api_error(r) or {"ok": False, "status": r.status_code, "error": r.text[:300]}
    data = r.json()
    text_parts = []
    for element in (data.get("body", {}).get("content") or []):
        para = element.get("paragraph")
        if not para:
            continue
        for el in (para.get("elements") or []):
            tr = (el.get("textRun") or {}).get("content")
            if tr:
                text_parts.append(tr)
    return {
        "ok": True,
        "title": data.get("title"),
        "document_id": doc_id,
        "text": "".join(text_parts)[:20000],
        "url": f"https://docs.google.com/document/d/{doc_id}/edit",
    }


def _append_google_doc(uid, args):
    try:
        token = _get_valid_google_token(uid, 'google_docs')
    except Exception as e:
        return {"ok": False, "error": str(e)}
    doc_id = (args.get("document_id") or "").strip()
    text = args.get("text") or ""
    if not doc_id or not text:
        return {"ok": False, "error": "document_id and text are required"}
    # Fetch end index then insert at end
    meta = requests.get(
        f"https://docs.googleapis.com/v1/documents/{doc_id}",
        headers={"Authorization": f"Bearer {token}"},
        params={"fields": "body(content(endIndex))"},
        timeout=15,
    )
    if not meta.ok:
        return _google_api_error(meta) or {"ok": False, "status": meta.status_code, "error": meta.text[:300]}
    contents = meta.json().get("body", {}).get("content") or []
    end_index = 1
    for c in contents:
        if c.get("endIndex"):
            end_index = max(end_index, c["endIndex"])
    insert_at = max(1, end_index - 1)
    r = requests.post(
        f"https://docs.googleapis.com/v1/documents/{doc_id}:batchUpdate",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"requests": [{"insertText": {"location": {"index": insert_at}, "text": text}}]},
        timeout=15,
    )
    if not r.ok:
        return _google_api_error(r) or {"ok": False, "status": r.status_code, "error": r.text[:300]}
    return {"ok": True, "document_id": doc_id, "appended_chars": len(text)}


def _search_youtube(uid, args):
    try:
        token = _get_valid_google_token(uid, 'youtube')
    except Exception as e:
        return {"ok": False, "error": str(e)}
    q = (args.get("query") or "").strip()
    if not q:
        return {"ok": False, "error": "query is required"}
    max_results = max(1, min(int(args.get("max_results") or 8), 25))
    r = requests.get(
        "https://www.googleapis.com/youtube/v3/search",
        headers={"Authorization": f"Bearer {token}"},
        params={"part": "snippet", "q": q, "maxResults": max_results, "type": "video"},
        timeout=15,
    )
    if not r.ok:
        return _google_api_error(r) or {"ok": False, "status": r.status_code, "error": r.text[:300]}
    items = []
    for it in r.json().get("items", []):
        vid = (it.get("id") or {}).get("videoId")
        sn = it.get("snippet") or {}
        if not vid:
            continue
        items.append({
            "video_id": vid,
            "title": sn.get("title"),
            "channel": sn.get("channelTitle"),
            "description": (sn.get("description") or "")[:240],
            "published_at": sn.get("publishedAt"),
            "url": f"https://www.youtube.com/watch?v={vid}",
            "thumbnail": (((sn.get("thumbnails") or {}).get("medium") or {}).get("url")),
        })
    return {"ok": True, "videos": items, "count": len(items)}


def _list_youtube_subscriptions(uid, args):
    try:
        token = _get_valid_google_token(uid, 'youtube')
    except Exception as e:
        return {"ok": False, "error": str(e)}
    max_results = max(1, min(int(args.get("max_results") or 20), 50))
    r = requests.get(
        "https://www.googleapis.com/youtube/v3/subscriptions",
        headers={"Authorization": f"Bearer {token}"},
        params={"part": "snippet", "mine": "true", "maxResults": max_results},
        timeout=15,
    )
    if not r.ok:
        return _google_api_error(r) or {"ok": False, "status": r.status_code, "error": r.text[:300]}
    subs = []
    for it in r.json().get("items", []):
        sn = it.get("snippet") or {}
        subs.append({
            "title": sn.get("title"),
            "channel_id": (sn.get("resourceId") or {}).get("channelId"),
            "description": (sn.get("description") or "")[:200],
        })
    return {"ok": True, "subscriptions": subs, "count": len(subs)}


def _search_google_contacts(uid, args):
    try:
        token = _get_valid_google_token(uid, 'google_contacts')
    except Exception as e:
        return {"ok": False, "error": str(e)}
    q = (args.get("query") or "").strip()
    page_size = max(1, min(int(args.get("page_size") or 10), 30))
    headers = {"Authorization": f"Bearer {token}"}
    person_fields = "names,emailAddresses,phoneNumbers,organizations,photos"

    if q:
        # People API quirk: searchContacts needs a warmup request (empty query)
        # before it will return results for the first real query of a session.
        # Schema also requires `readMask` + `sources` query params (not in body).
        try:
            requests.get(
                "https://people.googleapis.com/v1/people:searchContacts",
                headers=headers,
                params={"query": "", "readMask": person_fields,
                        "sources": "READ_SOURCE_TYPE_CONTACT"},
                timeout=8,
            )
        except Exception:
            pass
        r = requests.get(
            "https://people.googleapis.com/v1/people:searchContacts",
            headers=headers,
            params={
                "query": q,
                "pageSize": page_size,
                "readMask": person_fields,
                "sources": "READ_SOURCE_TYPE_CONTACT",
            },
            timeout=15,
        )
        if r.ok:
            results = [_format_person(it.get("person") or {})
                       for it in (r.json().get("results") or [])]
            if results:
                return {"ok": True, "contacts": results, "count": len(results),
                        "source": "search"}
        elif r.status_code not in (200, 404):
            # Don't bail — fall through to the listConnections path which has
            # better permission coverage on read-only scope.
            print(f"[Contacts] search returned {r.status_code}: {r.text[:200]}")

    # Fallback: list all connections, then filter client-side.
    r = requests.get(
        "https://people.googleapis.com/v1/people/me/connections",
        headers=headers,
        params={
            "pageSize": min(max(page_size * 5, 50), 200),
            "personFields": person_fields,
            "sortOrder": "LAST_MODIFIED_DESCENDING",
        },
        timeout=20,
    )
    if not r.ok:
        return _google_api_error(r) or {"ok": False, "status": r.status_code, "error": r.text[:300]}
    results = [_format_person(p) for p in (r.json().get("connections") or [])]
    if q:
        ql = q.lower()
        results = [
            c for c in results
            if ql in (c.get("name") or "").lower()
            or any(ql in (e or "").lower() for e in (c.get("emails") or []))
            or any(ql in (ph or "") for ph in (c.get("phones") or []))
        ]
    return {"ok": True, "contacts": results[:page_size], "count": len(results),
            "source": "connections"}


def _format_person(p):
    names = (p.get("names") or [{}])[0]
    return {
        "name": names.get("displayName") or names.get("givenName"),
        "emails": [e.get("value") for e in (p.get("emailAddresses") or []) if e.get("value")],
        "phones": [ph.get("value") for ph in (p.get("phoneNumbers") or []) if ph.get("value")],
        "organization": ((p.get("organizations") or [{}])[0]).get("name"),
        "photo_url": ((p.get("photos") or [{}])[0]).get("url"),
    }


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
            "description": "Create a Google Calendar event on the user's primary calendar with optional Google Meet link.",
            "parameters": {"type": "object", "required": ["title", "start", "end"], "properties": {
                "title": {"type": "string"},
                "start": {"type": "string", "description": "RFC3339 datetime"},
                "end":   {"type": "string", "description": "RFC3339 datetime"},
                "description": {"type": "string"},
                "attendees": {"type": "array", "items": {"type": "string", "description": "email"}},
                "create_meet_link": {"type": "boolean", "description": "Set to true to generate an automatic Google Meet video conference link for this event"},
                "tz": {"type": "string", "description": "IANA timezone, defaults to Asia/Kolkata"}}}}},
    },
    "append_sheet_row": {
        "provider": "google_sheets",
        "handler": _append_sheet_row,
        "spec": {"type": "function", "function": {
            "name": "append_sheet_row",
            "description": "Append a new row of values to a Google Sheet spreadsheet.",
            "parameters": {"type": "object", "required": ["spreadsheet_id", "values"], "properties": {
                "spreadsheet_id": {"type": "string", "description": "Google Sheet ID from the sheet URL"},
                "values": {"type": "array", "items": {"type": "string"}, "description": "List of cell values to add to the new row (e.g. ['John Doe', 'john@example.com'])"},
                "sheet_name": {"type": "string", "description": "Tab sheet name, defaults to Sheet1"}}}}},
    },
    "create_google_task": {
        "provider": "google_tasks",
        "handler": _create_google_task,
        "spec": {"type": "function", "function": {
            "name": "create_google_task",
            "description": "Create a new task in the user's Google Tasks.",
            "parameters": {"type": "object", "required": ["title"], "properties": {
                "title": {"type": "string", "description": "Title of the task"},
                "notes": {"type": "string", "description": "Details or notes about the task"},
                "due": {"type": "string", "description": "RFC3339 timestamp for when the task is due (e.g. 2026-05-25T12:00:00Z)"}}}}},
    },
    "list_drive_files": {
        "provider": "google_drive",
        "handler": _list_drive_files,
        "spec": {"type": "function", "function": {
            "name": "list_drive_files",
            "description": "List or search files in the user's connected Google Drive.",
            "parameters": {"type": "object", "properties": {
                "query": {"type": "string", "description": "Optional file name search text"},
                "page_size": {"type": "integer", "description": "Max results, default 10, max 50"}
            }}}}
    },
    "read_drive_file": {
        "provider": "google_drive",
        "handler": _read_drive_file,
        "spec": {"type": "function", "function": {
            "name": "read_drive_file",
            "description": "Fetch metadata and view/download links for a Google Drive file by file_id.",
            "parameters": {"type": "object", "required": ["file_id"], "properties": {
                "file_id": {"type": "string", "description": "Google Drive file ID"}
            }}}}
    },
    "create_google_doc": {
        "provider": "google_docs",
        "handler": _create_google_doc,
        "spec": {"type": "function", "function": {
            "name": "create_google_doc",
            "description": "Create a new Google Doc with optional initial content. Returns the document URL.",
            "parameters": {"type": "object", "required": ["title"], "properties": {
                "title": {"type": "string", "description": "Title of the new document"},
                "content": {"type": "string", "description": "Optional initial body text (markdown not supported — plain text)"}
            }}}}
    },
    "read_google_doc": {
        "provider": "google_docs",
        "handler": _read_google_doc,
        "spec": {"type": "function", "function": {
            "name": "read_google_doc",
            "description": "Read the full text content of a Google Doc by its document_id.",
            "parameters": {"type": "object", "required": ["document_id"], "properties": {
                "document_id": {"type": "string", "description": "Google Docs document ID (from URL /document/d/<ID>/edit)"}
            }}}}
    },
    "append_google_doc": {
        "provider": "google_docs",
        "handler": _append_google_doc,
        "spec": {"type": "function", "function": {
            "name": "append_google_doc",
            "description": "Append text to the end of an existing Google Doc.",
            "parameters": {"type": "object", "required": ["document_id", "text"], "properties": {
                "document_id": {"type": "string"},
                "text": {"type": "string", "description": "Text to append (prepend a newline if you want a new paragraph)"}
            }}}}
    },
    "search_youtube": {
        "provider": "youtube",
        "handler": _search_youtube,
        "spec": {"type": "function", "function": {
            "name": "search_youtube",
            "description": "Search YouTube videos. Returns titles, channels, descriptions, and URLs for the top results.",
            "parameters": {"type": "object", "required": ["query"], "properties": {
                "query": {"type": "string", "description": "What to search on YouTube"},
                "max_results": {"type": "integer", "description": "Max videos to return (default 8, max 25)"}
            }}}}
    },
    "list_youtube_subscriptions": {
        "provider": "youtube",
        "handler": _list_youtube_subscriptions,
        "spec": {"type": "function", "function": {
            "name": "list_youtube_subscriptions",
            "description": "List the channels the user is subscribed to on YouTube.",
            "parameters": {"type": "object", "properties": {
                "max_results": {"type": "integer", "description": "Max channels to return (default 20, max 50)"}
            }}}}
    },
    "search_google_contacts": {
        "provider": "google_contacts",
        "handler": _search_google_contacts,
        "spec": {"type": "function", "function": {
            "name": "search_google_contacts",
            "description": "Search or list the user's Google Contacts. Returns name, emails, phones, organization.",
            "parameters": {"type": "object", "properties": {
                "query": {"type": "string", "description": "Optional name/email to filter by; omit to list all"},
                "page_size": {"type": "integer", "description": "Max results, default 10, max 30"}
            }}}}
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
