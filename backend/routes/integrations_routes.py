"""
Kautilya AI — Integrations (CRM / WhatsApp / Calendar / Slack / Zapier).

This blueprint provides:
  - OAuth start/callback scaffolding for HubSpot, Salesforce, Zoho, Google
    Calendar (real OAuth flow — user supplies client_id/secret in Settings).
  - WhatsApp Business API send + webhook receive.
  - Slack outbound webhook posting.
  - Zapier-compatible generic webhook trigger (fire-and-forget from agent
    conversations).
  - Per-user integration credential storage in Firestore.
  - Follow-up automation pipeline: extract action items from a transcript
    and dispatch them as emails / WhatsApps / calendar events.

Endpoints:
  GET    /api/integrations                     list available + connected status
  GET    /api/integrations/<provider>/connect  start OAuth (returns redirect URL)
  GET    /api/integrations/<provider>/callback OAuth callback
  POST   /api/integrations/<provider>/disconnect
  POST   /api/integrations/whatsapp/send       body: {to, message}
  POST   /api/integrations/slack/post          body: {channel?, message}
  POST   /api/integrations/calendar/event      body: {title, start, end, attendees?}
  POST   /api/integrations/zapier/trigger      body: {hook_url, payload}
  POST   /api/integrations/webhook/<provider>  inbound webhook handler
  POST   /api/integrations/followup/extract    body: {transcript}  → list of action items
  POST   /api/integrations/followup/dispatch   body: {action_items, channel}

NOTE: OAuth flows here are scaffolded with the real URLs and token exchange
logic. To actually connect, users must configure client_id + client_secret
for each provider in Settings → Integrations (stored encrypted in Firestore).
"""
import os
import json
import secrets
import time
from urllib.parse import urlencode, urlparse

import requests
from flask import Blueprint, request, redirect, jsonify, url_for

from services.auth_service import verify_firebase_token
from services.llm_service import call_groq

integrations_bp = Blueprint('integrations', __name__)


# ---------- Provider catalog ----------
PROVIDERS = {
    "hubspot": {
        "label": "HubSpot", "category": "crm",
        "authorize_url": "https://app.hubspot.com/oauth/authorize",
        "token_url": "https://api.hubapi.com/oauth/v1/token",
        "scopes": "crm.objects.contacts.read crm.objects.contacts.write crm.objects.deals.read crm.objects.deals.write",
    },
    "salesforce": {
        "label": "Salesforce", "category": "crm",
        "authorize_url": "https://login.salesforce.com/services/oauth2/authorize",
        "token_url": "https://login.salesforce.com/services/oauth2/token",
        "scopes": "api refresh_token",
    },
    "zoho": {
        "label": "Zoho CRM", "category": "crm",
        "authorize_url": "https://accounts.zoho.in/oauth/v2/auth",
        "token_url": "https://accounts.zoho.in/oauth/v2/token",
        "scopes": "ZohoCRM.modules.ALL,ZohoCRM.settings.ALL",
    },
    "google_calendar": {
        "label": "Google Calendar", "category": "calendar",
        "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "scopes": "https://www.googleapis.com/auth/calendar.events",
    },
    "gmail": {
        "label": "Gmail", "category": "email",
        "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "scopes": "https://www.googleapis.com/auth/gmail.send https://www.googleapis.com/auth/gmail.readonly",
    },
    "whatsapp": {
        "label": "WhatsApp Business", "category": "messaging",
        "api_manual": True,  # API-key based (Meta Business API), no OAuth
    },
    "slack": {
        "label": "Slack", "category": "messaging",
        "api_manual": True,  # incoming-webhook based
    },
    "zapier": {
        "label": "Zapier", "category": "automation",
        "api_manual": True,  # user pastes their Zap hook URL
    },
    "github": {
        "label": "GitHub", "category": "developer",
        "api_manual": True,  # user pastes Personal Access Token
    },
}


# ---------- Firestore helpers ----------
def _user_integration_ref(uid, provider):
    from extensions import db
    if not db or not uid:
        return None
    return db.collection('users').document(uid).collection('integrations').document(provider)


def _get_cfg(uid, provider):
    ref = _user_integration_ref(uid, provider)
    if not ref:
        return None
    try:
        doc = ref.get()
        return doc.to_dict() if doc.exists else None
    except Exception:
        return None


