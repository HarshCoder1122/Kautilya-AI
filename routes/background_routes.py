"""
Kautilya AI — Background Task Engine.

User submits a heavy task → worker runs it asynchronously → user can
leave / close tab / come back later and retrieve the result.

Endpoints:
  POST   /api/jarvis/background              create a task
  GET    /api/jarvis/background              list current user's tasks
  GET    /api/jarvis/background/<task_id>    fetch status + result
  DELETE /api/jarvis/background/<task_id>    cancel / delete
  GET    /api/jarvis/background/<task_id>/stream   live SSE stream

Storage: in-memory task table (MVP). If Firestore is available, a mirror
copy is written under `users/{uid}/background_tasks/{task_id}` so that
results survive a server restart.
"""
import json
import time
import uuid
import threading
from collections import deque

from flask import Blueprint, request, jsonify, Response

from config import SYSTEM_PROMPT
from services.auth_service import verify_firebase_token
from services.agent_loop_service import get_llm_response

background_bp = Blueprint('background', __name__)

# ---------- In-memory task registry ----------
# task_id -> {uid, title, model, max_thinking, status, created, updated,
#             chunks: deque[str], result: str, error: str|None, cancelled: bool}
TASKS = {}
TASKS_LOCK = threading.Lock()
MAX_TASKS_PER_USER = 10
MAX_TASK_AGE = 6 * 3600  # 6h


def _gc():
    now = time.time()
    with TASKS_LOCK:
        stale = [tid for tid, t in TASKS.items() if now - t['created'] > MAX_TASK_AGE]
        for tid in stale:
            TASKS.pop(tid, None)


def _mirror_to_firestore(uid, task_id, patch):
    try:
        from extensions import db
        if not db or not uid:
            return
        ref = db.collection('users').document(uid).collection('background_tasks').document(task_id)
        from firebase_admin import firestore
        patch = dict(patch)
        patch['updated_at'] = firestore.SERVER_TIMESTAMP
        ref.set(patch, merge=True)
    except Exception as e:
        print(f"[BG] Firestore mirror failed: {e}")


def _worker(task_id):
    with TASKS_LOCK:
        task = TASKS.get(task_id)
    if not task:
        return
    try:
        task['status'] = 'running'
        _mirror_to_firestore(task['uid'], task_id,
                              {'status': 'running', 'started_at': time.time()})
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT + "\n\n[BACKGROUND MODE] You are producing a high-quality, self-contained deliverable. The user has left — no follow-up questions. Structure your answer with a short Summary up top."},
            {"role": "user", "content": task['prompt']},
        ]
        gen = get_llm_response(
            messages, uid=task['uid'], model=task.get('model', 'pro'),
            max_thinking=task.get('max_thinking', True),
        )
        full = ""
        if gen is None:
            task['error'] = "LLM unavailable"
            task['status'] = 'error'
            return
        for item in gen:
            if task.get('cancelled'):
                task['status'] = 'cancelled'
                return
            if isinstance(item, str):
                try:
                    obj = json.loads(item)
                except Exception:
                    obj = {"chunk": item}
            elif isinstance(item, dict):
                obj = item
            else:
                continue
            chunk = obj.get('chunk')
            if chunk:
                full += chunk
            task['chunks'].append(obj)
            task['updated'] = time.time()
        task['result'] = full
        task['status'] = 'done'
        _mirror_to_firestore(task['uid'], task_id, {
            'status': 'done', 'result': full[:90000],
            'finished_at': time.time(),
        })
    except Exception as e:
        task['error'] = str(e)
        task['status'] = 'error'
        _mirror_to_firestore(task['uid'], task_id,
                              {'status': 'error', 'error': str(e)})
    finally:
        task['updated'] = time.time()


