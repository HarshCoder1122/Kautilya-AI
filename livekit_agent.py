import os
import json
import asyncio
import time as _time
from datetime import datetime
from dotenv import load_dotenv

from livekit import rtc, api
from livekit.agents import (
    AutoSubscribe,
    JobContext,
    WorkerOptions,
    cli,
    Agent,
    AgentSession,
)
from livekit.agents.llm import ChatMessage
from livekit.plugins import sarvam, openai, silero, cartesia, google

load_dotenv()

# ============== Firebase Admin Initialization ==============
db = None
FIREBASE_AVAILABLE = False
firestore = None  # populated after init

def initialize_firebase():
    global db, FIREBASE_AVAILABLE, firestore
    try:
        import firebase_admin
        from firebase_admin import credentials, firestore as _firestore
        if not firebase_admin._apps:
            sa_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON")
            if sa_json:
                try:
                    info = json.loads(sa_json)
                    cred = credentials.Certificate(info)
                    firebase_admin.initialize_app(cred)
                except:
                    if os.path.exists(sa_json):
                        cred = credentials.Certificate(sa_json)
                        firebase_admin.initialize_app(cred)
            if not firebase_admin._apps:
                try: firebase_admin.initialize_app()
                except: pass
        if firebase_admin._apps:
            db = _firestore.client()
            firestore = _firestore
            FIREBASE_AVAILABLE = True
            print("[Firebase] Connected and Ready")
    except Exception as e:
        print(f"[Firebase Error] {e}")

initialize_firebase()


# ============== Helpers ==============
GEMINI_LIVE_MODEL = os.environ.get("GEMINI_LIVE_MODEL", "gemini-3.1-flash-live-preview")

# Indian-accent / pronunciation guidance appended to Gemini Live system prompts.
INDIAN_ACCENT_INSTRUCTION = (
    "VOICE & ACCENT INSTRUCTIONS:\n"
    "- Speak in a natural Indian English accent (like a native Indian speaker from India).\n"
    "- Do NOT use a generic American or British accent.\n"
    "- When the user speaks Hindi or Hinglish, respond in Hindi/Hinglish written in the same script.\n"
    "- Pronounce Indian names, words and places the Indian way (e.g. 'Mumbai', 'Delhi', 'Bharat', 'Namaste').\n"
    "- Keep tone warm, polite, conversational and human — like a helpful Indian customer support agent.\n"
)


def _is_phone_like(s: str) -> bool:
    if not s:
        return False
    s = s.strip()
    if s.startswith("+"):
        return True
    digits = s.replace("-", "").replace(" ", "")
    return digits.isdigit() and len(digits) >= 7


def _phone_variants(raw: str):
    """Return all reasonable lookup keys for a phone number."""
    if not raw:
        return []
    s = raw.strip()
    no_plus = s.lstrip("+")
    out = []
    for v in (s, no_plus, "+" + no_plus):
        if v and v not in out:
            out.append(v)
    # Strip likely country code (91 for India) — best-effort
    if no_plus.startswith("91") and len(no_plus) >= 12:
        local = no_plus[2:]
        for v in (local, "+91" + local):
            if v not in out:
                out.append(v)
    return out


def _extract_phone_from_token(tok: str):
    """Return the token if it looks like a phone number, else None."""
    if not tok:
        return None
    t = tok.strip()
    if t.startswith("+") and t[1:].replace("-", "").isdigit():
        return t
    digits = t.replace("-", "").replace(" ", "")
    if digits.isdigit() and len(digits) >= 7:
        return t
    return None


def _resolve_agent_id(room_name: str):
    """Best-effort parser for LiveKit room names.

    Web (dashboard) format:           voice-<agent_id>--<short_uuid>
    Vobiz / SIP room formats seen:    voice-_+<phone>_<call_uuid>
                                      voice-+<phone>_<call_uuid>
                                      voice-<phone>_<call_uuid>
    For SIP rooms we return the **phone number** as `agent_id` (it acts as the
    lookup key for `active_calls`) and the trailing token as `call_id`.
    """
    clean = (room_name or "").replace("sip:", "").replace("sip-", "")
    parts = clean
    if "voice-" in parts:
        parts = clean.split("voice-", 1)[-1]

    # ---- Web call: <agent_id>--<short_uuid> ----
    if "--" in parts:
        agent_id, call_id = parts.split("--", 1)
        agent_id = (agent_id or "").lstrip("_")
        return agent_id, call_id or None

    # ---- SIP / telephony: pieces separated by underscores ----
    stripped = parts.lstrip("_")
    if "_" in stripped:
        tokens = [t for t in stripped.split("_") if t]
        phone = None
        for tok in tokens:
            ph = _extract_phone_from_token(tok)
            if ph:
                phone = ph
                break
        # Last token (which isn't the phone) = call uuid
        call_id = None
        for tok in reversed(tokens):
            if _extract_phone_from_token(tok) is None:
                call_id = tok
                break
        if phone:
            return phone, call_id
        # Fallback: keep the whole stripped string
        return stripped, None

    return stripped or None, None


