"""
Kautilya AI — Memory Service
User memory, session recording, file processing, prompt building.
"""
import os
import io
import json
import time
import hashlib
import base64
import requests
from PIL import Image
import PyPDF2
from docx import Document

from config import (
    CHAT_DATA_DIR, MAX_MEMORIES, SYSTEM_PROMPT, CODER_SYSTEM_PROMPT,
    GROQ_API_KEY,
)


def get_user_chat_dir(uid):
    user_dir = os.path.join(CHAT_DATA_DIR, uid)
    os.makedirs(user_dir, exist_ok=True)
    return user_dir


# TTL cache for user memory. Memory only changes when extract_memories
# saves new facts (background) or merge_identity_facts saves directly.
# Both invalidate via save_user_memory below. Without this, every new
# chat message did a Firestore read just to build the system prompt.
_user_memory_cache = {}   # uid -> (facts_list, expires_at)
_USER_MEMORY_TTL_SEC = 60.0


def _invalidate_user_memory_cache(uid):
    _user_memory_cache.pop(uid, None)


def get_user_memory(uid):
    """Load user memories — Firestore-first (user_memory collection), local file fallback.
    NOTE: Uses 'user_memory' collection, NOT 'memories' (that's the vector store)."""
    if not uid:
        return []
    now = time.time()
    cached = _user_memory_cache.get(uid)
    if cached and cached[1] > now:
        return cached[0]
    facts = []
    # Primary: Firestore — separate 'user_memory' collection to avoid collision with VectorStore
    try:
        from extensions import db, FIREBASE_AVAILABLE
        if FIREBASE_AVAILABLE and db:
            doc = db.collection('users').document(uid).collection('user_memory').document('facts').get()
            if doc.exists:
                facts = doc.to_dict().get('facts', [])
                _user_memory_cache[uid] = (facts, now + _USER_MEMORY_TTL_SEC)
                return facts
    except Exception as e:
        print(f"[Memory] Firestore read failed: {e}")
    # Fallback: local file
    mem_file = os.path.join(get_user_chat_dir(uid), 'memory.json')
    if os.path.exists(mem_file):
        try:
            with open(mem_file, 'r', encoding='utf-8') as f:
                facts = json.load(f).get('facts', [])
        except:
            facts = []
    _user_memory_cache[uid] = (facts, now + _USER_MEMORY_TTL_SEC)
    return facts


def save_user_memory(uid, facts):
    """Save user memories — writes to Firestore 'user_memory' collection and local file."""
    if not uid:
        return
    capped = facts[-MAX_MEMORIES:]
    # Update the in-process cache eagerly so subsequent reads in this process
    # see the new facts immediately (the Firestore write is async-ish under
    # the hood and the TTL would otherwise serve stale facts for 60s).
    _user_memory_cache[uid] = (capped, time.time() + _USER_MEMORY_TTL_SEC)
    # Primary: Firestore — separate collection from VectorStore's 'memories'
    try:
        from extensions import db, FIREBASE_AVAILABLE
        if FIREBASE_AVAILABLE and db:
            db.collection('users').document(uid).collection('user_memory').document('facts').set(
                {'facts': capped, 'updated': time.time()}, merge=True
            )
    except Exception as e:
        print(f"[Memory] Firestore write failed: {e}")
    # Also keep local file as backup
    try:
        mem_file = os.path.join(get_user_chat_dir(uid), 'memory.json')
        with open(mem_file, 'w', encoding='utf-8') as f:
            json.dump({'facts': capped, 'updated': time.time()}, f, ensure_ascii=False)
    except:
        pass


