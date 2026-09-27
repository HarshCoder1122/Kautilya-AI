# Getting started

This guide takes you from a fresh clone to a working Kautilya on `localhost`. Expect about 20 minutes, most of it spent creating cloud credentials.

## 1. Prerequisites

| Tool | Version | Notes |
|---|---|---|
| Python | 3.11 | The production image uses `python:3.11-slim` |
| Node.js | 20 or newer | Builds the React app; also runs `npx`-based MCP servers |
| Git | any | |
| ffmpeg | optional | Needed by the voice agent worker for audio processing |

You also need two cloud projects. Both have free tiers that are enough for development:

- **Firebase**, for sign-in (Google provider) and Firestore, where chats, agents, leads and settings live.
- **Google Cloud with Vertex AI enabled**, which runs every chat model (Gemini). It can be the same Google Cloud project that backs Firebase.

## 2. Create the cloud credentials

### Firebase

1. Create a project at [console.firebase.google.com](https://console.firebase.google.com).
2. **Authentication → Sign-in method** → enable **Google**. Under **Settings → Authorized domains**, make sure `localhost` is listed.
3. **Firestore Database** → create a database in production mode.
4. **Project settings → General → Your apps** → add a **Web app**. Copy the config object. These are your `REACT_APP_FIREBASE_*` values.
5. **Project settings → Service accounts** → **Generate new private key**. This JSON file is your `FIREBASE_SERVICE_ACCOUNT_JSON`.

> [!IMPORTANT]
> The service-account JSON is a real secret. Keep it out of git; `.gitignore` already blocks common file names. The web config from step 4 is public by design.

### Vertex AI

1. In [Google Cloud console](https://console.cloud.google.com), open the project and enable the **Vertex AI API**.
2. **IAM & Admin → Service accounts** → create one with the **Vertex AI User** role → **Keys → Add key → JSON**.
3. That JSON is your `GOOGLE_VERTEX_CREDENTIALS_JSON`. The project ID is read from it automatically.

For local development only, you can skip the key and run `gcloud auth application-default login`. The backend then falls back to Application Default Credentials.

## 3. Run the backend

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m playwright install chromium   # optional: Kautilya Computer's live browser
cp .env.example .env
```

Open `backend/.env` and fill in the **Required** block:

```ini
FLASK_SECRET_KEY=<python -c "import secrets;print(secrets.token_hex(32))">
GOOGLE_VERTEX_CREDENTIALS_JSON={"type":"service_account","project_id":"…", …}
FIREBASE_SERVICE_ACCOUNT_JSON={"type":"service_account","project_id":"…", …}
```

Paste each JSON on a single line. You can also give a file path for `FIREBASE_SERVICE_ACCOUNT_JSON`.

Start the API:

```bash
python app.py        # http://localhost:5000
```

The startup log prints one line per subsystem, for example `Firebase Admin: OK`, `Firestore: Connected`, and a warning for each optional provider without a key. Those warnings are expected.

## 4. Run the frontend

In a second terminal:

```bash
cd frontend
npm install --legacy-peer-deps
cp .env.example .env
```

Fill in `frontend/.env`:

```ini
REACT_APP_API_URL=http://localhost:5000
REACT_APP_FIREBASE_API_KEY=…
REACT_APP_FIREBASE_AUTH_DOMAIN=your-project.firebaseapp.com
REACT_APP_FIREBASE_PROJECT_ID=your-project
REACT_APP_FIREBASE_STORAGE_BUCKET=your-project.firebasestorage.app
REACT_APP_FIREBASE_MESSAGING_SENDER_ID=…
REACT_APP_FIREBASE_APP_ID=…
```

```bash
npm run dev          # http://localhost:3000, hot reload
```

Open http://localhost:3000, sign in with Google, accept the consent screen, and send your first message.

## 5. Production-style single server (optional)

Flask can serve the compiled React app itself, which is how the Docker image runs:

```bash
cd frontend && npm run build     # postbuild copies build/ → backend/static/
cd ../backend && python app.py   # now http://localhost:5000 serves the UI too
```

## 6. Turn on more features

Each optional block in `backend/.env.example` unlocks something. Common next steps:

| I want… | Add | Guide |
|---|---|---|
| Web search in answers | `SERPAPI_API_KEY` (and optionally `TAVILY_API_KEY`) | [configuration.md](configuration.md#search--maps) |
| Knowledge-base embeddings | `NVIDIA_NIM_API_KEY` | [configuration.md](configuration.md#model-providers) |
| Browser voice chat | `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET` | [voice-and-telephony.md](voice-and-telephony.md) |
| Agents on a phone number | LiveKit + a Vobiz or Exotel SIP trunk | [voice-and-telephony.md](voice-and-telephony.md#3-phone-numbers-sip) |
| Gmail, Calendar, HubSpot… | `<PROVIDER>_CLIENT_ID` / `_SECRET` | [integrations.md](integrations.md) |
| Paid plans | `RAZORPAY_*` | [configuration.md](configuration.md#billing--email) |

## Troubleshooting

| Symptom | Fix |
|---|---|
| Login popup closes and nothing happens | Add your host to Firebase **Authorized domains**, and check the `REACT_APP_FIREBASE_*` values |
| Browser console: `REACT_APP_FIREBASE_* env vars are not set` | `frontend/.env` is missing or you didn't restart `npm run dev` after editing it |
| Chat replies with a model or permission error | The Vertex service account needs the **Vertex AI User** role, and the Vertex AI API must be enabled |
| `401` on every API call | The frontend is calling a different backend than you think. Check `REACT_APP_API_URL` |
| CORS error from a custom domain | Add the origin to `ALLOWED_ORIGINS` (comma-separated) in `backend/.env` |
| Kautilya Computer says the browser is unavailable | Run `python -m playwright install chromium` inside the backend venv |
