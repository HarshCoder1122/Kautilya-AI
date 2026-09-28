"""
Kautilya AI — KautilyaClaw (multi-tenant personal messaging agents).

Every dashboard user can spin up their OWN 24/7 "Claw" bot on Telegram and/or
WhatsApp. They bring a channel credential (Telegram bot token / WhatsApp Cloud
API), we register a per-user webhook, and inbound messages are routed back to
THAT user's uid and run through the normal agent_loop — so the bot thinks with
the user's own Kautilya models, uses their connected integrations, and is
metered against their own tier limits. No master key, no key pasting.

Channels:
  • Telegram  — bring a @BotFather token. Webhook: /api/claw/tg/<secret>
  • WhatsApp  — bring Cloud API phone_number_id + access_token. The user points
                their Meta app webhook at /api/claw/wa/<secret> (verify token = secret).
"""
import os
import json
import time
import secrets
import threading

import requests
from flask import Blueprint, request, jsonify
from flask_cors import cross_origin

from services.auth_service import verify_firebase_token, record_usage

claw_bp = Blueprint('claw', __name__)

PUBLIC_BASE = (os.environ.get('CLAW_PUBLIC_BASE') or 'https://ai.revealiq.in').rstrip('/')
TG_API = "https://api.telegram.org/bot{token}/{method}"
WA_GRAPH = "https://graph.facebook.com/v21.0"
MSG_LIMIT = 4096
DEFAULT_PROMPT = ("You are a helpful, concise personal assistant on a messaging app. "
                  "Answer directly. Use the user's connected tools when relevant.")


# ───────────────────────── channel send helpers ─────────────────────────
def _tg(token, method, payload=None, timeout=20):
    try:
        return requests.post(TG_API.format(token=token, method=method),
                             json=(payload or {}), timeout=timeout).json()
    except Exception as e:
        print(f"[Claw] tg {method} error: {e}")
        return {}


def _tg_send(token, chat_id, text, reply_to=None):
    text = (text or "").strip() or "…"
    for i in range(0, len(text), MSG_LIMIT):
        p = {"chat_id": chat_id, "text": text[i:i + MSG_LIMIT], "disable_web_page_preview": True}
        if reply_to and i == 0:
            p["reply_to_message_id"] = reply_to
        _tg(token, "sendMessage", p)


def _wa_send(phone_id, access_token, to, text):
    text = (text or "").strip() or "…"
    for i in range(0, len(text), MSG_LIMIT):
        try:
            requests.post(
                f"{WA_GRAPH}/{phone_id}/messages",
                headers={"Authorization": f"Bearer {access_token}"},
                json={"messaging_product": "whatsapp", "to": to, "type": "text",
                      "text": {"body": text[i:i + MSG_LIMIT]}},
                timeout=20,
            )
        except Exception as e:
            print(f"[Claw] wa send error: {e}")


# ───────────────────────── shared agent core ─────────────────────────
def _run_agent(messages, uid, model_choice):
    """Drive the full Kautilya agent loop and return the final visible text.
    Runs as `uid`, so the user's models / integrations / limits apply."""
    from services.agent_loop_service import agent_loop, normalize_model_choice
    out = []
    for item in agent_loop(messages, uid=uid, model_choice=normalize_model_choice(model_choice)):
        try:
            d = json.loads(item) if isinstance(item, str) else item
        except Exception:
            if isinstance(item, str):
                out.append(item)
            continue
        if isinstance(d, dict) and "chunk" in d:
            out.append(d["chunk"])
    return "".join(out).strip()


