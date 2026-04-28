import os
import json
import asyncio
import re
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
from livekit.plugins import sarvam, openai, silero, cartesia, google

load_dotenv()

# ============== Firebase Admin Initialization ==============
db = None
FIREBASE_AVAILABLE = False
def initialize_firebase():
    global db, FIREBASE_AVAILABLE
    try:
        import firebase_admin
        from firebase_admin import credentials, firestore
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
            db = firestore.client()
            FIREBASE_AVAILABLE = True
            print("[Firebase] Connected and Ready")
    except Exception as e: print(f"[Firebase Error] {e}")

initialize_firebase()

class KautilyaAgent(Agent):
    def __init__(self, **kwargs):
        if 'instructions' not in kwargs:
            kwargs['instructions'] = "You are Kautilya AI assistant."
        super().__init__(**kwargs)

async def entrypoint(ctx: JobContext):
    # Start connecting immediately (parallel)
    connect_task = asyncio.create_task(ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY))
    
    print(f"[Agent] Rapid Startup for room: {ctx.room.name}")

    # Defaults
    system_prompt = "You are Kautilya AI assistant."
    welcome_message = "Hello, I am Kautilya."
    agent_id = None
    agent_language = "hi-IN"
    # HARDCODED: gemini-3.1-flash-live-preview
    agent_model = "gemini-3.1-flash-live-preview"
    
    # Extract agent ID from room name
    # Room name formats:
    #   SIP call:  "agentId--uuid"       (from SIP trunk)
    #   Web call:  "voice-agentId--uuid"  (from frontend)
    r_name = ctx.room.name
    if "--" in r_name:
        prefix = r_name.split("--")[0]
        # Strip known prefixes
        agent_id = prefix.replace("voice-", "").replace("phone-", "")
    
    print(f"[Config] Resolved agent_id: {agent_id}")

    if agent_id and FIREBASE_AVAILABLE and db:
        try:
            doc = db.collection('agents').document(agent_id).get()
            if doc.exists:
                data = doc.to_dict()
                system_prompt = data.get("system_prompt", system_prompt)
                welcome_message = data.get("welcome_message", welcome_message)
                agent_language = data.get("language", agent_language)
                db_model = data.get("model", "").lower()
                
                # If Gemini is selected, use hardcoded gemini-3.1 model
                if "gemini" in db_model:
                    agent_model = "gemini-3.1-flash-live-preview"
                else:
                    agent_model = db_model
                print(f"[Config] Loaded for agent: {agent_id} | Model: {agent_model}")
        except Exception as e:
            print(f"[Config] Error loading agent config: {e}")

    # Wait for room connection
    await connect_task

    is_gemini_live = "gemini" in agent_model.lower()

    if is_gemini_live:
        print(f"[Gemini] Initializing RealtimeModel ({agent_model})...")
        gemini_instructions = f"{system_prompt}\n\nIMPORTANT: Start the conversation by saying exactly: '{welcome_message}'"
        
        llm_plugin = google.realtime.RealtimeModel(
            model=agent_model,
            voice="Puck",
            instructions=gemini_instructions,
            temperature=0.8
        )
        session = AgentSession(llm=llm_plugin)
        agent = KautilyaAgent(instructions=gemini_instructions)
        await session.start(room=ctx.room, agent=agent)
        # Gemini 3.1 handles greeting via instructions (say() not supported)
    else:
        vad = silero.VAD.load()
        stt = sarvam.STT(language=agent_language)
        tts = sarvam.TTS(target_language_code=agent_language, model="bulbul:v3")
        llm_plugin = openai.LLM(
            base_url="https://api.groq.com/openai/v1",
            api_key=os.environ.get("GROQ_API_KEY"),
            model="llama-3.3-70b-versatile"
        )

        session = AgentSession(vad=vad, stt=stt, llm=llm_plugin, tts=tts)
        agent = KautilyaAgent(instructions=system_prompt)
        await session.start(room=ctx.room, agent=agent)
        await session.say(welcome_message)

    # Keep alive while connected
    while ctx.room.connection_state == rtc.ConnectionState.CONN_CONNECTED:
        await asyncio.sleep(1)

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
