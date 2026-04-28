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
from livekit.agents.llm import ChatMessage
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
    
    # Extract agent ID from room name safely
    r_name = ctx.room.name
    print(f"[Agent] Raw Room Name: {r_name}")
    
    # Clean up any potential SIP/LiveKit prefixes
    clean_name = r_name.replace("sip:", "").replace("sip-", "")
    
    if "voice-" in clean_name:
        # Extract everything between 'voice-' and '--' or '_'
        # Room names like voice-_+91... or voice-agentid--uuid
        parts = clean_name.split("voice-")[-1]
        # Split by '--' first, then by '_'
        agent_id = parts.split("--")[0]
        if "_" in agent_id and not agent_id.startswith("_"):
             agent_id = agent_id.split("_")[0]
        
        # Strip leading underscores if any (common in some SIP room names)
        agent_id = agent_id.lstrip("_")
    elif "--" in clean_name:
        agent_id = clean_name.split("--")[0]
    else:
        agent_id = clean_name.lstrip("_")
        
    print(f"[Config] Resolved agent_id candidate: {agent_id}")

    if agent_id and FIREBASE_AVAILABLE and db:
        try:
            # FALLBACK: If it looks like a phone number or SIP-mangled name, check our Call Mapping
            if "_" in agent_id or len(agent_id) < 20 or agent_id.startswith("+"):
                call_uuid = agent_id.split("_")[-1]
                print(f"[Config] Searching mapping for CallUUID: {call_uuid} (Retry Loop Enabled)")
                
                # Retry loop to handle Firestore write latency from the webhook process
                for attempt in range(5):
                    mapping_doc = db.collection('call_mappings').document(call_uuid).get()
                    if mapping_doc.exists:
                        agent_id = mapping_doc.to_dict().get('agent_id')
                        # STORE the resolved Call ID for transcript saving
                        ctx.room.metadata = json.dumps({"resolved_call_id": call_uuid})
                        print(f"[Config] 🎯 Attempt {attempt+1}: Mapped CallUUID to Agent ID: {agent_id}")
                        break
                    if attempt < 4:
                        print(f"[Config] Attempt {attempt+1}: Mapping not found yet, retrying in 500ms...")
                        import time
                        time.sleep(0.5)
                else:
                    print(f"[Config] ❌ Mapping not found after 5 attempts for {call_uuid}")

            # FINAL FALLBACK: Search by Customer Number (if mapping by UUID failed)
            doc = db.collection('agents').document(agent_id).get()
            if not doc or not doc.exists:
                print(f"[Config] UUID mapping failed. Searching for active call by customer number...")
                # We try to find any active call mapping for the participant in the room
                # Wait for at least one participant to join if it's a SIP call
                for attempt in range(5):
                    participants = ctx.room.remote_participants
                    if participants:
                        for p_sid, p in participants.items():
                            identity = p.identity
                            if "sip-" in identity or identity.startswith("+") or p.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP:
                                # Extract phone number from identity or attributes
                                clean_id = identity.replace("sip-", "").lstrip("+")
                                if "_" in clean_id: clean_id = clean_id.split("_")[0] # handle sip_number_uuid
                                
                                print(f"[Config] Found participant: {clean_id}. Checking active_calls...")
                                call_doc = db.collection('active_calls').document(clean_id).get()
                                if call_doc.exists:
                                    agent_id = call_doc.to_dict().get('agent_id')
                                    print(f"[Config] 🎯 Found Agent ID via Customer Number: {agent_id}")
                                    break
                        if agent_id: break
                    import time
                    time.sleep(0.5)

            # LAST RESORT: Search by Vobiz Number (Old logic style)
            if not agent_id or (doc and not doc.exists):
                 vobiz_num = clean_name.split("_")[-2] if "_" in clean_name else ""
                 if vobiz_num.startswith("+"):
                     print(f"[Config] Last resort: searching by Vobiz number {vobiz_num}")
                     agents_ref = db.collection('agents').where('vobiz_number', '==', vobiz_num).limit(1).get()
                     if agents_ref:
                         agent_id = agents_ref[0].id
                         print(f"[Config] 🎯 Found Agent ID via Vobiz Number: {agent_id}")

            if agent_id:
                doc = db.collection('agents').document(agent_id).get()
            call_id = clean_name.split("--")[-1]
            if "_" in call_id: call_id = call_id.split("_")[-1]
            print(f"[Config] Extracted Call ID for transcripts: {call_id}")

            doc = db.collection('agents').document(agent_id).get()
            if doc.exists:
                data = doc.to_dict()
                print(f"[Config] Firestore Data Keys: {list(data.keys())}")
                print(f"[Config] Prompt Snippet: {str(data.get('system_prompt', ''))[:100]}...")
                
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
        print(f"[Gemini] Instructions Length: {len(system_prompt)} characters")
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
        
        # Trigger Gemini to speak first by simulating a user message or system prompt
        try:
            # Using a list of strings for content to satisfy pydantic while avoiding 'types.UnionType' errors
            msg = ChatMessage(role="user", content=["I have just joined the call. Please introduce yourself exactly as instructed."])
            if hasattr(session, 'chat_ctx'):
                session.chat_ctx.messages.append(msg)
                print("[Gemini] ✅ Greeting trigger injected.")
        except Exception as e:
            print(f"[Gemini] Greeting trigger warning: {e}")
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

    # SESSION ENDED - Save Transcript
    print(f"[Agent] Session ended for {ctx.room.name}. Saving transcript...")
    try:
        if FIREBASE_AVAILABLE and db and agent_id:
            transcript_text = ""
            if hasattr(session, 'chat_ctx'):
                for m in session.chat_ctx.messages:
                    role = m.role.upper()
                    content = m.content
                    if isinstance(content, list):
                        # Extract text from list of ChatContent or strings
                        parts = []
                        for p in content:
                            if hasattr(p, 'text'): parts.append(p.text)
                            elif isinstance(p, str): parts.append(p)
                        content = " ".join(parts)
                    transcript_text += f"{role}: {content}\n"
            
            if transcript_text.strip():
                # Use the resolved call ID if we found one, otherwise fallback to room name parts
                final_call_id = call_id
                try:
                    if ctx.room.metadata:
                        room_meta = json.loads(ctx.room.metadata)
                        final_call_id = room_meta.get("resolved_call_id", call_id)
                except: pass

                db.collection('agents').document(agent_id).collection('transcripts').add({
                    "call_id": final_call_id,
                    "agent_id": agent_id,
                    "transcript": transcript_text,
                    "created_at": firestore.SERVER_TIMESTAMP
                })
                print(f"[Agent] ✅ Transcript saved for call: {final_call_id}")
            else:
                print("[Agent] ⚠️ No transcript content to save.")
    except Exception as e:
        print(f"[Agent] ❌ Error saving transcript: {e}")

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
