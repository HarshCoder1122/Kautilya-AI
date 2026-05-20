import os
import re
import json
import uuid
import asyncio
import time as _time
import sys
import threading
from datetime import datetime
from dotenv import load_dotenv
from fastapi import FastAPI
import uvicorn

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
from services.llm_service import call_nvidia

load_dotenv()

# Force unbuffered output for faster logs on HF
sys.stdout.reconfigure(line_buffering=True) if hasattr(sys.stdout, 'reconfigure') else None

# ============== Health Check Server (Hugging Face) ==============
app = FastAPI()

@app.get("/")
def health_check():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

def run_health_check():
    uvicorn.run(app, host="0.0.0.0", port=7860, log_level="warning")

# ---- Module-level pre-warm (runs ONCE when worker process starts) ----
_PREWARMED_VAD = None

def _get_vad():
    global _PREWARMED_VAD
    if _PREWARMED_VAD is None:
        _PREWARMED_VAD = silero.VAD.load()
        print("[PreWarm] VAD loaded", flush=True)
    return _PREWARMED_VAD

# Call this at module load time so idle workers are ready:
try:
    _get_vad()
    print("[PreWarm] VAD pre-loaded at startup", flush=True)
except Exception as e:
    print(f"[PreWarm] VAD warmup failed: {e}", flush=True)

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
            print("[Firebase] Connected and Ready", flush=True)
    except Exception as e:
        print(f"[Firebase Error] {e}", flush=True)

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


def _ids_match(left: str, right: str) -> bool:
    """Loose but explicit match for provider call identifiers."""
    if not left or not right:
        return False
    return str(left).strip() == str(right).strip()


def _clean_placeholders(text: str) -> str:
    """Removes raw template variables like {name}, {email_id} if they weren't resolved."""
    if not text: return ""
    return re.sub(r'\{[a-zA-Z0-9_ \-]+\}', '', text).strip()


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
    # 1. Web calls always use '--' separator
    if "--" in rn:
        return False
    # 2. Check identity of participants
    for p in (room.remote_participants or {}).values():
        if (p.identity or "").lower().startswith("sip"):
            return True
    # 3. Check room name patterns
    if "sip" in rn:
        return True
    if rn.startswith("voice-") and "_" in rn:
        after = rn.split("voice-", 1)[-1]
        if after.startswith("_+") or after.startswith("+"):
            return True
        # Check if it resolves to a phone number
        aid, _ = _resolve_agent_id(room_name)
        if aid and _is_phone_like(aid):
            return True
    return False


