import os
import json
import asyncio
import time
import glob
import aiohttp
import re
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
    function_tool,
    RunContext,
)
from livekit.agents.llm import ChatContext, ChatMessage
from livekit.agents.voice import room_io

load_dotenv()

# ============== Firebase Admin Initialization ==============
db = None
FIREBASE_AVAILABLE = False
FB_INIT_MSG = "Not initialized"

def initialize_firebase():
    global db, FIREBASE_AVAILABLE, FB_INIT_MSG
    try:
        import firebase_admin
        from firebase_admin import credentials, firestore

        if not firebase_admin._apps:
            sa_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON")
            cred = None

            if sa_json:
                try:
                    info = json.loads(sa_json)
                    cred = credentials.Certificate(info)
                    FB_INIT_MSG = "Initialized from JSON string (ENV)"
                except json.JSONDecodeError:
                    if os.path.exists(sa_json):
                        cred = credentials.Certificate(sa_json)
                        FB_INIT_MSG = f"Initialized from path (ENV): {sa_json}"

            if not cred:
                print("[Firebase] Checking for local service account JSON files...")
                json_files = glob.glob("*.json")
                for jf in json_files:
                    if "firebase-adminsdk" in jf.lower():
                        try:
                            cred = credentials.Certificate(jf)
                            FB_INIT_MSG = f"Initialized from discovered file: {jf}"
                            print(f"[Firebase] {FB_INIT_MSG}")
                            break
                        except:
                            continue

            if cred:
                firebase_admin.initialize_app(cred)
            else:
                try:
                    firebase_admin.initialize_app()
                    FB_INIT_MSG = "Initialized via Application Default Credentials"
                except Exception as e:
                    FB_INIT_MSG = f"No credentials found. Error: {e}"

        if firebase_admin._apps:
            db = firestore.client()
            FIREBASE_AVAILABLE = True
            print(f"[Firebase Status] {FB_INIT_MSG}")
    except ImportError:
        FB_INIT_MSG = "firebase-admin NOT INSTALLED"
        print(f"[Firebase Status] {FB_INIT_MSG}")
    except Exception as e:
        FB_INIT_MSG = f"Initialization error: {e}"
        print(f"[Firebase Status] {FB_INIT_MSG}")

initialize_firebase()

# ============== Voice ID Map (Cartesia) ==============
CARTESIA_VOICE_MAP = {
    "shubh": "a0e99841-438c-4a64-b679-ae501e7d6091",
    "meera": "b7d50908-b3f3-4a3c-9e97-0e2e12b0e3e3",
    "arjun": "a0e99841-438c-4a64-b679-ae501e7d6091",
    "priya": "b7d50908-b3f3-4a3c-9e97-0e2e12b0e3e3",
    "default": "a0e99841-438c-4a64-b679-ae501e7d6091",
}

def get_cartesia_voice_id(voice_name):
    if not voice_name:
        return CARTESIA_VOICE_MAP["default"]
    if len(str(voice_name)) > 20 and '-' in str(voice_name):
        return str(voice_name)
    return CARTESIA_VOICE_MAP.get(str(voice_name).lower(), CARTESIA_VOICE_MAP["default"])

def load_system_prompt():
    prompt_path = os.path.join(os.path.dirname(__file__), "system_prompt_cloud.txt")
    if os.path.exists(prompt_path):
        with open(prompt_path, "r", encoding="utf-8") as f:
            prompt = f.read().strip()
            prompt += (
                "\n\nCRITICAL CONVERSATION RULES:\n"
                "1. Speak only in pure natural text.\n"
                "2. Never output markdown tags or XML tags.\n"
                "3. Keep responses concise and conversational."
            )
            return prompt
    return (
        "You are KAUTILYA AI, an advanced AI assistant with strategic insight. "
        "Speak only in pure natural text. No tags."
    )

    return cleaned.strip()

def clean_prompt(text: str) -> str:
    if not text:
        return ""
    # Remove any unpopulated placeholders like {NAME}, {name}, {LOCATION}, etc.
    # We replace them with 'there' or empty strings for natural flow.
    cleaned = re.sub(r'\{[A-Z_a-z]+\}', '', text)
    # Also handle common literal placeholders
    cleaned = cleaned.replace('NAME', 'there').replace('{NAME}', 'there')
    return cleaned.strip()


# ============== Agent Class (v1.x) ==============

