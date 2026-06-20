---
title: KautilyaClaw
emoji: 🦞
colorFrom: indigo
colorTo: blue
sdk: docker
app_port: 18789
pinned: false
short_description: OpenClaw running on Kautilya AI models, 24/7 on a HF Space
---

# 🦞 KautilyaClaw on Hugging Face Spaces

Runs [OpenClaw](https://docs.openclaw.ai) on **Kautilya AI (RevealIQ) models** as a 24/7 **Docker Space** — no VPS needed. Your personal agent lives in Telegram/WhatsApp and thinks with Kautilya Coder/Pro/Daily via your `/v1` endpoint.

> Run this as its **own** Space — separate from the Kautilya backend Space (that one runs Flask; this one runs the OpenClaw gateway).

## Deploy (≈5 min)

1. **Create a new Space** → SDK: **Docker** → Blank.
2. Copy the contents of this `huggingface/` folder into the Space repo root:
   - `Dockerfile`, `entrypoint.sh`, `openclaw.json.template`, and this `README.md`.
3. **Space Settings → Variables and secrets → New secret**, add:

   | Secret | Value |
   |--------|-------|
   | `KAUTILYA_BASE_URL` | `https://<your-kautilya-backend>/v1` |
   | `KAUTILYA_API_KEY` | the **master** key (unmetered, `uid:"admin"`) |
   | `OPENCLAW_GATEWAY_TOKEN` | `openssl rand -hex 32` |
   | `TELEGRAM_BOT_TOKEN` | from [@BotFather](https://t.me/BotFather) |
   | `TELEGRAM_ALLOW_FROM` | your numeric Telegram id ([@userinfobot](https://t.me/userinfobot)) |
   | `WHATSAPP_ALLOW_FROM` | your number, country code, no `+` (only if using WhatsApp) |

4. The Space builds and boots. Open the Space URL → OpenClaw dashboard (protected by `OPENCLAW_GATEWAY_TOKEN`).
5. **Telegram:** just DM your bot — it works immediately (long-polling, no webhook).
6. **WhatsApp:** open the Space → **Logs**, run a login from the dashboard/terminal and scan the QR. *Enable persistent storage first (below) or you'll re-scan after every restart.*

## HF-specific notes (important)

- **Sandbox is OFF.** HF Spaces can't run docker-in-docker, so per-session sandboxing is disabled (`sandbox.mode: "off"`). **Safety = the allowlists.** Keep `TELEGRAM_ALLOW_FROM` / `WHATSAPP_ALLOW_FROM` tight — only you.
- **Persistent storage** (Settings → add persistent storage, ~$ small/mo) mounts at `/data`. With it, WhatsApp login + memory survive restarts. Without it, state is **ephemeral** — fine for Telegram, annoying for WhatsApp.
- **Telegram is the recommended channel on HF** — zero saved-state, survives sleeps/restarts.
- **Keep the Space awake.** Free Spaces sleep on inactivity → bot goes offline. Use an upgraded/always-on Space (or the same tier your backend Space uses) for a true 24/7 bot.
- **Bind:** the container sets `OPENCLAW_GATEWAY_BIND=custom:0.0.0.0` and listens on `18789` (matches `app_port` above) so HF can route to it.

## Switch model
Edit `openclaw.json.template` → `agents.defaults.model.primary`:
`kautilya/kautilya-coder` (default, agentic) · `kautilya/kautilya-pro` (reasoning) · `kautilya/kautilya-daily` (fast). Commit → Space rebuilds.

---

See the parent [`kautilyaclaw/README.md`](../README.md) for the VPS/Docker-Compose path and full architecture.
