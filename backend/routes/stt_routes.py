import os
import requests
import logging
import threading
import time
from flask import Blueprint, request, jsonify
from flask_cors import cross_origin
from services.auth_service import verify_firebase_token, record_usage

logger = logging.getLogger(__name__)

stt_bp = Blueprint('stt', __name__)

# RevealIQ STT Space (Nemotron 3.5 streaming ASR, ONNX INT4). Separate Space
# from the TTS one — override with STT_SPACE_BASE if the repo name differs.
STT_BASE = (os.environ.get('STT_SPACE_BASE')
            or 'https://HarshSharma1212-RevealIQ-STT.hf.space').rstrip('/')


def _hf_headers():
    hf_token = os.environ.get('REVEALIQ_HF_TOKEN') or os.environ.get('HF_TOKEN')
    return {'Authorization': f'Bearer {hf_token}'} if hf_token else {}


def _warmup_stt():
    """Ping the STT Space every 4 minutes to keep it warm (free CPU sleeps)."""
    while True:
        try:
            requests.get(f'{STT_BASE}/health', headers=_hf_headers(), timeout=10)
        except Exception:
            pass
        time.sleep(240)


threading.Thread(target=_warmup_stt, daemon=True).start()


@stt_bp.route('/stt/revealiq/status', methods=['GET', 'OPTIONS'])
@cross_origin()
def revealiq_stt_status():
    """Surface the Space's model readiness so the UI can show 'warming up'."""
    if request.method == 'OPTIONS':
        return '', 200
    try:
        r = requests.get(f'{STT_BASE}/health', headers=_hf_headers(), timeout=10)
        return jsonify(r.json()), r.status_code
    except Exception as e:
        return jsonify({"status": "unreachable", "ready": False, "error": str(e)}), 502


@stt_bp.route('/stt/revealiq/transcribe', methods=['POST', 'OPTIONS'])
@cross_origin()
def revealiq_transcribe():
    """Proxy an audio blob to the RevealIQ STT Space and return the transcript.

    Used by STT Studio for BOTH file upload and the live mode (which posts one
    short segment at a time). Accepts multipart 'file' or a raw audio body.
    """
    if request.method == 'OPTIONS':
        return '', 200

    try:
        token_data = verify_firebase_token()
        uid = token_data.get('uid') if token_data else None
        if not uid:
            return jsonify({"error": "Unauthorized"}), 401

        # Accept either multipart upload or a raw audio body (live PCM/webm).
        if 'file' in request.files:
            f = request.files['file']
            audio_bytes = f.read()
            filename = f.filename or 'audio.wav'
            content_type = f.mimetype or 'application/octet-stream'
        else:
            audio_bytes = request.get_data()
            filename = 'audio.wav'
            content_type = request.content_type or 'application/octet-stream'

        if not audio_bytes:
            return jsonify({"error": "audio is required"}), 400

        language = (request.form.get('language')
                    or request.args.get('language') or '').strip()

        files = {'file': (filename, audio_bytes, content_type)}
        data = {}
        if language:
            data['language'] = language

        url = f'{STT_BASE}/v1/audio/transcriptions'
        headers = _hf_headers()

        # The Space is single-instance CPU; HF's edge can 429/502/503 under
        # bursts. Each segment is short and idempotent, so a bounded retry is
        # safe and keeps the live transcript flowing.
        RETRY_STATUSES = {429, 502, 503, 504}
        BACKOFFS = (0.5, 1.0, 2.0)
        resp = None
        last_status = None
        for attempt in range(len(BACKOFFS) + 1):
            try:
                resp = requests.post(url, headers=headers, files=files, data=data,
                                     timeout=(15, 120))
            except requests.exceptions.RequestException as conn_err:
                logger.warning(f"[STT] connect error (attempt {attempt + 1}): {conn_err}")
                if attempt < len(BACKOFFS):
                    time.sleep(BACKOFFS[attempt])
                    continue
                return jsonify({"error": "Upstream unreachable"}), 502

            if resp.ok:
                break
            last_status = resp.status_code
            if resp.status_code in RETRY_STATUSES and attempt < len(BACKOFFS):
                time.sleep(BACKOFFS[attempt])
                continue
            break

        if resp is None or not resp.ok:
            body = resp.text[:300] if resp is not None else ''
            logger.warning(f"[STT] upstream failed {last_status}: {body}")
            # 503 = model still warming; surface it so the UI can retry softly.
            status = last_status if last_status in (429, 503) else 502
            return jsonify({"error": f"Transcription failed ({last_status})",
                            "detail": body, "retryable": True}), status

        result = resp.json()

        # Bill by transcribed audio seconds (rounded up), reported by the Space.
        secs = int(round(result.get('duration', 0) or 0)) or 1
        threading.Thread(
            target=record_usage, args=(uid, 'stt_seconds', secs, 'revealiq-nemotron'),
            daemon=True,
        ).start()

        return jsonify(result), 200

    except Exception as e:
        logger.exception("[STT] transcribe error")
        return jsonify({"error": str(e)}), 500