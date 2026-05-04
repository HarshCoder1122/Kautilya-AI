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
if not NVIDIA_API_KEY:
    print("[CONFIG] WARNING: NVIDIA_API_KEY not set — Pro/Coder models will fall back to Groq Llama")

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

# File-based override (optional)
_prompt_path = os.path.join(BASE_DIR, "system_prompt_cloud.txt")
if os.path.exists(_prompt_path):
    with open(_prompt_path, "r", encoding="utf-8") as f:
        SYSTEM_PROMPT = f.read().strip()
    print(f"[CONFIG] Loaded custom system prompt from {SYSTEM_PROMPT[:50]}...")

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