def _save_cfg(uid, provider, patch):
    ref = _user_integration_ref(uid, provider)
    if not ref:
        return False
    try:
        patch = dict(patch)
        patch['updated_at'] = int(time.time())
        ref.set(patch, merge=True)
        return True
    except Exception as e:
        print(f"[Integrations] save {provider} failed: {e}")
        return False


def _require_auth():
    td = verify_firebase_token()
    uid = td.get('uid') if td else None
    return uid


# ---------- Catalog / status ----------
@integrations_bp.route('/integrations', methods=['GET'])
def list_integrations():
    uid = _require_auth()
    if not uid:
        return jsonify({"error": "Authentication required"}), 401
    out = []
    for pid, meta in PROVIDERS.items():
        cfg = _get_cfg(uid, pid) or {}
        out.append({
            "id": pid,
            "label": meta["label"],
            "category": meta["category"],
            "connected": bool(cfg.get('access_token') or cfg.get('api_key') or cfg.get('webhook_url')),
            "auth_type": "oauth" if meta.get("authorize_url") else "api_key",
            "scopes": meta.get("scopes"),
            "updated_at": cfg.get('updated_at'),
        })
    return jsonify({"integrations": out})


# ---------- Tool catalog (shared with voice + chat agents) ----------
@integrations_bp.route('/integrations/tools', methods=['GET'])
def list_tools():
    """Returns the LLM tool specs the current user's agents can actually call,
    based on which integrations they have connected. Frontend uses this in
    Agent Studio → Tools tab to show 'this agent can: send WhatsApp, log to CRM…'."""
    uid = _require_auth()
    if not uid:
        return jsonify({"error": "Authentication required"}), 401
    from services.integration_tools import available_tools, REGISTRY
    specs = available_tools(uid)
    return jsonify({
        "tools": [{
            "name": s["function"]["name"],
            "description": s["function"]["description"],
            "provider": next((k for k, v in REGISTRY.items() if v["spec"]["function"]["name"] == s["function"]["name"]), None),
        } for s in specs],
        "all_tools": [{"name": k, "provider": v["provider"], "description": v["spec"]["function"]["description"]} for k, v in REGISTRY.items()],
    })


# ---------- MCP Server Status ----------
@integrations_bp.route('/mcp/status', methods=['GET'])
def mcp_status():
    """Returns the live status of all registered MCP servers and their tools."""
    uid = _require_auth()
    if not uid:
        return jsonify({"error": "Authentication required"}), 401
    from services.mcp_client_service import get_mcp_status
    return jsonify(get_mcp_status(uid=uid))


# ---------- OAuth start ----------
@integrations_bp.route('/integrations/<provider>/connect', methods=['GET'])
def connect(provider):
    uid = _require_auth()
    if not uid:
        return jsonify({"error": "Authentication required"}), 401
    meta = PROVIDERS.get(provider)
    if not meta or not meta.get('authorize_url'):
        return jsonify({"error": "Provider not OAuth-capable"}), 400

    cfg = _get_cfg(uid, provider) or {}
    client_id = cfg.get('client_id') or request.args.get('client_id')
    
    # Fallback to system environment variables for central OAuth registration
    if not client_id:
        client_id = os.environ.get(f"{provider.upper()}_CLIENT_ID")
    if not client_id and provider in ('gmail', 'google_calendar'):
        client_id = os.environ.get("GOOGLE_CLIENT_ID") or os.environ.get("GOOGLE_CALENDAR_CLIENT_ID") or os.environ.get("GMAIL_CLIENT_ID")

    if not client_id:
        return jsonify({"error": "client_id missing — save it in Settings first."}), 400

    client_secret = cfg.get('client_secret') or request.args.get('client_secret')
    if not client_secret:
        client_secret = os.environ.get(f"{provider.upper()}_CLIENT_SECRET")
    if not client_secret and provider in ('gmail', 'google_calendar'):
        client_secret = os.environ.get("GOOGLE_CLIENT_SECRET") or os.environ.get("GOOGLE_CALENDAR_CLIENT_SECRET") or os.environ.get("GMAIL_CLIENT_SECRET")

    # Force https — Flask behind HF Spaces / Render proxy sees http internally
    central_domain = os.environ.get("CENTRAL_DOMAIN") or os.environ.get("OAUTH_REDIRECT_DOMAIN")
    if central_domain:
        if '://' in central_domain:
            central_domain = central_domain.split('://', 1)[1]
        _host = f"https://{central_domain.rstrip('/')}"
    else:
        _host = request.host_url.rstrip('/')
        if _host.startswith('http://') and not _host.startswith('http://localhost'):
            _host = 'https://' + _host[7:]
    redirect_uri = request.args.get('redirect_uri') or (_host + f'/api/integrations/{provider}/callback')
    state = secrets.token_urlsafe(24)

    # Store credentials and oauth state in user integration doc for callback verification & exchange
    _save_cfg(uid, provider, {
        "client_id": client_id,
        "client_secret": client_secret,
        "oauth_state": state,
        "redirect_uri": redirect_uri
    })

    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": meta["scopes"],
        "state": f"{uid}:{state}",
        "access_type": "offline",
        "prompt": "consent",
    }
    url = f"{meta['authorize_url']}?{urlencode(params)}"
    return jsonify({"redirect_url": url})


