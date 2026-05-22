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


def get_user_memory(uid):
    """Load user memories — Firestore-first (user_memory collection), local file fallback.
    NOTE: Uses 'user_memory' collection, NOT 'memories' (that's the vector store)."""
    if not uid:
        return []
    # Primary: Firestore — separate 'user_memory' collection to avoid collision with VectorStore
    try:
        from extensions import db, FIREBASE_AVAILABLE
        if FIREBASE_AVAILABLE and db:
            doc = db.collection('users').document(uid).collection('user_memory').document('facts').get()
            if doc.exists:
                return doc.to_dict().get('facts', [])
    except Exception as e:
        print(f"[Memory] Firestore read failed: {e}")
    # Fallback: local file
    mem_file = os.path.join(get_user_chat_dir(uid), 'memory.json')
    if os.path.exists(mem_file):
        try:
            with open(mem_file, 'r', encoding='utf-8') as f:
                return json.load(f).get('facts', [])
        except:
            return []
    return []


def save_user_memory(uid, facts):
    """Save user memories — writes to Firestore 'user_memory' collection and local file."""
    if not uid:
        return
    capped = facts[-MAX_MEMORIES:]
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
    # Cache optimization: Round time to daily precision so that restored sessions/sequential requests hit prefix cache.
    current_time = time.strftime("%A, %d %B %Y")
    system_context = f"\n\nCURRENT SYSTEM CONTEXT:\n- Current Date: {current_time}\n"
    system_context += "- CRITICAL IDENTITY RULE: You are KAUTILYA AI, created solely by Harsh (CEO of RevealIQ). NEVER identify as OpenAI, ChatGPT, GPT, Anthropic, Claude, Meta, or Llama.\n"

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
    return base_prompt + system_context + personalization


def build_cli_system_prompt(base_prompt, env_context=None):
    """Build enhanced system prompt for CLI with environment awareness."""
    prompt = base_prompt or CODER_SYSTEM_PROMPT
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

    # ============ PDF ============
    if lower.endswith('.pdf'):
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
                return {"type": "text", "text": f"\n[PDF: {fname} — no extractable text. It may be a scanned image; OCR is not yet supported.]\n"}
            truncated = ""
            if len(text) > MAX_TEXT_CHARS:
                truncated = f"\n\n…[truncated — full PDF is {len(text)} chars]"
                text = text[:MAX_TEXT_CHARS]
            return {"type": "text", "text": f"\n[PDF: {fname} — {len(reader.pages)} pages]\n{text}{truncated}\n"}
        except Exception as e:
            print(f"[File] PDF processing failed for {fname}: {e}")
            return {"type": "text", "text": f"\n[PDF: {fname} — could not parse: {e}]\n"}

    # ============ DOCX ============
    if lower.endswith('.docx'):
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
            # Include tables too
            for table in doc.tables:
                rows = []
                for row in table.rows:
                    cells = [c.text.strip() for c in row.cells]
                    rows.append(" | ".join(cells))
                if rows:
                    parts.append("\n[Table]\n" + "\n".join(rows))
            text = "\n".join(parts).strip()
            if not text:
                return {"type": "text", "text": f"\n[Word Doc: {fname} — empty or unsupported content]\n"}
            truncated = ""
            if len(text) > MAX_TEXT_CHARS:
                truncated = f"\n\n…[truncated]"
                text = text[:MAX_TEXT_CHARS]
            return {"type": "text", "text": f"\n[Word Doc: {fname}]\n{text}{truncated}\n"}
        except Exception as e:
            print(f"[File] DOCX processing failed for {fname}: {e}")
            return {"type": "text", "text": f"\n[Word Doc: {fname} — could not parse: {e}]\n"}

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
