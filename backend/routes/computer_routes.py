"""
Kautilya AI — Computer Routes.

Read-only REST surface for the "Kautilya Computer" panel: lets the frontend
browse the persistent per-session sandbox that the agent's [FILE_WRITE:] /
[FILE_READ:] / [FILE_LIST:] / [RUN_PYTHON:] tools operate on
(services/computer_service.py). Writing only ever happens from the agent
loop, never directly from the client, so this blueprint is GET-only.

GET /api/computer/files?session_id=...             -> { files: [{path, bytes}] }
GET /api/computer/file?session_id=...&name=...      -> { path, content, truncated, bytes }
GET /api/computer/browser                           -> current browser state (see below)

The browser (services/browser_service.py) is scoped per USER, not per chat —
one persistent "computer" regardless of which conversation you're in — so
/computer/browser deliberately takes NO session_id: it returns whatever the
CURRENT state of that one shared browser is, so opening the panel in a
different chat than the one that did the browsing still shows the truth.
"""
from flask import Blueprint, request, jsonify

from services.auth_service import verify_firebase_token
from services.computer_service import list_files, read_file
from services.browser_service import get_current_state

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


@computer_bp.route('/computer/browser', methods=['GET'])
def api_computer_browser():
    token_data = verify_firebase_token()
    uid = token_data.get('uid') if token_data else None
    if not uid:
        return jsonify({"error": "Authentication required"}), 401

    try:
        res = get_current_state(uid)
    except Exception as e:
        return jsonify({"error": f"Could not read browser state: {e}"}), 500

    if not res.get("ok"):
        # No active browser for this user yet — not an error, just empty.
        return jsonify({"active": False})

    return jsonify({
        "active": True,
        "url": res.get("url"),
        "title": res.get("title"),
        "screenshot_b64": res.get("screenshot_b64"),
        "links": res.get("links") or [],
    })
