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

from config import GROQ_API_KEY, SARVAM_API_KEY, STATIC_FOLDER, LIVEKIT_URL, CARTESIA_API_KEY, ELEVENLABS_API_KEY, REVEALIQ_HF_TOKEN
from services.tts_service import clean_text_for_tts, detect_tts_voice
from services.auth_service import verify_firebase_token, record_usage

voice_bp = Blueprint('voice', __name__)


@voice_bp.route('/voice/transcribe', methods=['POST'])
def voice_transcribe():
    if 'audio' not in request.files:
        return jsonify({"error": "No audio file provided"}), 400
    audio_file = request.files['audio']
    if not audio_file.filename:
        return jsonify({"error": "No selected file"}), 400
    token_data = verify_firebase_token()
    uid = token_data.get('uid') if token_data else None
    temp_path = os.path.join(os.getcwd(), f"temp_{uuid.uuid4()}.webm")
    try:
        audio_file.save(temp_path)
        if not GROQ_API_KEY:
            if os.path.exists(temp_path): os.remove(temp_path)
            return jsonify({"error": "Groq API Key missing"}), 500
        # Estimate audio seconds from file size (webm @ ~16 kbps mono ≈ 2KB/s)
        try:
            size_bytes = os.path.getsize(temp_path)
            est_seconds = max(1, int(size_bytes / 2048))
        except Exception:
            est_seconds = 1
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
            if uid:
                record_usage(uid, 'stt_seconds', est_seconds, model='whisper-large-v3')
            return jsonify({"text": text})
        else:
            return jsonify({"error": f"Groq Error: {resp.text}"}), resp.status_code
    except Exception as e:
        if os.path.exists(temp_path):
            try: os.remove(temp_path)
            except: pass
        return jsonify({"error": str(e)}), 500


@voice_bp.route('/voice/speak', methods=['POST'])
def voice_speak():
    data = request.get_json()
    text = data.get("text", "").strip()
    if not text:
        return jsonify({"error": "No text provided"}), 400
    if not SARVAM_API_KEY:
        return jsonify({"error": "Sarvam API Key missing"}), 500
    token_data = verify_firebase_token()
    uid = token_data.get('uid') if token_data else None
    text = clean_text_for_tts(text)
    if not text:
        return jsonify({"error": "No speakable text"}), 400
    if uid:
        record_usage(uid, 'tts_chars', len(text), model='sarvam-bulbul-v3')
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


@voice_bp.route('/livekit/token', methods=['POST', 'GET'])
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


@voice_bp.route('/v1/audio/voices', methods=['GET'])
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


@voice_bp.route('/voice/preview', methods=['POST'])
def voice_preview():
    """Generate a short TTS preview audio clip for a specific voice and provider."""
    data = request.get_json() or {}
    voice = data.get('voice', 'shubh')
    provider = data.get('provider', 'sarvam')
    text = data.get('text', "Namaste! This is a preview of how my voice will sound on the call.")
    
    if not text:
        return jsonify({"error": "No text provided"}), 400
        
    token_data = verify_firebase_token()
    uid = token_data.get('uid') if token_data else None
    
    # Simple rate limiting/usage tracking
    if uid:
        record_usage(uid, 'tts_chars', len(text), model=f'preview-{provider}')

    provider_lower = provider.lower()
    
    if provider_lower == 'sarvam':
        if not SARVAM_API_KEY:
            return jsonify({"error": "Sarvam API Key missing"}), 500
            
        text = clean_text_for_tts(text)
        if not text:
            return jsonify({"error": "No speakable text"}), 400
            
        try:
            payload = {
                "inputs": [text],
                "target_language_code": "hi-IN",
                "speaker": voice,
                "model": "bulbul:v3",
                "pace": 1.1,
                "speech_sample_rate": 22050,
                "output_audio_codec": "mp3",
                "enable_preprocessing": True
            }
            resp = requests.post("https://api.sarvam.ai/text-to-speech",
                               headers={"api-subscription-key": SARVAM_API_KEY, "Content-Type": "application/json"},
                               json=payload, timeout=10)
            if resp.status_code != 200:
                return jsonify({"error": f"Sarvam API Error: {resp.text}"}), 500
            rjson = resp.json()
            if "audios" not in rjson or len(rjson["audios"]) == 0:
                return jsonify({"error": "No audio returned"}), 500
            audio_data = base64.b64decode(rjson["audios"][0])
            return Response(audio_data, mimetype="audio/mpeg")
        except Exception as e:
            return jsonify({"error": str(e)}), 500
            
    elif provider_lower == 'revealiq':
        # Split prefix if present (e.g. "revealiq:af_heart" -> "af_heart")
        voice_clean = voice.split(":", 1)[1] if ":" in voice else voice
        model = 'kokoro-hi' if ('hi' in voice_clean.lower() or voice_clean.startswith('hf_') or voice_clean.startswith('hm_')) else 'kokoro-en'
        
        url = 'https://ai.revealiq.in/v1/audio/speech'
        headers = {
            'Content-Type': 'application/json',
        }
        hf_token = REVEALIQ_HF_TOKEN or os.environ.get('HF_TOKEN')
        if hf_token:
            headers['Authorization'] = f'Bearer {hf_token}'
            
        payload = {
            'model': model,
            'input': text,
            'voice': voice_clean,
            'speed': 1.0,
            'response_format': 'mp3'
        }
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=20)
            if not resp.ok:
                return jsonify({"error": f"RevealIQ API Error: {resp.text}"}), 500
            return Response(resp.content, mimetype="audio/mpeg")
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    elif provider_lower == 'cartesia':
        if not CARTESIA_API_KEY:
            return jsonify({"error": "Cartesia API Key missing"}), 500
            
        voice_clean = voice.split(":", 1)[1] if ":" in voice else voice
        url = 'https://api.cartesia.ai/tts'
        headers = {
            'X-API-Key': CARTESIA_API_KEY,
            'Cartesia-Version': '2024-06-10',
            'Content-Type': 'application/json'
        }
        payload = {
            'text': text,
            'model_id': 'sonic-english',
            'voice': {
                'mode': 'id',
                'id': voice_clean
            },
            'output_format': {
                'container': 'mp3',
                'sample_rate': 44100
            }
        }
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=20)
            if not resp.ok:
                return jsonify({"error": f"Cartesia API Error: {resp.text}"}), 500
            return Response(resp.content, mimetype="audio/mpeg")
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    elif provider_lower == 'elevenlabs':
        if not ELEVENLABS_API_KEY:
            return jsonify({"error": "ElevenLabs API Key missing"}), 500
            
        voice_clean = voice.split(":", 1)[1] if ":" in voice else voice
        url = f'https://api.elevenlabs.io/v1/text-to-speech/{voice_clean}'
        headers = {
            'xi-api-key': ELEVENLABS_API_KEY,
            'Content-Type': 'application/json',
            'accept': 'audio/mpeg'
        }
        payload = {
            'text': text,
            'model_id': 'eleven_monolingual_v1',
            'voice_settings': {
                'stability': 0.5,
                'similarity_boost': 0.75
            }
        }
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=20)
            if not resp.ok:
                return jsonify({"error": f"ElevenLabs API Error: {resp.text}"}), 500
            return Response(resp.content, mimetype="audio/mpeg")
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    return jsonify({"error": f"Preview not supported for provider: {provider}"}), 400
