# Configuration

Kautilya is configured entirely through environment variables. Nothing secret lives in the code.

- **Backend:** copy [`backend/.env.example`](../backend/.env.example) to `backend/.env`. `config.py` loads it with `python-dotenv` at startup.
- **Frontend:** copy [`frontend/.env.example`](../frontend/.env.example) to `frontend/.env`. `REACT_APP_*` values are baked in at build time; the others are read by `server.js` at runtime.

Only three backend variables are required. Everything else turns on a feature, and a missing key disables that feature with a one-line note in the startup log instead of crashing.

> [!WARNING]
> Every `REACT_APP_*` variable ends up in the public JavaScript bundle. Never put a secret there.

---

## Required

| Variable | Description |
|---|---|
| `FLASK_SECRET_KEY` | Signs Flask sessions. Any long random string. |
| `GOOGLE_VERTEX_CREDENTIALS_JSON` | Service-account JSON (one line) with the **Vertex AI User** role. Runs every chat tier. Leave empty locally to use `gcloud auth application-default login`. |
| `FIREBASE_SERVICE_ACCOUNT_JSON` | Firebase Admin service account, as JSON or a file path. Verifies ID tokens and connects Firestore. (`FIREBASE_SERVICE_ACCOUNT` is accepted as a legacy alias by the workers.) |

### Vertex AI

| Variable | Default | Description |
|---|---|---|
| `VERTEX_PROJECT_ID` | project of the service account | Override the Google Cloud project |
| `VERTEX_LOCATION` | `global` | `global` is required for the Gemini 3.x family |

The model behind each tier is defined in `services/agent_loop_service.py`:

| Tier / API model | Primary | Fallback |
|---|---|---|
| `kautilya-daily` | Gemini 3.6 Flash | Gemini 2.5 Flash |
| `kautilya-pro` | Gemini 3.1 Pro | Gemini 2.5 Pro |
| `kautilya-coder` | Gemini 3.1 Pro | Gemini 2.5 Pro |
| `kautilya-fast` | Gemini 3.5 Flash-Lite | Gemini 2.5 Flash-Lite |

## Model providers

| Variable | Used for |
|---|---|
| `GROQ_API_KEY` (+ `_BACKUP`, `_3`…`_5`) | Whisper speech-to-text, the voice-agent fallback LLM, Truth Lens cross-checks. Extra keys rotate on rate limits. |
| `NVIDIA_NIM_API_KEY`, `NVIDIA_NIM_BASE_URL`, `EMBED_MODEL` | Knowledge-base embeddings (default model `baai/bge-m3`) |
| `NVIDIA_API_KEY` (+ `_BACKUP`, `_3`…`_5`) | NVIDIA NIM text models used by some legacy paths |
| `GEMINI_API_KEY` | AI Studio key for vision, the vector store and Gemini Live voice |
| `GEMINI_LIVE_MODEL` | Realtime model for voice agents (default `gemini-3.1-flash-live-preview`) |
| `OPENROUTER_API_KEY` | Last-resort fallback router |
| `NIM_ANALYTICS_MODEL`, `NIM_ANALYTICS_FALLBACK_MODEL` | Post-call analysis models |
| `RESEARCH_PLANNER_MODEL`, `RESEARCH_SYNTH_MODEL`, `RESEARCH_SYNTH_FALLBACK_MODEL`, `RESEARCH_SYNTH_RETRY_BACKOFF` | Deep Research planner and synthesiser overrides |
| `RESEARCH_SECOND_PASS` | `1` (default) runs a second search round for better recall |
| `RESEARCH_QUERIES_R1`, `RESEARCH_FOLLOWUPS`, `RESEARCH_PER_QUERY`, `RESEARCH_PER_DOMAIN`, `RESEARCH_MAX_SOURCES` | Deep Research breadth: first-round queries, follow-ups, results per query, results per domain, total sources (defaults 6 / 5 / 6 / 3 / 12) |
| `RESEARCH_DOC_CHARS`, `RESEARCH_FETCH_TIMEOUT`, `RESEARCH_DEADLINE_S` | Characters kept per source, per-fetch timeout, overall deadline (defaults 3000 / 7 s / 540 s) |
| `RESEARCH_CONTINUATIONS`, `RESEARCH_SYNTH_TOKENS`, `RESEARCH_SYNTH_RETRIES` | Report length and retry budget (defaults 2 / 12000 / 2) |
| `AGENT_MAX_TURNS_DEFAULT`, `AGENT_MAX_TURNS_CODER` | Maximum tool-chaining turns per answer (defaults 80 / 200) |
| `LLM_CB_FAILURE_THRESHOLD`, `LLM_CB_COOLDOWN_SECONDS` | Circuit breaker: failures before a provider is skipped, and for how long |
| `LLM_MEMCACHE_MAX` | Size of the in-memory response cache (default 500) |
| `TRUTH_LENS` | `1` (default) enables cross-model answer verification |
| `ANSWER_SIZE_CLASSIFIER` | `1` enables an extra call that sizes answers to the question (default off) |