def _generate(uid, claw, session_key, text):
    """Limit-check, load rolling history, run the agent as `uid`, persist, return reply."""
    from extensions import db, limit_manager
    if text.strip().lower() in ("/reset", "reset"):
        try:
            db.collection('claws').document(uid).collection('sessions').document(session_key).delete()
        except Exception:
            pass
        return "🧹 Conversation cleared."
    if text.strip() in ("/start", "/help"):
        return (f"👋 Hi! I'm {claw.get('name') or 'your Kautilya Claw'}. Ask me anything — "
                "I can also use your connected tools. Send /reset to clear our chat.")

    is_pro = limit_manager.is_pro_user(uid)
    try:
        if not limit_manager.check_chat_limit(uid, is_pro=is_pro):
            return "⚠️ You've hit today's free message limit. Upgrade to Kautilya Pro for more."
    except Exception:
        pass

    sess_ref = db.collection('claws').document(uid).collection('sessions').document(session_key)
    history = []
    try:
        snap = sess_ref.get()
        if snap.exists:
            history = (snap.to_dict() or {}).get('messages', [])[-10:]
    except Exception:
        pass

    messages = [{"role": "system", "content": claw.get('system_prompt') or DEFAULT_PROMPT}]
    messages += [m for m in history if m.get("role") in ("user", "assistant")]
    messages.append({"role": "user", "content": text})

    reply = _run_agent(messages, uid, claw.get('model') or 'kautilya-daily') or \
        "Hmm, I couldn't generate a reply. Try rephrasing?"

    new_hist = (history + [{"role": "user", "content": text},
                           {"role": "assistant", "content": reply}])[-12:]
    try:
        from firebase_admin import firestore
        sess_ref.set({"messages": new_hist, "updated_at": firestore.SERVER_TIMESTAMP}, merge=True)
    except Exception:
        sess_ref.set({"messages": new_hist})
    try:
        record_usage(uid, 'claw_messages', 1, model=claw.get('model'))
    except Exception:
        pass
    return reply


# ───────────────────────── background processors ─────────────────────────
def _process_tg(uid, claw, update):
    msg = (update or {}).get("message") or {}
    chat = msg.get("chat") or {}
    chat_id = chat.get("id")
    text = (msg.get("text") or "").strip()
    from_id = str((msg.get("from") or {}).get("id") or "")
    if not chat_id or not text:
        return
    token = claw.get("tg_token")
    try:
        allow = [str(x) for x in (claw.get("tg_allow_from") or [])]
        if allow and from_id not in allow:
            _tg_send(token, chat_id, "🔒 This Claw is private. The owner hasn't allowlisted you.")
            return
        _tg(token, "sendChatAction", {"chat_id": chat_id, "action": "typing"})
        reply = _generate(uid, claw, f"tg_{chat_id}", text)
        _tg_send(token, chat_id, reply, reply_to=msg.get("message_id"))
    except Exception as e:
        print(f"[Claw] tg process error uid={uid}: {e}")


def _process_wa(uid, claw, value):
    try:
        msgs = (value or {}).get("messages") or []
        if not msgs:
            return  # status callback (delivered/read) — ignore
        m = msgs[0]
        if m.get("type") != "text":
            return
        frm = m.get("from")
        text = ((m.get("text") or {}).get("body") or "").strip()
        if not frm or not text:
            return
        allow = [str(x) for x in (claw.get("wa_allow_from") or [])]
        if allow and str(frm) not in allow:
            _wa_send(claw.get("wa_phone_id"), claw.get("wa_token"), frm,
                     "🔒 This Claw is private. The owner hasn't allowlisted you.")
            return
        reply = _generate(uid, claw, f"wa_{frm}", text)
        _wa_send(claw.get("wa_phone_id"), claw.get("wa_token"), frm, reply)
    except Exception as e:
        print(f"[Claw] wa process error uid={uid}: {e}")


# ───────────────────────── dashboard API ─────────────────────────
def _uid():
    td = verify_firebase_token()
    return td.get('uid') if td else None


@claw_bp.route('/claw', methods=['GET', 'OPTIONS'])
@cross_origin()
def claw_get():
    if request.method == 'OPTIONS':
        return '', 200
    from extensions import db
    uid = _uid()
    if not uid:
        return jsonify({"error": "Authentication required"}), 401
    doc = db.collection('claws').document(uid).get()
    if not doc.exists:
        return jsonify({"configured": False})
    d = doc.to_dict() or {}
    tg_on = bool(d.get("tg_token"))
    wa_on = bool(d.get("wa_phone_id"))
    return jsonify({
        # The doc exists → the Claw is set up (Web Chat works with zero setup,
        # even before any external messaging channel is connected).
        "configured": True,
        "web": {"enabled": True},
        "enabled": d.get("enabled", True),
        "name": d.get("name"),
        "model": d.get("model", "kautilya-daily"),
        "system_prompt": d.get("system_prompt", ""),
        "telegram": {
            "configured": tg_on,
            "bot_username": d.get("tg_bot_username"),
            "bot_link": f"https://t.me/{d.get('tg_bot_username')}" if d.get('tg_bot_username') else None,
            "allow_from": d.get("tg_allow_from", []),
        },
        "whatsapp": {
            "configured": wa_on,
            "phone_number_id": d.get("wa_phone_id"),
            "webhook_url": f"{PUBLIC_BASE}/api/claw/wa/{d.get('wa_secret')}" if d.get('wa_secret') else None,
            "verify_token": d.get("wa_secret"),
            "allow_from": d.get("wa_allow_from", []),
        },
    })


