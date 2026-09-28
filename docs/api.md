# API reference

Every capability in the UI is available over HTTP. All paths below are relative to your backend (for example `http://localhost:5000`) and live under `/api`.

## Authentication

Send `Authorization: Bearer <token>` with every request. Two kinds of token are accepted:

| Token | Get it from | Use it for |
|---|---|---|
| **Firebase ID token** | The Firebase Auth SDK after Google sign-in | The web app and your own browser clients |
| **`kautilya-…` API key** | **Dashboard → Developer API**, or `POST /api/keys/create` | Scripts, servers, IDE agents (Cline, Cursor…) |

API keys are stored hashed. Revoke them with `POST /api/keys/revoke`. The operator's `KAUTILYA_API_KEY` is a master key that acts as `admin` and bypasses metering. Never hand it out.

### Rate limits

| Tier | Developer API | In-app chat |
|---|---|---|
| Free | 10 / min, 100 / day | 5 / min, 30 / day |
| Pro | 60 / min, 10,000 / day | 20 / min, unlimited |

Beyond the daily cap, requests draw from pay-as-you-go credits. Over-limit requests return `429` with a human-readable message.

---

## OpenAI-compatible API

Drop-in for any OpenAI client, IDE agent or proxy.

| Method | Path | |
|---|---|---|
| `GET` | `/api/v1/models` | List available models |
| `POST` | `/api/v1/chat/completions` | Chat completions, streaming or not |

**Models:**

| Model | Best for | Context (free / pro) | Max output |
|---|---|---|---|
| `kautilya-daily` | Fast everyday chat | 32k / 64k | — |
| `kautilya-pro` | Reasoning, analysis, writing | 64k / 128k | 16,384 |
| `kautilya-coder` | Code generation and refactors | 64k / 256k | 32,768 |
| `kautilya-fast` | Lowest latency (Flash-Lite) | 32k | 4,096 |

Supported body fields: `model`, `messages`, `stream`, `max_tokens` / `max_completion_tokens`.

### Python

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:5000/api/v1", api_key="kautilya-...")

resp = client.chat.completions.create(
    model="kautilya-coder",
    messages=[
        {"role": "system", "content": "You are a senior Python reviewer."},
        {"role": "user", "content": "Refactor this into a dataclass: ..."},
    ],
)
print(resp.choices[0].message.content)
```

### Node

```js
import OpenAI from "openai";

const client = new OpenAI({ baseURL: "http://localhost:5000/api/v1", apiKey: "kautilya-..." });
const stream = await client.chat.completions.create({
  model: "kautilya-daily",
  messages: [{ role: "user", content: "Summarise today's standup notes" }],
  stream: true,
});
for await (const part of stream) process.stdout.write(part.choices[0]?.delta?.content ?? "");
```

### Cline, Cursor, Continue

Choose the **OpenAI Compatible** provider, set the base URL to `https://<your-backend>/api/v1`, paste your `kautilya-…` key, and pick `kautilya-coder` as the model.

---

## Chat & research (native)

