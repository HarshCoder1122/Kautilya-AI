import os
import re
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
    # 1. Check identity of participants
    for p in (room.remote_participants or {}).values():
        if (p.identity or "").lower().startswith("sip"):
            return True
    # 2. Check room name patterns
    return "sip" in rn or rn.startswith("voice-")
    # combo is a strong SIP signal.
    after = rn.split("voice-", 1)[-1]
    if after.startswith("_+") or after.startswith("+"):
        return True
    aid, _ = _resolve_agent_id(room_name)
    if aid and _is_phone_like(aid):
        return True
    return False


async def _lookup_by_phone(phone_raw: str):
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
        # ---- 1. FIFO claim from pending subcollection ----
        try:
            pending_q = (db.collection('active_calls').document(v)
                           .collection('pending')
                           .where(filter=firestore.FieldFilter('claimed', '==', False))
                           .order_by('created_at')
                           .limit(1))
            pending_docs = list(pending_q.stream())
            if pending_docs:
                claim_ref = pending_docs[0].reference

                @firestore.transactional
                def _claim(tx, ref):
                    snap = ref.get(transaction=tx)
                    if not snap.exists:
                        return None
                    data = snap.to_dict() or {}
                    if data.get('claimed'):
                        return None
                    tx.update(ref, {"claimed": True,
                                     "claimed_at": firestore.SERVER_TIMESTAMP})
                    return data

                tx_result = _claim(db.transaction(), claim_ref)
                if tx_result and tx_result.get('agent_id'):
                    mapped = tx_result['agent_id']
                    agent_doc = db.collection('agents').document(mapped).get()
                    if agent_doc.exists:
                        print(f"[Config] 🎯 active_calls/{v}/pending → agent {mapped} (FIFO claim)")
                        return agent_doc, mapped
        except Exception as e:
            print(f"[Config] FIFO claim error on {v}: {e}")

        # ---- 2. Legacy top-level doc fallback ----
        try:
            call_doc = db.collection('active_calls').document(v).get()
            if call_doc.exists:
                mapped = (call_doc.to_dict() or {}).get('agent_id')
                if mapped:
                    doc = db.collection('agents').document(mapped).get()
                    if doc.exists:
                        print(f"[Config] 🎯 active_calls/{v} → agent {mapped} (legacy)")
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
            results = db.collection('agents').where(filter=firestore.FieldFilter('vobiz_number', '==', v)).limit(1).get()
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

    agent_voice = "shubh"
    handoff_enabled = False
    handoff_number = ""
    handoff_callback_message = "All our support team members are busy right now. Would you like to add a callback request?"

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
                if meta.get("voice"):
                    agent_voice = meta["voice"]
                meta_loaded = True
                print(f"[Config] ⚡ Loaded from room metadata: agent={agent_id} model={selected_model} voice={agent_voice}")
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
                agent_voice = data.get("voice") or agent_voice
                handoff_enabled = bool(data.get("handoff_enabled", False))
                handoff_number = data.get("handoff_number", "")
                handoff_callback_message = data.get("handoff_callback_message") or handoff_callback_message
                print(f"[Config] Model selected in dashboard: {selected_model}")
            except Exception as e:
                print(f"[Config] Error reading agent doc: {e}")
        else:
            print(f"[Config] ⚠️ No agent doc resolved for {raw_agent_id} — using defaults")

    if handoff_enabled:
        hardcoded_instructions = f"""
\n\n---
IMPORTANT HANDOFF INSTRUCTIONS:
If the user requests to speak with a human or support, DO NOT transfer them immediately.
Instead, tell them exactly: "{handoff_callback_message}"
If they agree to a callback, ask for their preferred time and note it down. 
(For your internal context, the assigned support number is {handoff_number}, but you must follow this callback flow as the team is currently busy.)
---
"""
        system_prompt += hardcoded_instructions

    await connect_task

    is_gemini_live = "gemini" in (selected_model or "").lower()
    session = None
    agent_obj = None

    # ========== Transcript collection (events from AgentSession) ==========
    # Both Sarvam-pipeline and Gemini-Live sessions fire conversation events;
    # subscribing here gives us a single, ordered list of turns regardless of
    # which path is active.
    transcript_turns = []  # list of {"role": "...", "content": "...", "ts": float}

    def _record_turn(role, content):
        if not content:
            return
        try:
            text = content
            if isinstance(content, (list, tuple)):
                parts = []
                for p in content:
                    if hasattr(p, 'text'):
                        parts.append(p.text)
                    elif isinstance(p, str):
                        parts.append(p)
                text = " ".join(parts)
            text = str(text or "").strip()
            if not text:
                return
            # De-dupe last entry (Gemini sometimes emits partial+final)
            if transcript_turns and transcript_turns[-1].get('role') == role:
                last = transcript_turns[-1].get('content', '')
                if text == last or text in last or last in text:
                    transcript_turns[-1] = {"role": role, "content": text, "ts": _time.time()}
                    return
            transcript_turns.append({"role": role, "content": text, "ts": _time.time()})
        except Exception as e:
            print(f"[Transcript] record warning: {e}")

    def _attach_session_events(sess):
        if sess is None:
            return
        # 1. The canonical livekit-agents 1.x event
        try:
            @sess.on("conversation_item_added")
            def _on_item(ev):
                item = getattr(ev, 'item', None) or ev
                role = getattr(item, 'role', None) or 'unknown'
                content = getattr(item, 'text_content', None)
                if content is None:
                    content = getattr(item, 'content', '')
                _record_turn(str(role).lower(), content)
        except Exception as e:
            print(f"[Transcript] conversation_item_added hook failed: {e}")

        # 2. Fallback events (older API versions)
        for evname, role in (("user_input_transcribed", "user"),
                             ("agent_speech_committed", "assistant"),
                             ("agent_response_committed", "assistant")):
            try:
                @sess.on(evname)
                def _on_evt(ev, _role=role):
                    text = getattr(ev, 'transcript', None) or getattr(ev, 'text', None) or getattr(ev, 'content', None)
                    if text is None and hasattr(ev, 'message'):
                        text = getattr(ev.message, 'content', None)
                    _record_turn(_role, text)
            except Exception:
                pass

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
                "voice": agent_voice if agent_voice in ["Puck", "Charon", "Kore", "Fenrir", "Aoede"] else "Puck",
                "instructions": gemini_instructions,
                "temperature": 0.8,
            }
            try:
                llm_plugin = google.realtime.RealtimeModel(language=agent_language, **llm_kwargs)
            except TypeError:
                llm_plugin = google.realtime.RealtimeModel(**llm_kwargs)

            session = AgentSession(llm=llm_plugin)
            agent_obj = KautilyaAgent(instructions=gemini_instructions)
            _attach_session_events(session)
            await session.start(room=ctx.room, agent=agent_obj)

            # Kick off the first turn so Gemini actually speaks the welcome
            # line. Without this the realtime session sits idle and we see
            # "received server content but no active generation" warnings.
            greet_prompt = (
                f"I have just joined the call. Greet me warmly in {agent_language} with: \"{welcome_message}\""
                if welcome_message else
                "I have just joined the call. Please introduce yourself exactly as instructed."
            )
            triggered = False
            try:
                if hasattr(session, 'generate_reply'):
                    await session.generate_reply(instructions=greet_prompt)
                    triggered = True
                    print("[Gemini] ✅ generate_reply() kicked off welcome turn.")
            except Exception as e:
                print(f"[Gemini] generate_reply failed: {e}")
            if not triggered:
                try:
                    if hasattr(session, 'say'):
                        await session.say(welcome_message or "Hello, I am here to help you.")
                        triggered = True
                        print("[Gemini] ✅ session.say() fallback used.")
                except Exception as e:
                    print(f"[Gemini] say fallback failed: {e}")
            if not triggered:
                try:
                    msg = ChatMessage(role="user", content=[greet_prompt])
                    if hasattr(session, 'chat_ctx'):
                        session.chat_ctx.messages.append(msg)
                        print("[Gemini] ⚠️ Only chat_ctx injected (no generate_reply support).")
                except Exception as e:
                    print(f"[Gemini] chat_ctx fallback failed: {e}")
        else:
            print(f"[Pipeline] Using STT/LLM/TTS path — model={selected_model} lang={agent_language}")
            vad = silero.VAD.load()
            stt = sarvam.STT(language=agent_language)
            tts = sarvam.TTS(target_language_code=agent_language, speaker=agent_voice, model="bulbul:v3")
            llm_plugin = openai.LLM(
                base_url="https://api.groq.com/openai/v1",
                api_key=os.environ.get("GROQ_API_KEY"),
                model="llama-3.3-70b-versatile",
            )

            session = AgentSession(vad=vad, stt=stt, llm=llm_plugin, tts=tts)
            agent_obj = KautilyaAgent(instructions=system_prompt)
            _attach_session_events(session)
            await session.start(room=ctx.room, agent=agent_obj)
            # Small delay to allow SIP bridge to stabilize and avoid synchronizer race
            await asyncio.sleep(0.8)
            await session.say(welcome_message)
    except Exception as e:
        print(f"[Agent] ❌ Session start failed: {e}")
        return

    while ctx.room.connection_state == rtc.ConnectionState.CONN_CONNECTED:
        await asyncio.sleep(1)

    # ========== SESSION ENDED — Persist transcript & call log ==========
    duration_seconds = int(_time.time() - started_at)
    print(f"[Agent] Session ended for {ctx.room.name} (duration {duration_seconds}s). Saving log...")

    # 1. Backfill from chat_ctx if event hooks didn't catch anything (covers
    #    older livekit-agents versions and Sarvam pipeline edge cases).
    if not transcript_turns and session is not None and hasattr(session, 'chat_ctx'):
        try:
            for m in getattr(session.chat_ctx, 'messages', []) or []:
                role = (getattr(m, 'role', '') or 'unknown').lower()
                content = getattr(m, 'content', '')
                _record_turn(role, content)
        except Exception as e:
            print(f"[Transcript] chat_ctx backfill warning: {e}")

    # 2. Build a clean ordered transcript (drop the system role)
    convo_turns = [t for t in transcript_turns if t.get('role') in ('user', 'assistant')]
    transcript_text = "\n".join(f"{t['role'].upper()}: {t['content']}" for t in convo_turns).strip()
    msg_count = len(convo_turns)

    # 3. Post-call analysis via NVIDIA NIM (Coder/Nemotron). Best-effort —
    #    if it fails or has no transcript, fall back to neutral defaults.
    summary = ""
    sentiment = "neutral"
    key_topics: list = []
    outcome_label = "completed" if transcript_text else "no_audio"
    try:
        if transcript_text and msg_count >= 2:
            from services.llm_service import call_nvidia
            analysis_prompt = (
                "You are a call-quality analyst. Read the call transcript below "
                "(roles: USER = customer, ASSISTANT = AI agent). Reply with STRICT JSON only:\n"
                '{"summary": "<1-2 sentence summary>",'
                ' "sentiment": "positive|neutral|negative",'
                ' "outcome": "successful|partial|failed",'
                ' "topics": ["topic1", "topic2"]}\n\n'
                f"TRANSCRIPT:\n{transcript_text[:6000]}"
            )
            print(f"[Analysis] Calling NVIDIA NIM (Coder) for {msg_count}-turn transcript...")
            result = call_nvidia(
                [{"role": "user", "content": analysis_prompt}],
                stream=False,
                max_tokens=600,
                model='nvidia/llama-3.1-nemotron-70b-instruct',
            )
            if isinstance(result, str) and result.strip():
                # Extract the first JSON object out of the response (Nemotron
                # sometimes wraps reasoning in <thinking> tags).
                cleaned = re.sub(r"<thinking>.*?</thinking>", "", result, flags=re.DOTALL).strip()
                m = re.search(r"\{[\s\S]*\}", cleaned)
                if m:
                    try:
                        parsed = json.loads(m.group(0))
                        summary = (parsed.get('summary') or '').strip()
                        sentiment = (parsed.get('sentiment') or 'neutral').lower()
                        if sentiment not in ('positive', 'neutral', 'negative'):
                            sentiment = 'neutral'
                        outcome_label = (parsed.get('outcome') or outcome_label).lower()
                        topics = parsed.get('topics') or []
                        if isinstance(topics, list):
                            key_topics = [str(t).strip() for t in topics if str(t).strip()][:5]
                        print(f"[Analysis] ✅ summary='{summary[:80]}' sentiment={sentiment} outcome={outcome_label}")
                    except Exception as je:
                        print(f"[Analysis] JSON parse failed: {je}")
    except Exception as e:
        print(f"[Analysis] NIM call failed: {e}")

    if not summary:
        # Fallback summary: first non-empty user turn or first line of transcript
        if convo_turns:
            first_user = next((t for t in convo_turns if t['role'] == 'user'), convo_turns[0])
            summary = first_user['content'][:200]
        else:
            summary = "Call ended without conversation."

    # 4. Persist
    try:
        if FIREBASE_AVAILABLE and db and agent_id:
            final_call_id = call_id or ctx.room.name
            try:
                if ctx.room.metadata:
                    final_call_id = json.loads(ctx.room.metadata).get("resolved_call_id", final_call_id)
            except Exception:
                pass

            log_payload = {
                'agent_id': agent_id,
                'call_id': final_call_id,
                'channel': 'voice_sip' if is_sip else 'voice_web',
                'duration': duration_seconds,
                'status': outcome_label,
                'messages': msg_count,
                'transcript': transcript_text,
                'turns': convo_turns,           # structured form for richer UI
                'analysis': summary,            # backwards-compat alias
                'summary': summary,
                'sentiment': sentiment,
                'topics': key_topics,
                'outcome': outcome_label != 'no_audio',
                'model': selected_model,
                'language': agent_language,
                'created_at': firestore.SERVER_TIMESTAMP,
                'timestamp': int(_time.time()),
            }

            db.collection('agents').document(agent_id).collection('agent_logs').add(log_payload)

            try:
                db.collection('agents').document(agent_id).update({
                    "call_count": firestore.Increment(1)
                })
            except Exception as e:
                print(f"[Agent] call_count update warning: {e}")

            print(f"[Agent] ✅ agent_logs entry written for call {final_call_id} (msgs={msg_count}, sentiment={sentiment})")
    except Exception as e:
        print(f"[Agent] ❌ Error saving call log: {e}")


