import os
import requests
import json
import logging
import threading
import time
from flask import Blueprint, request, send_file, jsonify
from flask_cors import cross_origin
from services.auth_service import verify_firebase_token, record_usage

logger = logging.getLogger(__name__)

tts_bp = Blueprint('tts', __name__)

from config import REVEALIQ_TTS_URL
REVEALIQ_BASE = REVEALIQ_TTS_URL

# NOTE: keep-warm pinging moved to services/warmup_service.py (one single-
# flighted pinger for STT + TTS + voice, instead of one thread per worker per
# module). Started once from app.py.


@tts_bp.route('/tts/revealiq/stream', methods=['POST', 'OPTIONS'])
@cross_origin()
def reveal_iq_stream():
    """Stream raw PCM audio from RevealIQ (Zero-Lag)."""
    if request.method == 'OPTIONS':
        return '', 200
    
    try:
        token_data = verify_firebase_token()
        uid = token_data.get('uid') if token_data else None
        if not uid:
            return jsonify({"error": "Unauthorized"}), 401

        data = request.get_json(silent=True) or {}
        text = data.get('text', '').strip()
        if not text:
            return jsonify({"error": "text is required"}), 400
        raw_model = data.get('model', 'swara-en')
        model = 'kokoro-hi' if 'hi' in raw_model.lower() else 'kokoro-en'
        voice = data.get('voice', 'af_bella')
        speed = data.get('speed', 1.0)

        hf_token = os.environ.get('REVEALIQ_HF_TOKEN') or os.environ.get('HF_TOKEN')
        url = f'{REVEALIQ_BASE}/v1/audio/stream'

        headers = {'Content-Type': 'application/json'}
        if hf_token:
            headers['Authorization'] = f'Bearer {hf_token}'

        print(f"[TTS Stream] POST {url} | model={model} voice={voice}", flush=True)

        payload = {
            'model': model,
            'input': text,
            'voice': voice,
            'speed': float(speed),
        }

        # Request streaming from Space. Connect timeout 15s, but NO read
        # timeout — long messages take 30-90s of continuous chunk delivery
        # and a scalar `timeout=60` was killing playback mid-stream.
        #
        # The Space is single-GPU and HF's edge throttles it (HTTP 429, the
        # "We're on a journey" HTML page) under bursts of concurrent requests.
        # No audio byte has shipped yet at this point, so retrying the POST is
        # safe. Ride out brief blips with a short bounded backoff before giving
        # up — total added latency ~3.5s worst case.
        RETRY_STATUSES = {429, 502, 503, 504}
        BACKOFFS = (0.5, 1.0, 2.0)  # attempts = len + 1 = 4
        resp = None
        last_status = None
        for attempt in range(len(BACKOFFS) + 1):
            try:
                resp = requests.post(url, headers=headers, json=payload, stream=True, timeout=(15, None))
            except requests.exceptions.RequestException as conn_err:
                last_status = None
                print(f"[TTS Stream] RevealIQ connect error (attempt {attempt + 1}): {conn_err}", flush=True)
                if attempt < len(BACKOFFS):
                    time.sleep(BACKOFFS[attempt])
                    continue
                return jsonify({"error": "Upstream unreachable"}), 502

            if resp.ok:
                break

            last_status = resp.status_code
            if resp.status_code in RETRY_STATUSES and attempt < len(BACKOFFS):
                print(f"[TTS Stream] RevealIQ {resp.status_code} (attempt {attempt + 1}), "
                      f"retrying in {BACKOFFS[attempt]}s", flush=True)
                resp.close()
                time.sleep(BACKOFFS[attempt])
                continue
            break

        if resp is None or not resp.ok:
            body = resp.text[:300] if resp is not None else ''
            print(f"[TTS Stream] RevealIQ FAILED {last_status} after retries: {body}", flush=True)
            # Surface 429 as 429 so the client can distinguish "busy, retry"
            # from a genuine server fault and back off / show a soft message.
            status = 429 if last_status == 429 else 502
            return jsonify({"error": f"Streaming failed ({last_status})", "retryable": True}), status

        # Record usage AFTER confirming the upstream accepted the request —
        # moved out of the critical path so Firestore write doesn't add
        # latency before the first audio byte ships to the client.
        import threading as _th
        _th.Thread(target=record_usage, args=(uid, 'tts_chars', len(text), model), daemon=True).start()

        from flask import Response
        def generate():
            for chunk in resp.iter_content(chunk_size=1024):  # 1KB chunks = lower TTFB
                if chunk:
                    yield chunk

        return Response(
            generate(),
            mimetype='application/octet-stream',
            headers={
                'X-Sample-Rate': '24000',
                'X-Channels': '1',
                'X-Bit-Depth': '16',
                'Cache-Control': 'no-cache',
            }
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@tts_bp.route('/tts/revealiq/synthesize', methods=['POST', 'OPTIONS'])
@cross_origin()
def reveal_iq_synthesize():
    """Synthesize speech using RevealIQ (Kokoro-82M) engine."""
    if request.method == 'OPTIONS':
        return '', 200
    
    try:
        token_data = verify_firebase_token()
        uid = token_data.get('uid') if token_data else None
        if not uid:
            return jsonify({"error": "Unauthorized"}), 401

        data = request.get_json()
        text = data.get('text', '')
        # Standardize model names for Kokoro engine
        raw_model = data.get('model', 'swara-en')
        model = 'kokoro-hi' if 'hi' in raw_model.lower() else 'kokoro-en'
            
        voice = data.get('voice', 'af_bella')
        speed = data.get('speed', 1.0)
        
        if not text:
            return jsonify({"error": "Text is required"}), 400

        # Record usage
        record_usage(uid, 'tts_chars', len(text), model)
        
        hf_token = os.environ.get('REVEALIQ_HF_TOKEN') or os.environ.get('HF_TOKEN')
        
        url = f'{REVEALIQ_BASE}/v1/audio/speech'
        headers = {
            'Content-Type': 'application/json',
        }
        if hf_token:
            headers['Authorization'] = f'Bearer {hf_token}'
        
        payload = {
            'model': model,
            'input': text,
            'voice': voice,
            'speed': float(speed),
            'response_format': 'wav'
        }
        
        print(f"[RevealIQ] Synthesis request: URL={url} | Model={model} | Voice={voice}")
        
        response = requests.post(url, headers=headers, json=payload, timeout=45)
        
        if not response.ok:
            print(f"[RevealIQ] Synthesis failed: {response.text}")
            return jsonify({"error": f"TTS synthesis failed: {response.text}"}), 500
        
        from flask import Response
        return Response(
            response.content,
            mimetype='audio/wav',
            headers={'Content-Disposition': 'attachment; filename=revealiq_audio.wav'}
        )
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@tts_bp.route('/tts/cartesia/synthesize', methods=['POST', 'OPTIONS'])
@cross_origin()
def cartesia_synthesize():
    """Synthesize speech using Cartesia TTS."""
    if request.method == 'OPTIONS':
        return '', 200
    
    try:
        token_data = verify_firebase_token()
        uid = token_data.get('uid') if token_data else None
        if not uid:
            return jsonify({"error": "Unauthorized"}), 401

        data = request.get_json()
        text = data.get('text', '')
        voice = data.get('voice', '')
        
        if not text:
            return jsonify({"error": "Text is required"}), 400
        if not voice:
            return jsonify({"error": "Voice ID is required"}), 400

        # Record usage
        record_usage(uid, 'tts_chars', len(text), 'cartesia')
        
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


@tts_bp.route('/tts/elevenlabs/synthesize', methods=['POST', 'OPTIONS'])
@cross_origin()
def elevenlabs_synthesize():
    """Synthesize speech using ElevenLabs TTS."""
    if request.method == 'OPTIONS':
        return '', 200
    
    try:
        token_data = verify_firebase_token()
        uid = token_data.get('uid') if token_data else None
        if not uid:
            return jsonify({"error": "Unauthorized"}), 401

        data = request.get_json()
        text = data.get('text', '')
        voice_id = data.get('voice_id', '')
        
        if not text:
            return jsonify({"error": "Text is required"}), 400
        if not voice_id:
            return jsonify({"error": "Voice ID is required"}), 400

        # Record usage
        record_usage(uid, 'tts_chars', len(text), 'elevenlabs')
        
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


@tts_bp.route('/tts/sarvam/synthesize', methods=['POST', 'OPTIONS'])
@cross_origin()
def sarvam_synthesize():
    """Synthesize speech using Sarvam AI TTS."""
    if request.method == 'OPTIONS':
        return '', 200
    
    try:
        token_data = verify_firebase_token()
        uid = token_data.get('uid') if token_data else None
        if not uid:
            return jsonify({"error": "Unauthorized"}), 401

        data = request.get_json()
        text = data.get('text', '')
        language = data.get('language', 'hi-IN')
        
        if not text:
            return jsonify({"error": "Text is required"}), 400

        # Record usage
        record_usage(uid, 'tts_chars', len(text), 'sarvam')
        
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
