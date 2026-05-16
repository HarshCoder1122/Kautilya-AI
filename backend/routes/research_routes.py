"""
Kautilya AI — Research Routes.

POST /api/research/stream   { question, session_id? }
    SSE stream with events:
      { event: "query",   queries: [...] }
      { event: "sources", sources: [...] }
      { event: "chunk",   chunk: "…" }
      { event: "done" }
"""
import json
from flask import Blueprint, request, Response, jsonify

from services.auth_service import verify_firebase_token
from services.research_service import deep_research_stream
from routes.chat_routes import save_to_firestore

research_bp = Blueprint('research', __name__)


@research_bp.route('/research/stream', methods=['POST'])
def api_research_stream():
    token_data = verify_firebase_token()
    uid = token_data.get('uid') if token_data else None
    if not uid:
        return jsonify({"error": "Authentication required"}), 401

    data = request.get_json(silent=True) or {}
    question = (data.get('question') or data.get('message') or '').strip()
    session_id = (data.get('session_id') or '').strip() or None
    if not question:
        return jsonify({"error": "question required"}), 400

    # Save the user's question immediately so it's persisted even if they
    # close the tab mid-stream.
    if session_id:
        try:
            save_to_firestore(uid, session_id, "user", question)
        except Exception as e:
            print(f"[Research] User-save failed: {e}")

    def sse():
        full_answer = ""
        sources_collected = []
        try:
            for event in deep_research_stream(question):
                # Accumulate the answer so we can persist it on completion.
                if isinstance(event, dict):
                    if event.get('event') == 'chunk' and event.get('chunk'):
                        full_answer += event['chunk']
                    elif event.get('event') == 'sources' and event.get('sources'):
                        sources_collected = event['sources']
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'event': 'chunk', 'chunk': f'[error: {e}]'})}\n\n"
        yield "data: [DONE]\n\n"
        # Persist the final assistant answer (best-effort, never raises).
        if session_id and full_answer:
            try:
                payload = full_answer
                if sources_collected:
                    payload = full_answer + "\n\n__sources__: " + json.dumps(sources_collected)
                save_to_firestore(uid, session_id, "assistant", payload)
                print(f"[Research] Saved response ({len(full_answer)} chars) for session {session_id}")
            except Exception as e:
                print(f"[Research] Save failed: {e}")

    return Response(sse(), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})