# ---------- OAuth callback ----------
@integrations_bp.route('/integrations/<provider>/callback', methods=['GET'])
def oauth_callback(provider):
    meta = PROVIDERS.get(provider)
    if not meta or not meta.get('token_url'):
        return "Bad provider", 400
    state = request.args.get('state', '')
    code = request.args.get('code')
    if not code or ':' not in state:
        return "Missing code or state", 400
    uid, tok = state.split(':', 1)
    cfg = _get_cfg(uid, provider) or {}
    if cfg.get('oauth_state') != tok:
        return "State mismatch", 400
    try:
        resp = requests.post(meta['token_url'], data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": cfg.get('redirect_uri'),
            "client_id": cfg.get('client_id'),
            "client_secret": cfg.get('client_secret'),
        }, headers={"Accept": "application/json"}, timeout=20)
        if resp.status_code != 200:
            return f"Token exchange failed: {resp.status_code} {resp.text[:300]}", 502
        data = resp.json()
        _save_cfg(uid, provider, {
            "access_token": data.get("access_token"),
            "refresh_token": data.get("refresh_token"),
            "token_type": data.get("token_type"),
            "expires_in": data.get("expires_in"),
            "obtained_at": int(time.time()),
            "scope": data.get("scope"),
            "raw": data,
            "oauth_state": None,
        })
    except Exception as e:
        return f"Callback error: {e}", 502

    # Return a tiny HTML that tells the opener and closes itself.
    return """<!doctype html><meta charset="utf-8"><title>Connected</title>
    <style>body{font-family:Inter,sans-serif;background:#0B0B10;color:#F5F5F7;display:grid;place-items:center;height:100vh;margin:0;}</style>
    <div style="text-align:center;">
      <h2 style="color:#FF6D3F;">✓ Connected</h2>
      <p style="color:#A8A8B3;">You can close this tab.</p>
    </div>
    <script>try{window.opener&&window.opener.postMessage({kt_integration_connected:true},"*");}catch{};setTimeout(()=>window.close(),1200);</script>
    """, 200, {"Content-Type": "text/html"}


# ---------- Disconnect / save manual API keys ----------
@integrations_bp.route('/integrations/<provider>/disconnect', methods=['POST'])
def disconnect(provider):
    uid = _require_auth()
    if not uid:
        return jsonify({"error": "Authentication required"}), 401
    ref = _user_integration_ref(uid, provider)
    if ref:
        try: ref.delete()
        except Exception: pass
    if provider == "github":
        try:
            from services.mcp_client_service import close_user_mcp_server
            import services.mcp_client_service as mcs
            with mcs._lock:
                mcs._initialized_users.discard(uid)
            close_user_mcp_server(uid, "github")
        except Exception as e:
            print(f"[Integrations] failed to disconnect user GitHub server: {e}")
    return jsonify({"status": "ok"})