_IDENTITY_PATTERNS = [
    # (regex with one capture group, fact-template, fact-key for dedup)
    (r'\bmy\s+github(?:\s+(?:user(?:\s*name)?|id|handle|account|username))?\s+(?:is|:|=)\s+["\']?([A-Za-z0-9][A-Za-z0-9_\-]{0,38})\b', "User's GitHub username is {0}", "github_username"),
    (r'\b(?:i\s+am|i\'m|im)\s+([A-Za-z0-9][A-Za-z0-9_\-]{2,38})\s+on\s+github\b', "User's GitHub username is {0}", "github_username"),
    (r'\bmy\s+(?:user\s*id|userid|handle|username)\s+(?:is|:|=)\s+["\']?([A-Za-z0-9][A-Za-z0-9_\-\.]{1,38})\b', "User's primary handle / user id is {0}", "primary_handle"),
    (r'\bmy\s+(?:twitter|x)(?:\s+handle)?\s+(?:is|:|=)\s+@?([A-Za-z0-9_]{1,15})\b', "User's Twitter/X handle is @{0}", "twitter_handle"),
    (r'\bmy\s+linkedin\s+(?:is|:|=)\s+(?:https?://[^\s]+/in/)?([A-Za-z0-9\-]{3,80})\b', "User's LinkedIn slug is {0}", "linkedin_slug"),
    (r'\bmy\s+instagram(?:\s+handle)?\s+(?:is|:|=)\s+@?([A-Za-z0-9_\.]{1,30})\b', "User's Instagram handle is @{0}", "instagram_handle"),
    (r'\bmy\s+(?:work\s+)?email\s+(?:is|:|=)\s+([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})\b', "User's stated email is {0}", "user_email"),
    (r'\bmy\s+phone(?:\s+number)?\s+(?:is|:|=)\s+(\+?[\d\s\-]{7,20})\b', "User's phone number is {0}", "phone_number"),
    (r'\b(?:i\s+am|i\'m|im|call\s+me|my\s+name\s+is)\s+([A-Z][A-Za-z]{1,30})\b', "User's preferred first name is {0}", "first_name"),
]


def extract_identity_facts_inline(user_msg):
    """Cheap regex scan for self-disclosed identifiers ('my github is harshcoder1122',
    'my email is X', 'I'm Harsh'). Runs synchronously BEFORE the LLM call so the
    current turn already sees the fact — unlike the LLM-based extract_memories
    which only runs AFTER the response and helps subsequent turns.

    Returns: list of (fact_string, dedup_key, raw_value) tuples found.
    """
    import re as _re
    if not user_msg or not isinstance(user_msg, str):
        return []
    found = []
    seen_keys = set()
    for pattern, template, key in _IDENTITY_PATTERNS:
        if key in seen_keys:
            continue
        m = _re.search(pattern, user_msg, _re.IGNORECASE)
        if m:
            value = m.group(1).strip()
            if not value:
                continue
            found.append((template.format(value), key, value))
            seen_keys.add(key)
    return found


def merge_identity_facts_into_memory(uid, new_facts):
    """Replace any prior fact with the same dedup key, then save. Returns the
    list of human-readable fact strings that were newly stored (for logging)."""
    if not uid or not new_facts:
        return []
    existing = get_user_memory(uid) or []
    # Drop prior facts that share a key prefix with any new one — keeps the
    # most recent self-disclosure when the user updates their handle.
    key_prefixes = {f"User's {k.replace('_', ' ')}" for _, k, _ in new_facts}
    # Above is fuzzy; use template-prefix matching instead for reliability.
    new_prefixes = [s.split(' is ')[0] for s, _, _ in new_facts]
    kept = [m for m in existing if not any(m.startswith(p + ' is ') or m.startswith(p) for p in new_prefixes)]
    stored = []
    for fact_str, _key, _val in new_facts:
        if fact_str not in kept:
            kept.append(fact_str)
            stored.append(fact_str)
    if stored:
        save_user_memory(uid, kept)
    return stored


def extract_memories(user_msg, assistant_msg, existing_memories):
    try:
        def get_text_content(msg):
            if isinstance(msg, list):
                return " ".join([p["text"] for p in msg if p.get("type") == "text"])
            return str(msg)
        user_text = get_text_content(user_msg)
        assistant_text = get_text_content(assistant_msg)
        extraction_prompt = [
            {"role": "system", "content": (
                "You are an expert at user profiling and memory extraction. Your goal is to build a detailed personal profile of the user "
                "by extracting short, high-value facts from their conversation with an AI assistant.\n\n"
                "FOCUS ON:\n- Identity: Name, age, gender, occupation, location.\n"
                "- Preferences: Likes, dislikes, favorite tools, coding style, language choice.\n"
                "- Context: Current projects, career goals, family, pets, habits.\n"
                "- Important Information: Specific dates, unique ID numbers, birthdays, or keys they share.\n\n"
                "RULES:\n- Output ONLY a JSON array of strings.\n"
                "- Each string must be a concise, standalone fact.\n"
                "- Use the third person ('User is...', 'User likes...').\n"
                "- NEVER repeat a fact that is already in the 'ALREADY KNOWN FACTS' list.\n"
                "- If no meaningful new facts are found, return [].\n- STRICT JSON ONLY."
            )},
            {"role": "user", "content": (
                f"ALREADY KNOWN FACTS:\n{json.dumps(existing_memories)}\n\n"
                f"USER SAID: {user_text}\n\nASSISTANT REPLIED: {assistant_text}\n\n"
                "Extract new facts (JSON array only):"
            )}
        ]
        if GROQ_API_KEY:
            resp = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
                json={"model": "llama-3.3-70b-versatile", "messages": extraction_prompt,
                      "temperature": 0.1, "max_tokens": 200},
                timeout=8
            )
            if resp.status_code == 200:
                content = resp.json()["choices"][0]["message"]["content"].strip()
                if content.startswith("```"):
                    content = content.split("```")[1]
                    if content.startswith("json"):
                        content = content[4:]
                new_facts = json.loads(content)
                if isinstance(new_facts, list):
                    return [f for f in new_facts if isinstance(f, str) and f.strip()]
        return []
    except Exception as e:
        print(f"[Memory] Extraction failed: {e}")
        return []