class KautilyaAgent(Agent):
    """
    ScatterAI / KAUTILYA voice agent — LiveKit Agents v1.x compatible.
    All tools are defined as methods decorated with @function_tool.
    Agent-level config is injected after construction via set_config().
    """
    def __init__(self):
        super().__init__(instructions="")  # Will be set via set_config
        self._agent_kb: list = []
        self._call_objective: str = ""
        self._session: AgentSession | None = None  # Back-reference set in entrypoint
        self.room: rtc.Room | None = None  # Set in entrypoint
        self._on_shutdown: callable | None = None # Callback to terminate the room

    def set_config(self, system_prompt: str, call_objective: str, agent_kb: list):
        self._agent_kb = agent_kb
        self._call_objective = call_objective
        # In v1.x, the 'instructions' property is read-only. We set the internal attribute.
        cleaned_prompt = clean_prompt(system_prompt)
        self._instructions = (
            f"CALL OBJECTIVE: {call_objective}\n\n{cleaned_prompt}\n\n"
            "CRITICAL CONVERSATION RULES:\n"
            "1. LANGUAGE MATCHING: ALWAYS respond in the same language as the user. If they speak English, you speak English. If they speak Hindi, you speak Hindi. If they mix (Hinglish), you speak Hinglish.\n"
            "2. MISSING NAME: If you don't know the person's name (or if it was a placeholder), DO NOT use 'NAME'. Instead, ask 'May I know who am I speaking with?' or address them naturally as 'there'.\n"
            "3. NEVER call end_call unless the user literally says 'bye', 'goodbye', 'hang up', or 'end the call'.\n"
            "4. NEVER call end_call due to silence or pauses — the system handles this.\n"
            "5. Keep responses SHORT (1-2 sentences max).\n"
        )

    # ---------- Tools ----------

    @function_tool
    async def search_knowledge_base(self, context: RunContext, query: str) -> str:
        """Search the agent's knowledge base for relevant information."""
        print(f"[RAG] Searching KB for: {query}")
        
        # Keep the session alive during potentially long RAG calls
        if hasattr(self, '_session_vars'):
            self._session_vars['agent_is_thinking'] = True
            self._session_vars['last_user_interaction'] = time.time()
        results = []
        q_low = query.lower()
        for doc in self._agent_kb:
            for chunk in doc.get("chunks", []):
                if any(word in chunk.lower() for word in q_low.split()):
                    results.append(chunk)
                    if len(results) >= 3:
                        break
        if not results:
            return "No specific information found in the knowledge base."
        return "\n\n---\n\n".join(results)

    @function_tool
    async def end_call(self, context: RunContext, reason: str = "User requested to end the call") -> str:
        """End the phone call. ONLY use this when the user explicitly says 'bye', 'goodbye', 'hang up', or 'end the call'. NEVER call this for silence or pauses."""
        print(f"[Tool] Ending call: {reason}")
        if self._session:
            try:
                await self._session.say("Thank you for calling. Goodbye!", allow_interruptions=False)
                await asyncio.sleep(2)
            except RuntimeError:
                pass  # Session already closing
        
        if self._on_shutdown:
            await self._on_shutdown()
        elif self.room:
            await self.room.disconnect()
            
        return "Call ended."

    @function_tool
    async def human_handoff(self, context: RunContext, reason: str = "Complex query") -> str:
        """Transfer to a human agent. ONLY use this when the user explicitly says 'talk to a human', 'speak to a person', or 'transfer me'. NEVER use for any other reason."""
        print(f"[Tool] Human handoff: {reason}")
        if self._session:
            try:
                await self._session.say(
                    "One moment while I transfer you to a human specialist.",
                    allow_interruptions=False,
                )
                await asyncio.sleep(2)
            except RuntimeError:
                pass
        
        if self._on_shutdown:
            await self._on_shutdown()
        elif self.room:
            await self.room.disconnect()
            
        return "Transferring..."


# ============== Entrypoint ==============

