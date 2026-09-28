"""
Kautilya AI — Research Routes (resilient / background-safe).

The deep-research pipeline runs in a BACKGROUND THREAD that is independent of
the client connection — exactly like the main chat stream. So if the user
leaves the app, backgrounds the tab, or hits a network blip mid-research:

  • the research keeps running server-side to completion,
  • a placeholder assistant message is written immediately and the partial
    report is flushed to Firestore every ~0.8s,
  • the final report (+ citations) is saved even if nobody is listening.

When the user returns, the frontend re-hydrates the conversation from Firestore
and the report is there — nothing vanishes.

POST /api/research/stream   { question, session_id? }
    SSE stream with events:
      { event: "status",  message }
      { event: "query",   queries }
      { event: "sources", sources }
      { thinking } / { thinking_done }
      { event: "chunk",   chunk }
      { event: "artifact", artifactType, artifactTitle }
      { event: "done" }
"""
import json
import time
import queue
import threading

from flask import Blueprint, request, Response, jsonify

from services.auth_service import verify_firebase_token
from services.research_service import deep_research_stream
from routes.chat_routes import save_to_firestore

research_bp = Blueprint('research', __name__)

# How often the in-progress report is flushed back to Firestore so a returning
# user sees an almost-current partial (bounds the "vanished output" window).
FLUSH_INTERVAL_SEC = 0.8


@research_bp.route('/research/stream', methods=['POST'])
def api_research_stream():
    token_data = verify_firebase_token()
    uid = token_data.get('uid') if token_data else None
    if not uid:
        return jsonify({"error": "Authentication required"}), 401

    data = request.get_json(silent=True) or {}
    question = (data.get('question') or data.get('message') or '').strip()
    session_id = (data.get('session_id') or '').strip() or None
    depth = (data.get('depth') or 'standard').strip().lower()
    if depth not in ('quick', 'standard', 'exhaustive'):
        depth = 'standard'
    mode = (data.get('mode') or 'research').strip().lower()
    if mode not in ('research', 'prd'):
        mode = 'research'
    if not question:
        return jsonify({"error": "question required"}), 400

    # Persist the user's question + reserve a streaming assistant placeholder
    # up-front so the exchange survives even if the client disconnects a moment
    # later. The placeholder's id lets us flush partials into the same doc.
    research_msg_id = None
    if session_id:
        try:
            save_to_firestore(uid, session_id, "user", question)
            research_msg_id = save_to_firestore(
                uid, session_id, "assistant", "", streaming=True,
                extras={'agent_type': 'researcher'},
            )
        except Exception as e:
            print(f"[Research] pre-save failed: {e}")

    def stream():
        """SSE generator. The heavy work happens in `_run_research` on its own
        thread; this loop just forwards queued events to the client. If the
        client goes away, the thread finishes and saves regardless."""
        chunk_queue: "queue.Queue" = queue.Queue()
        holder = {'answer': '', 'sources': [], 'thinking': '', 'artifact': None}
        last_flush = [time.time()]

        def _flush(force=False):
            if not (session_id and research_msg_id):
                return
            now = time.time()
            if not force and now - last_flush[0] < FLUSH_INTERVAL_SEC:
                return
            try:
                save_to_firestore(
                    uid, session_id, "assistant", holder['answer'],
                    message_id=research_msg_id, streaming=True,
                    extras={'citations': holder['sources'], 'agent_type': 'researcher'},
                )
                last_flush[0] = now
            except Exception as e:
                print(f"[Research] partial flush failed: {e}")

        def _run_research():
            try:
                for event in deep_research_stream(question, depth=depth, mode=mode):
                    if isinstance(event, dict):
                        ev = event.get('event')
                        if ev == 'chunk' and event.get('chunk'):
                            holder['answer'] += event['chunk']
                        elif ev == 'sources' and event.get('sources'):
                            holder['sources'] = event['sources']
                        elif ev == 'artifact':
                            holder['artifact'] = {
                                'type': event.get('artifactType', 'document'),
                                'title': event.get('artifactTitle'),
                            }
                        elif 'thinking' in event and isinstance(event.get('thinking'), str):
                            holder['thinking'] += event['thinking']
                    chunk_queue.put(json.dumps(event))
                    _flush()
            except Exception as e:
                print(f"[Research] pipeline error: {e}")
                chunk_queue.put(json.dumps({'event': 'chunk', 'chunk': f'[error: {e}]'}))
            finally:
                chunk_queue.put(None)  # sentinel
                # ---- Final save — runs even if the client disconnected ----
                if session_id and holder['answer']:
                    try:
                        save_to_firestore(
                            uid, session_id, "assistant", holder['answer'],
                            message_id=research_msg_id, streaming=False,
                            extras={
                                'citations': holder['sources'],
                                'agent_type': 'researcher',
                                'artifact': holder['artifact'],
                                'thinking': holder['thinking'] or None,
                            },
                        )
                        print(f"[Research] Saved report ({len(holder['answer'])} chars) for session {session_id}")
                    except Exception as e:
                        print(f"[Research] final save failed: {e}")
                elif session_id and research_msg_id:
                    # Produced nothing — clear the placeholder so the UI stops waiting.
                    try:
                        save_to_firestore(uid, session_id, "assistant", "[no response]",
                                          message_id=research_msg_id, streaming=False)
                    except Exception:
                        pass

        t = threading.Thread(target=_run_research, daemon=True)
        t.start()

        while True:
            try:
                item = chunk_queue.get(timeout=180)
            except queue.Empty:
                print(f"[Research] queue timeout for session {session_id}")
                break
            if item is None:
                break
            yield f"data: {item}\n\n"
        yield "data: [DONE]\n\n"

    return Response(stream(), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no',
                             'Connection': 'keep-alive'})