@claw_bp.route('/claw/update', methods=['POST', 'OPTIONS'])
@cross_origin()
def claw_update():
    """Shared brain settings: name / model / personality / enabled."""
    if request.method == 'OPTIONS':
        return '', 200
    from extensions import db
    from firebase_admin import firestore
    uid = _uid()
    if not uid:
        return jsonify({"error": "Authentication required"}), 401
    ref = db.collection('claws').document(uid)
    if not ref.get().exists:
        return jsonify({"error": "No Claw configured yet"}), 404
    b = request.get_json(silent=True) or {}
    f = {"updated_at": firestore.SERVER_TIMESTAMP}
    if 'name' in b: f['name'] = str(b['name'])[:80]
    if 'model' in b: f['model'] = str(b['model'])
    if 'system_prompt' in b: f['system_prompt'] = str(b['system_prompt'])[:6000]
    if 'enabled' in b: f['enabled'] = bool(b['enabled'])
    if 'tg_allow_from' in b:
        f['tg_allow_from'] = [str(x).strip() for x in (b['tg_allow_from'] or []) if str(x).strip()][:50]
    if 'wa_allow_from' in b:
        f['wa_allow_from'] = [str(x).strip() for x in (b['wa_allow_from'] or []) if str(x).strip()][:50]
    ref.update(f)
    return jsonify({"ok": True})


@claw_bp.route('/claw/telegram/setup', methods=['POST', 'OPTIONS'])
@cross_origin()
def claw_tg_setup():
    if request.method == 'OPTIONS':
        return '', 200
    from extensions import db
    from firebase_admin import firestore
    uid = _uid()
    if not uid:
        return jsonify({"error": "Authentication required"}), 401
    b = request.get_json(silent=True) or {}
    token = (b.get('telegram_token') or '').strip()
    if not token or ':' not in token:
        return jsonify({"error": "A valid Telegram bot token is required (from @BotFather)."}), 400
    me = _tg(token, "getMe")
    if not me.get("ok"):
        return jsonify({"error": "Telegram rejected this token. Re-check it from @BotFather."}), 400
    bot = me["result"]

    ref = db.collection('claws').document(uid)
    cur = ref.get().to_dict() if ref.get().exists else {}
    secret = cur.get('tg_secret') or secrets.token_urlsafe(24)
    patch = {
        "uid": uid,
        "tg_token": token,
        "tg_bot_id": bot.get("id"),
        "tg_bot_username": bot.get("username"),
        "tg_secret": secret,
        "name": cur.get("name") or (b.get('name') or bot.get('first_name') or 'My Claw')[:80],
        "model": cur.get("model") or (b.get('model') or 'kautilya-daily'),
        "system_prompt": cur.get("system_prompt") if cur.get("system_prompt") is not None else (b.get('system_prompt') or '')[:6000],
        "enabled": cur.get("enabled", True),
        "updated_at": firestore.SERVER_TIMESTAMP,
        "created_at_ts": cur.get("created_at_ts") or int(time.time()),
    }
    ref.set(patch, merge=True)
    db.collection('claw_hooks').document(secret).set({"uid": uid, "channel": "telegram"})

    res = _tg(token, "setWebhook", {
        "url": f"{PUBLIC_BASE}/api/claw/tg/{secret}",
        "secret_token": secret,
        "allowed_updates": ["message"],
        "drop_pending_updates": True,
    })
    if not res.get("ok"):
        return jsonify({"error": f"Could not set Telegram webhook: {res.get('description', 'unknown')}"}), 502
    return jsonify({"ok": True, "bot_username": bot.get("username"),
                    "bot_link": f"https://t.me/{bot.get('username')}"})


@claw_bp.route('/claw/telegram/delete', methods=['POST', 'OPTIONS'])
@cross_origin()
def claw_tg_delete():
    if request.method == 'OPTIONS':
        return '', 200
    from extensions import db
    uid = _uid()
    if not uid:
        return jsonify({"error": "Authentication required"}), 401
    ref = db.collection('claws').document(uid)
    d = ref.get().to_dict() if ref.get().exists else None
    if d:
        if d.get("tg_token"):
            _tg(d["tg_token"], "deleteWebhook", {"drop_pending_updates": True})
        if d.get("tg_secret"):
            try: db.collection('claw_hooks').document(d["tg_secret"]).delete()
            except Exception: pass
        ref.update({"tg_token": None, "tg_bot_id": None, "tg_bot_username": None, "tg_secret": None})
    return jsonify({"ok": True})


