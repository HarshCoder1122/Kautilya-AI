"""
Kautilya AI — Computer Routes.

Read-only REST surface for the "Kautilya Computer" panel: lets the frontend
browse the persistent per-session sandbox that the agent's [FILE_WRITE:] /
[FILE_READ:] / [FILE_LIST:] / [RUN_PYTHON:] tools operate on
(services/computer_service.py). Writing only ever happens from the agent
loop, never directly from the client, so this blueprint is GET-only.

GET /api/computer/files?session_id=...             -> { files: [{path, bytes}] }
GET /api/computer/file?session_id=...&name=...      -> { path, content, truncated, bytes }
"""
from flask import Blueprint, request, jsonify

from services.auth_service import verify_firebase_token
from services.computer_service import list_files, read_file

computer_bp = Blueprint('computer', __name__)


@computer_bp.route('/computer/files', methods=['GET'])
def api_computer_files():
    token_data = verify_firebase_token()
    uid = token_data.get('uid') if token_data else None
    if not uid:
        return jsonify({"error": "Authentication required"}), 401

    session_id = (request.args.get('session_id') or '').strip()
    if not session_id:
        return jsonify({"error": "session_id required"}), 400

    try:
        files = list_files(uid, session_id)
    except Exception as e:
        return jsonify({"error": f"Could not list workspace: {e}"}), 500

    return jsonify({"files": files})


@computer_bp.route('/computer/file', methods=['GET'])
def api_computer_file():
    token_data = verify_firebase_token()
    uid = token_data.get('uid') if token_data else None
    if not uid:
        return jsonify({"error": "Authentication required"}), 401

    session_id = (request.args.get('session_id') or '').strip()
    name = (request.args.get('name') or '').strip()
    if not session_id or not name:
        return jsonify({"error": "session_id and name required"}), 400

    try:
        res = read_file(uid, session_id, name)
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403
    except Exception as e:
        return jsonify({"error": f"Could not read file: {e}"}), 500

    if not res.get("ok"):
        return jsonify({"error": res.get("error", "read failed")}), 404

    return jsonify({
        "path": name,
        "content": res["content"],
        "truncated": res["truncated"],
        "bytes": res["bytes"],
    })