if __name__ == "__main__":
    # ---- Warm-pool configuration ----
    # `num_idle_processes` keeps N agent processes pre-spawned and pre-
    # connected to LiveKit so the moment a job is dispatched there is no
    # cold-start. Default 2 (one for the active call, one ready for the
    # next). Override with env LIVEKIT_NUM_IDLE.
    try:
        num_idle = int(os.environ.get("LIVEKIT_NUM_IDLE", "2"))
    except ValueError:
        num_idle = 2

    worker_kwargs = {"entrypoint_fnc": entrypoint}

    # Optional explicit-dispatch mode. Set LIVEKIT_AGENT_NAME=kautilya-voice
    # and LIVEKIT_SIP_DIRECT_DISPATCH=1 (with a Direct-mode SIP dispatch
    # rule on the LiveKit dashboard) to enable zero-silence pre-dispatch
    # in routes/webhooks_routes.py::vobiz_answer.
    agent_name = os.environ.get("LIVEKIT_AGENT_NAME", "").strip()
    if agent_name:
        worker_kwargs["agent_name"] = agent_name
        print(f"[Worker] Explicit-dispatch mode (agent_name={agent_name})")

    # `num_idle_processes` was added in livekit-agents 1.x. Older versions
    # silently ignore it; if the constructor rejects it, fall back.
    try:
        opts = WorkerOptions(num_idle_processes=num_idle, **worker_kwargs)
        print(f"[Worker] Warm pool: {num_idle} idle process(es)")
    except TypeError:
        opts = WorkerOptions(**worker_kwargs)
        print("[Worker] num_idle_processes not supported by this livekit-agents version — running without warm pool")

    cli.run_app(opts)
