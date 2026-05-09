"""
Kautilya AI — TTS Routes Blueprint
Handles /api/tts/* endpoints for Text-to-Speech synthesis.
"""
import os
import requests
from flask import Blueprint, request, send_file
from flask_cors import cross_origin

tts_bp = Blueprint('tts', __name__)


@tts_bp.route('/api/tts/revealiq/synthesize', methods=['POST', 'OPTIONS'])
@cross_origin()
def reveal_iq_synthesize():
    """Synthesize speech using RevealIQ (Kokoro-82M) engine."""
    if request.method == 'OPTIONS':
        return '', 200
    
    try:
        data = request.get_json()
        text = data.get('text', '')
        model = data.get('model', 'kokoro-en')
        voice = data.get('voice', 'af_heart')
        speed = data.get('speed', 1.0)
        
        if not text:
            return jsonify({"error": "Text is required"}), 400
        
        hf_token = os.environ.get('REVEALIQ_HF_TOKEN')
        if not hf_token:
            return jsonify({"error": "RevealIQ HF token not configured"}), 500
        
        # Call RevealIQ Hugging Face Space
        url = 'https://harshsharma1212-revealiq-asr.hf.space/v1/audio/speech'
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {hf_token}',
        }
        payload = {
            'model': model,
            'input': text,
            'voice': voice,
            'speed': speed,
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        
        if not response.ok:
            return jsonify({"error": f"TTS synthesis failed: {response.text}"}), 500
        
        # Return audio blob
        from flask import Response
        return Response(
            response.content,
            mimetype='audio/wav',
            headers={'Content-Disposition': 'attachment; filename=revealiq_audio.wav'}
        )
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@tts_bp.route('/api/tts/cartesia/synthesize', methods=['POST', 'OPTIONS'])
@cross_origin()
def cartesia_synthesize():
    """Synthesize speech using Cartesia TTS."""
    if request.method == 'OPTIONS':
        return '', 200
    
    try:
        data = request.get_json()
        text = data.get('text', '')
        voice = data.get('voice', '')
        
        if not text:
            return jsonify({"error": "Text is required"}), 400
        if not voice:
            return jsonify({"error": "Voice ID is required"}), 400
        
        api_key = os.environ.get('CARTESIA_API_KEY')
        if not api_key:
            return jsonify({"error": "Cartesia API key not configured"}), 500
        
        # Call Cartesia API
        url = 'https://api.cartesia.ai/tts'
        headers = {
            'Content-Type': 'application/json',
            'X-API-Key': api_key,
        }
        payload = {
            'text': text,
            'voice': voice,
            'output_format': 'mp3',
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        
        if not response.ok:
            return jsonify({"error": f"Cartesia TTS failed: {response.text}"}), 500
        
        # Return audio blob
        from flask import Response
        return Response(
            response.content,
            mimetype='audio/mpeg',
            headers={'Content-Disposition': 'attachment; filename=cartesia_audio.mp3'}
        )
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@tts_bp.route('/api/tts/elevenlabs/synthesize', methods=['POST', 'OPTIONS'])
@cross_origin()
def elevenlabs_synthesize():
    """Synthesize speech using ElevenLabs TTS."""
    if request.method == 'OPTIONS':
        return '', 200
    
    try:
        data = request.get_json()
        text = data.get('text', '')
        voice_id = data.get('voice_id', '')
        
        if not text:
            return jsonify({"error": "Text is required"}), 400
        if not voice_id:
            return jsonify({"error": "Voice ID is required"}), 400
        
        api_key = os.environ.get('ELEVENLABS_API_KEY')
        if not api_key:
            return jsonify({"error": "ElevenLabs API key not configured"}), 500
        
        # Call ElevenLabs API
        url = f'https://api.elevenlabs.io/v1/text-to-speech/{voice_id}'
        headers = {
            'Content-Type': 'application/json',
            'xi-api-key': api_key,
        }
        payload = {
            'text': text,
            'model_id': 'eleven_multilingual_v2',
            'output_format': 'mp3_44100_128',
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        
        if not response.ok:
            return jsonify({"error": f"ElevenLabs TTS failed: {response.text}"}), 500
        
        # Return audio blob
        from flask import Response
        return Response(
            response.content,
            mimetype='audio/mpeg',
            headers={'Content-Disposition': 'attachment; filename=elevenlabs_audio.mp3'}
        )
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@tts_bp.route('/api/tts/sarvam/synthesize', methods=['POST', 'OPTIONS'])
@cross_origin()
def sarvam_synthesize():
    """Synthesize speech using Sarvam AI TTS."""
    if request.method == 'OPTIONS':
        return '', 200
    
    try:
        data = request.get_json()
        text = data.get('text', '')
        language = data.get('language', 'hi-IN')
        
        if not text:
            return jsonify({"error": "Text is required"}), 400
        
        api_key = os.environ.get('SARVAM_API_KEY')
        if not api_key:
            return jsonify({"error": "Sarvam API key not configured"}), 500
        
        # Call Sarvam API
        url = 'https://api.sarvam.ai/text-to-speech/synthesize'
        headers = {
            'Content-Type': 'application/json',
            'api-subscription-key': api_key,
        }
        payload = {
            'inputs': [text],
            'target_language_code': language,
            'speaker': 'meera',
            'model': 'bulbul',
            'pitch': 0,
            'style': 'formal',
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        
        if not response.ok:
            return jsonify({"error": f"Sarvam TTS failed: {response.text}"}), 500
        
        # Return audio blob (Sarvam returns WAV)
        from flask import Response
        return Response(
            response.content,
            mimetype='audio/wav',
            headers={'Content-Disposition': 'attachment; filename=sarvam_audio.wav'}
        )
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
