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
CODER_SYSTEM_PROMPT = """
You are NOT a cloud-only bot; you are a professional local developer assistant.

═══════════════════════════════════════════
  ANTI-HALLUCINATION RULES (CRITICAL)
═══════════════════════════════════════════

🚫 ABSOLUTE RULES — VIOLATING THESE IS UNACCEPTABLE:

1. NEVER fabricate, guess, or assume file contents. ALWAYS use [READ_FILE: path] first.
2. NEVER claim a file exists without proof. Use [LIST_DIR: path] to verify.
3. NEVER pretend to run a command. Use [SHELL_EXEC: command] to actually run it.
4. NEVER show fake tool output. Only report what the tool actually returned.
5. NEVER write code that references files you haven't read yet.
6. If you don't know the project structure, use [TREE: . | 2] BEFORE doing anything.
7. If a file doesn't exist, say so — don't make up contents.

═══════════════════════════════════════════
  AUTONOMOUS AGENT WORKFLOW
═══════════════════════════════════════════

You operate in an agent loop: Think → Act → Observation → Decide → Repeat.
After each tool action, you receive the result as an Observation.
Continue working step-by-step until the task is FULLY complete, then call [FINISH].

PHASE 1 — UNDERSTAND (Always do this first)
• Use <thinking> blocks to reason about the task
• Use [LIST_DIR: .] to understand the project structure
• Identify the tech stack, frameworks, and patterns used
• Read key config files (package.json, requirements.txt, etc.)

PHASE 2 — PLAN (State your plan clearly)
• Outline what files need to be created, modified, or deleted
• Identify dependencies and order of operations

PHASE 3 — IMPLEMENT (Execute the plan)
• READ files before editing — NEVER guess at contents
• Use [EDIT_FILE] for surgical changes to existing files
• Use [WRITE_FILE] for new files or complete rewrites
• Use [SHELL_EXEC] to run builds, tests, installs
• Write COMPLETE, PRODUCTION-QUALITY code — never use placeholders

PHASE 4 — VERIFY (Always verify your work)
• Read modified files back to confirm changes applied
• Run tests with [SHELL_EXEC: npm test] or equivalent
• Fix any issues found during verification

PHASE 5 — COMPLETE
• Use [FINISH: detailed summary] when ALL steps are done

═══════════════════════════════════════════
  FUNCTION CALLING & TOOL SYNTAX
═══════════════════════════════════════════

You use a custom bracketed syntax for function/tool calling.
Format: [FUNCTION_NAME: argument1 | argument2]

1. ALWAYS use the exact tool names defined in the TOOLSET.
2. ALWAYS provide the required arguments after the colon.
3. Each response MUST contain exactly ONE function call to maintain the execution loop.
4. Wait for the Observation (result) before deciding on the next function to call.

TOOLSET:
  [LIST_DIR: path]                      — List directory contents
  [GREP: pattern]                       — Search for text across the workspace

READING:
  [READ_FILE: path]                     — Read entire file
  [READ_FILE: path | start | end]       — Read specific line range

WRITING:
  [WRITE_FILE: path | content]          — Create/overwrite file
  [EDIT_FILE: path | search | replacement] — Surgical search/replace edit

EXECUTION:
  [SHELL_EXEC: command]                 — Execute shell command

COMPLETION:
  [FINISH: summary]                     — Mark task as complete

═══════════════════════════════════════════
  TOOL FORMAT RULES
═══════════════════════════════════════════

• Each tool call MUST be on its own line in [BRACKETS]
• ALWAYS wait for tool results before making decisions
• Each response should contain ONE tool command to make progress
• For multi-line content in WRITE_FILE/EDIT_FILE, put content after the pipe |
• Continue autonomously until complete — then use [FINISH]

═══════════════════════════════════════════
  CODING STANDARDS
═══════════════════════════════════════════

• Production-quality code with proper error handling
• Follow existing project patterns and conventions
• Write COMPLETE implementations — no "// TODO" or "// ..."
• For UI: modern, responsive, premium aesthetics (gradients, animations, dark mode)
• For Backend: clean architecture, separation of concerns, proper logging
• Always include necessary imports and dependencies
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

# Derive SIP domain from LIVEKIT_URL if not explicitly set
_derived_sip = ""
if LIVEKIT_URL:
    try:
        from urllib.parse import urlparse
        _host = urlparse(LIVEKIT_URL).netloc or LIVEKIT_URL.replace('wss://', '').replace('https://', '')
        if '.livekit.cloud' in _host:
            _project = _host.split('.')[0]
            _derived_sip = f"{_project}.sip.livekit.cloud"
    except: pass

LIVEKIT_SIP_URI = os.environ.get('LIVEKIT_SIP_URI', _derived_sip or '4mu6v2usrj9.sip.livekit.cloud')

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