## Search & maps

| Variable | Description |
|---|---|
| `SERPAPI_API_KEY` | Web search for chat and Deep Research |
| `TAVILY_API_KEY` | Second search provider, queried in parallel and merged |
| `OMDB_API_KEY` | Movie lookups |
| `MAPPLS_CLIENT_ID`, `MAPPLS_CLIENT_SECRET` | Mappls (MapmyIndia) REST search and geocoding. Without them, maps fall back to OpenStreetMap. |
| `MAPPLS_MAP_SDK_KEY`, `MAPPLS_REST_KEY`, `MAPPLS_API_KEY` | Browser map SDK key and routing key (both fall back to `MAPPLS_API_KEY`) |

## Kautilya Computer (live browser)

Requires `pip install playwright && python -m playwright install chromium`. The Docker image does this for you.

| Variable | Default | Description |
|---|---|---|
| `BROWSER_MAX_SESSIONS` | `2` | Concurrent browser sessions per worker |
| `BROWSER_SESSION_TTL_S` | `1800` | Idle seconds before a session is closed |

## Voice, TTS & STT

| Variable | Description |
|---|---|
| `SARVAM_API_KEY` | Sarvam TTS/STT for Indian languages |
| `CARTESIA_API_KEY`, `ELEVENLABS_API_KEY` | Hosted TTS providers |
| `REVEALIQ_TTS_URL` | Base URL of your Kokoro TTS engine ([`RevealIQ ASR models/`](../RevealIQ%20ASR%20models)) |
| `STT_SPACE_BASE` | Base URL of your Nemotron STT engine ([`voicerecog/`](../voicerecog)) |
| `REVEALIQ_HF_TOKEN` / `HF_TOKEN` | Bearer token for those engines when hosted as private Hugging Face Spaces |

### LiveKit & telephony

| Variable | Description |
|---|---|
| `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET` | Your LiveKit Cloud (or self-hosted) project |
| `LIVEKIT_SIP_URI` | Your project's **SIP domain**, e.g. `abc123.sip.livekit.cloud`. This is a different host from `LIVEKIT_URL`. |
| `LIVEKIT_OUTBOUND_TRUNK_ID` | Outbound SIP trunk used for campaign and test calls |
| `LIVEKIT_AGENT_NAME` | Worker name for explicit agent dispatch |
| `LIVEKIT_NUM_IDLE` | Warm idle worker processes (default `2`) |
| `LIVEKIT_SIP_DIRECT_DISPATCH` | `true` dispatches inbound SIP calls straight to the named agent |
| `FREE_OUTBOUND_CALL_LIMIT` | Outbound calls allowed on the free tier (default `5`) |
| `WEBHOOK_SECRET` | Shared secret appended to the Vobiz / Exotel answer and events webhook URLs. Set it, or anyone could hit those endpoints. |
| `VOBIZ_MASTER_USER`, `VOBIZ_MASTER_PASS`, `VOBIZ_MASTER_NUMBER` | Master Vobiz account for test calls from Agent Studio |
| `CAMPAIGN_CONCURRENCY`, `CAMPAIGN_GLOBAL_MAX`, `CAMPAIGN_DIAL_PACING`, `CAMPAIGN_POLL_INTERVAL` | Outbound dialer tuning (`campaign_worker.py`) |

## Billing & email

| Variable | Description |
|---|---|
| `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET` | Razorpay API credentials |
| `RAZORPAY_WEBHOOK_SECRET` | Verifies `payment.captured` webhooks |
| `RAZORPAY_PRO_PLAN_ID`, `PRO_PRICE_INR` | Pro plan and its price (default ₹599) |
| `RESEND_API_KEY`, `RESEND_FROM`, `RESEND_MIN_INTERVAL` | Transactional email: welcome and re-engagement mails |
| `APP_URL` | Link used inside emails |
| `EMAIL_TEST_TOKEN` | Protects the email test endpoint |

## Integrations & MCP

