# Deployment

A production Kautilya is up to five independently deployable pieces. Only the first is mandatory.

| Component | Required | Runs on |
|---|---|---|
| [Backend](#backend) (API + UI) | ✅ | Any Docker host: Hugging Face Space, Koyeb, Render, Cloud Run, a VM |
| [Frontend server](#frontend) | optional | Node host (Koyeb, Render, Vercel-style) when you don't want Flask serving the UI |
| [Voice agent worker](#voice-agent-worker) | for voice | Any always-on Python host near your LiveKit region |
| [Speech engines](#speech-engines) | optional | CPU Docker Spaces |
| [KautilyaClaw](#kautilyaclaw) | optional | Docker Compose or an HF Space |

---

## Backend

`backend/Dockerfile` builds a production image based on `python:3.11-slim`. It includes:

- ffmpeg and Noto/DejaVu fonts, for document and PDF generation
- Node 20 plus the GitHub and sequential-thinking MCP servers
- Chromium and its system libraries, for Kautilya Computer
- a non-root `user` (uid 1000), as Hugging Face requires

`start.sh` starts the campaign worker in the background, then Gunicorn with `gthread` workers on `$PORT` (default `7860`).

### 1. Build the UI into the image

Flask serves the React build from `backend/static/`. That folder is generated, not committed, so build it first:

```bash
cd frontend
npm install --legacy-peer-deps
REACT_APP_FIREBASE_API_KEY=… REACT_APP_FIREBASE_AUTH_DOMAIN=… \
REACT_APP_FIREBASE_PROJECT_ID=… REACT_APP_FIREBASE_APP_ID=… \
REACT_APP_FIREBASE_MESSAGING_SENDER_ID=… REACT_APP_FIREBASE_STORAGE_BUCKET=… \
npm run build            # postbuild copies build/ → ../backend/static/
```

Leave `REACT_APP_API_URL` empty so the app calls its own origin.

### 2. Run the container

```bash
cd backend
docker build -t kautilya-backend .
docker run -p 7860:7860 --env-file .env kautilya-backend
```

`.dockerignore` keeps `.env`, service-account files and virtualenvs out of the image. Pass secrets at runtime.

### Hugging Face Spaces

1. Create a Space with the **Docker** SDK. `backend/README.md` already carries the front-matter (`sdk: docker`, `app_port: 7860`).
2. Push the contents of `backend/`, including the built `static/` folder.
3. Add every secret under **Settings → Variables and secrets**, never in files. `GOOGLE_VERTEX_CREDENTIALS_JSON` and `FIREBASE_SERVICE_ACCOUNT_JSON` go in as one-line JSON.
4. `PUBLIC_BASE_URL` is detected automatically from the Space name, and webhook URLs are built from it.

> [!TIP]
> A private Space needs an HF token on every request. Put the frontend server (below) in front of it with `HF_TOKEN`, rather than baking a token into the React build.

### Koyeb, Render, Cloud Run, a VM

Deploy the same image. The platform's `PORT` is honoured, and `Procfile` (`web: sh start.sh`) works on buildpack platforms. Size Gunicorn with `GUNICORN_WORKERS` and `GUNICORN_THREADS`. Chat streaming is I/O-bound, so threads matter more than workers.

### Checklist

- [ ] `FLASK_SECRET_KEY` is set. Without it, sessions reset on every restart.
- [ ] Your domain is in `ALLOWED_ORIGINS` and in Firebase **Authorized domains**.
- [ ] If your Firebase auth domain is your own domain, `/__/auth/*` is proxied to `FIREBASE_AUTH_HOST`. The default derives from your project ID.
- [ ] Webhooks can reach you: `PUBLIC_BASE_URL`, Razorpay webhook → `/api/billing/razorpay-webhook`, telephony → [voice guide](voice-and-telephony.md).
- [ ] `WEBHOOK_SECRET` is set if you use telephony.
- [ ] `KAUTILYA_API_KEY` (the unmetered master key) is either unset or known only to you.

## Frontend

The simplest setup is to let the backend serve the UI (above). To host the frontend separately, `frontend/server.js` is an Express server that:

- serves `build/` with long-lived caching for hashed assets, and never caches `index.html` or `sw.js`
- proxies `/api/*` to `BACKEND_URL`, streaming SSE through unbuffered
- adds `Authorization: Bearer $HF_TOKEN` server-side for private HF Space backends
- proxies `/__/*` to Firebase Auth when `REACT_APP_FIREBASE_PROJECT_ID` is set
- pings the backend periodically so a sleeping Space stays warm

```bash
cd frontend
npm run build
BACKEND_URL=https://your-backend.example.com HF_TOKEN=hf_… PORT=8000 npm start
```

`frontend/koyeb.yaml` and `frontend/deploy_frontend.sh` are starting points for Koyeb.

## Voice agent worker

`livekit_agent.py` has to run continuously wherever it can reach LiveKit and Firestore. It uses the backend's environment.

```bash
cd backend
sh start_worker.sh      # two self-restarting `python livekit_agent.py start` loops
```

A second Docker Space or container built from `backend/`, with `CMD ["sh", "start_worker.sh"]`, works well. Scale by running more replicas. LiveKit load-balances jobs across workers. See [voice-and-telephony.md](voice-and-telephony.md).

## Speech engines

| Engine | Folder | Endpoint | Point the backend at it with |
|---|---|---|---|
| Kokoro TTS (English, Hindi) | [`RevealIQ ASR models/`](../RevealIQ%20ASR%20models) | `/v1/audio/speech`, `/v1/audio/stream` | `REVEALIQ_TTS_URL` |
| Nemotron streaming STT | [`voicerecog/`](../voicerecog) | `/v1/audio/transcriptions` | `STT_SPACE_BASE` |

Each folder is a complete Docker Space: its README front-matter, Dockerfile and model-caching script are included. Push the folder to a new **Docker** Space. A free CPU instance is enough. If the Space is private, set `REVEALIQ_HF_TOKEN`.

Free Spaces sleep when idle. The backend's warm-up service pings `STT_SPACE_BASE` and `VOICE_SPACE_URL` every `WARMUP_INTERVAL_SEC`; disable it with `DISABLE_WARMUP=1`.

## KautilyaClaw

Follow [`kautilyaclaw/README.md`](../kautilyaclaw/README.md) for a VPS (Docker Compose) or [`kautilyaclaw/huggingface/`](../kautilyaclaw/huggingface/README.md) for a Space. It needs your backend's `/api/v1` base URL and an API key.

## Upgrading

```bash
git pull
cd frontend && npm install --legacy-peer-deps && npm run build
cd ../backend && pip install -r requirements.txt
# then redeploy the backend image and restart the voice worker
```

There are no database migrations. Firestore documents are schemaless, and the code tolerates missing fields.
