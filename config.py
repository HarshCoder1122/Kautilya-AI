"""
Kautilya AI — Centralized Configuration
All environment variables, constants, and runtime settings.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ============== Paths ==============
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_FOLDER = os.path.join(BASE_DIR, 'static')
CHAT_DATA_DIR = os.path.join(BASE_DIR, 'chat_data')
os.makedirs(CHAT_DATA_DIR, exist_ok=True)

# ============== Flask ==============
FLASK_SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", os.urandom(24).hex())

# ============== API Keys ==============
# SECURITY: All keys MUST come from environment variables. No hardcoded defaults.
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
SERPAPI_API_KEY = os.environ.get("SERPAPI_API_KEY", "")
MAPPLS_API_KEY = os.environ.get("MAPPLS_API_KEY", "")
SARVAM_API_KEY = os.environ.get("SARVAM_API_KEY", "")
NVIDIA_API_KEY = os.environ.get("NVIDIA_API_KEY", "")

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

# ============== System Prompt ==============
SYSTEM_PROMPT = ""
_prompt_path = os.path.join(BASE_DIR, "system_prompt_cloud.txt")
if os.path.exists(_prompt_path):
    with open(_prompt_path, "r", encoding="utf-8") as f:
        SYSTEM_PROMPT = f.read().strip()
else:
    SYSTEM_PROMPT = "You are KAUTILYA AI, an advanced AI assistant. Be helpful, strategic, and concise."

# ============== Coder System Prompt ==============
# Cloud-chat coder persona. There is NO filesystem / shell tool layer here —
# the user is on a public website and just wants direct answers and code.
# Do NOT teach the model bracket commands; let it write code in fenced
# blocks like every other modern AI chat (ChatGPT / Claude / Gemini).
CODER_SYSTEM_PROMPT = """
You are **Kautilya Coder**, a senior software engineer who pairs with the user
through a chat interface. You write clean, production-grade code and explain
your reasoning clearly.

# How you respond
- Default to **direct, working code** in fenced blocks tagged with the right
  language (```python, ```jsx, ```css, ```bash, …).
- Keep prose tight: brief context above the code, brief notes below if the
  user needs to install something or run a command.
- For multi-file projects, output each file in its own fenced block prefixed
  with a short comment like `// File: src/components/Hero.jsx` so the user
  can copy them out cleanly.
- When the user asks for a website / app / component, **build it now** with
  real markup, styling and behavior. Do not ask permission, do not stub out
  with `// TODO`, do not describe what you "would" do.
- If a request is ambiguous, make the most reasonable assumption, state it
  in one line, and proceed.

# What you do NOT do
- You have no access to the user's filesystem, shell, network, or any tools.
  Never claim to "list files", "read the project", "run npm install for
  you", "check the directory" or similar — you cannot. Just write the code
  the user can run themselves.
- Do not invent bracket commands like `[LIST_DIR]`, `[READ_FILE]`,
  `[SHELL_EXEC]`, `[FINISH]`, etc. They do nothing. Plain prose + fenced
  code blocks only.
- Do not pretend to have observed output you did not.

# Style & quality bar
- Modern best practices for whatever stack is requested (Vue 3 + Vite,
  React + Vite, FastAPI, Express, Tailwind, etc.).
- Beautiful, responsive UI when building frontends — proper spacing,
  hierarchy, accessible contrast, dark-mode-friendly when appropriate.
- Real error handling, not bare try/except pass.
- Include the imports and dependencies needed; if something is non-obvious
  (e.g. `npm i lucide-react`), tell the user.
- Reasoning is welcome — explain trade-offs in 2-4 lines when they matter.
  Otherwise keep it short and let the code speak.

You are talking to a developer who values their time. Skip filler, skip
disclaimers, deliver the answer.
"""

# ============== Constants ==============
MAX_HISTORY = 20
CONVERSATION_TTL = 3600  # 1 hour
MAX_KEYS_PER_USER = 5
MAX_AGENTS_FREE = 1
MAX_AGENTS_PRO = 5
MAX_MEMORIES = 50
API_KEY_PREFIX = "kautilya-"

# ============== Rate Limits ==============
API_RATE_LIMITS = {
    "free": {"llm_tokens": 10000, "tts_chars": 5000, "stt_seconds": 60, "max_tokens": 2048},
    "pro":  {"llm_tokens": 1000000, "tts_chars": 500000, "stt_seconds": 6000, "max_tokens": 16384},
}

_MESSAGE_RATE_LIMITS = {
    "guest":  {"per_minute": 2,  "per_day": 10},
    "free":   {"per_minute": 5,  "per_day": 30},
    "pro":    {"per_minute": 20, "per_day": None},  # None = unlimited
}

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

# SIP URI — hardcoded to match LiveKit Cloud project SIP domain
# Project URL (meet-2wx5nfq3) is DIFFERENT from SIP domain (4mu6v2usrj9)
# Do NOT derive from LIVEKIT_URL — they are separate domains
LIVEKIT_SIP_URI = os.environ.get('LIVEKIT_SIP_URI', '4mu6v2usrj9.sip.livekit.cloud')

# ============== Admin ==============
ADMIN_SECRET_KEY = os.environ.get("ADMIN_SECRET_KEY", "")
KAUTILYA_API_KEY = os.environ.get("KAUTILYA_API_KEY", "")

# ============== CSP Header ==============
CSP_POLICY = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' 'unsafe-eval' "
        "https://cdn.jsdelivr.net https://cdnjs.cloudflare.com "
        "https://www.gstatic.com https://apis.google.com "
        "https://checkout.razorpay.com https://cdn.razorpay.com; "
    "style-src 'self' 'unsafe-inline' "
        "https://fonts.googleapis.com https://cdnjs.cloudflare.com "
        "https://cdn.jsdelivr.net; "
    "font-src 'self' https://fonts.gstatic.com https://fonts.googleapis.com; "
    "img-src 'self' data: blob: https: http: https://unpkg.com; "
    "connect-src 'self' https: wss: https://api.razorpay.com https://lumberjack.razorpay.com; "
    "media-src 'self' blob: https:; "
    "frame-src 'self' https://accounts.google.com https://*.firebaseapp.com "
        "https://api.razorpay.com https://lumberjack.razorpay.com https://checkout.razorpay.com; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "form-action 'self'"
)
