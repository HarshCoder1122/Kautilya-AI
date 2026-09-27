---
title: KautilyaVoice
emoji: 🎙️
colorFrom: indigo
colorTo: purple
sdk: docker
app_port: 7860
---

# Kautilya AI: backend

The Flask API, agent loop and realtime voice worker behind [Kautilya AI](../README.md).

> The front-matter above configures this folder as a Hugging Face **Docker** Space. Keep it if you deploy there.

## Run locally

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium   # optional: Kautilya Computer
cp .env.example .env                    # fill in the "Required" block
python app.py                           # http://localhost:5000
```

Voice agent worker (needs `LIVEKIT_*`):

```bash
python livekit_agent.py start           # or: sh start_worker.sh
```

## Layout

| Path | What |
|---|---|
| `app.py` | Entry point: blueprints, CORS, CSP, MCP boot, schedulers |
| `config.py` | Every environment variable and tier limit |
| `extensions.py` | Firebase Admin, Firestore, Razorpay, rate-limit manager |
| `routes/` | 27 blueprints (chat, research, agents, telephony, billing, integrations…) |
| `services/` | Agent loop, LLM calls, browser, memory, research, email, TTS… |
| `middleware/` | Rate limiting and request security |
| `livekit_agent.py` | LiveKit Agents voice worker |
| `campaign_worker.py` | Outbound dialer |
| `mcp_config.json` | MCP server registry |
| `system_prompts.py`, `skills_spec.py`, `personalities_spec.py`, `tools_spec.py` | Prompts, skills, personalities, tool specs |

## Docs

- [Getting started](../docs/getting-started.md) · [Configuration](../docs/configuration.md) · [Architecture](../docs/architecture.md)
- [API reference](../docs/api.md) · [Voice & telephony](../docs/voice-and-telephony.md) · [Deployment](../docs/deployment.md)