async def _lookup_by_phone(phone_raw: str, call_id: str = None):
    """Resolve (agent_doc, agent_id) for a phone number, race-safe.

    Strategy:
      1. **FIFO claim** — read `active_calls/<phone>/pending` ordered by
         created_at ASC, transactionally mark the OLDEST unclaimed entry as
         claimed and return its agent_id. This survives the case where two
         simultaneous calls to the same phone wrote into `active_calls`
         within milliseconds of each other (latest-wins would mis-route the
         first call to the second call's agent).
      2. **Top-level fallback** — if no pending docs exist (e.g. webhook
         ran before this code shipped, or campaign worker only wrote the
         legacy shape), fall back to the latest-wins `active_calls/<phone>`
         document to remain backwards-compatible.
    """
    if not (db and phone_raw):
        return None, None

    for v in _phone_variants(phone_raw):
        pending_call_already_claimed = False

        # ---- 1. Deterministic lookup by call_id (NEW) ----
        try:
            if call_id:
                pending_ref = db.collection('active_calls').document(v).collection('pending').document(call_id)
                
                @firestore.transactional
                def _claim_deterministic(tx, ref):
                    snap = ref.get(transaction=tx)
                    if not snap.exists:
                        return None
                    data = snap.to_dict() or {}
                    if data.get('claimed'):
                        return {"_already_claimed": True, **data}
                    tx.update(ref, {"claimed": True, "claimed_at": firestore.SERVER_TIMESTAMP})
                    return data

                tx_result = _claim_deterministic(db.transaction(), pending_ref)
                if tx_result and tx_result.get('_already_claimed'):
                    pending_call_already_claimed = True
                    print(f"[Config] active_calls/{v}/pending/{call_id} already claimed; rejecting duplicate room", flush=True)
                    continue
                if tx_result and tx_result.get('agent_id'):
                    mapped = tx_result['agent_id']
                    agent_doc = db.collection('agents').document(mapped).get()
                    if agent_doc.exists:
                        print(f"[Config] 🎯 active_calls/{v}/pending/{call_id} → agent {mapped} (Deterministic)", flush=True)
                        return agent_doc, mapped
        except Exception as e:
            print(f"[Config] Deterministic claim error on {v}/{call_id}: {e}", flush=True)

        # ---- 2. FIFO claim fallback ----
        # In standard SIP mode, LiveKit generates a random suffix (call_id)
        # which won't match the Vobiz CallUUID. If the deterministic lookup
        # above failed, we fall back to FIFO claim to catch the pending call.
        try:
            pending_q = (db.collection('active_calls').document(v)
                           .collection('pending')
                           .where(filter=firestore.FieldFilter('claimed', '==', False))
                           .where(filter=firestore.FieldFilter('completed', '!=', True))
                           .order_by('created_at')
                           .limit(1))
            pending_docs = list(pending_q.stream())
            if pending_docs:
                claim_ref = pending_docs[0].reference

                @firestore.transactional
                def _claim_fifo(tx, ref):
                    snap = ref.get(transaction=tx)
                    if not snap.exists:
                        return None
                    data = snap.to_dict() or {}
                    if data.get('claimed'):
                        return None
                    tx.update(ref, {"claimed": True,
                                     "claimed_at": firestore.SERVER_TIMESTAMP})
                    return data

                tx_result = _claim_fifo(db.transaction(), claim_ref)
                if tx_result and tx_result.get('agent_id'):
                    mapped = tx_result['agent_id']
                    agent_doc = db.collection('agents').document(mapped).get()
                    if agent_doc.exists:
                        print(f"[Config] 🎯 active_calls/{v}/pending → agent {mapped} (FIFO claim)", flush=True)
                        return agent_doc, mapped
        except Exception as e:
            print(f"[Config] FIFO claim error on {v}: {e}", flush=True)

        # ---- 3. Legacy top-level doc fallback ----
        try:
            if pending_call_already_claimed:
                continue
            call_doc = db.collection('active_calls').document(v).get()
            if call_doc.exists:
                call_data = call_doc.to_dict() or {}
                stored_call_id = call_data.get('call_uuid') or call_data.get('call_id')
                # Only skip if we have BOTH IDs and they strictly mismatch.
                # If room_call_id is a random suffix, we ignore the mismatch.
                is_real_uuid = len(str(call_id)) > 15 
                if call_id and stored_call_id and is_real_uuid and not _ids_match(call_id, stored_call_id):
                    print(f"[Config] Skipping active_calls/{v} legacy mapping: mismatch {call_id} vs {stored_call_id}", flush=True)
                    continue
                mapped = call_data.get('agent_id')
                if mapped:
                    doc = db.collection('agents').document(mapped).get()
                    if doc.exists:
                        print(f"[Config] 🎯 active_calls/{v} → agent {mapped} (legacy)", flush=True)
                        return doc, mapped
        except Exception as e:
            print(f"[Config] active_calls/{v} lookup error: {e}", flush=True)
    return None, None


async def _cleanup_pending_doc(phone: str, call_id: str):
    """Mark the pending doc as completed so it never gets re-claimed."""
    if not (db and phone and call_id):
        return
    try:
        for v in _phone_variants(phone):
            ref = db.collection('active_calls').document(v).collection('pending').document(call_id)
            
            def _update_doc():
                snap = ref.get()
                if snap.exists:
                    ref.update({
                        "completed": True,
                        "completed_at": firestore.SERVER_TIMESTAMP,
                        "claimed": True,
                    })
                    return True
                return False

            updated = await asyncio.to_thread(_update_doc)
            if updated:
                print(f"[Cleanup] Marked pending/{call_id} as completed for {v}", flush=True)
                break
    except Exception as e:
        print(f"[Cleanup] Error: {e}", flush=True)


