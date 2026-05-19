"""
Kautilya AI — Coder Project Routes
Persists parsed multi-file coder projects to Firestore keyed by message_id,
so files survive even if the underlying message text is edited or truncated.

POST /api/coder/project/save   { uid, message_id, title, files: [{name, language, content}] }
GET  /api/coder/project/<message_id>?uid=...
"""
from flask import Blueprint, request, jsonify

projects_bp = Blueprint('projects', __name__)


@projects_bp.route('/coder/project/save', methods=['POST'])
def save_project():
    from extensions import db
    if not db:
        return jsonify({"error": "Firestore unavailable"}), 503

    data = request.get_json(silent=True) or {}
    uid = (data.get('uid') or '').strip()
    message_id = (data.get('message_id') or '').strip()
    files = data.get('files') or []
    title = (data.get('title') or 'Untitled Project').strip()

    if not uid or not message_id:
        return jsonify({"error": "uid and message_id required"}), 400
    if not isinstance(files, list) or not files:
        return jsonify({"error": "files must be a non-empty list"}), 400

    # Sanity-limit individual file size & total payload (Firestore doc max 1MiB).
    MAX_FILE = 700_000
    MAX_TOTAL = 900_000
    total = 0
    cleaned = []
    for f in files:
        name = (f.get('name') or '').strip()
        if not name:
            continue
        content = f.get('content') or ''
        if not isinstance(content, str):
            content = str(content)
        if len(content) > MAX_FILE:
            content = content[:MAX_FILE] + '\n// [truncated]'
        total += len(content) + len(name)
        if total > MAX_TOTAL:
            break
        cleaned.append({
            'name': name,
            'language': f.get('language') or '',
            'content': content,
        })

    if not cleaned:
        return jsonify({"error": "no valid files"}), 400

    try:
        from firebase_admin import firestore as _fs
        ref = db.collection('users').document(uid).collection('coder_projects').document(message_id)
        ref.set({
            'message_id': message_id,
            'title': title,
            'files': cleaned,
            'file_count': len(cleaned),
            'updated_at': _fs.SERVER_TIMESTAMP,
        }, merge=True)
        return jsonify({"ok": True, "file_count": len(cleaned)})
    except Exception as e:
        print(f"[CoderProject] save failed: {e}")
        return jsonify({"error": str(e)}), 500


@projects_bp.route('/coder/project/<message_id>', methods=['GET'])
def load_project(message_id):
    from extensions import db
    if not db:
        return jsonify({"error": "Firestore unavailable"}), 503

    uid = (request.args.get('uid') or '').strip()
    if not uid or not message_id:
        return jsonify({"error": "uid and message_id required"}), 400

    try:
        ref = db.collection('users').document(uid).collection('coder_projects').document(message_id)
        snap = ref.get()
        if not snap.exists:
            return jsonify({"found": False, "files": []})
        data = snap.to_dict() or {}
        return jsonify({
            "found": True,
            "title": data.get('title') or '',
            "files": data.get('files') or [],
        })
    except Exception as e:
        print(f"[CoderProject] load failed: {e}")
        return jsonify({"error": str(e)}), 500