def _looks_like_sip_room(room_name: str, room: rtc.Room) -> bool:
    if not room_name:
        return False
    rn = room_name.lower()
    if "sip" in rn:
        return True
    # Vobiz pre-warmed rooms use voice-_+<phone>_<call> — the underscore/plus
    # combo is a strong SIP signal.
    after = rn.split("voice-", 1)[-1]
    if after.startswith("_+") or after.startswith("+"):
        return True
    aid, _ = _resolve_agent_id(room_name)
    if aid and _is_phone_like(aid):
        return True
    return False


async def _lookup_by_phone(phone_raw: str):
    """Try every variant of a phone number against active_calls; return
    (agent_doc, agent_id) or (None, None)."""
    if not (db and phone_raw):
        return None, None
    for v in _phone_variants(phone_raw):
        try:
            call_doc = db.collection('active_calls').document(v).get()
            if call_doc.exists:
                mapped = (call_doc.to_dict() or {}).get('agent_id')
                if mapped:
                    doc = db.collection('agents').document(mapped).get()
                    if doc.exists:
                        print(f"[Config] 🎯 active_calls/{v} → agent {mapped}")
                        return doc, mapped
        except Exception as e:
            print(f"[Config] active_calls/{v} lookup error: {e}")
    return None, None


async def _lookup_by_call_id(call_id: str):
    if not (db and call_id):
        return None, None
    try:
        m = db.collection('call_mappings').document(call_id).get()
        if m.exists:
            mapped = (m.to_dict() or {}).get('agent_id')
            if mapped:
                doc = db.collection('agents').document(mapped).get()
                if doc.exists:
                    print(f"[Config] 🎯 call_mappings/{call_id} → agent {mapped}")
                    return doc, mapped
    except Exception as e:
        print(f"[Config] call_mappings/{call_id} lookup error: {e}")
    return None, None


async def _lookup_by_vobiz_number(phone_raw: str):
    if not (db and phone_raw):
        return None, None
    try:
        for v in _phone_variants(phone_raw):
            results = db.collection('agents').where('vobiz_number', '==', v).limit(1).get()
            if results:
                d = results[0]
                if d.exists:
                    print(f"[Config] 🎯 agent.vobiz_number={v} → agent {d.id}")
                    return d, d.id
    except Exception as e:
        print(f"[Config] vobiz_number lookup error: {e}")
    return None, None


async def _resolve_agent_doc(ctx: JobContext, parsed_id: str, call_id: str, is_sip: bool):
    """Resolve the Firestore agent document.

    Web calls: `parsed_id` IS the agent UUID — direct hit, zero retries.
    SIP calls: `parsed_id` is the customer phone number; we look it up in
    `active_calls`, then `call_mappings`, then by `vobiz_number`. Each lookup
    retries up to ~3s to wait out webhook write latency.
    """
    if not (FIREBASE_AVAILABLE and db) or not parsed_id:
        return None, parsed_id

    if not is_sip:
        # Web call → parsed_id is the agent UUID
        try:
            doc = db.collection('agents').document(parsed_id).get()
            if doc.exists:
                return doc, parsed_id
        except Exception as e:
            print(f"[Config] Direct agent lookup failed: {e}")
        return None, parsed_id

    # ---------- SIP path ----------
    print(f"[Config] SIP fallback chain → phone={parsed_id} call_id={call_id}")

    # Pass 1: try every signal up-front
    for attempt in range(6):  # ~3s with 0.5s sleeps
        # 1. active_calls by phone (set by trigger_vobiz_call BEFORE dial)
        doc, aid = await _lookup_by_phone(parsed_id)
        if doc:
            try:
                ctx.room.metadata = json.dumps({"resolved_agent_id": aid, "resolved_call_id": call_id or ""})
            except Exception:
                pass
            return doc, aid

        # 2. call_mappings by call uuid (set by webhook on ringing)
        doc, aid = await _lookup_by_call_id(call_id)
        if doc:
            try:
                ctx.room.metadata = json.dumps({"resolved_agent_id": aid, "resolved_call_id": call_id})
            except Exception:
                pass
            return doc, aid

        # 3. Look at any SIP participants that have joined
        try:
            for _, p in (ctx.room.remote_participants or {}).items():
                identity = (p.identity or "")
                # Identity examples: "sip_+911171366938", "sip-+911...", "+911..."
                identity_clean = identity.replace("sip-", "")
                if identity_clean.startswith("sip_"):
                    identity_clean = identity_clean[len("sip_"):]
                # Try the full cleaned identity AND any embedded tokens
                candidates = [identity_clean]
                for tok in identity_clean.split("_"):
                    if _extract_phone_from_token(tok):
                        candidates.append(tok)
                for c in candidates:
                    doc, aid = await _lookup_by_phone(c)
                    if doc:
                        try:
                            ctx.room.metadata = json.dumps({"resolved_agent_id": aid, "resolved_call_id": call_id or ""})
                        except Exception:
                            pass
                        return doc, aid
        except Exception as e:
            print(f"[Config] participant scan error: {e}")

        if attempt < 5:
            await asyncio.sleep(0.5)

    # 4. Last resort: agent document with this phone as vobiz_number
    doc, aid = await _lookup_by_vobiz_number(parsed_id)
    if doc:
        return doc, aid

    return None, parsed_id


