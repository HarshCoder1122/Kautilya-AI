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
        total_tokens = 0
        tts_usage = 0
        stt_usage = 0

        import datetime
        today_str = datetime.date.today().strftime('%Y-%m-%d')
        # Pre-seed last 14 days of date labels
        today = datetime.date.today()
        date_list = [(today - datetime.timedelta(days=i)).strftime('%Y-%m-%d') for i in range(14)]
        
        # We will count call volumes per day in the last 14 days
        calls_per_day = {d: 0 for d in date_list}

        total_calls = 0
        failed_calls = 0
        daily_calls = 0
        avg_sentiment = 0.0
        success_rate = "0%"

        if db:
            # 1. Fetch token and media usage from api_usage
            try:
                daily_docs = db.collection('api_usage').document(uid).collection('daily').stream()
                for doc in daily_docs:
                    data = doc.to_dict() or {}
                    
                    # LLM Tokens
                    try:
                        val = data.get('llm_tokens')
                        if val is not None:
                            total_tokens += int(float(val))
                    except (ValueError, TypeError) as ex:
                        print(f"[Analytics] Error parsing llm_tokens for doc {doc.id}: {ex}")
                        
                    # TTS Chars
                    try:
                        val = data.get('tts_chars')
                        if val is not None:
                            tts_usage += int(float(val))
                    except (ValueError, TypeError) as ex:
                        print(f"[Analytics] Error parsing tts_chars for doc {doc.id}: {ex}")
                        
                    # STT Seconds
                    try:
                        val = data.get('stt_seconds')
                        if val is not None:
                            stt_usage += int(float(val))
                    except (ValueError, TypeError) as ex:
                        print(f"[Analytics] Error parsing stt_seconds for doc {doc.id}: {ex}")
            except Exception as e:
                import traceback
                print(f"[Analytics] api_usage aggregation error: {e}")
                traceback.print_exc()

            # 2. Fetch call logs from agent_logs to calculate call statistics
            sentiment_scores = []

            try:
                from firebase_admin import firestore
                agents_docs = db.collection('agents').where(filter=firestore.FieldFilter('uid', '==', uid)).stream()
                for agent_doc in agents_docs:
                    agent_id = agent_doc.id
                    logs = db.collection('agents').document(agent_id).collection('agent_logs').limit(500).stream()
                    for log in logs:
                        log_data = log.to_dict() or {}
                        total_calls += 1

                        status = (log_data.get('status') or '').lower()
                        if status in ('failed', 'no_audio', 'error'):
                            failed_calls += 1

                        # Group logs by date for trend
                        ts = log_data.get('created_at') or log_data.get('timestamp')
                        if ts:
                            log_day = None
                            if hasattr(ts, 'to_datetime'):
                                try:
                                    ts = ts.to_datetime()
                                except Exception:
                                    pass
                            if hasattr(ts, 'strftime'):
                                log_day = ts.strftime("%Y-%m-%d")
                            elif hasattr(ts, 'timestamp'):
                                try:
                                    log_day = datetime.datetime.fromtimestamp(ts.timestamp()).strftime("%Y-%m-%d")
                                except Exception:
                                    pass
                            elif isinstance(ts, (int, float)):
                                log_day = datetime.date.fromtimestamp(ts).strftime("%Y-%m-%d")
                            
                            if log_day:
                                if log_day == today_str:
                                    daily_calls += 1
                                if log_day in calls_per_day:
                                    calls_per_day[log_day] += 1

                        sentiment = (log_data.get('sentiment') or '').lower()
                        if sentiment == 'positive':
                            sentiment_scores.append(1.0)
                        elif sentiment == 'neutral':
                            sentiment_scores.append(0.6)
                        elif sentiment == 'negative':
                            sentiment_scores.append(0.2)
            except Exception as e:
                print(f"[Analytics] call log fetch error: {e}")

            if total_calls > 0:
                success_rate = f"{int(((total_calls - failed_calls) / total_calls) * 100)}%"

            if sentiment_scores:
                avg_sentiment = round(sum(sentiment_scores) / len(sentiment_scores) * 10, 1)

        # Build chronological trend data for the area chart
        daily_usage = [{"date": d, "count": calls_per_day[d]} for d in reversed(date_list)]

        return jsonify({
            "total_calls": total_calls,
            "failed_calls": failed_calls,
            "daily_calls": daily_calls,
            "success_rate": success_rate,
            "avg_sentiment": avg_sentiment,
            "total_tokens": total_tokens,
            "tts_usage": tts_usage,
            "stt_usage": stt_usage,
            "daily_usage": daily_usage,
        })
    except Exception as e:
        print(f"[Analytics] Usage endpoint error: {e}")
        return jsonify({
            "total_calls": 0, "failed_calls": 0, "daily_calls": 0,
            "success_rate": "0%", "avg_sentiment": 0.0, "total_tokens": 0,
            "tts_usage": 0, "stt_usage": 0, "daily_usage": []
        })