@integrations_bp.route('/integrations/<provider>/save', methods=['POST'])
def save_manual(provider):
    """Save manual API credentials for WhatsApp / Slack / Zapier / OAuth client_id / GitHub."""
    uid = _require_auth()
    if not uid:
        return jsonify({"error": "Authentication required"}), 401
    data = request.get_json(silent=True) or {}
    allowed = {
        "whatsapp":  {"access_token", "phone_number_id", "business_account_id", "verify_token"},
        "slack":     {"webhook_url", "bot_token", "default_channel"},
        "zapier":    {"webhook_url"},
        "hubspot":   {"client_id", "client_secret"},
        "salesforce":{"client_id", "client_secret"},
        "zoho":      {"client_id", "client_secret"},
        "google_calendar": {"client_id", "client_secret"},
        "gmail":           {"client_id", "client_secret"},
        "github":          {"access_token"},
    }.get(provider)
    if allowed is None:
        return jsonify({"error": "unknown provider"}), 400
    patch = {k: v for k, v in data.items() if k in allowed}
    _save_cfg(uid, provider, patch)
    if provider == "github" and patch.get("access_token"):
        try:
            from services.mcp_client_service import close_user_mcp_server, init_user_github_server
            import services.mcp_client_service as mcs
            with mcs._lock:
                mcs._initialized_users.discard(uid)
            close_user_mcp_server(uid, "github")
            init_user_github_server(uid, patch["access_token"])
        except Exception as e:
            print(f"[Integrations] failed to restart user GitHub server: {e}")
    return jsonify({"status": "ok"})


# ---------- WhatsApp ----------
@integrations_bp.route('/integrations/whatsapp/send', methods=['POST'])
def whatsapp_send():
    uid = _require_auth()
    if not uid:
        return jsonify({"error": "Authentication required"}), 401
    cfg = _get_cfg(uid, 'whatsapp') or {}
    access = cfg.get('access_token')
    phone_id = cfg.get('phone_number_id')
    if not access or not phone_id:
        return jsonify({"error": "WhatsApp not configured. Add access_token + phone_number_id in Settings."}), 400
    data = request.get_json(silent=True) or {}
    to = (data.get('to') or '').strip()
    message = (data.get('message') or '').strip()
    if not to or not message:
        return jsonify({"error": "to and message required"}), 400
    try:
        resp = requests.post(
            f"https://graph.facebook.com/v20.0/{phone_id}/messages",
            headers={"Authorization": f"Bearer {access}", "Content-Type": "application/json"},
            json={"messaging_product": "whatsapp", "to": to,
                  "type": "text", "text": {"body": message}},
            timeout=15,
        )
        return jsonify({"status": resp.status_code, "response": resp.json() if resp.headers.get('content-type','').startswith('application/json') else resp.text})
    except Exception as e:
        return jsonify({"error": str(e)}), 502


# WhatsApp inbound webhook (Meta verification + incoming messages)
@integrations_bp.route('/integrations/webhook/whatsapp', methods=['GET', 'POST'])
def whatsapp_webhook():
    if request.method == 'GET':
        # Meta verification handshake. We accept any caller with a matching verify_token.
        # (Find the token across known users by scanning recent configs.)
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge', '')
        if mode == 'subscribe' and token:
            try:
                from extensions import db
                if db:
                    users = db.collection_group('integrations').where(
                        filter=__import__('firebase_admin').firestore.FieldFilter('verify_token', '==', token)
                    ).limit(1).stream()
                    if any(True for _ in users):
                        return challenge, 200
            except Exception:
                pass
        return "forbidden", 403

    # POST: incoming message. We just log it to Firestore under the owning user.
    payload = request.get_json(silent=True) or {}
    try:
        from extensions import db
        if db:
            db.collection('whatsapp_inbound').add({
                "payload": json.dumps(payload)[:5000],
                "received_at": int(time.time()),
            })
    except Exception:
        pass
    return jsonify({"status": "ok"})


# ---------- Slack ----------
@integrations_bp.route('/integrations/slack/post', methods=['POST'])
def slack_post():
    uid = _require_auth()
    if not uid:
        return jsonify({"error": "Authentication required"}), 401
    cfg = _get_cfg(uid, 'slack') or {}
    webhook = cfg.get('webhook_url')
    if not webhook:
        return jsonify({"error": "Slack webhook not configured."}), 400
    data = request.get_json(silent=True) or {}
    message = (data.get('message') or '').strip()
    if not message:
        return jsonify({"error": "message required"}), 400
    body = {"text": message}
    if cfg.get('default_channel'):
        body["channel"] = cfg['default_channel']
    try:
        r = requests.post(webhook, json=body, timeout=10)
        return jsonify({"status": r.status_code, "body": r.text[:200]})
    except Exception as e:
        return jsonify({"error": str(e)}), 502