@background_bp.route('/api/jarvis/background', methods=['POST'])
def create_task():
    token_data = verify_firebase_token()
    uid = token_data.get('uid') if token_data else None
    if not uid:
        return jsonify({"error": "Authentication required"}), 401

    _gc()
    with TASKS_LOCK:
        user_open = sum(1 for t in TASKS.values()
                        if t['uid'] == uid and t['status'] in ('queued', 'running'))
    if user_open >= MAX_TASKS_PER_USER:
        return jsonify({"error": f"Too many active background tasks (max {MAX_TASKS_PER_USER})."}), 429

    data = request.get_json(silent=True) or {}
    prompt = (data.get('prompt') or data.get('message') or '').strip()
    if not prompt:
        return jsonify({"error": "prompt required"}), 400

    title = (data.get('title') or prompt[:80]).strip()
    model = data.get('model') or 'pro'
    max_thinking = bool(data.get('max_thinking', True))

    task_id = f"bg_{uuid.uuid4().hex[:20]}"
    now = time.time()
    task = {
        'id': task_id, 'uid': uid, 'title': title, 'prompt': prompt,
        'model': model, 'max_thinking': max_thinking,
        'status': 'queued', 'created': now, 'updated': now,
        'chunks': deque(maxlen=4000), 'result': '', 'error': None,
        'cancelled': False,
    }
    with TASKS_LOCK:
        TASKS[task_id] = task

    _mirror_to_firestore(uid, task_id, {
        'id': task_id, 'title': title, 'prompt': prompt[:2000],
        'model': model, 'max_thinking': max_thinking,
        'status': 'queued', 'created_at': now,
    })

    threading.Thread(target=_worker, args=(task_id,), daemon=True).start()
    return jsonify({"status": "ok", "task_id": task_id, "title": title})


@background_bp.route('/api/jarvis/background', methods=['GET'])
def list_tasks():
    token_data = verify_firebase_token()
    uid = token_data.get('uid') if token_data else None
    if not uid:
        return jsonify({"error": "Authentication required"}), 401
    _gc()
    with TASKS_LOCK:
        items = [
            {k: v for k, v in t.items() if k not in ('chunks', 'prompt')}
            for t in TASKS.values() if t['uid'] == uid
        ]
    items.sort(key=lambda x: x['created'], reverse=True)
    return jsonify({"tasks": items})


@background_bp.route('/api/jarvis/background/<task_id>', methods=['GET'])
def get_task(task_id):
    token_data = verify_firebase_token()
    uid = token_data.get('uid') if token_data else None
    if not uid:
        return jsonify({"error": "Authentication required"}), 401
    with TASKS_LOCK:
        task = TASKS.get(task_id)
    if not task or task['uid'] != uid:
        # Try Firestore fallback
        try:
            from extensions import db
            if db:
                doc = db.collection('users').document(uid).collection('background_tasks').document(task_id).get()
                if doc.exists:
                    return jsonify(doc.to_dict())
        except Exception:
            pass
        return jsonify({"error": "Not found"}), 404
    resp = {k: v for k, v in task.items() if k != 'chunks'}
    return jsonify(resp)


@background_bp.route('/api/jarvis/background/<task_id>', methods=['DELETE'])
def delete_task(task_id):
    token_data = verify_firebase_token()
    uid = token_data.get('uid') if token_data else None
    if not uid:
        return jsonify({"error": "Authentication required"}), 401
    with TASKS_LOCK:
        task = TASKS.get(task_id)
        if task and task['uid'] == uid:
            task['cancelled'] = True
            TASKS.pop(task_id, None)
    try:
        from extensions import db
        if db:
            db.collection('users').document(uid).collection('background_tasks').document(task_id).delete()
    except Exception:
        pass
    return jsonify({"status": "ok"})


@background_bp.route('/api/jarvis/background/<task_id>/stream', methods=['GET'])
def stream_task(task_id):
    token_data = verify_firebase_token()
    uid = token_data.get('uid') if token_data else None
    if not uid:
        return jsonify({"error": "Authentication required"}), 401
    with TASKS_LOCK:
        task = TASKS.get(task_id)
    if not task or task['uid'] != uid:
        return jsonify({"error": "Not found"}), 404

    def emit():
        idx = 0
        # Replay existing chunks first
        while True:
            with TASKS_LOCK:
                chunks = list(task['chunks'])
                status = task['status']
            while idx < len(chunks):
                yield f"data: {json.dumps(chunks[idx])}\n\n"
                idx += 1
            if status in ('done', 'error', 'cancelled'):
                yield f"data: {json.dumps({'event': 'end', 'status': status})}\n\n"
                yield "data: [DONE]\n\n"
                return
            time.sleep(0.4)

    return Response(emit(), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})
