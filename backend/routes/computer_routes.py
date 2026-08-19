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
GET /api/computer/browser/live                      -> SSE stream of live screencast frames

The browser (services/browser_service.py) is scoped per USER, not per chat —
one persistent "computer" regardless of which conversation you're in — so
/computer/browser* deliberately take NO session_id: they operate on whatever
the CURRENT state of that one shared browser is, so opening the panel in a
different chat than the one that did the browsing still shows the truth.

/computer/browser/live is a REAL live view (Chrome DevTools Protocol
screencast — the same mechanism remote-browser tools like Browserbase use),
not a polled screenshot: each `data:` line is one JPEG frame, arriving
continuously (~8fps cap) for as long as the connection stays open. The
screencast only runs while at least one client is actually connected here —
see services/browser_service.py's _start_screencast_if_needed /
_stop_screencast_if_idle.
"""
import queue as _queue
import time as _time

from flask import Blueprint, request, jsonify, Response

from services.auth_service import verify_firebase_token
from services.computer_service import list_files, read_file
from services.browser_service import get_current_state, open_live_view, close_live_view

computer_bp = Blueprint('computer', __name__)

# How long the SSE loop waits for a frame before sending a keep-alive
# comment (proxies/browsers can otherwise decide the connection is dead).
_LIVE_FRAME_WAIT_S = 5
# Hard ceiling on ONE stream connection's lifetime — the frontend reconnects
# after this rather than a single request pinning a gunicorn thread forever.
_LIVE_MAX_DURATION_S = 10 * 60


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


@computer_bp.route('/computer/browser/live', methods=['GET'])
def api_computer_browser_live():
    token_data = verify_firebase_token()
    uid = token_data.get('uid') if token_data else None
    if not uid:
        return jsonify({"error": "Authentication required"}), 401

    q = open_live_view(uid)
    if q is None:
        return jsonify({"error": "No active browser session to watch"}), 404

    def stream():
        start = _time.time()
        try:
            while _time.time() - start < _LIVE_MAX_DURATION_S:
                try:
                    frame_b64 = q.get(timeout=_LIVE_FRAME_WAIT_S)
                    yield f"data: {frame_b64}\n\n"
                except _queue.Empty:
                    yield ": keep-alive\n\n"
        finally:
            # Runs even if the client disconnects mid-stream (generator
            # close) — without this the screencast keeps encoding frames
            # for a viewer that already left.
            close_live_view(uid, q)

    return Response(stream(), mimetype='text/event-stream',
                     headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no',
                              'Connection': 'keep-alive'})