async def entrypoint(ctx: JobContext):
    print(f"[Real-time Agent] Starting session for room: {ctx.room.name}")
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    # --- Default Config ---
    system_prompt = load_system_prompt()
    agent_name = "Kautilya"
    raw_voice = ""
    welcome_message = "Greetings! I am Kautilya. How may I assist you today?"
    agent_language = "hi-IN"
    agent_id = None
    stt_provider = "sarvam"
    tts_provider = "sarvam"
    agent_model = "kautilya-daily"
    interruption_mode = "allow"
    silence_timeout_sec = 120
    nudge_timeout_sec = 60
    max_call_duration = 600
    call_objective = "Assist the caller and resolve their query."
    webhook_url = ""
    config_source = "Defaults"
    agent_kb = []

    def apply_config(config, source_label):
        nonlocal system_prompt, agent_name, raw_voice, welcome_message, agent_language, \
                  agent_id, stt_provider, tts_provider, agent_model, interruption_mode, \
                  silence_timeout_sec, nudge_timeout_sec, max_call_duration, config_source, \
                  agent_kb, call_objective, webhook_url
        if not config:
            return False

        print(f"[Config Match] Applying config from {source_label}")
        agent_kb = config.get("knowledge_base", [])
        system_prompt = config.get("system_prompt") or config.get("prompt") or config.get("instructions") or system_prompt
        agent_name = config.get("agent_name") or config.get("name") or agent_name
        raw_voice = config.get("voice", raw_voice)
        welcome_message = config.get("welcome_message") or config.get("welcome") or welcome_message
        agent_language = config.get("language") or config.get("lang") or agent_language
        agent_id = config.get("agent_id") or config.get("id")
        stt_provider = config.get("stt_provider", stt_provider)
        tts_provider = config.get("tts_provider", tts_provider)
        agent_model = config.get("model") or config.get("agent_model") or agent_model
        interruption_mode = config.get("interruption_mode", interruption_mode)
        
        # Hardened silence timeout: Minimum floor of 120 seconds to prevent immediate disconnects
        raw_timeout = int(float(config.get("silence_timeout", silence_timeout_sec)))
        silence_timeout_sec = max(120, raw_timeout)
        
        max_call_duration = int(config.get("max_call_duration", max_call_duration))
        call_objective = config.get("call_objective") or config.get("objective") or call_objective
        webhook_url = config.get("webhook_url") or config.get("webhook") or webhook_url
        config_source = source_label
        return True

    # === PRIORITY 0: SIP DID Lookup ===
    sip_resolved = False
    for p in ctx.room.remote_participants.values():
        if p.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP:
            sip_attrs = p.attributes or {}
            did_number = sip_attrs.get("sip.trunkPhoneNumber", "")
            caller_number = sip_attrs.get("sip.phoneNumber", "")
            trunk_id = sip_attrs.get("sip.trunkID", "")
            print(f"[SIP Call Detected] DID: {did_number} | Caller: {caller_number} | Trunk: {trunk_id}")

            if did_number and FIREBASE_AVAILABLE and db:
                try:
                    query = db.collection('agents').where('linked_numbers', 'array_contains', did_number).limit(1).stream()
                    for doc in query:
                        agent_data = doc.to_dict()
                        agent_data['agent_id'] = doc.id
                        apply_config(agent_data, f"SIP DID Lookup ({did_number} → {doc.id})")
                        sip_resolved = True
                        print(f"[SIP Routing] ✅ Matched agent '{doc.id}' for DID {did_number}")
                        break
                    if not sip_resolved:
                        print(f"[SIP Routing] ⚠️ No agent found for DID {did_number}")
                except Exception as e:
                    print(f"[SIP Routing] Firestore query error: {e}")
            break

    # === PRIORITY 1: Room Name / ENV → Firestore ===
    if not sip_resolved:
        env_agent_id = os.environ.get("AGENT_ID")
        r_name = ctx.room.name
        extracted_id = env_agent_id
        if not extracted_id and "--" in r_name:
            extracted_id = r_name.split("--")[0].replace("voice-", "").replace("phone-", "")

        if extracted_id:
            print(f"[Identity] Extracted agent_id: {extracted_id}")
            if FIREBASE_AVAILABLE and db:
                print(f"[Firestore] Fetching config for {extracted_id}...")
                try:
                    agent_doc = db.collection('agents').document(extracted_id).get()
                    if agent_doc.exists:
                        apply_config(agent_doc.to_dict(), f"Firestore ({extracted_id})")
                    else:
                        print(f"[Firestore] Agent {extracted_id} not found.")
                except Exception as e:
                    print(f"[Firestore] Fetch error: {e}")

    # === PRIORITY 2: Room / Participant Metadata ===
    raw_meta_str = ctx.room.metadata
    if not raw_meta_str:
        raw_meta_str = ctx.room.local_participant.metadata if ctx.room.local_participant else ""

    if raw_meta_str:
        try:
            m = json.loads(raw_meta_str)
            apply_config(m.get("config", m), "Room/Local Metadata")
        except:
            pass

    for p in ctx.room.remote_participants.values():
        if p.kind != rtc.ParticipantKind.PARTICIPANT_KIND_SIP and p.metadata:
            try:
                m = json.loads(p.metadata)
                apply_config(m.get("config", m), f"Participant Metadata ({p.identity})")
            except:
                continue

    print(f"[Real-time Agent] FINAL RESOLUTION | Source: {config_source}")
    print(f"[Real-time Agent] Name: {agent_name} | STT: {stt_provider} | TTS: {tts_provider} | Lang: {agent_language}")
    print(f"[Real-time Agent] Prompt Sample: {system_prompt[:60]}... (Total {len(system_prompt)} chars)")

    # --- Initialize Plugins ---
    from livekit.plugins import cartesia, openai, silero, deepgram, sarvam, google

    # Hardened VAD for lightning-fast, noise-resistant speech detection
    # activation_threshold=0.3 Catch even soft speech to prevent false silence timeouts
    # activation_threshold=0.15 Catch even a whisper to prevent false silence timeouts
    vad = silero.VAD.load(
        min_speech_duration=0.1,
        min_silence_duration=0.5,
        activation_threshold=0.15
    )

    # STT
    if stt_provider == "openai":
        stt = openai.STT()
    elif stt_provider == "deepgram":
        stt = deepgram.STT()
    else:
        stt = sarvam.STT(language=agent_language)

    # LLM (Primary: Groq, Fallback: Sarvam-105b)
    groq_keys_raw = [
        os.environ.get("GROQ_API_KEY", ""),
        os.environ.get("GROQ_API_KEY_BACKUP", ""),
        os.environ.get("GROQ_API_KEY_3", ""),
        os.environ.get("GROQ_API_KEY_4", ""),
        os.environ.get("GROQ_API_KEY_5", ""),
    ]
    groq_keys = [k for k in groq_keys_raw if k]
    sarvam_key = os.environ.get("SARVAM_API_KEY")

    if groq_keys:
        import random
        chosen_key = random.choice(groq_keys)
        print(f"[LLM Config] Using Groq (llama-3.3-70b-versatile) - Primary")
        llm_plugin = openai.LLM(
            base_url="https://api.groq.com/openai/v1",
            api_key=chosen_key,
            model="llama-3.3-70b-versatile",
            temperature=0.7
        )
    elif sarvam_key:
        print(f"[LLM Config] Groq unavailable. Using Sarvam LLM (sarvam-105b) - Fallback")
        llm_plugin = sarvam.LLM(model="sarvam-105b", api_key=sarvam_key, temperature=0.7)
    else:
        print(f"[LLM Config] WARNING: No reliable LLM key found. Defaulting to OpenAI.")
        llm_plugin = openai.LLM()

    # TTS
    if tts_provider == "openai":
        tts = openai.TTS()
    elif tts_provider == "sarvam":
        speaker = raw_voice if raw_voice and '-' not in str(raw_voice) else "aditya"
        print(f"[TTS Config] Sarvam Bulbul:v3 | Speaker: {speaker}")
        tts = sarvam.TTS(target_language_code=agent_language, speaker=speaker, model="bulbul:v3")
    else:
        v_id = get_cartesia_voice_id(raw_voice)
        tts_model = "sonic-multilingual" if "en" not in agent_language.lower() else "sonic-english"
        print(f"[TTS Config] Cartesia {tts_model} | Voice: {v_id}")
        tts = cartesia.TTS(model=tts_model, voice=v_id)

    # --- Build Agent ---
    agent = KautilyaAgent()
    agent.set_config(system_prompt, call_objective, agent_kb)
    agent.room = ctx.room

    # --- Build Session (v1.x Optimized for high speed and low error) ---
    session = AgentSession(
        vad=vad,
        stt=stt,
        llm=llm_plugin,
        tts=tts,
        # close_on_disconnect=False  # Uncomment to keep session alive after disconnect
    )
    agent._session = session  # Back-reference so tools can call session.say()

    # --- Transcript & Interaction Tracking ---
    transcript_log: list[str] = []
    last_user_interaction = time.time()
    nudge_sent = False
    session_active = True
    user_is_speaking = False
    agent_is_thinking = False
    agent_is_speaking = False
    user_speech_end_time = 0.0  # Grace period after user finishes speaking
    
    # Shared variables for tools to update state
    session_vars = {
        'agent_is_thinking': agent_is_thinking,
        'last_user_interaction': last_user_interaction
    }
    agent._session_vars = session_vars
    total_tts_chars = 0

    async def terminate_session():
        nonlocal session_active
        if not session_active:
            return
        session_active = False
        room_name = ctx.room.name
        print(f"[Shutdown] Hard-clearing room {room_name}...")
        
        # Initialize LiveKit API
        lk_url = os.environ.get("LIVEKIT_URL")
        lk_key = os.environ.get("LIVEKIT_API_KEY")
        lk_secret = os.environ.get("LIVEKIT_API_SECRET")
        
        if not all([lk_url, lk_key, lk_secret]):
            print(f"[Shutdown] WARNING: Missing LiveKit Credentials. Attempting soft disconnect only.")
            await ctx.room.disconnect()
            return

        lk_api = api.LiveKitAPI(lk_url, lk_key, lk_secret)
        try:
            # DELETE ROOM FIRST: This forces all participants (including this worker) to drop
            # and triggers the server-side cleanup immediately.
            await lk_api.room.delete_room(api.DeleteRoomRequest(room=room_name))
            print(f"[Shutdown] Room {room_name} deleted successfully.")
            
            # Brief wait for signaling to propagate
            await asyncio.sleep(0.5)
            await ctx.room.disconnect()
        except Exception as e:
            if "closing transport" not in str(e).lower():
                print(f"[Shutdown] Error during cleanup for {room_name}: {e}")
            # Ensure we at least disconnect locally if deletion failed
            try: await ctx.room.disconnect()
            except: pass
        finally:
            await lk_api.aclose()

    agent._on_shutdown = terminate_session

    @session.on("user_speech_started")
    def on_user_speech_started():
        nonlocal last_user_interaction, nudge_sent, user_is_speaking
        user_is_speaking = True
        last_user_interaction = time.time()
        nudge_sent = False
        print("[VAD] User started speaking")

    @session.on("user_speech_committed")
    def on_user_speech(msg: ChatMessage):
        nonlocal last_user_interaction, nudge_sent, user_is_speaking, user_speech_end_time
        user_is_speaking = False
        user_speech_end_time = time.time()  # Mark when speech ended for grace period
        content = msg.content if isinstance(msg.content, str) else str(msg.content)
        if content:
            transcript_log.append(f"User: {content}")
            print(f"[STT] Committed: {content}")
            agent_is_thinking = True
            last_user_interaction = time.time()
            nudge_sent = False

    @session.on("agent_speech_started")
    def on_agent_speech_started():
        nonlocal agent_is_speaking, agent_is_thinking, last_user_interaction
        agent_is_thinking = False
        agent_is_speaking = True
        last_user_interaction = time.time()
        print("[Turn] Agent started speaking")

    @session.on("agent_speech_stopped")
    def on_agent_speech_stopped():
        nonlocal agent_is_speaking, last_user_interaction
        agent_is_speaking = False
        last_user_interaction = time.time()
        print("[Turn] Agent stopped speaking")

    @session.on("agent_speech_committed")
    def on_agent_speech(msg: ChatMessage):
        nonlocal total_tts_chars
        content = msg.content if isinstance(msg.content, str) else str(msg.content)
        if content:
            cleaned = clean_text(content)
            transcript_log.append(f"Agent: {cleaned}")
            total_tts_chars += len(cleaned)

    # --- Start Session ---
    await session.start(
        room=ctx.room,
        agent=agent,
        room_options=room_io.RoomOptions(),
    )

    # Say welcome
    await session.say(welcome_message, allow_interruptions=(interruption_mode == "allow"))
    
    # CRITICAL: Reset the silence timer ONLY after the welcome message finishes
    # This prevents the agent from disconnecting while the session is just starting up.
    last_user_interaction = time.time()
    nudge_sent = False
    
    print(f"[Real-time Agent] AgentSession started.")

    start_time = time.time()

    # --- Silence Monitor (separate task, safe) ---
    async def silence_monitor():
        nonlocal nudge_sent, session_active, last_user_interaction
        GRACE_PERIOD = 8.0  # seconds after user finishes speaking before silence timer is considered
        while session_active:
            await asyncio.sleep(2)  # Check every 2s
            if not session_active:
                break

            # Sync with shared session vars (updated by tools)
            agent_is_thinking = session_vars['agent_is_thinking']
            last_user_interaction = session_vars['last_user_interaction']

            # Keep the timer alive whenever any party is active
            if user_is_speaking or agent_is_thinking or agent_is_speaking:
                last_user_interaction = time.time()
                session_vars['last_user_interaction'] = last_user_interaction
                continue 

            # Grace period
            if user_speech_end_time > 0 and (time.time() - user_speech_end_time) < GRACE_PERIOD:
                last_user_interaction = time.time()
                session_vars['last_user_interaction'] = last_user_interaction
                continue

            silence_duration = time.time() - last_user_interaction

            if silence_duration > 300: # 5 min fallback
                print(f"[Timeout] 5 min silence. Ending.")
                await terminate_session()
                break


            elif silence_duration > nudge_timeout_sec and not nudge_sent:
                print(f"[Nudge] Silence {silence_duration:.0f}s. Tracking only.")
                nudge_sent = True
                last_user_interaction = time.time()
                session_vars['last_user_interaction'] = last_user_interaction


    silence_task = asyncio.create_task(silence_monitor())

    # --- Main loop: wait for disconnect or max duration ---
    try:
        while ctx.room.connection_state == rtc.ConnectionState.CONN_CONNECTED:
            if time.time() - start_time > max_call_duration:
                print(f"[Timeout] Max call duration {max_call_duration}s reached.")
                try:
                    await session.say("We've reached the maximum call duration. Goodbye!", allow_interruptions=False)
                    await asyncio.sleep(3)
                except RuntimeError:
                    pass
                await terminate_session()
                break
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        pass
    finally:
        session_active = False
        if not silence_task.done():
            silence_task.cancel()

    duration = int(time.time() - start_time)
    print(f"[Real-time Agent] Session ended. Duration: {duration}s")

    # --- Post-Call Analysis ---
    async def perform_post_call_analysis():
        if not transcript_log or duration < 2:
            return
        if not agent_id:
            print(f"[Intelligence] Skipping post-call analysis: No agent_id resolved.")
            return

        print(f"[Intelligence] Starting post-call analysis for agent {agent_id}...")
        full_transcript = "\n".join(transcript_log)

        analysis_prompt = f"""
Analyze the following phone conversation transcript.
Objective was: {call_objective}

Return a JSON object with:
1. "summary": A 2-sentence summary of the call.
2. "sentiment": One of "positive", "neutral", "negative".
3. "outcome": Whether the objective was achieved (true/false).
4. "extracted_data": Any lead info found (name, email, etc).

TRANSCRIPT:
{full_transcript}
"""
        try:
            resp = await llm_plugin.chat(messages=[{"role": "user", "content": analysis_prompt}])
            analysis_text = resp.choices[0].message.content

            flask_url = os.environ.get("FLASK_URL") or f"http://127.0.0.1:{os.environ.get('PORT', '5000')}"
            payload = {
                "agent_id": agent_id,
                "duration": duration,
                "transcript": full_transcript,
                "analysis": analysis_text,
                "usage": {
                    "llm_tokens": int(len(full_transcript) / 4),
                    "tts_chars": total_tts_chars,
                    "stt_seconds": duration
                },
                "timestamp": datetime.now().isoformat(),
            }

            async with aiohttp.ClientSession() as http_sess:
                post_resp = await http_sess.post(f"{flask_url}/api/agents/{agent_id}/calls", json=payload, timeout=10)
                print(f"[Intelligence] Post-call data sent to /api/agents/{agent_id}/calls -> Status: {post_resp.status}")
                if webhook_url:
                    await http_sess.post(webhook_url, json=payload, timeout=5)
                    print(f"[Intelligence] ✅ Dispatched to webhook: {webhook_url}")

        except Exception as e:
            print(f"[Intelligence Error] Post-call failed: {e}")

    asyncio.create_task(perform_post_call_analysis())


if __name__ == "__main__":
    cli.run_app(WorkerOptions(
        entrypoint_fnc=entrypoint,
        initialize_process_timeout=120.0,
    ))
