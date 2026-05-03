"""
Kautilya AI — Code Interpreter Routes.

POST /api/code/run   { code: str, files?: [{name, content_b64}] }
  → { stdout, stderr, figures: [base64], exit_code, duration_ms, timed_out }
"""
from flask import Blueprint, request, jsonify

from services.auth_service import verify_firebase_token, record_usage
from services.code_interpreter_service import run_python

code_bp = Blueprint('code', __name__)

MAX_CODE_LEN = 50_000


@code_bp.route('/api/code/run', methods=['POST'])
def api_code_run():
    token_data = verify_firebase_token()
    uid = token_data.get('uid') if token_data else None
    if not uid:
        return jsonify({"error": "Authentication required"}), 401

    data = request.get_json(silent=True) or {}
    code = (data.get('code') or '').strip()
    if not code:
        return jsonify({"error": "code required"}), 400
    if len(code) > MAX_CODE_LEN:
        return jsonify({"error": f"code too long ({len(code)} > {MAX_CODE_LEN})"}), 413

    files = data.get('files') or []
    timeout = min(int(data.get('timeout') or 25), 60)

    try:
        result = run_python(code, timeout=timeout, files=files)
    except Exception as e:
        return jsonify({"error": f"Interpreter crashed: {e}"}), 500

    try:
        record_usage(uid, 'code_runs', 1)
    except Exception:
        pass

    return jsonify(result)