@claw_bp.route('/claw/whatsapp/setup', methods=['POST', 'OPTIONS'])
@cross_origin()
def claw_wa_setup():
    if request.method == 'OPTIONS':
        return '', 200
    from extensions import db
    from firebase_admin import firestore
    uid = _uid()
    if not uid:
        return jsonify({"error": "Authentication required"}), 401
    b = request.get_json(silent=True) or {}
    phone_id = (b.get('phone_number_id') or '').strip()
    access_token = (b.get('access_token') or '').strip()
    if not phone_id or not access_token:
        return jsonify({"error": "WhatsApp Cloud API phone_number_id and access_token are required."}), 400

    # Soft-validate the credentials against Graph.
    try:
        chk = requests.get(f"{WA_GRAPH}/{phone_id}",
                          headers={"Authorization": f"Bearer {access_token}"}, timeout=15)
        if chk.status_code >= 400:
            return jsonify({"error": f"WhatsApp rejected these credentials: {chk.json().get('error', {}).get('message', chk.text)[:160]}"}), 400
    except Exception as e:
        return jsonify({"error": f"Couldn't verify WhatsApp credentials: {e}"}), 400

    ref = db.collection('claws').document(uid)
    cur = ref.get().to_dict() if ref.get().exists else {}
    secret = cur.get('wa_secret') or secrets.token_urlsafe(24)
    ref.set({
        "uid": uid,
        "wa_phone_id": phone_id,
        "wa_token": access_token,
        "wa_secret": secret,
        "name": cur.get("name") or (b.get('name') or 'My Claw'),
        "model": cur.get("model") or (b.get('model') or 'kautilya-daily'),
        "system_prompt": cur.get("system_prompt") or (b.get('system_prompt') or ''),
        "enabled": cur.get("enabled", True),
        "updated_at": firestore.SERVER_TIMESTAMP,
        "created_at_ts": cur.get("created_at_ts") or int(time.time()),
    }, merge=True)
    db.collection('claw_hooks').document(secret).set({"uid": uid, "channel": "whatsapp"})

    return jsonify({
        "ok": True,
        "webhook_url": f"{PUBLIC_BASE}/api/claw/wa/{secret}",
        "verify_token": secret,
        "note": "Add this Callback URL + Verify Token in your Meta app → WhatsApp → Configuration, then subscribe to 'messages'.",
    })


@claw_bp.route('/claw/whatsapp/delete', methods=['POST', 'OPTIONS'])
@cross_origin()
def claw_wa_delete():
    if request.method == 'OPTIONS':
        return '', 200
    from extensions import db
    uid = _uid()
    if not uid:
        return jsonify({"error": "Authentication required"}), 401
    ref = db.collection('claws').document(uid)
    d = ref.get().to_dict() if ref.get().exists else None
    if d:
        if d.get("wa_secret"):
            try: db.collection('claw_hooks').document(d["wa_secret"]).delete()
            except Exception: pass
        ref.update({"wa_phone_id": None, "wa_token": None, "wa_secret": None})
    return jsonify({"ok": True})


# ───────────────────────── web chat (free, zero-setup) ─────────────────────────
@claw_bp.route('/claw/web/chat', methods=['POST', 'OPTIONS'])
@cross_origin()
def claw_web_chat():
    """Chat with your Claw straight from the dashboard — no token, no phone,
    free, works everywhere. Runs the same agent as your uid (your limits)."""
    if request.method == 'OPTIONS':
        return '', 200
    from extensions import db
    from firebase_admin import firestore
    uid = _uid()
    if not uid:
        return jsonify({"error": "Authentication required"}), 401
    body = request.get_json(silent=True) or {}
    message = (body.get('message') or '').strip()
    session_id = (body.get('session_id') or 'web')[:60]
    if not message:
        return jsonify({"error": "message is required"}), 400

    ref = db.collection('claws').document(uid)
    snap = ref.get()
    if snap.exists:
        claw = snap.to_dict() or {}
    else:
        # First web message auto-creates a default Claw so settings/channels light up.
        claw = {"uid": uid, "name": "My Claw", "model": "kautilya-daily",
                "system_prompt": "", "enabled": True, "created_at_ts": int(time.time())}
        ref.set({**claw, "updated_at": firestore.SERVER_TIMESTAMP}, merge=True)

    if not claw.get("enabled", True):
        return jsonify({"reply": "⏸️ This Claw is paused. Resume it in Agent settings."})

    reply = _generate(uid, claw, f"web_{session_id}", message)
    return jsonify({"reply": reply})