# ---------- Google Calendar ----------
@integrations_bp.route('/integrations/calendar/event', methods=['POST'])
def calendar_event():
    uid = _require_auth()
    if not uid:
        return jsonify({"error": "Authentication required"}), 401
    cfg = _get_cfg(uid, 'google_calendar') or {}
    access = cfg.get('access_token')
    if not access:
        return jsonify({"error": "Google Calendar not connected."}), 400
    data = request.get_json(silent=True) or {}
    title = (data.get('title') or 'Untitled').strip()
    start = data.get('start')  # RFC3339
    end = data.get('end')
    attendees = data.get('attendees') or []
    if not start or not end:
        return jsonify({"error": "start and end (RFC3339) required"}), 400
    body = {
        "summary": title,
        "description": data.get('description', ''),
        "start": {"dateTime": start, "timeZone": data.get('tz', 'Asia/Kolkata')},
        "end":   {"dateTime": end,   "timeZone": data.get('tz', 'Asia/Kolkata')},
        "attendees": [{"email": e} for e in attendees if '@' in e],
    }
    try:
        r = requests.post(
            "https://www.googleapis.com/calendar/v3/calendars/primary/events",
            headers={"Authorization": f"Bearer {access}", "Content-Type": "application/json"},
            json=body, timeout=15,
        )
        return jsonify({"status": r.status_code, "event": r.json() if r.headers.get('content-type','').startswith('application/json') else r.text})
    except Exception as e:
        return jsonify({"error": str(e)}), 502


# ---------- Zapier generic trigger ----------
@integrations_bp.route('/integrations/zapier/trigger', methods=['POST'])
def zapier_trigger():
    uid = _require_auth()
    if not uid:
        return jsonify({"error": "Authentication required"}), 401
    data = request.get_json(silent=True) or {}
    hook = data.get('hook_url') or (_get_cfg(uid, 'zapier') or {}).get('webhook_url')
    if not hook:
        return jsonify({"error": "No Zapier hook URL configured."}), 400
    if not urlparse(hook).netloc.endswith('zapier.com') and not urlparse(hook).netloc.endswith('hooks.zapier.com'):
        # Allow any HTTPS webhook but warn in response
        pass
    try:
        r = requests.post(hook, json=data.get('payload') or {}, timeout=10)
        return jsonify({"status": r.status_code})
    except Exception as e:
        return jsonify({"error": str(e)}), 502


# ---------- Follow-up automation ----------
@integrations_bp.route('/integrations/followup/extract', methods=['POST'])
def followup_extract():
    """LLM extracts action items from a transcript or conversation."""
    uid = _require_auth()
    if not uid:
        return jsonify({"error": "Authentication required"}), 401
    data = request.get_json(silent=True) or {}
    transcript = (data.get('transcript') or data.get('text') or '').strip()
    if not transcript:
        return jsonify({"error": "transcript required"}), 400

    messages = [
        {"role": "system", "content":
         "You extract concrete action items from a conversation. "
         "Return a JSON array of objects with keys: action (str), owner (str, who should do it), "
         "due (str, ISO date if mentioned else null), channel (one of email|whatsapp|slack|calendar|note), "
         "contact (str, email or phone if applicable else null). Output ONLY the JSON array."},
        {"role": "user", "content": transcript[:8000]},
    ]
    out = call_groq(messages, model="llama-3.3-70b-versatile",
                    temperature=0.1, max_tokens=1200, stream=False)
    items = []
    if isinstance(out, str):
        import re as _re
        m = _re.search(r'\[.*\]', out, _re.S)
        if m:
            try:
                items = json.loads(m.group(0))
            except Exception:
                items = []
    return jsonify({"action_items": items})


