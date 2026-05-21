"""
Kautilya AI — Transactional Email Service (Zoho SMTP)

Sends lifecycle emails from hello@revealiq.in:
  • welcome           — first time a user signs in
  • pro_upgraded      — user just became Pro
  • pro_demoted       — user lost Pro (cancelled / expired)

All sends are best-effort and run in a background thread so they never
block the request that triggered them. Failures are logged, not raised.

Env vars:
  ZOHO_SMTP_HOST       (default: smtp.zoho.in)
  ZOHO_SMTP_PORT       (default: 587 — STARTTLS)
  ZOHO_SMTP_USER       (default: hello@revealiq.in)
  ZOHO_SMTP_PASSWORD   (REQUIRED — Zoho app-specific password)
  ZOHO_FROM_NAME       (default: Kautilya AI)
  APP_URL              (default: https://ai.revealiq.in — for CTA links)
"""
import os
import smtplib
import threading
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr


SMTP_HOST = os.environ.get("ZOHO_SMTP_HOST", "smtp.zoho.in")
SMTP_PORT = int(os.environ.get("ZOHO_SMTP_PORT", "587"))
SMTP_USER = os.environ.get("ZOHO_SMTP_USER", "hello@revealiq.in")
SMTP_PASS = os.environ.get("ZOHO_SMTP_PASSWORD", "")
FROM_NAME = os.environ.get("ZOHO_FROM_NAME", "Kautilya AI")
APP_URL = os.environ.get("APP_URL", "https://ai.revealiq.in")


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

def _shell(title: str, preheader: str, inner_html: str) -> str:
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{title}</title>
<style>{_BASE_CSS}</style></head>
<body>
<span style="display:none !important;opacity:0;color:transparent;height:0;width:0;overflow:hidden;">{preheader}</span>
<div class="wrap"><div class="card">{inner_html}</div>
<div class="footer">
  You're receiving this from <a href="{APP_URL}">Kautilya AI</a> · made by RevealIQ in India 🇮🇳<br/>
  Need help? Reply to this email or write to <a href="mailto:hello@revealiq.in">hello@revealiq.in</a>
</div></div></body></html>"""


def _welcome_html(name: str) -> str:
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
    </div>"""
    return _shell("Welcome to Kautilya AI", f"Welcome aboard {first} — your AI workspace is ready.", inner)


def _pro_upgraded_html(name: str) -> str:
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
      <p style="font-size:13px;color:#8b949e;margin-top:24px;">Your subscription renews monthly via Razorpay. Cancel anytime from the Razorpay email or by writing to us.</p>
    </div>"""
    return _shell("You're now on Kautilya Pro", f"Pro is active — unlimited chat and 10,000 API calls/day are unlocked.", inner)


def _pro_demoted_html(name: str) -> str:
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
      <p style="font-size:13px;color:#8b949e;margin-top:24px;">If this was unexpected (failed renewal, card issue), just hit reply — we'll sort it out.</p>
    </div>"""
    return _shell("Your Kautilya Pro plan has ended", "You've been moved back to the Free tier. Re-subscribe anytime.", inner)


# ---------- SMTP send ----------
def _send_raw(to_email: str, subject: str, html_body: str) -> bool:
    if not to_email:
        return False
    if not SMTP_PASS:
        print("[Email] ZOHO_SMTP_PASSWORD not set — skipping send")
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = formataddr((FROM_NAME, SMTP_USER))
        msg["To"] = to_email
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as s:
            s.ehlo()
            s.starttls()
            s.ehlo()
            s.login(SMTP_USER, SMTP_PASS)
            s.sendmail(SMTP_USER, [to_email], msg.as_string())
        print(f"[Email] Sent '{subject}' to {to_email}")
        return True
    except Exception as e:
        print(f"[Email] Send to {to_email} failed: {e}")
        return False


def _send_async(to_email: str, subject: str, html_body: str):
    t = threading.Thread(target=_send_raw, args=(to_email, subject, html_body), daemon=True)
    t.start()


# ---------- Public API ----------
def send_welcome_email(email: str, name: str = ""):
    if not email: return
    _send_async(email, "Welcome to Kautilya AI 🇮🇳", _welcome_html(name))


def send_pro_upgraded_email(email: str, name: str = ""):
    if not email: return
    _send_async(email, "You're now on Kautilya Pro 👑", _pro_upgraded_html(name))


def send_pro_demoted_email(email: str, name: str = ""):
    if not email: return
    _send_async(email, "Your Kautilya Pro plan has ended", _pro_demoted_html(name))
