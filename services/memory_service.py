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
    if not uid:
        return []
    mem_file = os.path.join(get_user_chat_dir(uid), 'memory.json')
    if os.path.exists(mem_file):
        try:
            with open(mem_file, 'r', encoding='utf-8') as f:
                return json.load(f).get('facts', [])
        except:
            return []
    return []


def save_user_memory(uid, facts):
    if not uid:
        return
    mem_file = os.path.join(get_user_chat_dir(uid), 'memory.json')
    capped = facts[-MAX_MEMORIES:]
    with open(mem_file, 'w', encoding='utf-8') as f:
        json.dump({'facts': capped, 'updated': time.time()}, f, ensure_ascii=False)


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


def build_personalized_prompt(base_prompt, user_name=None, memories=None, user_email=None, settings=None):
    current_time = time.strftime("%A, %d %B %Y, %I:%M %p %Z")
    system_context = f"\n\nCURRENT SYSTEM CONTEXT:\n- Current Date and Time: {current_time}\n"
    system_context += "- CRITICAL IDENTITY RULE: You are KAUTILYA AI, created solely by Harsh (CEO of RevealIQ). NEVER identify as OpenAI, ChatGPT, GPT, Anthropic, Claude, Meta, or Llama.\n"
    personalization = "\n\nPERSONALIZATION:\n"
    display_name = (settings or {}).get('preferred_name') or user_name or (user_email.split('@')[0] if user_email else 'Friend')
    personalization += f"- User: {display_name}\n"
    if memories:
        personalization += "- Memories:\n  " + "\n  ".join([f"• {m}" for m in memories[:20]]) + "\n"
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


def process_uploaded_file(file):
    filename = file.filename.lower()
    if filename.endswith(('.png', '.jpg', '.jpeg', '.webp', '.gif')):
        try:
            img = Image.open(file.stream)
            img.thumbnail((1024, 1024))
            buffered = io.BytesIO()
            fmt = img.format if img.format else 'JPEG'
            img.save(buffered, format=fmt)
            img_str = base64.b64encode(buffered.getvalue()).decode('utf-8')
            return {"type": "image_url", "image_url": {"url": f"data:image/{fmt.lower()};base64,{img_str}"}}
        except Exception as e:
            print(f"[File] Image processing failed: {e}")
            return None
    elif filename.endswith(('.txt', '.md', '.py', '.js', '.html', '.css', '.json', '.xml', '.csv')):
        try:
            text = file.read().decode('utf-8', errors='ignore')
            return {"type": "text", "text": f"\n[File: {file.filename}]\n{text}\n"}
        except:
            return None
    elif filename.endswith('.pdf'):
        try:
            reader = PyPDF2.PdfReader(file.stream)
            text = "\n".join([page.extract_text() for page in reader.pages])
            return {"type": "text", "text": f"\n[PDF: {file.filename}]\n{text.strip()}\n"}
        except Exception as e:
            print(f"[File] PDF processing failed: {e}")
            return None
    elif filename.endswith('.docx'):
        try:
            doc = Document(file.stream)
            text = "\n".join([para.text for para in doc.paragraphs])
            return {"type": "text", "text": f"\n[Word Doc: {file.filename}]\n{text.strip()}\n"}
        except Exception as e:
            print(f"[File] DOCX processing failed: {e}")
            return None
    return None


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
