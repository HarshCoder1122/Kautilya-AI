"""
Kautilya AI — Research Routes.

POST /api/research/stream   { question }
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

research_bp = Blueprint('research', __name__)


@research_bp.route('/research/stream', methods=['POST'])
def api_research_stream():
    token_data = verify_firebase_token()
    uid = token_data.get('uid') if token_data else None
    if not uid:
        return jsonify({"error": "Authentication required"}), 401

    data = request.get_json(silent=True) or {}
    question = (data.get('question') or data.get('message') or '').strip()
    if not question:
        return jsonify({"error": "question required"}), 400

    def sse():
        try:
            for event in deep_research_stream(question):
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'event': 'chunk', 'chunk': f'[error: {e}]'})}\n\n"
        yield "data: [DONE]\n\n"

    return Response(sse(), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})
