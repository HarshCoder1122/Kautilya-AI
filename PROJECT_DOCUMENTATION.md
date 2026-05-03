# Kautilya AI — Developer Documentation

> Strategic AI platform with chat, voice agents, deep research, code interpreter,
> embeddable widgets, and an OpenAI-compatible API. Built by RevealIQ.
>
> Base URL (production): `https://ai.revealiq.in`

A live HTML version of this page is served at **`/docs`** inside the app —
with a one-click **"Copy for AI"** button that puts the entire API surface onto
your clipboard so you can paste it into ChatGPT/Claude/Cursor and ask them to
write an integration for you.

---

## 0. Quick-start tutorials (start here)

### 0.1 Get an API key (3 clicks)

1. Open **[ai.revealiq.in](https://ai.revealiq.in/)** → sign in with Google.
2. Click your avatar in the sidebar → **Settings → API Keys**.
3. Click **"Generate New Key"**, give it a name (e.g. *"My Laptop"*), copy the
   `kautilya-...` value shown in the popup — **this is the only time it is
   shown**. Store it in your password manager or `.env`.

```bash
# Linux / macOS
export KAUTILYA_API_KEY="kautilya-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

# Windows PowerShell
$env:KAUTILYA_API_KEY = "kautilya-xxxx..."
```

**Verify it works:**

```bash
curl -H "Authorization: Bearer $KAUTILYA_API_KEY" https://ai.revealiq.in/v1/models
```

You should see `kautilya-daily`, `kautilya-pro`, and `kautilya-coder`.

---

### 0.2 Use the API from Python (30 seconds)

```python
# pip install openai
from openai import OpenAI
import os

client = OpenAI(
    base_url="https://ai.revealiq.in/v1",
    api_key=os.environ["KAUTILYA_API_KEY"],
)

stream = client.chat.completions.create(
    model="kautilya-pro",                             # or kautilya-coder / kautilya-daily
    messages=[{"role": "user", "content": "Draft a 2-line pitch for an Indian fintech SME."}],
    stream=True,
    extra_body={"max_thinking": True},                # enable reasoning channel
)

for chunk in stream:
    delta = chunk.choices[0].delta
    if delta.content:
        print(delta.content, end="", flush=True)
```

---

### 0.3 Use Kautilya inside Cline / Continue / Cursor

Kautilya's `/v1` endpoints are **fully OpenAI-compatible**, so any tool that
accepts a custom OpenAI base URL works.

**Cline (VS Code extension):**

1. Install **Cline** from the VS Code marketplace.
2. Open Cline settings (gear icon in the sidebar).
3. Provider: **OpenAI Compatible**.
4. Base URL: `https://ai.revealiq.in/v1`
5. API Key: your `kautilya-...` key.
6. Model ID: `kautilya-coder` (recommended) or `kautilya-pro`.
7. Save. Cline now uses Kautilya for code generation + refactors.

**Continue (VS Code / JetBrains):**

`~/.continue/config.json`:

```json
{
  "models": [{
    "title": "Kautilya Coder",
    "provider": "openai",
    "model": "kautilya-coder",
    "apiBase": "https://ai.revealiq.in/v1",
    "apiKey": "kautilya-xxxx..."
  }]
}
```

**Cursor:** Settings → Models → Add custom model → provider `OpenAI`, base URL
`https://ai.revealiq.in/v1`, API key `kautilya-...`, model name `kautilya-coder`.

**LiteLLM / any other OpenAI SDK:** use the same base URL + key.

---

### 0.4 Create your first voice/chat agent (dashboard)

1. Go to **[Dashboard](https://ai.revealiq.in/dashboard) → Agents**.
2. Click **"New Agent"**. Fill in:
   - **Name**: e.g. *"Sales SDR — India SaaS"*
   - **System prompt**: what this agent does, tone, rules. Keep ~200–500 words.
   - **Welcome message**: first thing the caller / visitor hears.
   - **Model**: `kautilya-pro` for quality, `kautilya-daily` for speed/cost.
   - **Voice**: pick from the preview list (optional; only for voice).
   - **Language**: `en-IN`, `hi-IN`, or any supported locale.
   - **Agent type**: `inbound` / `outbound` / `web`.
3. Click **Create**. You'll land on the Agent Studio where you can tweak
   everything further.

---

### 0.5 Create an agent via the API

```python
import os, requests

API = "https://ai.revealiq.in"
H = {"Authorization": f"Bearer {os.environ['KAUTILYA_API_KEY']}",
     "Content-Type": "application/json"}

payload = {
    "name": "Support Bot",
    "system_prompt": (
        "You are Support Bot for Acme Corp. Be patient, acknowledge the issue "
        "first, then solve. If the user is angry, de-escalate. "
        "Never promise refunds — route those to a human."
    ),
    "welcome_message": "Hi! I'm from Acme support. What's going on today?",
    "model": "kautilya-pro",
    "language": "en",
    "agent_type": "web",
    "temperature": 0.6,
    "max_tokens": 1024,
}
r = requests.post(f"{API}/api/agents/create", headers=H, json=payload)
agent_id = r.json()["agent_id"]
print("Created:", agent_id)
```

---

### 0.6 Put the agent on your website

From the dashboard:

1. **Dashboard → Embed on Web**.
2. Pick the agent, choose brand color + allowed origins
   (e.g. `https://acme.com, *.acme.com` or `*` for any).
3. Click **"Generate embed token"**.
4. **Copy** the `<script>` tag it produces and paste it before `</body>` on
   your site.

From the API:

```python
import os, requests
API = "https://ai.revealiq.in"
H = {"Authorization": f"Bearer {os.environ['KAUTILYA_API_KEY']}",
     "Content-Type": "application/json"}

r = requests.post(
    f"{API}/api/agents/{agent_id}/embed-token",
    headers=H,
    json={"allowed_origins": ["https://acme.com", "*.acme.com"]},
)
print(r.json()["script_tag"])
```

The widget:
- Floats as a chat bubble in the corner of your site.
- Streams responses from your agent's configured model + system prompt.
- After ~2 assistant turns, asks visitors for name/email/phone.
- Leads appear on **Dashboard → Leads** and (optionally) get forked to a
  webhook (`lead_webhook_url` on the agent — Zapier, Slack, your CRM).

---

### 0.7 Wire lead webhooks (Zapier / Slack / CRM)

Set `lead_webhook_url` on the agent — every captured lead POSTs there:

```python
requests.post(f"{API}/api/agents/{agent_id}/update", headers=H,
              json={"lead_webhook_url": "https://hooks.zapier.com/hooks/catch/xxxx/yyyy/"})
```

The payload is:

```json
{
  "id": "lead_xxxx", "uid": "agent-owner-uid",
  "agent_id": "...", "name": "...", "email": "...", "phone": "...",
  "message": "last conversation transcript (truncated)",
  "source": "https://acme.com/pricing", "status": "new",
  "created_at": 1730000000
}
```

---

### 0.8 Run a bulk outbound campaign

```python
# 1. Upload leads + create campaign
r = requests.post(f"{API}/api/campaigns/create", headers=H, json={
    "agent_id": agent_id,
    "name": "Oct outreach — EdTech",
    "leads": [
        {"phone": "+919876543210", "name": "Ravi"},
        {"phone": "+919123456789", "name": "Priya"},
    ],
})
camp_id = r.json()["campaign_id"]

# 2. Start dialing
requests.post(f"{API}/api/campaigns/{camp_id}/start", headers=H)
```

The `campaign_worker.py` daemon picks it up and dials through your configured
telephony provider (Vobiz or Exotel — set up under **Telephony**).

---

### 0.9 Cheat-sheet

| I want to…                               | Go to                                    |
|------------------------------------------|------------------------------------------|
| Chat with Kautilya in browser            | `/` (the chat UI)                        |
| Use Kautilya from my code                | `/v1/chat/completions` with API key      |
| Build a voice/chat agent                 | Dashboard → **Agents**                   |
| Put an agent on my website               | Dashboard → **Embed on Web**             |
| See captured leads                       | Dashboard → **Leads**                    |
| Dial hundreds of leads automatically     | Dashboard → **Campaigns**                |
| Connect HubSpot / Salesforce / WhatsApp  | Dashboard → **Integrations**             |
| Regenerate my API key                    | Dashboard → **Settings → API Keys**      |
| Upgrade plan                             | Dashboard → **Billing**                  |
| Read this documentation                  | `/docs` (with **Copy for AI** button)    |

---

## 1. Authentication

All authenticated API calls use an **`Authorization: Bearer <token>`** header.
Two token types are accepted:

| Token format                | Obtain from                        | Intended for                 |
|-----------------------------|------------------------------------|------------------------------|
| Firebase ID token           | Browser (Firebase Auth SDK)        | Dashboard + chat UI          |
| `kautilya-...` API key      | Dashboard → Settings → API Keys    | Server scripts, Cline, Cursor |

The `kautilya-` keys also work against the OpenAI-compatible `/v1/*` endpoints.

---

## 2. Model catalog

Kautilya routes each request to one of three frontier backends:

| Alias               | Underlying model                       | Best for                       |
|---------------------|----------------------------------------|---------------------------------|
| `kautilya-daily`    | Llama-3.3-70B (Groq)                   | Fast chat, short answers        |
| `kautilya-pro`      | Nemotron-3-Super-120B (NVIDIA NIM)     | Strategic reasoning, analysis   |
| `kautilya-coder`    | DeepSeek-V4-Pro (NVIDIA NIM)           | Code generation, refactoring    |

Both `kautilya-pro` and `kautilya-coder` support a **Max Thinking** toggle.
Enable via:

```json
{ "extra_body": { "max_thinking": true } }
```

The `auto` model ID triggers our multi-agent orchestrator — requests are
routed to a Researcher / Coder / Sales / Support / General agent based on
intent.

---

## 3. Chat APIs

### 3.1 Streaming chat

```
POST /api/jarvis/stream       (multipart/form-data OR JSON)
```

| Field           | Type           | Notes |
|-----------------|----------------|-------|
| `message`       | string         | User message (or `text`) |
| `session_id`    | string         | Persistent session id (generated if missing) |
| `model`         | `daily` \| `pro` \| `coder` \| `auto` | Default `daily` |
| `max_thinking`  | `"1"` / `"0"`  | Enables reasoning channel on Pro/Coder |
| `files`         | file[]         | PDFs, CSVs, images — auto-parsed |

**Response:** `text/event-stream`. Each `data:` line is a JSON event:

```json
{"chunk": "hello"}                        # content delta
{"thinking": "Let me plan..."}             # reasoning delta (if max_thinking)
{"thinking_done": true}                    # reasoning finished
{"tool_calls": [...]}                      # OpenAI-style tool calls
{"event": "agent", "agent": "coder", ...}  # auto-router decision
{"type": "status", "message": "Searching..."}
```

### 3.2 OpenAI-compatible (for Cline, Continue, Cursor, LiteLLM, OpenAI SDK)

```
POST /v1/chat/completions
GET  /v1/models
```

Same shape as OpenAI. Auth: `Authorization: Bearer kautilya-...`.

```python
from openai import OpenAI
client = OpenAI(base_url="https://ai.revealiq.in/v1", api_key="kautilya-...")
stream = client.chat.completions.create(
    model="kautilya-coder",
    messages=[{"role": "user", "content": "Write a Python FastAPI to-do app."}],
    stream=True,
    extra_body={"max_thinking": True},
)
for chunk in stream:
    delta = chunk.choices[0].delta
    if delta.content: print(delta.content, end="")
```

### 3.3 Deep Research

```
POST /api/research/stream     { "question": "..." }
```

SSE events:
```
{"event": "query",   "queries": ["..."]}
{"event": "sources", "sources": [{"title", "url", "snippet", "site"}]}
{"event": "chunk",   "chunk": "..."}
{"event": "done"}
```

### 3.4 Background tasks (long-running)

```
POST   /api/jarvis/background              {prompt, model?, max_thinking?}
GET    /api/jarvis/background              list
GET    /api/jarvis/background/<id>         status + result
GET    /api/jarvis/background/<id>/stream  live SSE
DELETE /api/jarvis/background/<id>         cancel
```

### 3.5 Code Interpreter

```
POST /api/code/run       { "code": "...", "files"?: [{name, content_b64}] }
```

Returns `stdout`, `stderr`, `figures: [base64 PNG]`, `exit_code`, `duration_ms`.
Allowed imports: `numpy`, `pandas`, `matplotlib`, `seaborn`, `scipy`, `sklearn`,
`requests`, most stdlib. Blocked: `subprocess`, `socket`, `ctypes`,
`multiprocessing`, `pickle`, `marshal`, etc.

---

## 4. Agents API

```
POST   /api/agents/create                  { name, system_prompt, model, voice, ... }
GET    /api/agents/list
GET    /api/agents/<id>
POST   /api/agents/<id>/update             (or PUT /api/agents/<id>)
POST   /api/agents/<id>/delete             (or DELETE /api/agents/<id>)
POST   /api/agents/<id>/chat               streaming chat with this specific agent
GET    /api/agents/<id>/logs               call logs / analytics
GET    /api/agents/<id>/kb                 knowledge base files
POST   /api/agents/<id>/kb                 upload a file
POST   /api/agents/<id>/kb-url             index a URL
DELETE /api/agents/<id>/kb/<file_id>       remove a KB file
POST   /api/agents/<id>/call-outbound      { phone } — trigger outbound call
POST   /api/agents/<id>/embed-token        { allowed_origins? } — rotate embed
```

---

## 5. Embed your agent on any website

Every agent can be exposed as a floating chat bubble on your own website.

1. Go to **Dashboard → Embed on Web**.
2. Pick an agent, choose brand color + allowed origins, click **Generate embed token**.
3. Copy the snippet it produces. Paste it just before `</body>` on your site:

```html
<script src="https://ai.revealiq.in/embed.js"
        data-agent="AGENT_ID"
        data-token="kte_XXXX"
        data-primary="#FF6D3F"
        data-position="bottom-right"></script>
```

Behaviour:

- Floating bubble in the chosen corner.
- Opens a chat panel with the agent's welcome message.
- Streams replies via `/embed/<agent_id>/chat`.
- After a couple of turns, prompts visitor for name / email / phone.
- Submissions hit `/embed/<agent_id>/lead` and appear on your **Leads** page.
- Optionally fanned out to any `lead_webhook_url` set on the agent (Zapier / Slack / your CRM).

### Public embed endpoints

```
GET  /embed.js
GET  /embed/<agent_id>/config?token=...
POST /embed/<agent_id>/chat              SSE stream
POST /embed/<agent_id>/lead              lead capture
```

---

## 6. Leads

```
GET    /api/leads                         list your leads
PATCH  /api/leads/<id>    { status? , notes? , score? }
DELETE /api/leads/<id>
```

Statuses: `new`, `contacted`, `qualified`, `lost`.

---

## 7. Campaigns (bulk outbound dialer)

```
GET    /api/campaigns
POST   /api/campaigns/create              { agent_id, leads: [{phone, name?}] }
POST   /api/campaigns/<id>/start
POST   /api/campaigns/<id>/pause
POST   /api/campaigns/<id>/resume
DELETE /api/campaigns/<id>
```

A background worker (`campaign_worker.py`) polls Firestore and dials at the
configured pacing.

---

## 8. Telephony (Vobiz / Exotel)

```
GET    /api/telephony/config              your saved provider credentials
POST   /api/telephony/save                { exotel: {...}, vobiz: {...} }
```

Outbound calls flow: Dashboard → `/api/agents/<id>/call-outbound` →
`services/telephony_dialer.py` → provider SIP trunk → LiveKit agent worker.

---

## 9. Integrations

```
GET    /api/integrations                       list + connected status
GET    /api/integrations/<provider>/connect    OAuth start (returns redirect_url)
GET    /api/integrations/<provider>/callback   OAuth callback
POST   /api/integrations/<provider>/save       manual API key save
POST   /api/integrations/<provider>/disconnect
POST   /api/integrations/whatsapp/send         { to, message }
POST   /api/integrations/slack/post            { message }
POST   /api/integrations/calendar/event        { title, start, end, attendees? }
POST   /api/integrations/zapier/trigger        { hook_url, payload }
POST   /api/integrations/followup/extract      { transcript } → action items
POST   /api/integrations/followup/dispatch     { action_items[] }
```

Providers: `hubspot`, `salesforce`, `zoho`, `google_calendar`, `whatsapp`, `slack`, `zapier`.

---

## 10. User / Billing / Keys

```
GET  /api/jarvis/status                       tier, usage, limits
GET  /api/user/profile
POST /api/user/profile                        { displayName, preferences }

GET  /api/billing/config
POST /api/billing/create-order                Razorpay order for Pro
POST /api/billing/verify-payment
GET  /api/billing/transactions

POST /api/keys/create                         { name }
GET  /api/keys/list
POST /api/keys/revoke                         { key_hash }
```

---

## 11. Tiers & Rate limits

| Tier   | Messages/day | LLM tokens/day | TTS chars/day | Models              |
|--------|--------------|----------------|---------------|----------------------|
| Guest  | 10           | —              | —             | Daily                |
| Free   | 30           | 10,000         | 5,000         | Daily                |
| Pro    | unlimited    | 1,000,000      | 500,000       | All + Coder + Max Thinking |

---

## 12. Architecture overview

```
Browser / Cline ─┐
 Dashboard  ─────┤     Flask (Gunicorn)      ┌─→ NVIDIA NIM (Nemotron, DeepSeek-V4)
 Embed JS   ─────┤  ┌───────────────────┐   ├─→ Groq (Llama 3.3)
                 ├─▶│ routes/           │   ├─→ Gemini Vision
 /v1/*      ─────┤  │ services/         │───┤
 Webhooks   ─────┘  │ orchestrator      │   ├─→ SerpAPI / Google / Wikipedia
                    │ code_interpreter  │   ├─→ Vobiz / Exotel SIP
                    │ research_service  │   └─→ LiveKit (voice runtime)
                    └───────┬───────────┘
                            │
                     Firestore (chats, agents, leads, campaigns, keys, billing)
```

---

## 13. Source layout

```
app.py                       Flask entry; blueprint registry; CORS; CSP
config.py                    Env vars; CSP; rate-limit matrix
system_prompts.py            Tier-specific prompt overlays (Daily / Pro / Coder / Research)
system_prompt_cloud.txt      Master prompt (identity + rules)

routes/
  chat_routes.py             /api/jarvis/stream, /api/chat
  openai_compat_routes.py    /v1/chat/completions, /v1/models
  background_routes.py       /api/jarvis/background*
  code_routes.py             /api/code/run
  research_routes.py         /api/research/stream
  embed_routes.py            /embed.js, /embed/<id>/*, /api/leads/*
  integrations_routes.py     /api/integrations/*
  agents_routes.py           /api/agents/*
  campaigns_routes.py        /api/campaigns/*
  telephony_routes.py        /api/telephony/*, outbound dial
  billing_routes.py          /api/billing/*
  keys_routes.py             /api/keys/*
  user_routes.py             /api/user/*
  voice_routes.py            /api/voice/*  (TTS / STT bridges)
  webhooks_routes.py         SIP / provider inbound hooks
  static_routes.py           /, /dashboard, /playground

services/
  llm_service.py             NVIDIA + Groq + OpenRouter unified calls
  agent_loop_service.py      Agent loop (think → act → observe)
  orchestrator_service.py    Multi-agent intent routing
  code_interpreter_service.py Sandboxed Python runner
  research_service.py        Perplexity-style deep research
  memory_service.py          Long-term memory + RAG
  vector_store_service.py    Gemini-embedding-backed vector store
  command_service.py         Legacy bracket-command executor (CLI only)
  tts_service.py             Edge-TTS voice mapping
  telephony_dialer.py        Vobiz + Exotel outbound dial
  auth_service.py            Firebase + API-key verification

static/
  index.html                 Premium chat UI
  script-premium.js          Chat SPA (thinking, tools, research, code runner)
  style-premium.css          Chat CSS tokens + responsive rules
  embed.js                   Drop-in widget (Shadow DOM)
  dashboard-v2/              Built Vue 3 SPA (from dashboard-app/)

dashboard-app/               Vue 3 + Vite + Pinia + Tailwind
```

---

## 14. Getting help for your integration

**Copy for AI** (button available at `/docs`) copies this whole document plus
the list of endpoints onto your clipboard in a format optimised for pasting
into ChatGPT / Claude / Cursor / Cline. Ask the AI something like:

> "Given the Kautilya docs I just pasted, write a Python script that creates an
> agent called 'Support Bot', enables embedding, and prints the snippet."

— and you'll get working code back.

Maintained by **Harsh Vardhan · RevealIQ Industries**.