def build_personalized_prompt(base_prompt, user_name=None, memories=None, user_email=None, settings=None, uid=None):
    from datetime import datetime, timezone, timedelta
    
    # Compute India Standard Time (IST, UTC+5:30)
    ist_tz = timezone(timedelta(hours=5, minutes=30))
    now_ist = datetime.now(ist_tz)
    
    # Round down to the hour to preserve LLM prefix caching
    rounded_ist = now_ist.replace(minute=0, second=0, microsecond=0)
    current_date = rounded_ist.strftime("%A, %d %B %Y")
    current_time_str = rounded_ist.strftime("%I:%M %p")
    
    system_context = (
        f"\n\nCURRENT SYSTEM CONTEXT:\n"
        f"- Current Date (India Standard Time): {current_date}\n"
        f"- Current Time (India Standard Time): {current_time_str}\n"
        f"- CRITICAL IDENTITY RULE: You are KAUTILYA AI, created solely by Harsh (CEO of RevealIQ). NEVER identify as OpenAI, ChatGPT, GPT, Anthropic, Claude, Meta, or Llama.\n"
        f"- USER-IDENTITY ZERO-HALLUCINATION RULE (critical for tool calls): NEVER invent or guess the user's:\n"
        f"  GitHub username, Twitter/X handle, LinkedIn, Instagram, email address, phone number, employee ID, customer ID, or any other identifying handle.\n"
        f"  These can ONLY come from: (a) the CONNECTED INTEGRATIONS / Known facts block below, (b) something the user said verbatim earlier in THIS chat,\n"
        f"  (c) the user's message right now. If none of those provide it, you MUST ASK the user — do NOT pick a similar-looking name from your training data\n"
        f"  (e.g. do NOT call mcp_github_search_users with 'HarshCasper' just because it sounds plausible). Wrong-account calls are a worse failure than asking.\n"
    )

    # Load full profile/settings from Firestore if settings is not fully provided
    profile_data = settings or {}
    if (not profile_data or 'preferred_name' not in profile_data) and uid:
        try:
            from extensions import db, FIREBASE_AVAILABLE
            if FIREBASE_AVAILABLE and db:
                pdoc = db.collection('users').document(uid).collection('settings').document('profile').get()
                if pdoc.exists:
                    profile_data = pdoc.to_dict() or {}
        except:
            pass

    # Resolve display name: settings preferred_name > settings display_name > Firebase Auth record > token name
    preferred_name = profile_data.get('preferred_name')
    display_name = preferred_name or profile_data.get('display_name') or user_name
    
    if not display_name and uid:
        # Try Firebase Auth user record for proper displayName (set during signup)
        try:
            from firebase_admin import auth as fb_auth
            user_record = fb_auth.get_user(uid)
            display_name = user_record.display_name
        except:
            pass

    # If display_name still looks like an email prefix / username (lowercase, digits,
    # underscores) rather than a real human name, treat it as unknown — the model
    # should not address the user by a machine-y username.
    def _looks_like_real_name(n):
        if not n or len(n) < 2:
            return False
        # Real names typically have a capitalized first letter, no digits, no underscores.
        if any(c.isdigit() for c in n):
            return False
        if '_' in n or '.' in n:
            return False
        if n == n.lower() and len(n) > 12:  # long lowercase blob = probably handle
            return False
        return True

    # If it is explicitly configured preferred name, bypass real name looks verification
    is_name_valid = False
    if preferred_name:
        is_name_valid = True
    elif display_name and _looks_like_real_name(display_name):
        is_name_valid = True

    personalization = "\n\nPERSONALIZATION:\n"
    personalization += "- GREETING RULE: Use India Standard Time (IST) as provided in CURRENT SYSTEM CONTEXT for all time-based references and greetings. Greet the user with 'Good morning', 'Good afternoon', or 'Good evening' matching the current IST hour of the day.\n"
    if is_name_valid:
        personalization += f"- User's name: {display_name}\n"
        personalization += f"- Address the user as '{display_name}' when natural — never use generic 'Sir/Ma'am'.\n"
    else:
        # No proper name available. Tell the model to skip generic salutations
        # and wait for the user to introduce themselves.
        personalization += "- User's name is not on file yet. Do NOT address them by username, email-prefix, or generic 'Sir/Ma'am'. Use a friendly conversational tone. If asked, mention they can set their name in Dashboard → Settings.\n"
    
    work_function = profile_data.get('work_function')
    personal_preferences = profile_data.get('personal_preferences')
    
    if work_function:
        personalization += f"- User's role/work function: {work_function}\n"
    if personal_preferences:
        personalization += f"- User's personalization instructions/custom preferences:\n{personal_preferences}\n"

    if user_email:
        personalization += f"- User email (for reference, do not greet with it): {user_email}\n"
    if memories:
        personalization += "- Known facts about this user:\n  " + "\n  ".join([f"• {m}" for m in memories[:20]]) + "\n"

    # Connected integrations identity — so the agent knows e.g. the user's
    # GitHub login when they say "check my repo" without having to ask.
    integrations_block = ""
    if uid:
        try:
            from extensions import db, FIREBASE_AVAILABLE
            if FIREBASE_AVAILABLE and db:
                idocs = db.collection('users').document(uid).collection('integrations').stream()
                lines = []
                for d in idocs:
                    cfg = d.to_dict() or {}
                    if not (cfg.get('access_token') or cfg.get('api_key') or cfg.get('webhook_url')):
                        continue
                    pid = d.id
                    bits = [pid]
                    if cfg.get('username'):
                        bits.append(f"username: {cfg['username']}")
                    if cfg.get('email') and pid != 'github':
                        bits.append(f"email: {cfg['email']}")
                    if cfg.get('name') and not cfg.get('username'):
                        bits.append(f"name: {cfg['name']}")
                    if cfg.get('profile_url'):
                        bits.append(cfg['profile_url'])
                    lines.append("• " + " — ".join(bits))
                if lines:
                    integrations_block = (
                        "\n\nCONNECTED INTEGRATIONS (use these identities when calling tools — do NOT ask the user "
                        "for their username/handle if it's listed here):\n" + "\n".join(lines) + "\n"
                    )
        except Exception as e:
            print(f"[Prompt] integrations block failed: {e}")

    return base_prompt + system_context + personalization + integrations_block