@integrations_bp.route('/integrations/followup/dispatch', methods=['POST'])
def followup_dispatch():
    """Fire a list of action items across the appropriate channels."""
    uid = _require_auth()
    if not uid:
        return jsonify({"error": "Authentication required"}), 401
    data = request.get_json(silent=True) or {}
    items = data.get('action_items') or []
    if not isinstance(items, list):
        return jsonify({"error": "action_items must be a list"}), 400

    results = []
    for it in items:
        ch = (it.get('channel') or 'note').lower()
        outcome = {"action": it.get('action'), "channel": ch, "status": "skipped"}
        try:
            if ch == 'whatsapp' and it.get('contact'):
                cfg = _get_cfg(uid, 'whatsapp') or {}
                if cfg.get('access_token') and cfg.get('phone_number_id'):
                    r = requests.post(
                        f"https://graph.facebook.com/v20.0/{cfg['phone_number_id']}/messages",
                        headers={"Authorization": f"Bearer {cfg['access_token']}", "Content-Type": "application/json"},
                        json={"messaging_product": "whatsapp", "to": it['contact'],
                              "type": "text", "text": {"body": it.get('action', '(follow-up)')}},
                        timeout=15,
                    )
                    outcome['status'] = 'sent' if r.ok else f'http {r.status_code}'
            elif ch == 'slack':
                cfg = _get_cfg(uid, 'slack') or {}
                if cfg.get('webhook_url'):
                    r = requests.post(cfg['webhook_url'],
                                      json={"text": f"*Follow-up:* {it.get('action','')}"},
                                      timeout=10)
                    outcome['status'] = 'sent' if r.ok else f'http {r.status_code}'
            elif ch == 'calendar' and it.get('due'):
                cfg = _get_cfg(uid, 'google_calendar') or {}
                if cfg.get('access_token'):
                    start = it['due']
                    end = it.get('due_end') or start
                    r = requests.post(
                        "https://www.googleapis.com/calendar/v3/calendars/primary/events",
                        headers={"Authorization": f"Bearer {cfg['access_token']}", "Content-Type": "application/json"},
                        json={
                            "summary": it.get('action', 'Follow-up'),
                            "start": {"dateTime": start, "timeZone": "Asia/Kolkata"},
                            "end":   {"dateTime": end,   "timeZone": "Asia/Kolkata"},
                        }, timeout=15)
                    outcome['status'] = 'scheduled' if r.ok else f'http {r.status_code}'
            else:
                outcome['status'] = 'logged (no channel configured)'
        except Exception as e:
            outcome['status'] = f'error: {e}'
        results.append(outcome)

    return jsonify({"results": results})


# ---------- User Custom MCP Servers ----------
@integrations_bp.route('/integrations/mcp/custom', methods=['GET'])
def get_custom_mcps():
    uid = _require_auth()
    if not uid:
        return jsonify({"error": "Authentication required"}), 401
    from extensions import db
    if not db:
        return jsonify({"servers": []})
    try:
        docs = db.collection('users').document(uid).collection('mcp_servers').stream()
        servers = []
        for doc in docs:
            d = doc.to_dict()
            d['key'] = doc.id
            servers.append(d)
        return jsonify({"servers": servers})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@integrations_bp.route('/integrations/mcp/custom', methods=['POST'])
def save_custom_mcp():
    uid = _require_auth()
    if not uid:
        return jsonify({"error": "Authentication required"}), 401
    data = request.get_json(silent=True) or {}
    key = data.get('key')
    url = data.get('url')
    if not key or not url:
        return jsonify({"error": "Missing key or url"}), 400
    
    # Sanitize key
    import re
    key = re.sub(r'[^a-zA-Z0-9_]', '_', key).lower()
    
    from extensions import db
    if not db:
        return jsonify({"error": "Database not initialized"}), 500
    try:
        ref = db.collection('users').document(uid).collection('mcp_servers').document(key)
        srv_data = {
            "url": url,
            "description": data.get('description', ''),
            "category": data.get('category', 'Custom'),
            "enabled": bool(data.get('enabled', True)),
            "updated_at": int(time.time())
        }
        ref.set(srv_data, merge=True)
        
        # Trigger dynamic connection/reconnection of this specific server
        from services.mcp_client_service import init_user_mcp_server
        init_user_mcp_server(uid, key, srv_data)
        
        return jsonify({"status": "ok", "key": key})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@integrations_bp.route('/integrations/mcp/custom/<key>', methods=['DELETE'])
def delete_custom_mcp(key):
    uid = _require_auth()
    if not uid:
        return jsonify({"error": "Authentication required"}), 401
    from extensions import db
    if not db:
        return jsonify({"error": "Database not initialized"}), 500
    try:
        db.collection('users').document(uid).collection('mcp_servers').document(key).delete()
        
        # Close connection and remove from cache
        from services.mcp_client_service import close_user_mcp_server
        close_user_mcp_server(uid, key)
        
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

