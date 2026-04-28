"""
Kautilya AI — Voice Routes Blueprint
Handles /api/voice/* endpoints (transcribe, speak).
"""
import os
import re
import uuid
import base64
import requests

from flask import Blueprint, request, jsonify, Response

from config import GROQ_API_KEY, SARVAM_API_KEY, STATIC_FOLDER, LIVEKIT_URL
from services.tts_service import clean_text_for_tts, detect_tts_voice

voice_bp = Blueprint('voice', __name__)


@voice_bp.route('/api/voice/transcribe', methods=['POST'])
def voice_transcribe():
    if 'audio' not in request.files:
        return jsonify({"error": "No audio file provided"}), 400
    audio_file = request.files['audio']
    if not audio_file.filename:
        return jsonify({"error": "No selected file"}), 400
    temp_path = os.path.join(os.getcwd(), f"temp_{uuid.uuid4()}.webm")
    try:
        audio_file.save(temp_path)
        if not GROQ_API_KEY:
            if os.path.exists(temp_path): os.remove(temp_path)
            return jsonify({"error": "Groq API Key missing"}), 500
        with open(temp_path, "rb") as file:
            resp = requests.post(
                "https://api.groq.com/openai/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
                files={"file": (temp_path, file, "audio/webm")},
                data={"model": "whisper-large-v3", "response_format": "json",
                      "prompt": "Conversational Hindi, English, and Hinglish. Do not transcribe silence."},
                timeout=30
            )
        if os.path.exists(temp_path): os.remove(temp_path)
        if resp.status_code == 200:
            text = resp.json().get("text", "").strip()
            text = re.sub(r'\[.*?\]|\(.*?\)', '', text).strip()
            hallucinations = ["thank you", "thanks for watching", "welcome", "subscribe",
                              "please subscribe", "thank you.", "welcome.", "thanks.", "subtitles by", "amara.org"]
            if text.lower() in hallucinations or len(text) < 2:
                text = ""
            return jsonify({"text": text})
        else:
            return jsonify({"error": f"Groq Error: {resp.text}"}), resp.status_code
    except Exception as e:
        if os.path.exists(temp_path):
            try: os.remove(temp_path)
            except: pass
        return jsonify({"error": str(e)}), 500


@voice_bp.route('/api/voice/speak', methods=['POST'])
def voice_speak():
    data = request.get_json()
    text = data.get("text", "").strip()
    if not text:
        return jsonify({"error": "No text provided"}), 400
    if not SARVAM_API_KEY:
        return jsonify({"error": "Sarvam API Key missing"}), 500
    text = clean_text_for_tts(text)
    if not text:
        return jsonify({"error": "No speakable text"}), 400
    voice_config = detect_tts_voice(text)
    try:
        payload = {
            "inputs": [text],
            "target_language_code": voice_config['code'],
            "speaker": voice_config['speaker'],
            "model": "bulbul:v3",
            "pace": 1.1,
            "speech_sample_rate": 22050,
            "output_audio_codec": "mp3",
            "enable_preprocessing": True
        }
        resp = requests.post("https://api.sarvam.ai/text-to-speech",
                           headers={"api-subscription-key": SARVAM_API_KEY, "Content-Type": "application/json"},
                           json=payload, timeout=30)
        if resp.status_code != 200:
            return jsonify({"error": f"Sarvam API Error: {resp.text}"}), 500
        rjson = resp.json()
        if "audios" not in rjson or len(rjson["audios"]) == 0:
            return jsonify({"error": "No audio returned"}), 500
        audio_data = base64.b64decode(rjson["audios"][0])
        return Response(audio_data, mimetype="audio/mpeg")
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@voice_bp.route('/api/livekit/token', methods=['POST', 'GET'])
def generate_livekit_token():
    """Generates a token for the LiveKit agent voice streaming connection."""
    import os
    from extensions import db
    try:
        from livekit import api
    except ImportError:
        return jsonify({"error": "LiveKit SDK not installed"}), 500

    lk_api_key = os.environ.get("LIVEKIT_API_KEY")
    lk_api_secret = os.environ.get("LIVEKIT_API_SECRET")
    if not lk_api_key or not lk_api_secret:
        return jsonify({"error": "LiveKit configuration missing on server."}), 500

    data = request.get_json(silent=True) or request.args or {}
    participant_name = data.get("participantName", "RevealIQ User")
    agent_id = data.get("agentId", "")
    
    if agent_id:
        room_name = f"voice-{agent_id}--{uuid.uuid4().hex[:4]}"
    else:
        room_name = f"room-{uuid.uuid4().hex[:8]}"
    identity = f"user-{uuid.uuid4().hex[:8]}"
    
    token = api.AccessToken(lk_api_key, lk_api_secret) \
        .with_identity(identity) \
        .with_name(participant_name) \
        .with_grants(api.VideoGrants(
            room_join=True,
            room=room_name,
        ))
    
    # Add room metadata if agent_id is provided
    if agent_id and db:
        try:
            agent_doc = db.collection('agents').document(agent_id).get()
            if agent_doc.exists:
                agent_data = agent_doc.to_dict()
                import json
                token.with_metadata(json.dumps({
                    "agent_id": agent_id,
                    "system_prompt": agent_data.get("system_prompt", ""),
                    "voice": agent_data.get("voice", "shubh"),
                    "model": agent_data.get("model", "kautilya-daily"),
                    "welcome_message": agent_data.get("welcome_message", "")
                }))
        except Exception as e:
            print(f"[LiveKit] Metadata error: {e}")

    return jsonify({
        "token": token.to_jwt(), 
        "roomName": room_name,
        "wsUrl": LIVEKIT_URL or "wss://your-project.livekit.cloud"
    })


@voice_bp.route('/api/v1/audio/voices', methods=['GET'])
def api_v1_voices():
    """Returns a list of available TTS voices (cached)."""
    from flask import current_app
    if not hasattr(current_app, 'edge_voices_cache'):
        try:
            import asyncio
            import edge_tts
            voices = asyncio.run(edge_tts.list_voices())
            current_app.edge_voices_cache = [{"name": v["Name"], "shortName": v["ShortName"], "gender": v["Gender"], "locale": v["Locale"]} for v in voices]
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    return jsonify({"voices": current_app.edge_voices_cache})