def build_cli_system_prompt(base_prompt, env_context=None):
    """Build enhanced system prompt for CLI with environment awareness."""
    from datetime import datetime, timezone, timedelta
    
    # Compute India Standard Time (IST, UTC+5:30)
    ist_tz = timezone(timedelta(hours=5, minutes=30))
    now_ist = datetime.now(ist_tz)
    
    # Round down to the hour to preserve LLM prefix caching
    rounded_ist = now_ist.replace(minute=0, second=0, microsecond=0)
    current_date = rounded_ist.strftime("%A, %d %B %Y")
    current_time_str = rounded_ist.strftime("%I:%M %p")
    
    system_context = (
        f"\n\nCURRENT SYSTEM CONTEXT:\n"
        f"- Current Date (India Standard Time): {current_date}\n"
        f"- Current Time (India Standard Time): {current_time_str}\n"
        f"- GREETING RULE: Use India Standard Time (IST) as provided in CURRENT SYSTEM CONTEXT for all time-based references and greetings. Greet the user with 'Good morning', 'Good afternoon', or 'Good evening' matching the current IST hour of the day.\n"
        f"- CRITICAL IDENTITY RULE: You are KAUTILYA AI, created solely by Harsh (CEO of RevealIQ). NEVER identify as OpenAI, ChatGPT, GPT, Anthropic, Claude, Meta, or Llama.\n"
    )
    
    prompt = base_prompt or CODER_SYSTEM_PROMPT
    prompt += system_context
    if env_context:
        prompt += f"\n\n═══════════════════════════════════════════\n  CURRENT ENVIRONMENT\n═══════════════════════════════════════════\n{env_context}\n"
    return prompt



