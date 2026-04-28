import os
import json
import asyncio
import time
import glob
import re
from datetime import datetime
from dotenv import load_dotenv
from livekit import rtc, api
from livekit.agents import (
    AutoSubscribe,
    JobContext,
    WorkerOptions,
    cli,
    llm,
)
from livekit.plugins import sarvam, openai, silero, cartesia

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
            print("[Firebase] Connected")
    except Exception as e: print(f"[Firebase Error] {e}")

initialize_firebase()

async def entrypoint(ctx: JobContext):
    print(f"[Agent] Starting room: {ctx.room.name}")
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    # Defaults
    system_prompt = "You are Kautilya AI assistant."
    welcome_message = "Hello, I am Kautilya."
    agent_id = None
    agent_language = "hi-IN"
    
    # PRIORITY 1: Room Name (agentId--uuid)
    r_name = ctx.room.name
    sip_resolved = False
    
    # SIP DID Lookup
    for p in ctx.room.remote_participants.values():
        if p.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP:
            did = (p.attributes or {}).get("sip.trunkPhoneNumber")
            if did and FIREBASE_AVAILABLE and db:
                try:
                    q = db.collection('agents').where('linked_numbers', 'array_contains', did).limit(1).stream()
                    for doc in q:
                        agent_id = doc.id
                        sip_resolved = True
                        break
                except: pass
            break

    if not sip_resolved and "--" in r_name:
        agent_id = r_name.split("--")[0].replace("voice-", "").replace("phone-", "")

    # Fetch Config
    if agent_id and FIREBASE_AVAILABLE and db:
        try:
            doc = db.collection('agents').document(agent_id).get()
            if doc.exists:
                data = doc.to_dict()
                system_prompt = data.get("system_prompt", system_prompt)
                welcome_message = data.get("welcome_message", welcome_message)
                agent_language = data.get("language", agent_language)
                print(f"[Config] Loaded for agent: {agent_id}")
        except: pass

    # --- Setup Pipeline Agent ---
    from livekit.agents.pipeline import VoicePipelineAgent
    
    vad = silero.VAD.load()
    stt = sarvam.STT(language=agent_language)
    tts = sarvam.TTS(target_language_code=agent_language, model="bulbul:v3")
    llm_plugin = openai.LLM(base_url="https://api.groq.com/openai/v1", api_key=os.environ.get("GROQ_API_KEY"), model="llama-3.3-70b-versatile")

    initial_ctx = llm.ChatContext().append(role="system", text=system_prompt)

    agent = VoicePipelineAgent(
        vad=vad,
        stt=stt,
        llm=llm_plugin,
        tts=tts,
        chat_ctx=initial_ctx,
    )

    agent.start(ctx.room)
    await agent.say(welcome_message, allow_interruptions=True)

    while ctx.room.connection_state == rtc.ConnectionState.CONN_CONNECTED:
        await asyncio.sleep(1)

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
