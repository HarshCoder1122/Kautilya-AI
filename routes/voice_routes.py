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

from config import GROQ_API_KEY, SARVAM_API_KEY, STATIC_FOLDER
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
