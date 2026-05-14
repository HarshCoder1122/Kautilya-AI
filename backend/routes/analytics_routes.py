"""
Kautilya AI — Analytics Routes
Provides usage, call volume, and trends data for the Dashboard.
"""
import time
from flask import Blueprint, jsonify, request
from services.auth_service import verify_firebase_token

analytics_bp = Blueprint('analytics', __name__)


def _date_buckets(days=14):
    """Return list of date label buckets for chart data."""
    import datetime
    today = datetime.date.today()
    return [(today - datetime.timedelta(days=i)).strftime('%b %d') for i in range(days - 1, -1, -1)]


@analytics_bp.route('/analytics/usage', methods=['GET'])
def get_usage():
    """Return overall usage statistics for the authenticated user."""
    from extensions import db
    token_data = verify_firebase_token()
    uid = token_data.get('uid') if token_data else None
    if not uid:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        usage = {
            "total_calls": 0,
            "failed_calls": 0,
            "avg_sentiment": 0.0,
            "success_rate": "0%",
            "total_tokens": 0,
            "daily_usage": [],
        }

        if db:
            # Fetch call logs from agents
            try:
                agents_docs = db.collection('agents').where('uid', '==', uid).limit(20).stream()
                total_calls = 0
                failed_calls = 0
                for agent_doc in agents_docs:
                    agent_id = agent_doc.id
                    logs = db.collection('agents').document(agent_id).collection('call_logs').limit(200).stream()
                    for log in logs:
                        log_data = log.to_dict()
                        total_calls += 1
                        if log_data.get('status') == 'failed':
                            failed_calls += 1
                usage["total_calls"] = total_calls
                usage["failed_calls"] = failed_calls
                if total_calls > 0:
                    usage["success_rate"] = f"{int(((total_calls - failed_calls) / total_calls) * 100)}%"
            except Exception as e:
                print(f"[Analytics] call log fetch error: {e}")

            # Fetch token usage
            try:
                usage_doc = db.collection('user_usage').document(uid).get()
                if usage_doc.exists:
                    udata = usage_doc.to_dict()
                    usage["total_tokens"] = udata.get('llm_tokens', 0)
            except Exception as e:
                print(f"[Analytics] token usage error: {e}")

        # Build daily usage buckets (placeholder trend)
        buckets = _date_buckets(14)
        usage["daily_usage"] = [{"date": d, "count": 0} for d in buckets]

        return jsonify(usage)
    except Exception as e:
        print(f"[Analytics] Usage error: {e}")
        return jsonify({
            "total_calls": 0, "failed_calls": 0, "avg_sentiment": 0.0,
            "success_rate": "0%", "total_tokens": 0, "daily_usage": []
        })


@analytics_bp.route('/analytics/call-volume', methods=['GET'])
def get_call_volume():
    """Return call volume bucketed by day for charts."""
    from extensions import db
    token_data = verify_firebase_token()
    uid = token_data.get('uid') if token_data else None
    if not uid:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        buckets_labels = _date_buckets(14)
        buckets = [{"label": b, "count": 0} for b in buckets_labels]
        total_calls = 0
        failed_calls = 0
        avg_sentiment = 0.0

        if db:
            try:
                agents_docs = db.collection('agents').where('uid', '==', uid).limit(20).stream()
                sentiment_total = 0.0
                sentiment_count = 0
                for agent_doc in agents_docs:
                    logs = db.collection('agents').document(agent_doc.id).collection('call_logs').limit(200).stream()
                    for log in logs:
                        log_data = log.to_dict()
                        total_calls += 1
                        if log_data.get('status') == 'failed':
                            failed_calls += 1
                        s = log_data.get('sentiment_score')
                        if isinstance(s, (int, float)):
                            sentiment_total += s
                            sentiment_count += 1
                if sentiment_count > 0:
                    avg_sentiment = round(sentiment_total / sentiment_count, 2)
            except Exception as e:
                print(f"[Analytics] call volume error: {e}")

        return jsonify({
            "buckets": buckets,
            "total_calls": total_calls,
            "failed_calls": failed_calls,
            "avg_sentiment": avg_sentiment,
        })
    except Exception as e:
        print(f"[Analytics] Call volume error: {e}")
        return jsonify({"buckets": [], "total_calls": 0, "failed_calls": 0, "avg_sentiment": 0.0})


@analytics_bp.route('/analytics/trends', methods=['GET'])
def get_trends():
    """Return trend data for charts (messages sent, sessions, etc.)."""
    from extensions import db
    token_data = verify_firebase_token()
    uid = token_data.get('uid') if token_data else None
    if not uid:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        buckets_labels = _date_buckets(14)
        trends = {
            "messages_per_day": [{"date": b, "count": 0} for b in buckets_labels],
            "sessions_per_day": [{"date": b, "count": 0} for b in buckets_labels],
            "models_used": {},
        }

        if db:
            try:
                from firebase_admin import firestore
                conv_docs = db.collection('users').document(uid).collection('conversations') \
                    .order_by('last_updated', direction=firestore.Query.DESCENDING).limit(100).stream()
                for conv in conv_docs:
                    pass  # Could build per-day counts here from timestamps
            except Exception as e:
                print(f"[Analytics] trends fetch error: {e}")

        return jsonify(trends)
    except Exception as e:
        print(f"[Analytics] Trends error: {e}")
        return jsonify({"messages_per_day": [], "sessions_per_day": [], "models_used": {}})