The native endpoints stream **Server-Sent Events** with richer events than the OpenAI format: thinking, tool steps, citations and verification. The full list is in the [SSE event reference](architecture.md#sse-event-reference).

### `POST /api/jarvis/stream`

`multipart/form-data` or JSON.

| Field | Type | Notes |
|---|---|---|
| `message` | string | The user message |
| `session_id` | string | Conversation id. Reuse it to continue a chat. |
| `model` | string | `auto` (default), `daily`, `pro`, `coder` |
| `max_thinking` | bool | Larger reasoning budget on Pro and Coder |
| `skill` | string | Activate a skill: `ppt-creator`, `frontend-design`, `research-whitepaper`, `diagram-architect`, `data-viz` |
| `files` | file[] | Images, PDFs, spreadsheets, documents |

```bash
curl -N http://localhost:5000/api/jarvis/stream \
  -H "Authorization: Bearer $TOKEN" \
  -F message="Compare Q2 and Q3 revenue from the attached sheet" \
  -F model=pro -F files=@q3.xlsx
```

Related: `POST /api/jarvis/stop` stops a running generation. `GET /api/jarvis/history`, `GET|DELETE /api/jarvis/history/<session_id>` and `POST /api/jarvis/share/<session_id>` handle history and sharing.

### `POST /api/research/stream`

```json
{ "question": "State of UPI credit lines in 2026", "session_id": "…", "depth": "standard", "mode": "research" }
```

`depth` is `quick`, `standard` or `exhaustive`; `mode` is `research` (cited report) or `prd` (product requirements document).

### Background tasks

For jobs that outlive a request:

| Method | Path | |
|---|---|---|
| `POST` | `/api/jarvis/background` | Start a task |
| `GET` | `/api/jarvis/background` | List your tasks |
| `GET` | `/api/jarvis/background/<task_id>` | Status and result |
| `GET` | `/api/jarvis/background/<task_id>/stream` | Live SSE progress |
| `DELETE` | `/api/jarvis/background/<task_id>` | Cancel |

### Code interpreter

`POST /api/code/run` takes `{ "code": "…", "files": [], "timeout": 25 }` and runs Python in a sandbox with a 60-second maximum. The response contains stdout, errors and any charts produced.

### Documents & exports

| Method | Path | |
|---|---|---|
| `POST` | `/api/artifact/create` · `GET /api/artifact/types` | Generate documents, spreadsheets, decks |
| `POST` | `/api/export/pdf` · `/docx` · `/excel` · `/deck` | Export content to files |
| `POST` | `/api/invoice/extract` · `/compute` · `/generate` | GST invoice pipeline |

---

## Agents

| Method | Path | |
|---|---|---|
| `POST` | `/api/agents/create` | Create an agent |
| `GET` | `/api/agents/list` | Your agents |
| `GET` · `PUT` · `DELETE` | `/api/agents/<agent_id>` | Read, update, delete |
| `POST` | `/api/agents/<agent_id>/chat` | Chat with an agent (uses its prompt and knowledge base) |
| `GET` · `POST` | `/api/agents/<agent_id>/logs` | Conversation and call logs |
| `POST` | `/api/agents/<agent_id>/livekit-token` | Token to join a voice room with the agent |
| `GET` · `POST` | `/api/agents/<agent_id>/kb` | List or upload knowledge-base files |
| `POST` | `/api/agents/<agent_id>/kb-url` · `/kb-crawl` | Ingest one URL, or crawl a whole site |
| `DELETE` | `/api/agents/<agent_id>/kb/<file_id>` | Remove a file |

Create body (every field optional except `name`):

```json
{
  "name": "Priya — Inbound Sales",
  "agent_type": "inbound",
  "system_prompt": "You are Priya, a friendly sales rep…",
  "welcome_message": "Namaste! Chai Theory se Priya bol rahi hoon.",
  "language": "hi-IN",
  "model": "kautilya-daily",
  "tts_provider": "cartesia",
  "voice": "shubh",
  "stt_provider": "sarvam",
  "temperature": 0.7,
  "max_tokens": 4096,
  "interruption_mode": "allow",
  "fallback_message": "Sorry, could you say that again?"
}
```

Defaults are shown. `agent_type` is `inbound` or `outbound`, `tts_provider` is `cartesia`, `elevenlabs`, `sarvam` or `revealiq`, `temperature` is clamped to 0–2 and `max_tokens` to 16,384.

## Embed an agent on any website

```bash
curl -X POST http://localhost:5000/api/agents/<agent_id>/embed-token -H "Authorization: Bearer $TOKEN"
```

```html
<script src="https://<your-backend>/api/embed.js"
        data-agent-id="AGENT_ID"
        data-token="EMBED_TOKEN"
        data-position="bottom-right"
        data-theme="dark"
        data-greeting="Hi! How can I help?"
        data-auto-open="false"></script>
```

The widget renders in a Shadow DOM, so it never clashes with your site's CSS. Public widget endpoints: `GET /api/embed/<agent_id>/config`, `POST /api/embed/<agent_id>/chat` and `POST /api/embed/<agent_id>/lead`.

## Leads

| Method | Path | |
|---|---|---|
| `GET` | `/api/leads` | Leads from calls and the widget |
| `PATCH` | `/api/leads/<lead_id>` | Update status or notes |
| `DELETE` | `/api/leads/<lead_id>` | Delete |

## Campaigns (outbound dialer)

| Method | Path | |
|---|---|---|
| `POST` | `/api/campaigns/upload` | Upload a CSV of leads |
| `POST` | `/api/campaigns/create` | Create a campaign for an agent |
| `POST` | `/api/campaigns/<id>/start` · `/resume` | Start dialing |
| `POST` | `/api/campaigns/<id>/stop` · `/pause` | Stop or pause |
| `GET` | `/api/campaigns/<id>/status` | Progress counters |
| `GET` · `DELETE` | `/api/campaigns` · `/api/campaigns/<id>` | List, delete |

## Telephony

| Method | Path | |
|---|---|---|
| `GET` · `POST` | `/api/telephony/config` · `/api/telephony/save` | Your SIP provider settings |
| `GET` | `/api/telephony/inbound-url/<agent_id>` | The URL to paste into your provider for inbound calls |
| `POST` | `/api/telephony/outbound-call` | Place a single outbound call |
| `GET` | `/api/telephony/diagnostic` | Checks that LiveKit and SIP are configured |

## Account, memory & privacy

| Method | Path | |
|---|---|---|
| `GET` · `PUT` | `/api/user/profile` | Profile |
| `GET` · `POST` | `/api/user/settings` | Preferences, personality |
| `GET` · `DELETE` | `/api/memory` | Long-term memory |
| `POST` | `/api/user/consent` | Record age confirmation and consent (DPDP Act 2023) |
| `GET` | `/api/user/my-data` | Export everything stored about you |
| `POST` | `/api/user/data-deletion` | Request erasure |
| `POST` · `GET` · `POST` | `/api/keys/create` · `/api/keys/list` · `/api/keys/revoke` | API keys |
