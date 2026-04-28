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
                json_files = glob.glob("*.json")
                for jf in json_files:
                    if "firebase-adminsdk" in jf.lower():
                        try:
                            cred = credentials.Certificate(jf)
                            FB_INIT_MSG = f"Initialized from discovered file: {jf}"
                            break
                        except: continue

            if cred: firebase_admin.initialize_app(cred)
            else:
                try:
                    firebase_admin.initialize_app()
                    FB_INIT_MSG = "Initialized via ADC"
                except: pass

        if firebase_admin._apps:
            db = firestore.client()
            FIREBASE_AVAILABLE = True
            print(f"[Firebase] {FB_INIT_MSG}")
    except Exception as e:
        print(f"[Firebase Error] {e}")

initialize_firebase()

def load_system_prompt():
    prompt_path = os.path.join(os.path.dirname(__file__), "system_prompt_cloud.txt")
    if os.path.exists(prompt_path):
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read().strip()
    return "You are KAUTILYA AI assistant. Speak only in plain text."

def clean_text_for_tts(text: str) -> str:
    if not text: return ""
    text = re.sub(r'[<>!=]=?|[=*_#`~]', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()

class KautilyaAgent(Agent):
    def __init__(self):
        super().__init__(instructions="")
        self._agent_kb = []
        self._call_objective = ""
        self._session = None
        self.room = None
        self._on_shutdown = None

    def set_config(self, system_prompt, call_objective, agent_kb):
        self._agent_kb = agent_kb
        self._call_objective = call_objective
        self._instructions = f"OBJECTIVE: {call_objective}\n\n{system_prompt}"

    @function_tool
    async def search_knowledge_base(self, context: RunContext, query: str) -> str:
        results = []
        q_low = query.lower()
        for doc in self._agent_kb:
            for chunk in doc.get("chunks", []):
                if any(word in chunk.lower() for word in q_low.split()):
                    results.append(chunk)
                    if len(results) >= 3: break
        return "\n\n".join(results) or "No info found."

    @function_tool
    async def end_call(self, context: RunContext, reason: str = "User ended") -> str:
        if self._on_shutdown: await self._on_shutdown()
        elif self.room: await self.room.disconnect()
        return "Call ended."

async def entrypoint(ctx: JobContext):
    print(f"[Agent] Starting room: {ctx.room.name}")
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    # Defaults
    system_prompt = load_system_prompt()
    welcome_message = "Hello, I am Kautilya."
    agent_id = None
    agent_language = "hi-IN"
    stt_provider = "sarvam"
    tts_provider = "sarvam"
    call_objective = "Assist caller."
    agent_kb = []
    config_source = "Defaults"

    def apply_config(config, source):
        nonlocal system_prompt, welcome_message, agent_id, agent_language, stt_provider, tts_provider, call_objective, agent_kb, config_source
        if not config: return False
        print(f"[Config] Applying from {source}")
        agent_kb = config.get("knowledge_base", [])
        system_prompt = config.get("system_prompt") or system_prompt
        welcome_message = config.get("welcome_message") or welcome_message
        agent_language = config.get("language") or agent_language
        agent_id = config.get("agent_id") or agent_id
        stt_provider = config.get("stt_provider", stt_provider)
        tts_provider = config.get("tts_provider", tts_provider)
        call_objective = config.get("call_objective") or call_objective
        config_source = source
        return True

    # PRIORITY 0: SIP DID
    sip_resolved = False
    for p in ctx.room.remote_participants.values():
        if p.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP:
            did = (p.attributes or {}).get("sip.trunkPhoneNumber")
            if did and FIREBASE_AVAILABLE and db:
                try:
                    q = db.collection('agents').where('linked_numbers', 'array_contains', did).limit(1).stream()
                    for doc in q:
                        apply_config(doc.to_dict(), f"SIP DID ({did})")
                        agent_id = doc.id
                        sip_resolved = True
                        break
                except: pass
            break

    # PRIORITY 1: Room Name (Legacy agentId--uuid)
    if not sip_resolved:
        r_name = ctx.room.name
        if "--" in r_name:
            extracted_id = r_name.split("--")[0].replace("voice-", "").replace("phone-", "")
            if FIREBASE_AVAILABLE and db:
                try:
                    doc = db.collection('agents').document(extracted_id).get()
                    if doc.exists:
                        apply_config(doc.to_dict(), f"Room Name ({extracted_id})")
                        agent_id = extracted_id
                except: pass

    # PRIORITY 2: Room Metadata
    if not agent_id and ctx.room.metadata:
        try:
            m = json.loads(ctx.room.metadata)
            apply_config(m, "Room Metadata")
        except: pass

    # --- Plugins ---
    from livekit.plugins import sarvam, openai, silero, cartesia
    vad = silero.VAD.load()
    stt = sarvam.STT(language=agent_language)
    
    # LLM (Groq)
    llm = openai.LLM(base_url="https://api.groq.com/openai/v1", api_key=os.environ.get("GROQ_API_KEY"), model="llama-3.3-70b-versatile")
    
    # TTS
    if tts_provider == "sarvam":
        tts = sarvam.TTS(target_language_code=agent_language, model="bulbul:v3")
    else:
        tts = cartesia.TTS()

    agent = KautilyaAgent()
    agent.set_config(system_prompt, call_objective, agent_kb)
    agent.room = ctx.room
    
    session = AgentSession(agent, vad=vad, stt=stt, llm=llm, tts=tts)
    agent._session = session
    
    async def terminate():
        await ctx.room.disconnect()
    agent._on_shutdown = terminate

    await session.start(ctx.room)
    await session.say(welcome_message)

    while ctx.room.connection_state == rtc.ConnectionState.CONN_CONNECTED:
        await asyncio.sleep(1)

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