def record_user_session(uid, session_id):
    from extensions import db, FIREBASE_AVAILABLE
    from flask import request
    if not FIREBASE_AVAILABLE or not db:
        return
    ua = request.headers.get('User-Agent', 'Unknown')
    ip = request.headers.get('X-Forwarded-For', request.remote_addr) or "unknown"
    if ',' in ip:
        ip = ip.split(',')[0].strip()
    current_device = "Desktop Browser"
    if "Mobile" in ua: current_device = "Mobile Device"
    if "iPhone" in ua: current_device = "iPhone"
    if "Android" in ua: current_device = "Android Device"
    browser = "Chrome" if "Chrome" in ua else "Safari" if "Safari" in ua else "Firefox" if "Firefox" in ua else "Browser"
    sid = session_id or hashlib.md5(f"{ua}{ip}".encode()).hexdigest()[:12]
    try:
        from firebase_admin import firestore
        db.collection('users').document(uid).collection('sessions').document(sid).set({
            "device": current_device, "browser": browser, "location": "India",
            "ip_prefix": ".".join(ip.split('.')[:3]) + ".xxx" if '.' in ip else ip,
            "last_active": firestore.SERVER_TIMESTAMP, "ua": ua
        }, merge=True)
    except Exception as e:
        print(f"[Session] Record failed: {e}")


MAX_UPLOAD_MB = 25
MAX_TEXT_CHARS = 60_000  # ~15k tokens — leaves room for the actual chat


# ─────────────────────────── PDF / DOCX helpers ───────────────────────────
# Heuristic constants — tuned for chat context (favor recall over precision).
_PDF_MAX_RASTERIZED_PAGES = 6        # cap image blocks so we don't blow tokens
_PDF_RASTERIZE_DPI = 144             # readable for vision OCR without bloat
_PDF_LOW_TEXT_THRESHOLD = 40         # < N chars on a page → assume scanned
_DOCX_MAX_EMBEDDED_IMAGES = 6


def _img_to_image_block(pil_img, target_max_dim=1280, prefer_jpeg=True):
    """Standard image → multipart block. Mirrors the existing image branch
    so PDF page rasters and DOCX embedded images go through the same vision
    pipeline as direct image uploads."""
    img = pil_img
    if prefer_jpeg and img.mode not in ('RGB', 'L'):
        img = img.convert('RGB')
    target_fmt = 'JPEG' if (prefer_jpeg and img.mode in ('RGB', 'L')) else 'PNG'
    img.thumbnail((target_max_dim, target_max_dim))
    buf = io.BytesIO()
    if target_fmt == 'JPEG':
        img.save(buf, format='JPEG', quality=85, optimize=True)
    else:
        img.save(buf, format='PNG', optimize=True)
    b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
    mime = 'image/jpeg' if target_fmt == 'JPEG' else 'image/png'
    return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}}


