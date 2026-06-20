# 🦞 KautilyaClaw

**Run [OpenClaw](https://docs.openclaw.ai) entirely on Kautilya AI (by RevealIQ) models — hosted 24/7 on your own server.**

This is the Kautilya equivalent of [KimiClaw](https://github.com/claudedjale/KimiClaw): a thin deploy-wrapper that points OpenClaw's agent runtime at **your** OpenAI-compatible endpoint (`/v1/chat/completions`) instead of Anthropic/OpenAI. Your personal AI agent lives in WhatsApp/Telegram, thinks with **Kautilya Coder / Pro / Daily**, and stays online even when your laptop is off.

```
WhatsApp / Telegram ──▶ KautilyaClaw (OpenClaw, this kit, on a VPS)
                              │  POST /v1/chat/completions  (Bearer kautilya-…)
                              ▼
                     Kautilya backend /v1 ──▶ NVIDIA NIM / Groq
                     (openai_compat_routes.py)   (Kimi K2.6, Nemotron, Mistral)
```

> The bot's brain runs on **your infra**. No Claude key, no OpenAI key. Just your Kautilya models.

---

## Where to host — pick one

| Option | Effort | Best when |
|--------|--------|-----------|
| **Hugging Face Docker Space** → [`huggingface/`](huggingface/README.md) | Lowest (no server to manage) | You already use HF and want it live now. **Start here.** |
| **VPS** (Docker Compose or pm2) — below | Small (a €4/mo box) | You want full sandboxing + always-on, no Space sleeps. |

> ⚠️ HF caveat: Spaces can't run docker-in-docker, so the per-session **sandbox is off** there — safety leans entirely on the allowlists. And free Spaces sleep on inactivity (use an always-on tier for a true 24/7 bot). The `huggingface/` README covers all of this.

---

## What you need

| Thing | Why |
|-------|-----|
| A small **Linux VPS** (Hetzner CX22 ~€4/mo, or Fly/DO/Railway) | OpenClaw needs a persistent process. **Not** the HF Space — that restarts and is ephemeral. |
| Your **Kautilya `/v1` base URL** | e.g. `https://api.kautilya.your-domain.com/v1` (same host the dashboard Developer API uses). |
| The **master `KAUTILYA_API_KEY`** | Authenticates as `uid:"admin"` → **unmetered** (skips the daily Developer-API cap). The agent makes many calls per task, so a normal key would get throttled. |
| A **Telegram bot token** (from [@BotFather](https://t.me/BotFather)) and/or a spare **WhatsApp number** | The channel the bot lives in. |

---

## Quick start — Docker (recommended)

```bash
git clone <your-repo> && cd kautilyaclaw
cp .env.example .env
nano .env                 # fill in KAUTILYA_BASE_URL, KAUTILYA_API_KEY, tokens
docker compose up -d --build
docker compose logs -f    # watch it boot; scan WhatsApp QR here if enabled
```

That's it — the gateway is now running 24/7 (`restart: unless-stopped`) and survives reboots.

## Quick start — bare VPS (no Docker)

```bash
cp .env.example .env
nano .env
bash setup.sh             # installs Node 22, openclaw, pm2; renders config; starts gateway
pm2 logs kautilyaclaw     # tail logs
```

`setup.sh` registers a `pm2 startup` hook, so KautilyaClaw comes back automatically after a reboot.

---

## Connect a channel

### Telegram (easiest)
1. Message [@BotFather](https://t.me/BotFather) → `/newbot` → copy the token into `TELEGRAM_BOT_TOKEN`.
2. Message [@userinfobot](https://t.me/userinfobot) → copy your numeric ID into `TELEGRAM_ALLOW_FROM`.
3. Restart (`docker compose up -d` or `pm2 restart kautilyaclaw`) and DM your bot. Done.

### WhatsApp (QR link)
WhatsApp links by scanning a QR with your phone (WhatsApp → **Linked Devices**):
```bash
# Docker:
docker compose exec kautilyaclaw openclaw channels login whatsapp
# bare VPS:
openclaw channels login whatsapp
```
Scan the QR printed in the terminal. The session is saved in the persisted volume, so you only do this once. Put the numbers allowed to message it in `WHATSAPP_ALLOW_FROM`.

---

## Choosing the model

Edit `agents.defaults.model.primary` in `openclaw.json.template` (then redeploy):

| `primary` value | Backing model | Best for |
|-----------------|---------------|----------|
| `kautilya/kautilya-coder` *(default)* | Kimi K2.6 | Agentic tool-use, coding, multi-step tasks |
| `kautilya/kautilya-pro` | Nemotron Super 120B | Reasoning + extended thinking |
| `kautilya/kautilya-daily` | Mistral Medium 3.5 | Fast everyday chat, lowest latency |

All three are defined in the provider block already — switching is a one-line change.

---

## Cost & limits

- The master key is **unmetered** at the API layer (`uid:"admin"` bypasses `check_developer_api_call`), so the bot never hits the daily Developer-API cap.
- Underlying spend is still your **NVIDIA NIM / Groq** usage — KautilyaClaw doesn't add a markup, it just routes to your existing `/v1`.

## Security notes (read this)

- **Allowlists are on by default.** Telegram `dmPolicy: "allowlist"` + WhatsApp `allowFrom` mean only the IDs/numbers you list can talk to the bot. Don't widen these unless you mean to.
- **The agent can run code/commands.** `agents.defaults.sandbox.mode: "non-main"` runs group/channel sessions in per-session Docker sandboxes. Keep it on. (OpenClaw third-party *skills* have been shown to do data exfiltration via prompt injection — only install skills you trust.)
- **The master key lives on this VPS.** Treat the box like a secret store: firewall the gateway port (`18789`), use SSH keys only, don't expose the dashboard publicly without `OPENCLAW_GATEWAY_TOKEN` + Cloudflare Access / a reverse-proxy auth.
- **`.env` is secrets.** It's gitignored here — never commit the real one.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `Unknown model 'kautilya-coder'` from the backend | `KAUTILYA_BASE_URL` is wrong or missing `/v1`. It must hit `openai_compat_routes.py`. |
| `401 Invalid API key` | `KAUTILYA_API_KEY` isn't the master key (or key is inactive). |
| Bot replies but says it's "Claude/Qwen" | Expected guard: the backend forces the identity to "Kautilya AI by RevealIQ". |
| `openclaw gateway` not found / wrong subcommand | Run `openclaw --help` (or `docker compose run --rm kautilyaclaw openclaw --help`) and set the right command in `docker-compose.yml` `command:` / `setup.sh`. |
| Rate-limit / 429 from backend | You used a normal user key, not the master key — switch to the master (unmetered) key. |
| Bot dies on reboot | bare VPS: re-run the `pm2 startup` line printed by `setup.sh`. Docker: `restart: unless-stopped` handles it. |

---

## What this kit does **not** do (yet)

This is **single-tenant** — one bot, your models, your VPS (exactly like KimiClaw). If you later want **every dashboard user to get their own bot** (multi-tenant SaaS), you'd add: a per-user routing/binding layer, an encrypted per-user credential vault, and per-tenant sandbox containers. That's a separate phase — ask and we'll design it.
