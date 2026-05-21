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
        chat_count = 0
        image_count = 0
        api_count = 0

        import datetime
        today_str = datetime.date.today().strftime('%Y-%m-%d')
        today = datetime.date.today()
        date_list = [(today - datetime.timedelta(days=i)).strftime('%Y-%m-%d') for i in range(14)]

        # Daily token trend so the chart on Usage page reflects real consumption
        tokens_per_day = {d: 0 for d in date_list}
        # Call volumes (agent voice calls) per day in the last 14 days
        calls_per_day = {d: 0 for d in date_list}

        total_calls = 0
        failed_calls = 0
        daily_calls = 0
        avg_sentiment = 0.0
        success_rate = "0%"
        api_usage_doc_count = 0
        agg_error = None

        if db:
            # 1. Primary source: enumerate api_usage/{uid}/daily/{date} docs.
            try:
                daily_docs = list(
                    db.collection('api_usage').document(uid).collection('daily').stream()
                )
                api_usage_doc_count = len(daily_docs)
                for doc in daily_docs:
                    data = doc.to_dict() or {}
                    doc_day = doc.id  # YYYY-MM-DD
                    for key, bucket_name in (
                        ('llm_tokens', 'tokens'),
                        ('tts_chars', 'tts'),
                        ('stt_seconds', 'stt'),
                        ('chat_count', 'chat'),
                        ('image_count', 'image'),
                        ('api_count', 'api'),
                    ):
                        try:
                            val = data.get(key)
                            if val is None:
                                continue
                            n = int(float(val))
                        except (ValueError, TypeError):
                            continue
                        if bucket_name == 'tokens':
                            total_tokens += n
                            if doc_day in tokens_per_day:
                                tokens_per_day[doc_day] += n
                        elif bucket_name == 'tts':
                            tts_usage += n
                        elif bucket_name == 'stt':
                            stt_usage += n
                        elif bucket_name == 'chat':
                            chat_count += n
                        elif bucket_name == 'image':
                            image_count += n
                        elif bucket_name == 'api':
                            api_count += n
            except Exception as e:
                import traceback
                agg_error = str(e)
                print(f"[Analytics] api_usage aggregation error: {e}")
                traceback.print_exc()

            # 2. Fallback / cross-check: if primary aggregation produced nothing
            #    (e.g. parent doc isn't materialised), aggregate from the flat
            #    usage_logs collection which record_usage writes one row at a time.
            if total_tokens == 0 and tts_usage == 0 and stt_usage == 0:
                try:
                    from firebase_admin import firestore as _fs
                    logs = (db.collection('usage_logs')
                              .where(filter=_fs.FieldFilter('uid', '==', uid))
                              .stream())
                    for log in logs:
                        d = log.to_dict() or {}
                        t = d.get('type')
                        try:
                            amount = int(float(d.get('amount') or 0))
                        except (ValueError, TypeError):
                            amount = 0
                        if amount <= 0 or not t:
                            continue
                        if t == 'llm_tokens':
                            total_tokens += amount
                            day = d.get('day')
                            if day in tokens_per_day:
                                tokens_per_day[day] += amount
                        elif t == 'tts_chars':
                            tts_usage += amount
                        elif t == 'stt_seconds':
                            stt_usage += amount
                    print(f"[Analytics] usage_logs fallback recovered tokens={total_tokens} tts={tts_usage} stt={stt_usage}")
                except Exception as e:
                    print(f"[Analytics] usage_logs fallback failed: {e}")

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

        # Build chronological trend data for the area chart. Order ascending
        # (oldest → today) so recharts renders left-to-right correctly.
        daily_usage = [
            {"date": d, "count": calls_per_day[d], "tokens": tokens_per_day[d]}
            for d in sorted(date_list)
        ]

        # Today's developer-API count is the cleanest "daily calls" signal for
        # users who only use the chat/dev API and have no voice agent logs.
        if daily_calls == 0:
            try:
                today_doc = (db.collection('api_usage').document(uid)
                               .collection('daily').document(today_str).get()) if db else None
                if today_doc and today_doc.exists:
                    td = today_doc.to_dict() or {}
                    daily_calls = int(td.get('api_count', 0) or 0) + int(td.get('chat_count', 0) or 0)
            except Exception as e:
                print(f"[Analytics] today doc lookup failed: {e}")

        return jsonify({
            "total_calls": total_calls,
            "failed_calls": failed_calls,
            "daily_calls": daily_calls,
            "success_rate": success_rate,
            "avg_sentiment": avg_sentiment,
            "total_tokens": total_tokens,
            "tts_usage": tts_usage,
            "stt_usage": stt_usage,
            "chat_count": chat_count,
            "image_count": image_count,
            "api_count": api_count,
            "daily_usage": daily_usage,
            "_debug": {
                "uid": uid,
                "api_usage_docs": api_usage_doc_count,
                "agg_error": agg_error,
            },
        })
    except Exception as e:
        print(f"[Analytics] Usage endpoint error: {e}")
        return jsonify({
            "total_calls": 0, "failed_calls": 0, "daily_calls": 0,
            "success_rate": "0%", "avg_sentiment": 0.0, "total_tokens": 0,
            "tts_usage": 0, "stt_usage": 0, "daily_usage": []
        })

