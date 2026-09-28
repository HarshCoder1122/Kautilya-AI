"""
Kautilya AI — Centralized Configuration
All environment variables, constants, and runtime settings.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ============== Paths ==============
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# HF Spaces specific: Try to use /tmp if /app/chat_data is not writable
CHAT_DATA_DIR = os.path.join(BASE_DIR, 'chat_data')
try:
    os.makedirs(CHAT_DATA_DIR, exist_ok=True)
    # Test writability
    test_file = os.path.join(CHAT_DATA_DIR, '.write_test')
    with open(test_file, 'w') as f: f.write('test')
    os.remove(test_file)
except Exception:
    CHAT_DATA_DIR = '/tmp/chat_data'
    os.makedirs(CHAT_DATA_DIR, exist_ok=True)
    print(f"[CONFIG] Read-only filesystem detected. Using {CHAT_DATA_DIR} for volatile storage.")

STATIC_FOLDER = os.path.join(BASE_DIR, 'static')

# ============== Flask ==============
FLASK_SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", os.urandom(24).hex())

# ============== API Keys ==============
# SECURITY: All keys MUST come from environment variables. No hardcoded defaults.
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
SERPAPI_API_KEY = os.environ.get("SERPAPI_API_KEY", "")
# Optional second web-search provider, queried IN PARALLEL with SerpAPI and
# merged (services/research_service.py::_search_round) — pure recall/quality
# upside. Fully optional: absent key = today's SerpAPI-only behavior.
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")
MAPPLS_API_KEY = os.environ.get("MAPPLS_API_KEY", "")
# ── Mappls (MapmyIndia) — maps, nearby search, routing ──
# Mappls splits credentials by product:
#   • CLIENT_ID / CLIENT_SECRET → OAuth token for the REST search/geocode APIs
#     (atlas.mappls.com). Without these, nearby/geocode fall back to OSM.
#   • MAP_SDK_KEY → the public JS Map SDK key the browser loads (domain-locked,
#     safe to expose). Falls back to MAPPLS_API_KEY.
#   • REST_KEY → the URL-path key for advancedmaps routing. Falls back to
#     MAPPLS_API_KEY.
# Everything degrades gracefully to free OpenStreetMap services if unset, so the
# map feature always works — Mappls just makes India results/looks much better.
MAPPLS_CLIENT_ID = os.environ.get("MAPPLS_CLIENT_ID", "")
MAPPLS_CLIENT_SECRET = os.environ.get("MAPPLS_CLIENT_SECRET", "")
MAPPLS_MAP_SDK_KEY = os.environ.get("MAPPLS_MAP_SDK_KEY", "") or MAPPLS_API_KEY
MAPPLS_REST_KEY = os.environ.get("MAPPLS_REST_KEY", "") or MAPPLS_API_KEY
if not (MAPPLS_CLIENT_ID and MAPPLS_CLIENT_SECRET):
    print("[CONFIG] Note: MAPPLS_CLIENT_ID/SECRET not set — maps will use OpenStreetMap fallback for nearby/geocode")
SARVAM_API_KEY = os.environ.get("SARVAM_API_KEY", "")
NVIDIA_API_KEY = os.environ.get("NVIDIA_API_KEY", "")
_NVIDIA_API_KEYS_RAW = [
    os.environ.get("NVIDIA_API_KEY", ""),
    os.environ.get("NVIDIA_API_KEY_BACKUP", ""),
    os.environ.get("NVIDIA_API_KEY_3", ""),
    os.environ.get("NVIDIA_API_KEY_4", ""),
    os.environ.get("NVIDIA_API_KEY_5", ""),
]
NVIDIA_API_KEYS = [k for k in _NVIDIA_API_KEYS_RAW if k]
if not NVIDIA_API_KEY:
    print("[CONFIG] WARNING: NVIDIA_API_KEY not set — Pro/Coder models will fall back to Groq Llama")

# ============== TTS Provider Keys ==============
REVEALIQ_HF_TOKEN = os.environ.get("REVEALIQ_HF_TOKEN", "")
# Base URL of the self-hosted TTS engine (see "RevealIQ ASR models/")
REVEALIQ_TTS_URL = os.environ.get("REVEALIQ_TTS_URL", "https://HarshSharma1212-RevealIQ-ASR.hf.space").rstrip("/")
CARTESIA_API_KEY = os.environ.get("CARTESIA_API_KEY", "")
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")

if not REVEALIQ_HF_TOKEN:
    print("[CONFIG] WARNING: REVEALIQ_HF_TOKEN not set — RevealIQ TTS disabled")

# Startup warnings for missing critical keys
if not OPENROUTER_API_KEY:
    print("[CONFIG] WARNING: OPENROUTER_API_KEY not set — OpenRouter fallback disabled")
if not GROQ_API_KEY:
    print("[CONFIG] WARNING: GROQ_API_KEY not set — primary LLM disabled")

# ============== Groq Multi-Key Rotation ==============
_groq_keys_raw = [
    os.environ.get("GROQ_API_KEY", ""),
    os.environ.get("GROQ_API_KEY_BACKUP", ""),
    os.environ.get("GROQ_API_KEY_3", ""),
    os.environ.get("GROQ_API_KEY_4", ""),
    os.environ.get("GROQ_API_KEY_5", ""),
]
GROQ_API_KEYS = [k for k in _groq_keys_raw if k]
GROQ_COOLDOWN_SECONDS = 60

print(f"[CONFIG] Loaded {len(GROQ_API_KEYS)} Groq API key(s)")

# ============== Gemini Keys ==============
# SECURITY FIX: Removed hardcoded Gemini key — must be set in environment
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
if not GEMINI_API_KEY:
    print("[CONFIG] WARNING: GEMINI_API_KEY not set — Gemini/VectorStore disabled")
GEMINI_API_KEYS = [GEMINI_API_KEY] if GEMINI_API_KEY else []

# ============== Vertex AI (Gemini) — primary chat/completion provider ==============
# All Daily/Pro/Coder chat completions run through Vertex AI Gemini models
# (services/llm_service.py::call_vertex_gemini). NVIDIA NIM and Groq are no
# longer used for chat text generation — only for embeddings (NVIDIA NIM,
# services/embedding_service.py) and speech-to-text (Groq Whisper,
# routes/voice_routes.py), which are separate capabilities left untouched.
#
# Credentials: prefer a full service-account JSON in GOOGLE_VERTEX_CREDENTIALS_JSON
# (set as an HF Space "secret" so it never touches the git-tracked repo or the
# deployed filesystem) and build credentials in-memory. Local dev without that
# env var falls back to Application Default Credentials (e.g. a
# GOOGLE_APPLICATION_CREDENTIALS file path, or `gcloud auth application-default login`).
VERTEX_PROJECT_ID = os.environ.get("VERTEX_PROJECT_ID", "")
# "global" is required for the newest Gemini 3.x model family — the older
# 2.5 generation is regional (e.g. us-central1) but also reachable via global.
VERTEX_LOCATION = os.environ.get("VERTEX_LOCATION", "global")
VERTEX_CREDENTIALS_JSON = os.environ.get("GOOGLE_VERTEX_CREDENTIALS_JSON", "")
VERTEX_CREDENTIALS = None
if VERTEX_CREDENTIALS_JSON:
    try:
        import json as _json
        from google.oauth2 import service_account as _service_account
        VERTEX_CREDENTIALS = _service_account.Credentials.from_service_account_info(
            _json.loads(VERTEX_CREDENTIALS_JSON),
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
        print("[CONFIG] Vertex AI credentials loaded from GOOGLE_VERTEX_CREDENTIALS_JSON")
        # No explicit project → use the one the service account belongs to
        if not VERTEX_PROJECT_ID:
            VERTEX_PROJECT_ID = _json.loads(VERTEX_CREDENTIALS_JSON).get("project_id", "")
    except Exception as _e:
        print(f"[CONFIG] WARNING: failed to parse GOOGLE_VERTEX_CREDENTIALS_JSON: {_e}")
if not VERTEX_CREDENTIALS:
    print("[CONFIG] GOOGLE_VERTEX_CREDENTIALS_JSON not set — Vertex AI will fall back to "
          "Application Default Credentials (fine for local dev, must be set in production)")

# ============== System Prompts ==============
# Import advanced tier-based system prompts
from system_prompts import (
    DAILY_SYSTEM_PROMPT,
    PRO_SYSTEM_PROMPT,
    CODER_SYSTEM_PROMPT_PRO,
    RESEARCH_SYSTEM_PROMPT,
    AGENT_PERSONALITIES,
    get_system_prompt
)

# Legacy support — default to daily tier
SYSTEM_PROMPT = DAILY_SYSTEM_PROMPT
CODER_SYSTEM_PROMPT = CODER_SYSTEM_PROMPT_PRO

# NOTE: system_prompt_cloud.txt is already loaded by system_prompts.py as the
# MASTER prompt and composed with the per-tier overlays. Do NOT re-read it here
# and overwrite SYSTEM_PROMPT — that used to silently drop Daily's tool, diagram
# and question-card overlays (the file always exists, so the "optional override"
# always fired). Edit the .txt to change the master; edit system_prompts.py to
# change a tier.

# ============== Constants ==============
MAX_HISTORY = 20
CONVERSATION_TTL = 3600  # 1 hour
MAX_KEYS_PER_USER = 5
MAX_AGENTS_FREE = 1
MAX_AGENTS_PRO = 5
MAX_MEMORIES = 50
API_KEY_PREFIX = "kautilya-"
# Free users get this many lifetime outbound MOBILE (test) calls before PRO is
# required. Web/browser calls (LiveKit) stay free. PRO = unlimited.
FREE_OUTBOUND_CALL_LIMIT = int(os.environ.get("FREE_OUTBOUND_CALL_LIMIT", "5"))

# ============== Rate Limits ==============
API_RATE_LIMITS = {
    "free": {"llm_tokens": 1000000, "tts_chars": 500000, "stt_seconds": 6000, "max_tokens": 2048},
    "pro":  {"llm_tokens": 10000000, "tts_chars": 5000000, "stt_seconds": 6000, "max_tokens": 16384},
}

_MESSAGE_RATE_LIMITS = {
    "guest":  {"per_minute": 2,  "per_day": 10},
    "free":   {"per_minute": 5,  "per_day": 30},
    "pro":    {"per_minute": 20, "per_day": None},  # in-app: unlimited for Pro
}

# Developer API (/api/v1/chat/completions) — third-party tools like Cline.
# These caps are separate from the in-app chat caps above.
# Beyond the daily cap the request falls through to PAYG credits.
_DEVELOPER_API_LIMITS = {
    # Caps measured in API CALLS per day (not tokens). Beyond the daily cap
    # the request falls through to PAYG credits at DEVELOPER_API_PAYG_PRICE.
    "free": {"per_minute": 10, "per_day": 100},
    "pro":  {"per_minute": 60, "per_day": 10000},
}
DEVELOPER_API_PAYG_PRICE = 1.00  # INR per API call after daily cap

# ============== Edge TTS Voice Mapping ==============
EDGE_TTS_VOICES = {
    'en': 'en-IN-PrabhatNeural',
    'hi': 'hi-IN-MadhurNeural',
    'bn': 'bn-IN-BashkarNeural',
    'ta': 'ta-IN-ValluvarNeural',
    'te': 'te-IN-MohanNeural',
    'mr': 'mr-IN-ManoharNeural',
    'gu': 'gu-IN-NiranjanNeural',
    'kn': 'kn-IN-GaganNeural',
    'ml': 'ml-IN-MidhunNeural',
    'pa': 'pa-IN-GurpreetNeural',
}

# ============== Razorpay ==============
RAZORPAY_KEY_ID = os.environ.get('RAZORPAY_KEY_ID', '')
RAZORPAY_KEY_SECRET = os.environ.get('RAZORPAY_KEY_SECRET', '')
RAZORPAY_WEBHOOK_SECRET = os.environ.get('RAZORPAY_WEBHOOK_SECRET', '')
RAZORPAY_PRO_PLAN_ID = os.environ.get('RAZORPAY_PRO_PLAN_ID', 'plan_JarvisPro599')

# ============== LiveKit ==============
LIVEKIT_URL = os.environ.get("LIVEKIT_URL", "")
LIVEKIT_API_KEY = os.environ.get("LIVEKIT_API_KEY", "")
LIVEKIT_API_SECRET = os.environ.get("LIVEKIT_API_SECRET", "")

# SIP URI — must match your LiveKit Cloud project's SIP domain
# (e.g. "<id>.sip.livekit.cloud"). The project URL and the SIP domain are
# DIFFERENT hosts — do NOT derive this from LIVEKIT_URL.
LIVEKIT_SIP_URI = os.environ.get('LIVEKIT_SIP_URI', '')

# ============== Firebase ==============
# Project ID comes from FIREBASE_PROJECT_ID, or is read out of the service
# account JSON so a single secret is enough for most deployments.
def _firebase_project_id():
    pid = os.environ.get("FIREBASE_PROJECT_ID", "").strip()
    if pid:
        return pid
    sa_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON", "")
    try:
        import json
        return json.loads(sa_json).get("project_id", "") if sa_json else ""
    except Exception:
        return ""

FIREBASE_PROJECT_ID = _firebase_project_id()
# Host that serves Firebase's /__/auth/* handler pages (proxied by static_routes)
FIREBASE_AUTH_HOST = os.environ.get(
    "FIREBASE_AUTH_HOST",
    f"https://{FIREBASE_PROJECT_ID}.firebaseapp.com" if FIREBASE_PROJECT_ID else "",
).rstrip('/')

# ============== Admin ==============
ADMIN_SECRET_KEY = os.environ.get("ADMIN_SECRET_KEY", "")
KAUTILYA_API_KEY = os.environ.get("KAUTILYA_API_KEY", "")

# ============== Infrastructure Base URL (For Webhooks) ==============
# Auto-detect HF Space URL if not provided
PUBLIC_BASE_URL = os.environ.get('PUBLIC_BASE_URL', '').rstrip('/')
if not PUBLIC_BASE_URL:
    hf_owner = os.environ.get('SPACE_AUTHOR_NAME')
    hf_name = os.environ.get('SPACE_REPO_NAME')
    if hf_owner and hf_name:
        PUBLIC_BASE_URL = f"https://{hf_owner}-{hf_name.replace('_', '-')}.hf.space"
        print(f"[CONFIG] Auto-detected HF Space URL: {PUBLIC_BASE_URL}")

# ============== Vobiz Master (for Studio Test Calls) ==============
# Test calls from the Studio always use these master credentials.
#
# These are read from the first env var that is actually set, across every
# name we've used in deployments. The canonical names are VOBIZ_MASTER_USER /
# _PASS / _NUMBER, but production Spaces have historically also used
# VOBIZ_USERNAME/PASSWORD/NUMBER, VOBIZ_AUTH_ID/TOKEN, and MASTER_VOBIZ_*.
# A name mismatch is exactly why a freshly-built test agent fell back to
# "Master Vobiz not set" while older agents (with a user-saved provider)
# still dialed — so we accept all of them instead of one rigid name.
def _first_env(*names, default=""):
    for n in names:
        v = (os.environ.get(n) or "").strip()
        if v:
            return v
    return default

VOBIZ_MASTER_USER = _first_env(
    "VOBIZ_MASTER_USER", "VOBIZ_MASTER_USERNAME", "VOBIZ_MASTER_AUTH_ID",
    "MASTER_VOBIZ_USER", "VOBIZ_USERNAME", "VOBIZ_USER", "VOBIZ_AUTH_ID",
)
VOBIZ_MASTER_PASS = _first_env(
    "VOBIZ_MASTER_PASS", "VOBIZ_MASTER_PASSWORD", "VOBIZ_MASTER_AUTH_TOKEN",
    "MASTER_VOBIZ_PASS", "VOBIZ_PASSWORD", "VOBIZ_PASS", "VOBIZ_AUTH_TOKEN",
)
VOBIZ_MASTER_NUMBER = _first_env(
    "VOBIZ_MASTER_NUMBER", "MASTER_VOBIZ_NUMBER", "VOBIZ_NUMBER",
    "VOBIZ_CALLER_ID", "VOBIZ_FROM",
)
if VOBIZ_MASTER_USER and VOBIZ_MASTER_PASS:
    print(f"[CONFIG] Vobiz master creds loaded (caller_id={'set' if VOBIZ_MASTER_NUMBER else 'MISSING'})")
else:
    print("[CONFIG] Vobiz master creds NOT set — Studio test calls will require a user-saved provider")

# ============== CSP Header ==============
# NOTE: the active Content-Security-Policy is built inline in app.py's
# set_security_headers(). A second copy used to live here and drift out of sync;
# it was unused (nothing imported CSP_POLICY) so it has been removed.
