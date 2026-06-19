"""
Kautilya AI — Transactional Email Service (Resend HTTP API)

Sends lifecycle emails from hello@revealiq.in:
  • welcome           — first time a user signs in
  • pro_upgraded      — user just became Pro
  • pro_demoted       — user lost Pro (cancelled / expired)

All sends are best-effort and run in a background thread so they never
block the request that triggered them. Failures are logged, not raised.

We switched off raw SMTP because most cloud hosts (Render, Heroku, Cloud
Run, App Engine, etc.) block outbound TCP on ports 25 / 465 / 587 to
prevent spam abuse — every Zoho connection attempt timed out from
production. Resend speaks HTTPS on 443 which is always allowed.

Env vars:
  RESEND_API_KEY   (REQUIRED — get from https://resend.com/api-keys)
  RESEND_FROM      (default: "Kautilya AI <hello@revealiq.in>" — the
                    domain part MUST be verified in Resend or sends 403)
  APP_URL          (default: https://ai.revealiq.in — for CTA links)
"""
import os
import time
import threading

import requests


import hashlib

RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
RESEND_FROM    = os.environ.get("RESEND_FROM", "Kautilya AI <hello@revealiq.in>")
APP_URL        = os.environ.get("APP_URL", "https://ai.revealiq.in")


def _unsub_link(uid: str) -> str:
    """Generate an unsubscribe URL for the given uid.
    Token = SHA-256(uid)[:32] — enumerate-resistant, no secret needed (unsubscribing is benign).
    """
    if not uid:
        return f"{APP_URL}/api/user/unsubscribe"
    token = hashlib.sha256(uid.encode()).hexdigest()[:32]
    return f"{APP_URL}/api/user/unsubscribe?token={token}"

_RESEND_ENDPOINT = "https://api.resend.com/emails"

if not RESEND_API_KEY:
    print("[Email] WARNING: RESEND_API_KEY not set — lifecycle emails will be skipped.")

# Resend's free tier allows only 2 requests/second; bursts (e.g. the miss-you
# scheduler emailing many users) get HTTP 429 and silently dropped. Pace every
# send through a process-wide throttle so we stay under the cap. 0.6s spacing ≈
# 1.67 req/s. Override with RESEND_MIN_INTERVAL.
_RESEND_MIN_INTERVAL = float(os.environ.get("RESEND_MIN_INTERVAL", "0.6"))
_rate_lock = threading.Lock()
_last_send_ts = [0.0]


def _throttle():
    with _rate_lock:
        now = time.monotonic()
        wait = _RESEND_MIN_INTERVAL - (now - _last_send_ts[0])
        if wait > 0:
            time.sleep(wait)
        _last_send_ts[0] = time.monotonic()


# ---------- HTML templates ----------
_BASE_CSS = """
  body{margin:0;padding:0;background:#0d1117;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;color:#e6edf3;}
  .wrap{max-width:560px;margin:40px auto;padding:0 20px;}
  .card{background:#161b22;border:1px solid #21262d;border-radius:16px;overflow:hidden;}
  .header{padding:32px 32px 8px 32px;}
  .brand{display:inline-block;padding:6px 12px;border-radius:8px;background:linear-gradient(135deg,#FF6D3F 0%,#FF8A5C 100%);color:#fff;font-weight:700;font-size:12px;letter-spacing:1.5px;text-transform:uppercase;}
  h1{font-size:24px;font-weight:600;margin:18px 0 8px 0;color:#fff;letter-spacing:-0.02em;}
  .sub{color:#8b949e;font-size:14px;line-height:1.6;margin:0;}
  .body{padding:8px 32px 24px 32px;}
  p{color:#c9d1d9;font-size:15px;line-height:1.65;margin:14px 0;}
  .features{margin:20px 0;padding:18px 20px;background:#0d1117;border:1px solid #21262d;border-radius:10px;}
  .features li{color:#c9d1d9;font-size:14px;line-height:1.85;list-style:none;padding-left:24px;position:relative;}
  .features li::before{content:'✓';position:absolute;left:0;color:#3fb950;font-weight:bold;}
  .cta{display:inline-block;margin:24px 0 8px 0;padding:13px 24px;background:#FF6D3F;color:#fff !important;text-decoration:none;border-radius:10px;font-weight:600;font-size:14px;}
  .footer{padding:20px 32px 32px 32px;border-top:1px solid #21262d;color:#6e7681;font-size:12px;line-height:1.6;text-align:center;}
  .footer a{color:#8b949e;text-decoration:none;}
  .accent{color:#FF6D3F;font-weight:600;}
  .badge{display:inline-block;padding:3px 10px;border-radius:999px;background:rgba(255,109,63,0.12);color:#FF6D3F;font-size:11px;font-weight:700;letter-spacing:0.8px;text-transform:uppercase;margin-bottom:12px;}
  .badge-warn{background:rgba(245,158,11,0.12);color:#f59e0b;}
"""

def _shell(title: str, preheader: str, inner_html: str, uid: str = "") -> str:
    unsub = _unsub_link(uid)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{title}</title>