| Variable | Description |
|---|---|
| `<PROVIDER>_CLIENT_ID`, `<PROVIDER>_CLIENT_SECRET` | OAuth app per provider, e.g. `HUBSPOT_`, `SALESFORCE_`, `SLACK_`, `GITHUB_`, `NOTION_` |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | One app for Gmail, Calendar, Drive, Sheets, Tasks, Docs, Contacts, YouTube |
| `MICROSOFT_CLIENT_ID`, `MICROSOFT_CLIENT_SECRET` | One app for Outlook, OneDrive, Teams |
| `CENTRAL_DOMAIN` (or `OAUTH_REDIRECT_DOMAIN`) | Public host that receives `/api/integrations/<id>/callback` |
| `MCP_DISABLED` | `true` skips all MCP servers |
| `MCP_ENABLED_SERVERS`, `MCP_SKIP_SERVERS` | Comma-separated allowlist / blocklist of keys from `mcp_config.json` |
| `MCP_SERVER_START_TIMEOUT`, `MCP_INIT_JITTER_MAX` | Startup tuning |

See [integrations.md](integrations.md) for the OAuth callback URLs and MCP setup.

## Firebase web config (optional)

The frontend normally reads its Firebase config from `REACT_APP_FIREBASE_*`. The backend can also serve it at `GET /api/config/firebase`:

| Variable | Description |
|---|---|
| `FIREBASE_PROJECT_ID` | Defaults to the `project_id` in the service account |
| `FIREBASE_AUTH_HOST` | Host proxied for `/__/auth/*` (default `https://<project>.firebaseapp.com`). Needed when your auth domain is your own domain. |
| `FIREBASE_API_KEY`, `FIREBASE_AUTH_DOMAIN`, `FIREBASE_STORAGE_BUCKET`, `FIREBASE_MESSAGING_SENDER_ID`, `FIREBASE_APP_ID` | Web config values |

## Server & admin

| Variable | Default | Description |
|---|---|---|
| `PORT` | `5000` (`app.py`), `7860` (`start.sh`) | Listen port |
| `GUNICORN_WORKERS`, `GUNICORN_THREADS` | `12`, `32` | Concurrency for `start.sh`. SSE streaming is I/O-bound, so threads matter most. |
| `ALLOWED_ORIGINS` | | Extra CORS origins for `/api/*`, comma-separated |
| `PUBLIC_BASE_URL` | auto on HF Spaces | Public URL of the backend, used to build webhook URLs |
| `KAUTILYA_API_KEY` | | Master API key. Authenticates as `admin` on `/api/v1/*` and is **unmetered**. Keep it secret. |
| `ADMIN_SECRET_KEY` | | Protects admin endpoints |
| `KT_FIG_DIR`, `KT_MAX_FIGS` | | Where the code interpreter saves charts, and how many per run |
| `CLAW_PUBLIC_BASE` | | Public URL used when wiring KautilyaClaw Telegram/WhatsApp webhooks |
| `DISABLE_WARMUP`, `WARMUP_INTERVAL_SEC`, `VOICE_SPACE_URL`, `WARMUP_EXTRA_URLS`, `WARMUP_LOCK_PATH` | | Keep-warm pings for sleeping Spaces |

## Tier limits

Message and API limits live in `backend/config.py`:

| Tier | In-app messages | Developer API calls |
|---|---|---|
| Guest | 2 / min, 10 / day | none |
| Free | 5 / min, 30 / day | 10 / min, 100 / day |
| Pro | 20 / min, unlimited / day | 60 / min, 10,000 / day |

Developer API calls beyond the daily cap fall through to pay-as-you-go credits (`DEVELOPER_API_PAYG_PRICE`). Use `backend/manage_user_tier.py` to promote a user to Pro by hand.

---

## Frontend variables

| Variable | When | Description |
|---|---|---|
| `REACT_APP_API_URL` | build | Backend URL. Leave empty when Flask serves the build (same origin). |
| `REACT_APP_FIREBASE_API_KEY`, `_AUTH_DOMAIN`, `_PROJECT_ID`, `_STORAGE_BUCKET`, `_MESSAGING_SENDER_ID`, `_APP_ID`, `_MEASUREMENT_ID` | build | Firebase web app config |
| `REACT_APP_FIREBASE_CONFIG` | build | Alternative: the whole config object as one JSON string |
| `REACT_APP_HF_API_TOKEN` | build | ⛔ **Don't set this in a public build.** It would ship your Hugging Face token to every visitor. Use `HF_TOKEN` with `server.js` instead. |
| `BACKEND_URL` | runtime | Where `server.js` proxies `/api/*` |
| `HF_TOKEN` | runtime | Added server-side as `Authorization` when the backend is a private HF Space |
| `PORT` | runtime | `server.js` listen port (default `8000`) |