async def _lookup_by_call_id(call_id: str):
    if not (db and call_id):
        return None, None
    try:
        m_ref = db.collection('call_mappings').document(call_id)

        @firestore.transactional
        def _claim_call_mapping(tx, ref):
            snap = ref.get(transaction=tx)
            if not snap.exists:
                return None
            data = snap.to_dict() or {}
            if data.get('worker_claimed'):
                return {"_already_claimed": True, **data}
            if data.get('agent_id'):
                tx.set(ref, {
                    "worker_claimed": True,
                    "worker_claimed_at": firestore.SERVER_TIMESTAMP,
                }, merge=True)
            return data

        data = _claim_call_mapping(db.transaction(), m_ref)
        if data and data.get('_already_claimed'):
            print(f"[Config] call_mappings/{call_id} already claimed; rejecting duplicate room", flush=True)
            return None, "__already_claimed__"
        mapped = (data or {}).get('agent_id')
        if mapped:
            doc = db.collection('agents').document(mapped).get()
            if doc.exists:
                print(f"[Config] 🎯 call_mappings/{call_id} → agent {mapped} (global claim)", flush=True)
                return doc, mapped
    except Exception as e:
        print(f"[Config] call_mappings/{call_id} lookup error: {e}", flush=True)
    return None, None


async def _lookup_by_vobiz_number(phone_raw: str):
    if not (db and phone_raw):
        return None, None
    try:
        for v in _phone_variants(phone_raw):
            results = db.collection('agents').where(filter=firestore.FieldFilter('vobiz_number', '==', v)).limit(1).get()
            if results:
                d = results[0]
                if d.exists:
                    print(f"[Config] 🎯 agent.vobiz_number={v} → agent {d.id}", flush=True)
                    return d, d.id
    except Exception as e:
        print(f"[Config] vobiz_number lookup error: {e}", flush=True)
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
            print(f"[Config] Direct agent lookup failed: {e}", flush=True)
        return None, parsed_id

    # ---------- SIP path ----------
    print(f"[Config] SIP fallback chain → phone={parsed_id} call_id={call_id}", flush=True)

    # Pass 1: try every signal up-front. Increased check frequency for faster startup.
    for attempt in range(15):  # ~3s with 0.2s sleeps
        # 1. Global call-id claim. This prevents duplicate rooms for the same
        # provider call from starting two agent sessions across phone variants.
        doc, aid = await _lookup_by_call_id(call_id)
        if aid == "__already_claimed__":
            return None, parsed_id
        if doc:
            try:
                ctx.room.metadata = json.dumps({"resolved_agent_id": aid, "resolved_call_id": call_id})
            except Exception:
                pass
            return doc, aid

        # 2. active_calls by phone (set by trigger_vobiz_call BEFORE dial)
        doc, aid = await _lookup_by_phone(parsed_id, call_id)
        if doc:
            try:
                ctx.room.metadata = json.dumps({"resolved_agent_id": aid, "resolved_call_id": call_id or ""})
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
                    doc, aid = await _lookup_by_phone(c, call_id)
                    if doc:
                        try:
                            ctx.room.metadata = json.dumps({"resolved_agent_id": aid, "resolved_call_id": call_id or ""})
                        except Exception:
                            pass
                        return doc, aid
        except Exception as e:
            print(f"[Config] participant scan error: {e}", flush=True)

        if attempt < 14:
            await asyncio.sleep(0.2)

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
    # START CONNECT AND LOOKUP IN PARALLEL
    connect_task = asyncio.create_task(ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY))
    started_at = _time.time()

    print(f"[Agent] Rapid Startup for room: {ctx.room.name}", flush=True)

    system_prompt = "You are Kautilya AI assistant."
    welcome_message = "Hello, I am Kautilya."
    agent_language = "hi-IN"
    selected_model = "kautilya-daily"
    owner_uid = None

    raw_agent_id, call_id = _resolve_agent_id(ctx.room.name)
    is_sip = _looks_like_sip_room(ctx.room.name, ctx.room)
    print(f"[Agent] Parsed agent_id={raw_agent_id} call_id={call_id} is_sip={is_sip}", flush=True)


    agent_voice = "shubh"
    handoff_enabled = False
    handoff_number = ""
    handoff_callback_message = "All our support team members are busy right now. Would you like to add a callback request?"

    # ----- FAST PATH: read agent config from room metadata (set by pre-warm) -----
    agent_id = raw_agent_id
    meta_loaded = False
    try:
        if ctx.room.metadata:
            meta = json.loads(ctx.room.metadata) or {}
            if isinstance(meta, dict) and meta.get("agent_id"):
                agent_id = meta["agent_id"]
                system_prompt = meta.get("system_prompt") or system_prompt
                welcome_message = meta.get("welcome_message") or welcome_message
                agent_language = meta.get("language") or agent_language
                selected_model = meta.get("model") or selected_model
                agent_voice = meta.get("voice") or agent_voice
                owner_uid = meta.get("uid")
                meta_loaded = True
                print(f"[Config] ⚡ Loaded from room metadata: agent={agent_id} model={selected_model}", flush=True)
    except Exception as e:
        print(f"[Config] room.metadata parse warning: {e}", flush=True)

    if meta_loaded and is_sip and call_id:
        _, claim_status = await _lookup_by_call_id(call_id)
        if claim_status == "__already_claimed__":
            print(f"[Agent] Rejecting duplicate SIP metadata room: {ctx.room.name}", flush=True)
            try:
                if connect_task.done(): await connect_task
                else: connect_task.cancel(); await connect_task
            except: pass
            return

    # Fallback path: resolve via Firestore
    if not meta_loaded:
        doc, agent_id = await _resolve_agent_doc(ctx, raw_agent_id, call_id, is_sip)
        if doc and getattr(doc, 'exists', False):
            try:
                data = doc.to_dict() or {}
                system_prompt = data.get("system_prompt") or system_prompt
                welcome_message = data.get("welcome_message") or welcome_message
                agent_language = data.get("language") or agent_language
                selected_model = (data.get("model") or selected_model)
                agent_voice = data.get("voice") or agent_voice
                owner_uid = data.get("uid")
                handoff_enabled = bool(data.get("handoff_enabled", False))
                handoff_number = data.get("handoff_number", "")
                handoff_callback_message = data.get("handoff_callback_message") or handoff_callback_message
                print(f"[Config] Loaded agent {agent_id} (Firestore)", flush=True)
            except Exception as e:
                print(f"[Config] Error reading agent doc: {e}", flush=True)
        else:
            if is_sip:
                print(f"[Agent] Rejecting SIP room without mapping: {ctx.room.name}", flush=True)
                try:
                    if connect_task.done(): await connect_task
                    else: connect_task.cancel(); await connect_task
                except: pass
                return
    
    system_prompt = _clean_placeholders(system_prompt)
    welcome_message = _clean_placeholders(welcome_message)

    if handoff_enabled:
        system_prompt += f"\n\nHANDOFF: If user wants human, say: \"{handoff_callback_message}\""

    # Hardcoded Lead Capture Instructions
    system_prompt += "\n\nLEAD CAPTURE: You MUST ask the user for their Name, Email ID, and Contact Number during the conversation if not already provided. This is essential for our records."

    await connect_task

    is_gemini_live = "gemini" in (selected_model or "").lower()
    session = None
    agent_obj = None
    transcript_turns = []

    def _record_turn(role, content):
        if not content: return
        text = str(content).strip()
        if not text: return
        if transcript_turns and transcript_turns[-1].get('role') == role:
            last = transcript_turns[-1].get('content', '')
            if text == last or text in last or last in text:
                transcript_turns[-1] = {"role": role, "content": text, "ts": _time.time()}
                return
        transcript_turns.append({"role": role, "content": text, "ts": _time.time()})

    def _attach_session_events(sess):
        if sess is None: return
        try:
            # ---- Multimodal / Gemini Realtime path ----
            @sess.on("conversation_item_added")
            def _on_item(ev):
                item = getattr(ev, 'item', None) or ev
                role = getattr(item, 'role', None) or 'unknown'
                content = getattr(item, 'text_content', None) or getattr(item, 'content', '')
                _record_turn(str(role).lower(), content)
        except: pass

        try:
            # ---- Standard VoiceAssistant / Pipeline path ----
            # Some versions use SpeechEvent with .transcript; others pass string.
            @sess.on("user_speech_committed")
            def _on_user_speech(ev):
                txt = getattr(ev, 'transcript', str(ev))
                _record_turn("user", txt)

            @sess.on("agent_speech_committed")
            def _on_agent_speech(ev):
                txt = getattr(ev, 'transcript', str(ev))
                _record_turn("assistant", txt)
        except: pass

    try:
        if is_gemini_live:
            api_model = _resolve_gemini_model(selected_model)
            gemini_instructions = f"{system_prompt}\n\n{INDIAN_ACCENT_INSTRUCTION}\nIMPORTANT: Greet with: \"{welcome_message}\""
            llm_kwargs = {
                "model": api_model,
                "voice": agent_voice if agent_voice in ["Puck", "Charon", "Kore", "Fenrir", "Aoede"] else "Puck",
                "instructions": gemini_instructions,
                "temperature": 0.8,
            }
            try: llm_plugin = google.realtime.RealtimeModel(language=agent_language, **llm_kwargs)
            except: llm_plugin = google.realtime.RealtimeModel(**llm_kwargs)

            session = AgentSession(llm=llm_plugin)
            agent_obj = KautilyaAgent(instructions=gemini_instructions)
            _attach_session_events(session)
            await session.start(room=ctx.room, agent=agent_obj)

            greet_prompt = f"Greet me warmly in {agent_language} with: \"{welcome_message}\""
            triggered = False
            try:
                model_lower = (selected_model or "").lower()
                is_multimodal = any(x in model_lower for x in ["flash", "live", "gemini"])
                if hasattr(session, 'generate_reply') and not is_multimodal:
                    await session.generate_reply(instructions=greet_prompt)
                    triggered = True
                elif hasattr(session, 'say'):
                    await session.say(welcome_message)
                    triggered = True
            except: pass
        else:
            vad = _get_vad()
            stt = sarvam.STT(language=agent_language)
            tts = sarvam.TTS(target_language_code=agent_language, speaker=agent_voice, model="bulbul:v3")
            llm_plugin = openai.LLM(base_url="https://api.groq.com/openai/v1", api_key=os.environ.get("GROQ_API_KEY"), model="llama-3.3-70b-versatile")
            session = AgentSession(vad=vad, stt=stt, llm=llm_plugin, tts=tts)
            agent_obj = KautilyaAgent(instructions=system_prompt)
            _attach_session_events(session)
            await session.start(room=ctx.room, agent=agent_obj)
            await asyncio.sleep(0.8)
            await session.say(welcome_message)
    except Exception as e:
        print(f"[Agent] ❌ Session start failed: {e}", flush=True)
        return

    while ctx.room.connection_state == rtc.ConnectionState.CONN_CONNECTED:
        await asyncio.sleep(1)

    # ========== SESSION ENDED — Persist transcript & call log ==========
    duration_seconds = int(_time.time() - started_at)
    print(f"[Agent] Session ended (duration {duration_seconds}s). Saving log...", flush=True)

    if not transcript_turns and session and hasattr(session, 'chat_ctx'):
        for m in getattr(session.chat_ctx, 'messages', []):
            _record_turn((getattr(m, 'role', '') or 'unknown').lower(), getattr(m, 'content', ''))

    convo_turns = [t for t in transcript_turns if t.get('role') in ('user', 'assistant')]
    transcript_text = "\n".join(f"{t['role'].upper()}: {t['content']}" for t in convo_turns).strip()
    msg_count = len(convo_turns)

    # Save transcript to global collection for compatibility with background analytics
    if FIREBASE_AVAILABLE and db and transcript_text and agent_id:
        try:
            t_doc = {
                "agent_id": agent_id,
                "call_id": call_id or ctx.room.name,
                "transcript": transcript_text,
                "created_at": firestore.SERVER_TIMESTAMP,
                "source": 'voice_sip' if is_sip else 'voice_web'
            }
            await asyncio.to_thread(db.collection('transcripts').add, t_doc)
            print(f"[Agent] Transcript saved for {agent_id} ({len(transcript_text)} chars)", flush=True)
        except Exception as e:
            print(f"[Agent] Transcript save warning: {e}", flush=True)

    summary = ""
    sentiment = "neutral"
    key_topics = []
    outcome_label = "completed" if transcript_text else "no_audio"

    print(f"[Agent] Analyzing transcript ({msg_count} turns, {len(transcript_text)} chars)...", flush=True)

    try:
        if transcript_text and msg_count >= 2:
            analysis_prompt = (
                "You are a call analyst. Extract JSON only:\n"
                '{"summary": "...", "sentiment": "positive|neutral|negative", "outcome": "...", "topics": [...], '
                '"lead": {"name": "...", "email": "...", "phone": "...", "intent": "...", "score": 0-10}}\n\n'
                f"TRANSCRIPT:\n{transcript_text[:6000]}"
            )
            # Offload blocking LLM call to thread to prevent health-check timeout
            result = await asyncio.to_thread(
                call_nvidia,
                [{"role": "user", "content": analysis_prompt}],
                stream=False,
                max_tokens=600,
                model='meta/llama-3.3-70b-instruct'
            )
            print(f"[Agent] Analysis result received from LLM", flush=True)
            if result:
                cleaned = re.sub(r"<thinking>.*?</thinking>", "", result, flags=re.DOTALL).strip()
                m = re.search(r"\{[\s\S]*\}", cleaned)
                if m:
                    parsed = json.loads(m.group(0))
                    summary = parsed.get('summary', '')
                    sentiment = parsed.get('sentiment', 'neutral')
                    outcome_label = parsed.get('outcome', outcome_label)
                    key_topics = (parsed.get('topics') or [])[:5]
                    print(f"[Agent] Analysis parsed: sentiment={sentiment}, outcome={outcome_label}", flush=True)
                    
                    lead_data = parsed.get('lead')
                    if lead_data and owner_uid:
                        # Only save if there's some useful info
                        if any(lead_data.get(k) for k in ['name', 'email', 'phone']):
                            lead_id = 'lead_' + uuid.uuid4().hex[:20]
                            lead_doc = {
                                "id": lead_id,
                                "uid": owner_uid,
                                "agent_id": agent_id,
                                "name": str(lead_data.get('name') or '')[:120],
                                "email": str(lead_data.get('email') or '')[:200],
                                "phone": str(lead_data.get('phone') or '')[:40],
                                "message": summary,
                                "source": 'voice_sip' if is_sip else 'voice_web',
                                "status": "new",
                                "sentiment": sentiment,
                                "intent": str(lead_data.get('intent') or '')[:400],
                                "score": int(lead_data.get('score') or 0),
                                "created_at": firestore.SERVER_TIMESTAMP,
                            }
                            await asyncio.to_thread(db.collection('leads').document(lead_id).set, lead_doc)
                            print(f"[Agent] 🏆 Lead captured: {lead_id}", flush=True)
                else:
                    print(f"[Agent] No JSON found in LLM response: {result[:200]}...", flush=True)
            else:
                print(f"[Agent] LLM returned empty analysis result", flush=True)
    except Exception as e:
        print(f"[Agent] Analysis block error: {e}", flush=True)

    if not summary and convo_turns: summary = convo_turns[0]['content'][:200]

    if is_sip and raw_agent_id and call_id:
        await _cleanup_pending_doc(raw_agent_id, call_id)

    try:
        if FIREBASE_AVAILABLE and db and agent_id:
            log_payload = {
                'agent_id': agent_id, 'call_id': call_id or ctx.room.name,
                'channel': 'voice_sip' if is_sip else 'voice_web',
                'duration': duration_seconds, 'status': outcome_label,
                'messages': msg_count, 'transcript': transcript_text,
                'summary': summary, 'sentiment': sentiment, 'topics': key_topics,
                'model': selected_model, 'language': agent_language,
                'created_at': firestore.SERVER_TIMESTAMP, 'timestamp': int(_time.time()),
            }
            
            def _save_final_logs():
                db.collection('agents').document(agent_id).collection('agent_logs').add(log_payload)
                db.collection('agents').document(agent_id).update({"call_count": firestore.Increment(1)})

            await asyncio.to_thread(_save_final_logs)
            print(f"[Agent] ✅ Log saved for {agent_id}", flush=True)
    except Exception as e:
        print(f"[Agent] ❌ Save failed: {e}", flush=True)


if __name__ == "__main__":
    try: num_idle = int(os.environ.get("LIVEKIT_NUM_IDLE", "2"))
    except: num_idle = 2

    worker_kwargs = {"entrypoint_fnc": entrypoint}
    agent_name = os.environ.get("LIVEKIT_AGENT_NAME", "").strip()
    if agent_name: worker_kwargs["agent_name"] = agent_name

    try: opts = WorkerOptions(num_idle_processes=num_idle, **worker_kwargs)
    except: opts = WorkerOptions(**worker_kwargs)

    # Start health check server in background to prevent HF timeout
    print("[HealthCheck] Starting server on port 7860...", flush=True)
    threading.Thread(target=run_health_check, daemon=True).start()

    cli.run_app(opts)