<style>{_BASE_CSS}</style></head>
<body>
<span style="display:none !important;opacity:0;color:transparent;height:0;width:0;overflow:hidden;">{preheader}</span>
<div class="wrap"><div class="card">{inner_html}</div>
<div class="footer">
  You're receiving this from <a href="{APP_URL}">Kautilya AI</a> · operated by Harsh Vardhan (RevealIQ, India) 🇮🇳<br/>
  Need help? Reply to this email or write to <a href="mailto:hello@revealiq.in">hello@revealiq.in</a><br/>
  <a href="{unsub}" style="color:#6e7681;">Unsubscribe from marketing emails</a> ·
  <a href="{APP_URL}/privacy" style="color:#6e7681;">Privacy Policy</a> ·
  <a href="{APP_URL}/terms" style="color:#6e7681;">Terms of Service</a>
</div></div></body></html>"""


def _welcome_html(name: str, uid: str = "") -> str:
    first = (name or "there").split(" ")[0]
    inner = f"""
    <div class="header">
      <span class="brand">Kautilya AI</span>
      <h1>Welcome to Kautilya, {first} 👋</h1>
      <p class="sub">Your AI co-founder for Indian SMEs — chat, voice agents, code, analytics, and more, all under one roof.</p>
    </div>
    <div class="body">
      <p>Thanks for signing up! Your account is live. Here's what you can do right away:</p>
      <ul class="features">
        <li>Chat with <strong>Kautilya Daily, Pro & Coder</strong> models</li>
        <li>Build <strong>voice agents</strong> powered by LiveKit & NVIDIA NIM</li>
        <li>Generate dashboards & analytics from a single CSV upload</li>
        <li>Use the <strong>OpenAI-compatible API</strong> from Cursor, Cline, Continue or your own apps</li>
      </ul>
      <a href="{APP_URL}/dashboard" class="cta">Open my dashboard →</a>
      <p style="font-size:13px;color:#8b949e;margin-top:24px;">Tip: the Free tier includes <span class="accent">30 chats/day</span> and <span class="accent">100 Developer API calls/day</span>. Upgrade to Pro anytime for unlimited in-app chat.</p>
      <p style="font-size:12px;color:#8b949e;margin-top:16px;">All AI responses are generated by large language models — not professional advice. Verify important information independently. <a href="{APP_URL}/terms" style="color:#8b949e;">Terms</a> · <a href="{APP_URL}/privacy" style="color:#8b949e;">Privacy</a></p>
    </div>"""
    return _shell("Welcome to Kautilya AI", f"Welcome aboard {first} — your AI workspace is ready.", inner, uid)


def _pro_upgraded_html(name: str, uid: str = "") -> str:
    first = (name or "there").split(" ")[0]
    inner = f"""
    <div class="header">
      <span class="brand">Kautilya Pro</span>
      <h1>You're now on Kautilya Pro, {first} 👑</h1>
      <p class="sub">Thanks for upgrading. All Pro perks are live on your account right now.</p>
    </div>
    <div class="body">
      <p>Here's what just unlocked for you:</p>
      <ul class="features">
        <li><strong>Unlimited</strong> daily in-app messages</li>
        <li><strong>10,000 Developer API calls/day</strong> (100× the free quota)</li>
        <li>Access to all models — <strong>Kautilya Pro & Coder</strong> with extended thinking</li>
        <li>Higher per-minute rate limits (<strong>20 req/min</strong>)</li>
        <li>PAYG credits cover anything beyond your daily cap</li>
      </ul>
      <a href="{APP_URL}/dashboard" class="cta">Start using Pro →</a>
      <p style="font-size:13px;color:#8b949e;margin-top:24px;">Your subscription renews monthly via Razorpay. Cancel anytime from the Razorpay email or by writing to <a href="mailto:hello@revealiq.in" style="color:#8b949e;">hello@revealiq.in</a>. See our <a href="{APP_URL}/refund" style="color:#8b949e;">Refund Policy</a>.</p>
    </div>"""
    return _shell("You're now on Kautilya Pro", f"Pro is active — unlimited chat and 10,000 API calls/day are unlocked.", inner, uid)


def _pro_demoted_html(name: str, uid: str = "") -> str:
    first = (name or "there").split(" ")[0]
    inner = f"""
    <div class="header">
      <span class="badge badge-warn">Plan change</span>
      <h1>Your Kautilya Pro plan has ended</h1>
      <p class="sub">Hi {first}, your Pro subscription is no longer active and your account has moved back to the Free tier.</p>
    </div>
    <div class="body">
      <p>You can keep using Kautilya AI on the Free tier — here's what stays available:</p>
      <ul class="features">
        <li>30 in-app messages per day</li>
        <li>100 Developer API calls per day</li>
        <li>Kautilya Daily model + voice agents</li>
        <li>Your existing API keys, agents, and chat history</li>
      </ul>
      <p>To restore Pro (unlimited chat, all models, 10,000 API calls/day) you can re-subscribe in one click:</p>
      <a href="{APP_URL}/dashboard/billing" class="cta">Re-subscribe to Pro →</a>
      <p style="font-size:13px;color:#8b949e;margin-top:24px;">If this was unexpected (failed renewal, card issue), just hit reply — we'll sort it out. See our <a href="{APP_URL}/refund" style="color:#8b949e;">Refund Policy</a>.</p>
    </div>"""
    return _shell("Your Kautilya Pro plan has ended", "You've been moved back to the Free tier. Re-subscribe anytime.", inner, uid)


# ---------- Resend HTTP send ----------
def _send_raw(to_email: str, subject: str, html_body: str) -> bool:
    """POST one transactional email via the Resend API. Best-effort: returns
    False on any failure and the caller (a background thread) absorbs it."""
    if not to_email:
        return False
    if not RESEND_API_KEY:
        print("[Email] RESEND_API_KEY not set — skipping send to", to_email)
        return False

    payload = {
        "from": RESEND_FROM,
        "to": [to_email],
        "subject": subject,
        "html": html_body,
    }
    headers = {
        "Authorization": f"Bearer {RESEND_API_KEY}",
        "Content-Type": "application/json",
    }
    # Up to 3 attempts: a 429 (rate limit) is transient, so throttle harder and
    # retry rather than silently dropping the email. Each attempt is paced by
    # the process-wide throttle so we don't exceed Resend's 2 req/s.
    resp = None
    for attempt in range(3):
        _throttle()
        try:
            resp = requests.post(_RESEND_ENDPOINT, json=payload, headers=headers, timeout=15)
        except Exception as e:
            print(f"[Email] Resend request to {to_email} failed: {e}")
            return False

        if 200 <= resp.status_code < 300:
            try:
                msg_id = (resp.json() or {}).get("id", "?")
            except Exception:
                msg_id = "?"
            print(f"[Email] Sent '{subject}' to {to_email} via Resend (id={msg_id})")
            return True

        if resp.status_code == 429 and attempt < 2:
            print(f"[Email] Resend 429 for {to_email} (attempt {attempt + 1}) — backing off")
            time.sleep(1.0 * (attempt + 1))
            continue
        break

    # 4xx (non-429): usually domain not verified, invalid From, or bad API key.
    # 5xx / exhausted 429: Resend hiccup — a single miss isn't worth a queue.
    print(f"[Email] Resend rejected send to {to_email}: "
          f"HTTP {resp.status_code} — {resp.text[:300]}")
    return False


def _send_async(to_email: str, subject: str, html_body: str):
    t = threading.Thread(target=_send_raw, args=(to_email, subject, html_body), daemon=True)
    t.start()


def _miss_you_html(name: str, uid: str = "") -> str:
    first = (name or "there").split(" ")[0]
    inner = f"""
    <div class="header">
      <span class="brand">Kautilya AI</span>
      <h1>We miss you, {first} 👋</h1>
      <p class="sub">It's been a couple of days — your AI workspace is waiting for you.</p>
    </div>
    <div class="body">
      <p>You left some interesting conversations unfinished. Come back and let Kautilya help you with whatever's on your plate today:</p>
      <ul class="features">
        <li>Ask <strong>Kautilya Pro</strong> to reason through a hard problem</li>
        <li>Build or tweak a <strong>voice agent</strong> for your team</li>
        <li>Run <strong>deep research</strong> on a market or competitor</li>
        <li>Generate a report, deck, or doc in seconds</li>
      </ul>
      <a href="{APP_URL}" class="cta">Jump back in →</a>
      <p style="font-size:13px;color:#8b949e;margin-top:24px;">
        You're on the <span class="accent">Free tier</span> — 30 chats/day, no credit card needed.
        Upgrade to Pro for unlimited access.
      </p>
    </div>"""
    return _shell("Kautilya misses you 👋", f"Hey {first}, come back — your AI workspace is waiting.", inner, uid)


# ---------- Public API ----------
def send_welcome_email(email: str, name: str = "", uid: str = ""):
    """Transactional — always sent (no marketing opt-in required)."""
    if not email: return
    _send_async(email, "Welcome to Kautilya AI 🇮🇳", _welcome_html(name, uid))


def send_pro_upgraded_email(email: str, name: str = "", uid: str = ""):
    """Transactional — always sent."""
    if not email: return
    _send_async(email, "You're now on Kautilya Pro 👑", _pro_upgraded_html(name, uid))


def send_pro_demoted_email(email: str, name: str = "", uid: str = ""):
    """Transactional — always sent."""
    if not email: return
    _send_async(email, "Your Kautilya Pro plan has ended", _pro_demoted_html(name, uid))


def send_miss_you_email(email: str, name: str = "", uid: str = ""):
    """Marketing re-engagement — only sent if user has opted in (or has not explicitly opted out).
    The scheduler already filters by welcomed_at; this function does not re-check opt-in
    so as not to require a DB call in the hot path, but the opt-in flag is checked in app.py scheduler.
    """
    if not email: return
    _send_async(email, "We miss you at Kautilya AI 👋", _miss_you_html(name, uid))