def _process_pdf(file, fname):
    """Claude-style PDF handling.

    Strategy (in order):
      1. Try PyMuPDF (fitz) for text + native page raster. Best layout
         fidelity and handles most PDFs cleanly.
      2. If a page yields very little text, ALSO rasterize that page as an
         image block so the vision model can read scanned content / charts.
      3. If PyMuPDF is unavailable, fall back to PyPDF2 (text only — matches
         old behavior so deployments without pymupdf still work).
      4. Return either a single text block (text-only case) OR a list of
         blocks (text + N images) — the caller flattens lists.
    """
    blocks = []
    try:
        import fitz  # PyMuPDF
    except ImportError:
        fitz = None

    if fitz:
        try:
            file.stream.seek(0)
            data = file.stream.read()
            doc = fitz.open(stream=data, filetype='pdf')
            text_pages = []
            scanned_or_visual_pages = []   # indices we should also rasterize
            for i, page in enumerate(doc):
                try:
                    page_text = page.get_text("text") or ""
                except Exception:
                    page_text = ""
                page_text = page_text.strip()
                if page_text:
                    text_pages.append(f"--- Page {i+1} ---\n{page_text}")
                if len(page_text) < _PDF_LOW_TEXT_THRESHOLD:
                    scanned_or_visual_pages.append(i)

            # If the WHOLE doc has no text, every page is a scan candidate.
            # Otherwise keep low-text pages + always include page 1 so the
            # model sees title/cover for context.
            if not text_pages:
                pages_to_raster = list(range(min(len(doc), _PDF_MAX_RASTERIZED_PAGES)))
            else:
                pages_to_raster = []
                if 0 not in scanned_or_visual_pages:
                    pages_to_raster.append(0)
                pages_to_raster.extend(p for p in scanned_or_visual_pages if p not in pages_to_raster)
                pages_to_raster = pages_to_raster[:_PDF_MAX_RASTERIZED_PAGES]

            # Build text block
            text_combined = "\n\n".join(text_pages).strip()
            if text_combined:
                truncated = ""
                if len(text_combined) > MAX_TEXT_CHARS:
                    truncated = f"\n\n…[truncated — full PDF text is {len(text_combined)} chars]"
                    text_combined = text_combined[:MAX_TEXT_CHARS]
                header = f"\n[PDF: {fname} — {len(doc)} pages, text extracted]\n"
                if pages_to_raster:
                    header += f"[Plus {len(pages_to_raster)} page image(s) below for layout/scan context.]\n"
                blocks.append({"type": "text", "text": header + text_combined + truncated + "\n"})
            else:
                blocks.append({"type": "text",
                               "text": f"\n[PDF: {fname} — {len(doc)} pages, no extractable text. "
                                       f"Rasterized {len(pages_to_raster)} page(s) for vision OCR.]\n"})

            # Rasterize selected pages
            zoom = _PDF_RASTERIZE_DPI / 72.0
            mat = fitz.Matrix(zoom, zoom)
            for pidx in pages_to_raster:
                try:
                    pix = doc[pidx].get_pixmap(matrix=mat, alpha=False)
                    img = Image.open(io.BytesIO(pix.tobytes("png")))
                    blocks.append({"type": "text", "text": f"\n[PDF page {pidx+1} of {fname}:]\n"})
                    blocks.append(_img_to_image_block(img, target_max_dim=1280, prefer_jpeg=True))
                except Exception as e:
                    print(f"[File] PDF page {pidx+1} raster failed: {e}")

            doc.close()
            print(f"[File] PDF {fname} → {len(text_pages)} text pages + {len(pages_to_raster)} image pages")
            return blocks if len(blocks) > 1 else (blocks[0] if blocks else None)
        except Exception as e:
            print(f"[File] PyMuPDF processing failed for {fname}: {e} — falling back to PyPDF2")

    # Fallback: PyPDF2 text-only (legacy behavior)
    try:
        file.stream.seek(0)
        reader = PyPDF2.PdfReader(file.stream)
        pages = []
        for i, page in enumerate(reader.pages):
            try:
                page_text = page.extract_text() or ""
            except Exception:
                page_text = ""
            if page_text.strip():
                pages.append(f"--- Page {i+1} ---\n{page_text.strip()}")
        text = "\n\n".join(pages).strip()
        if not text:
            return {"type": "text",
                    "text": f"\n[PDF: {fname} — no extractable text and PyMuPDF unavailable for OCR rasterization. "
                            f"Install pymupdf on the backend to handle scanned PDFs.]\n"}
        truncated = ""
        if len(text) > MAX_TEXT_CHARS:
            truncated = f"\n\n…[truncated — full PDF is {len(text)} chars]"
            text = text[:MAX_TEXT_CHARS]
        return {"type": "text", "text": f"\n[PDF: {fname} — {len(reader.pages)} pages]\n{text}{truncated}\n"}
    except Exception as e:
        print(f"[File] PDF processing failed for {fname}: {e}")
        return {"type": "text", "text": f"\n[PDF: {fname} — could not parse: {e}]\n"}