# ───────────── real OpenClaw console (per-user, owner-only link) ─────────────
# Each user links their OWN hosted OpenClaw (Clawdbot) console — its URL + gateway
# token are stored under THEIR uid and only ever returned to that same uid. So a
# Clawdbot linked to one account is invisible/inaccessible to every other user.
@claw_bp.route('/claw/openclaw', methods=['GET', 'OPTIONS'])
@cross_origin()
def claw_openclaw_get():
    if request.method == 'OPTIONS':
        return '', 200
    from extensions import db
    uid = _uid()
    if not uid:
        return jsonify({"error": "Authentication required"}), 401
    doc = db.collection('claws').document(uid).get()
    d = doc.to_dict() if doc.exists else {}
    url = (d or {}).get('openclaw_url')
    tok = (d or {}).get('openclaw_token')
    if url and tok:
        sep = '&' if '?' in url else '?'
        return jsonify({"linked": True, "console_url": f"{url}{sep}token={tok}", "base_url": url})
    return jsonify({"linked": False})


@claw_bp.route('/claw/openclaw/link', methods=['POST', 'OPTIONS'])
@cross_origin()
def claw_openclaw_link():
    if request.method == 'OPTIONS':
        return '', 200
    from extensions import db
    from firebase_admin import firestore
    uid = _uid()
    if not uid:
        return jsonify({"error": "Authentication required"}), 401
    b = request.get_json(silent=True) or {}
    url = (b.get('url') or '').strip().rstrip('/')
    tok = (b.get('token') or '').strip()
    if not url.startswith('http') or not tok:
        return jsonify({"error": "A valid console URL and gateway token are required."}), 400
    db.collection('claws').document(uid).set({
        "uid": uid, "openclaw_url": url, "openclaw_token": tok,
        "updated_at": firestore.SERVER_TIMESTAMP,
    }, merge=True)
    return jsonify({"ok": True})


@claw_bp.route('/claw/openclaw/unlink', methods=['POST', 'OPTIONS'])
@cross_origin()
def claw_openclaw_unlink():
    if request.method == 'OPTIONS':
        return '', 200
    from extensions import db
    uid = _uid()
    if not uid:
        return jsonify({"error": "Authentication required"}), 401
    ref = db.collection('claws').document(uid)
    if ref.get().exists:
        ref.update({"openclaw_url": None, "openclaw_token": None})
    return jsonify({"ok": True})


# ───────────────────────── inbound webhooks ─────────────────────────
@claw_bp.route('/claw/tg/<secret>', methods=['POST'])
def claw_tg_inbound(secret):
    from extensions import db
    if request.headers.get('X-Telegram-Bot-Api-Secret-Token') != secret:
        return "forbidden", 403
    hook = db.collection('claw_hooks').document(secret).get()
    uid = (hook.to_dict() or {}).get('uid') if hook.exists else None
    if not uid:
        return "ok", 200
    cd = db.collection('claws').document(uid).get()
    claw = cd.to_dict() if cd.exists else None
    if not claw or not claw.get("enabled", True) or not claw.get("tg_token"):
        return "ok", 200
    threading.Thread(target=_process_tg, args=(uid, claw, request.get_json(silent=True) or {}), daemon=True).start()
    return "ok", 200


@claw_bp.route('/claw/wa/<secret>', methods=['GET', 'POST'])
def claw_wa_inbound(secret):
    from extensions import db
    # Meta webhook verification handshake (GET).
    if request.method == 'GET':
        if (request.args.get('hub.mode') == 'subscribe'
                and request.args.get('hub.verify_token') == secret):
            return request.args.get('hub.challenge', ''), 200
        return "forbidden", 403

    hook = db.collection('claw_hooks').document(secret).get()
    uid = (hook.to_dict() or {}).get('uid') if hook.exists else None
    if not uid:
        return "ok", 200
    cd = db.collection('claws').document(uid).get()
    claw = cd.to_dict() if cd.exists else None
    if not claw or not claw.get("enabled", True) or not claw.get("wa_phone_id"):
        return "ok", 200

    body = request.get_json(silent=True) or {}
    try:
        for entry in body.get("entry", []):
            for ch in entry.get("changes", []):
                val = ch.get("value") or {}
                if val.get("messages"):
                    threading.Thread(target=_process_wa, args=(uid, claw, val), daemon=True).start()
    except Exception as e:
        print(f"[Claw] wa inbound parse error: {e}")
    return "ok", 200