def _resolve_gemini_model(db_model: str) -> str:
    """Map the dashboard's friendly Gemini aliases to a real, currently-supported
    Live API model id. The legacy `gemini-2.0-flash-exp` is no longer offered
    by Google; we now default to `gemini-3.1-flash-live-preview`.
    """
    default = GEMINI_LIVE_MODEL  # gemini-3.1-flash-live-preview
    if not db_model:
        return default
    m = db_model.lower().strip()

    # Friendly aliases coming from the Studio dropdown
    aliases = {
        "gemini-live": default,
        "gemini-flash-live": default,
        "gemini-2.0-flash": default,
        "gemini-2.0-flash-live": default,
        "gemini-2.0-flash-exp": default,   # legacy / discontinued
        "gemini-2.5-flash": default,
        "gemini-2.5-flash-live": default,
    }
    if m in aliases:
        return aliases[m]

    # If it already looks like a real live-preview model id, pass it through.
    if "live" in m and "preview" in m:
        return db_model

    return default


# ============== Agent ==============
class KautilyaAgent(Agent):
    def __init__(self, **kwargs):
        if 'instructions' not in kwargs:
            kwargs['instructions'] = "You are Kautilya AI assistant."
        super().__init__(**kwargs)


async def entrypoint(ctx: JobContext):
    connect_task = asyncio.create_task(ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY))
    started_at = _time.time()

    print(f"[Agent] Rapid Startup for room: {ctx.room.name}")

    system_prompt = "You are Kautilya AI assistant."
    welcome_message = "Hello, I am Kautilya."
    agent_language = "hi-IN"
    selected_model = "kautilya-daily"

    raw_agent_id, call_id = _resolve_agent_id(ctx.room.name)
    is_sip = _looks_like_sip_room(ctx.room.name, ctx.room)
    print(f"[Agent] Parsed agent_id={raw_agent_id} call_id={call_id} is_sip={is_sip}")

    # ----- FAST PATH: read agent config from room metadata (set by pre-warm) -----
    # Telephony webhooks call create_room_fire_and_forget() which embeds the full
    # agent config in the room metadata BEFORE the SIP user picks up. Reading
    # from there eliminates Firestore latency at the moment the call connects.
    agent_id = raw_agent_id
    meta_loaded = False
    try:
        if ctx.room.metadata:
            meta = json.loads(ctx.room.metadata) or {}
            if isinstance(meta, dict) and meta.get("agent_id"):
                agent_id = meta["agent_id"]
                if meta.get("system_prompt"):
                    system_prompt = meta["system_prompt"]
                if meta.get("welcome_message"):
                    welcome_message = meta["welcome_message"]
                if meta.get("language"):
                    agent_language = meta["language"]
                if meta.get("model"):
                    selected_model = meta["model"]
                meta_loaded = True
                print(f"[Config] ⚡ Loaded from room metadata: agent={agent_id} model={selected_model}")
    except Exception as e:
        print(f"[Config] room.metadata parse warning: {e}")

    # Fallback path: resolve via Firestore (used by Web calls and any SIP call
    # that didn't go through the pre-warm path).
    if not meta_loaded:
        doc, agent_id = await _resolve_agent_doc(ctx, raw_agent_id, call_id, is_sip)
        if doc and getattr(doc, 'exists', False):
            try:
                data = doc.to_dict() or {}
                print(f"[Config] Loaded agent {agent_id} keys={list(data.keys())}")
                system_prompt = data.get("system_prompt") or system_prompt
                welcome_message = data.get("welcome_message") or welcome_message
                agent_language = data.get("language") or agent_language
                selected_model = (data.get("model") or selected_model)
                print(f"[Config] Model selected in dashboard: {selected_model}")
            except Exception as e:
                print(f"[Config] Error reading agent doc: {e}")
        else:
            print(f"[Config] ⚠️ No agent doc resolved for {raw_agent_id} — using defaults")

    await connect_task

    is_gemini_live = "gemini" in (selected_model or "").lower()
    session = None
    agent_obj = None

    try:
        if is_gemini_live:
            api_model = _resolve_gemini_model(selected_model)
            print(f"[Gemini] Initializing RealtimeModel ({api_model}) — language={agent_language}")
            gemini_instructions = (
                f"{system_prompt}\n\n"
                f"{INDIAN_ACCENT_INSTRUCTION}\n"
                f"IMPORTANT: Begin the conversation by saying exactly: \"{welcome_message}\""
            )

            llm_kwargs = {
                "model": api_model,
                "voice": "Puck",
                "instructions": gemini_instructions,
                "temperature": 0.8,
            }
            try:
                llm_plugin = google.realtime.RealtimeModel(language=agent_language, **llm_kwargs)
            except TypeError:
                llm_plugin = google.realtime.RealtimeModel(**llm_kwargs)

            session = AgentSession(llm=llm_plugin)
            agent_obj = KautilyaAgent(instructions=gemini_instructions)
            await session.start(room=ctx.room, agent=agent_obj)

            try:
                msg = ChatMessage(role="user", content=["I have just joined the call. Please introduce yourself exactly as instructed."])
                if hasattr(session, 'chat_ctx'):
                    session.chat_ctx.messages.append(msg)
                    print("[Gemini] ✅ Greeting trigger injected.")
            except Exception as e:
                print(f"[Gemini] Greeting trigger warning: {e}")
        else:
            print(f"[Pipeline] Using STT/LLM/TTS path — model={selected_model} lang={agent_language}")
            vad = silero.VAD.load()
            stt = sarvam.STT(language=agent_language)
            tts = sarvam.TTS(target_language_code=agent_language, model="bulbul:v3")
            llm_plugin = openai.LLM(
                base_url="https://api.groq.com/openai/v1",
                api_key=os.environ.get("GROQ_API_KEY"),
                model="llama-3.3-70b-versatile",
            )

            session = AgentSession(vad=vad, stt=stt, llm=llm_plugin, tts=tts)
            agent_obj = KautilyaAgent(instructions=system_prompt)
            await session.start(room=ctx.room, agent=agent_obj)
            await session.say(welcome_message)
    except Exception as e:
        print(f"[Agent] ❌ Session start failed: {e}")
        return

    while ctx.room.connection_state == rtc.ConnectionState.CONN_CONNECTED:
        await asyncio.sleep(1)

    # ========== SESSION ENDED — Persist transcript & call log ==========
    duration_seconds = int(_time.time() - started_at)
    print(f"[Agent] Session ended for {ctx.room.name} (duration {duration_seconds}s). Saving log...")
    try:
        if FIREBASE_AVAILABLE and db and agent_id:
            transcript_text = ""
            msg_count = 0
            if session is not None and hasattr(session, 'chat_ctx'):
                for m in getattr(session.chat_ctx, 'messages', []) or []:
                    role = (getattr(m, 'role', '') or '').upper()
                    content = getattr(m, 'content', '')
                    if isinstance(content, list):
                        parts = []
                        for p in content:
                            if hasattr(p, 'text'): parts.append(p.text)
                            elif isinstance(p, str): parts.append(p)
                        content = " ".join(parts)
                    if not str(content).strip():
                        continue
                    transcript_text += f"{role}: {content}\n"
                    msg_count += 1

            final_call_id = call_id or ctx.room.name
            try:
                if ctx.room.metadata:
                    final_call_id = json.loads(ctx.room.metadata).get("resolved_call_id", final_call_id)
            except Exception:
                pass

            log_payload = {
                'agent_id': agent_id,
                'call_id': final_call_id,
                'duration': duration_seconds,
                'status': 'completed' if transcript_text.strip() else 'no_audio',
                'messages': msg_count,
                'transcript': transcript_text.strip(),
                'analysis': '',
                'summary': (transcript_text.strip().splitlines()[0][:200] if transcript_text.strip() else 'Call ended'),
                'sentiment': 'neutral',
                'outcome': bool(transcript_text.strip()),
                'model': selected_model,
                'language': agent_language,
                'created_at': firestore.SERVER_TIMESTAMP,
            }

            db.collection('agents').document(agent_id).collection('agent_logs').add(log_payload)

            try:
                db.collection('agents').document(agent_id).update({
                    "call_count": firestore.Increment(1)
                })
            except Exception as e:
                print(f"[Agent] call_count update warning: {e}")

            print(f"[Agent] ✅ agent_logs entry written for call {final_call_id} (msgs={msg_count})")
    except Exception as e:
        print(f"[Agent] ❌ Error saving call log: {e}")


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