def _process_docx(file, fname):
    """DOCX → text + embedded images. The old version only pulled paragraph
    text and tables; charts/screenshots/photos embedded in the doc were lost.
    We now also unzip the .docx (it's a zip) and pull anything under word/media/
    as image blocks so the vision model sees them too."""
    import zipfile
    blocks = []
    # Text + tables first (preserve old path)
    try:
        file.stream.seek(0)
        doc = Document(file.stream)
        parts = []
        for para in doc.paragraphs:
            if para.text.strip():
                style = (para.style.name or '').lower() if para.style else ''
                if 'heading' in style:
                    parts.append(f"\n## {para.text.strip()}\n")
                else:
                    parts.append(para.text.strip())
        for table in doc.tables:
            rows = []
            for row in table.rows:
                cells = [c.text.strip() for c in row.cells]
                rows.append(" | ".join(cells))
            if rows:
                parts.append("\n[Table]\n" + "\n".join(rows))
        text = "\n".join(parts).strip()
    except Exception as e:
        print(f"[File] DOCX text extraction failed for {fname}: {e}")
        text = ""

    # Embedded images (charts, screenshots, photos)
    embedded = []
    try:
        file.stream.seek(0)
        with zipfile.ZipFile(file.stream) as z:
            media_names = [n for n in z.namelist()
                           if n.startswith('word/media/') and
                           n.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.webp'))]
            for n in media_names[:_DOCX_MAX_EMBEDDED_IMAGES]:
                try:
                    raw = z.read(n)
                    img = Image.open(io.BytesIO(raw))
                    embedded.append((n.split('/')[-1], img))
                except Exception as e:
                    print(f"[File] DOCX embedded image {n} failed: {e}")
    except Exception as e:
        print(f"[File] DOCX zip scan failed for {fname}: {e}")

    if not text and not embedded:
        return {"type": "text", "text": f"\n[Word Doc: {fname} — empty or unsupported content]\n"}

    truncated = ""
    if text and len(text) > MAX_TEXT_CHARS:
        truncated = f"\n\n…[truncated]"
        text = text[:MAX_TEXT_CHARS]
    header = f"\n[Word Doc: {fname}"
    if embedded:
        header += f" — {len(embedded)} embedded image(s) included below"
    header += "]\n"
    if text:
        blocks.append({"type": "text", "text": header + text + truncated + "\n"})
    else:
        blocks.append({"type": "text", "text": header + "(no extractable paragraph text — see images)\n"})

    for img_name, img in embedded:
        blocks.append({"type": "text", "text": f"\n[Embedded image '{img_name}' from {fname}:]\n"})
        blocks.append(_img_to_image_block(img, target_max_dim=1280, prefer_jpeg=True))

    print(f"[File] DOCX {fname} → text + {len(embedded)} embedded images")
    return blocks if len(blocks) > 1 else blocks[0]


def process_uploaded_file(file):
    """Convert an uploaded file into a multipart content block for the LLM.

    Handles images (incl. RGBA → RGB, HEIC fallback), text, code, PDFs,
    DOCX, XLSX/CSV. Skips silently on oversized files instead of corrupting
    the message payload.
    """
    if not file or not getattr(file, 'filename', None):
        return None
    fname = file.filename
    lower = fname.lower()

    # ---- Size guard (Flask may already buffer in memory, so check early) ----
    try:
        file.stream.seek(0, 2)        # to end
        size_bytes = file.stream.tell()
        file.stream.seek(0)           # rewind for downstream readers
        if size_bytes > MAX_UPLOAD_MB * 1024 * 1024:
            print(f"[File] {fname} rejected — {size_bytes / 1024 / 1024:.1f}MB > {MAX_UPLOAD_MB}MB")
            return {"type": "text", "text": f"\n[File: {fname} skipped — exceeds {MAX_UPLOAD_MB}MB limit]\n"}
    except Exception:
        pass  # If we can't measure, let downstream try and fail.

    # ============ IMAGES ============
    if lower.endswith(('.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp', '.tiff', '.heic')):
        try:
            file.stream.seek(0)
            img = Image.open(file.stream)
            # GIF/PNG may need conversion; JPEG can't carry alpha
            target_fmt = 'PNG' if img.mode in ('RGBA', 'LA', 'P') else 'JPEG'
            if target_fmt == 'JPEG' and img.mode != 'RGB':
                img = img.convert('RGB')
            img.thumbnail((1280, 1280))
            buf = io.BytesIO()
            img.save(buf, format=target_fmt, quality=88 if target_fmt == 'JPEG' else None,
                     optimize=True)
            b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
            mime = 'image/png' if target_fmt == 'PNG' else 'image/jpeg'
            print(f"[File] Image {fname} → {target_fmt} ({len(buf.getvalue()) // 1024}KB)")
            return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}}
        except Exception as e:
            print(f"[File] Image processing failed for {fname}: {e}")
            return {"type": "text", "text": f"\n[Image: {fname} — could not decode: {e}]\n"}

    # ============ PLAIN TEXT / CODE ============
    if lower.endswith(('.txt', '.md', '.markdown', '.py', '.js', '.jsx', '.ts', '.tsx',
                       '.html', '.htm', '.css', '.scss', '.json', '.xml', '.yaml', '.yml',
                       '.csv', '.tsv', '.log', '.sh', '.sql', '.go', '.rs', '.java',
                       '.c', '.cpp', '.h', '.hpp', '.rb', '.php', '.swift', '.kt',
                       '.toml', '.ini', '.conf', '.env', '.dockerfile')):
        try:
            file.stream.seek(0)
            raw = file.stream.read()
            text = raw.decode('utf-8', errors='ignore').strip()
            if not text:
                return {"type": "text", "text": f"\n[File: {fname} is empty]\n"}
            truncated = ""
            if len(text) > MAX_TEXT_CHARS:
                truncated = f"\n\n…[truncated — original was {len(text)} chars, showing first {MAX_TEXT_CHARS}]"
                text = text[:MAX_TEXT_CHARS]
            return {"type": "text", "text": f"\n[File: {fname}]\n```\n{text}\n```{truncated}\n"}
        except Exception as e:
            print(f"[File] Text read failed for {fname}: {e}")
            return None

    # ============ PDF (Claude-style: text + page images for layout/scans) ============
    if lower.endswith('.pdf'):
        return _process_pdf(file, fname)

    # ============ DOCX (text + extracted embedded images) ============
    if lower.endswith('.docx'):
        return _process_docx(file, fname)

    # ============ XLSX ============
    if lower.endswith(('.xlsx', '.xls')):
        try:
            from openpyxl import load_workbook
            file.stream.seek(0)
            wb = load_workbook(file.stream, data_only=True, read_only=True)
            sheets_out = []
            for sheet in wb.worksheets:
                rows = []
                for row in sheet.iter_rows(values_only=True):
                    if any(c is not None for c in row):
                        rows.append(" | ".join("" if c is None else str(c) for c in row))
                    if len(rows) > 200:
                        rows.append("…[truncated — sheet has more rows]")
                        break
                if rows:
                    sheets_out.append(f"### Sheet: {sheet.title}\n" + "\n".join(rows))
            text = "\n\n".join(sheets_out).strip()
            if not text:
                return {"type": "text", "text": f"\n[Excel: {fname} — empty]\n"}
            return {"type": "text", "text": f"\n[Excel: {fname}]\n{text}\n"}
        except ImportError:
            return {"type": "text", "text": f"\n[Excel: {fname} — openpyxl not installed on backend]\n"}
        except Exception as e:
            print(f"[File] XLSX processing failed for {fname}: {e}")
            return {"type": "text", "text": f"\n[Excel: {fname} — could not parse: {e}]\n"}

    print(f"[File] Unsupported type: {fname}")
    return {"type": "text", "text": f"\n[File: {fname} — unsupported type. Try .pdf, .docx, .xlsx, image, or text/code.]\n"}


def generate_semantic_chunks(text, max_chunks=10):
    if not text or len(text) < 500:
        return [text] if text else []
    from services.llm_service import call_groq
    prompt = f"Split the following text into up to {max_chunks} logical, semantic sections. Each section should be a complete thought or topic. Return each section separated by '|||'.\n\nTEXT:\n{text[:10000]}"
    try:
        resp = call_groq([{"role": "user", "content": prompt}], temperature=0.3, model="llama-3.3-70b-versatile")
        if resp:
            chunks = [c.strip() for c in resp.split('|||') if c.strip()]
            return chunks
    except Exception as e:
        print(f"[AI Chunking] Error: {e}")
    size = 2000
    return [text[i:i+size] for i in range(0, len(text), size)]


def read_website(url):
    """Read a website using Jina Reader."""
    try:
        resp = requests.get(f"https://r.jina.ai/{url}", timeout=15,
                          headers={"Accept": "text/plain"})
        if resp.status_code == 200:
            return resp.text[:8000]
        return f"Error: HTTP {resp.status_code}"
    except Exception as e:
        return f"Error: {e}"
