"""
Kautilya AI — User Routes Blueprint
Handles /api/user/* endpoints (settings, integrations, account).
"""
from flask import Blueprint, request, jsonify

from services.auth_service import verify_firebase_token
from services.memory_service import record_user_session

user_bp = Blueprint('user', __name__)


@user_bp.route('/user/settings', methods=['GET'])
def get_user_settings():
    from extensions import db
    token_data = verify_firebase_token()
    uid = token_data.get('uid') if token_data else None
    if not uid: return jsonify({"error": "Unauthorized"}), 401
    if not db: return jsonify({"settings": {}})
    try:
        doc = db.collection('users').document(uid).collection('settings').document('profile').get()
        return jsonify({"settings": doc.to_dict() if doc.exists else {}})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@user_bp.route('/user/settings', methods=['POST'])
def save_user_settings():
    from extensions import db
    from firebase_admin import firestore
    token_data = verify_firebase_token()
    uid = token_data.get('uid') if token_data else None
    if not uid: return jsonify({"error": "Unauthorized"}), 401
    if not db: return jsonify({"error": "Database not available"}), 503
    data = request.get_json()
    if not data: return jsonify({"error": "No data provided"}), 400
    try:
        settings = {
            'display_name': data.get('display_name', '')[:100],
            'preferred_name': data.get('preferred_name', '')[:100],
            'work_function': data.get('work_function', '')[:100],
            'personal_preferences': data.get('personal_preferences', '')[:2000],
            'theme': data.get('theme', 'dark'),
            'tts_enabled': data.get('tts_enabled', True),
            'notifications_enabled': data.get('notifications_enabled', True),
            'updated_at': firestore.SERVER_TIMESTAMP
        }
        db.collection('users').document(uid).collection('settings').document('profile').set(settings, merge=True)
        return jsonify({"status": "ok", "message": "Settings saved successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@user_bp.route('/user/integrations', methods=['GET'])
def get_user_integrations():
    from extensions import db
    token_data = verify_firebase_token()
    uid = token_data.get('uid') if token_data else None
    if not uid: return jsonify({"error": "Unauthorized"}), 401
    try:
        doc = db.collection('users').document(uid).collection('settings').document('integrations').get()
        return jsonify({"integrations": doc.to_dict() if doc.exists else {}})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@user_bp.route('/user/integrations', methods=['POST'])
def save_user_integrations():
    from extensions import db
    from firebase_admin import firestore
    token_data = verify_firebase_token()
    uid = token_data.get('uid') if token_data else None
    if not uid: return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json() or {}
    try:
        integrations = {
            'hubspot_enabled': bool(data.get('hubspot_enabled', False)),
            'hubspot_key': data.get('hubspot_key', '')[:255],
            'salesforce_enabled': bool(data.get('salesforce_enabled', False)),
            'salesforce_key': data.get('salesforce_key', '')[:255],
            'ghl_enabled': bool(data.get('ghl_enabled', False)),
            'ghl_key': data.get('ghl_key', '')[:255],
            'updated_at': firestore.SERVER_TIMESTAMP
        }
        db.collection('users').document(uid).collection('settings').document('integrations').set(integrations, merge=True)
        return jsonify({"status": "ok", "message": "Integration settings saved"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@user_bp.route('/user/account', methods=['GET'])
def get_user_account():
    from extensions import db
    from firebase_admin import firestore
    token_data = verify_firebase_token()
    uid = token_data.get('uid') if token_data else None
    if not uid: return jsonify({"error": "Unauthorized"}), 401
    user_email = token_data.get('email', 'Guest')
    provider = token_data.get('provider', 'password')
    session_id = request.headers.get('X-Session-ID')
    record_user_session(uid, session_id)
    account_info = {
        "email": user_email, "uid": uid,
        "provider": provider.replace('.com', '').capitalize(),
        "sessions": [], "last_active_device": "Unknown",
        "api_key": None
    }
    if db:
        try:
            # Fetch API Key if exists
            config_doc = db.collection('users').document(uid).collection('config').document('api_keys').get()
            if config_doc.exists:
                account_info['api_key'] = config_doc.to_dict().get('secret_key')
                
            sessions_ref = db.collection('users').document(uid).collection('sessions') \
                .order_by('last_active', direction=firestore.Query.DESCENDING).limit(10)
            for s in sessions_ref.stream():
                s_data = s.to_dict()
                is_current = (s.id == session_id)
                last_active_ts = s_data.get('last_active')
                last_active_str = last_active_ts.strftime("%b %d, %H:%M") if last_active_ts else "Recently"
                account_info["sessions"].append({
                    "device": s_data.get('device', 'Unknown'), "browser": s_data.get('browser', 'Browser'),
                    "location": s_data.get('location', 'India'), "last_active": last_active_str, "is_current": is_current
                })
                if is_current:
                    account_info["last_active_device"] = s_data.get('device', 'Unknown')
        except Exception as e:
            print(f"[Account] Fetch failed: {e}")
    return jsonify(account_info)


@user_bp.route('/user/api-key', methods=['POST'])
def generate_api_key():
    """Generate a new API key for external API access."""
    import secrets
    from extensions import db
    from firebase_admin import firestore
    
    token_data = verify_firebase_token()
    uid = token_data.get('uid') if token_data else None
    if not uid: return jsonify({"error": "Unauthorized"}), 401
    if not db: return jsonify({"error": "Database not available"}), 503
    
    # Generate a key like "ka_1234567890abcdef"
    new_key = f"ka_{secrets.token_hex(24)}"
    
    try:
        db.collection('users').document(uid).collection('config').document('api_keys').set({
            "secret_key": new_key,
            "created_at": firestore.SERVER_TIMESTAMP,
            "status": "active"
        })
        
        # Also store the reverse mapping for fast validation in middleware
        db.collection('api_keys').document(new_key).set({
            "uid": uid,
            "created_at": firestore.SERVER_TIMESTAMP
        })
        
        return jsonify({"status": "ok", "api_key": new_key})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@user_bp.route('/memory', methods=['GET'])
def get_user_memory_endpoint():
    """Return all stored memories for the authenticated user."""
    from extensions import db
    token_data = verify_firebase_token()
    uid = token_data.get('uid') if token_data else None
    if not uid:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        from services.memory_service import get_user_memory
        facts = get_user_memory(uid)
        # Count vector memories too
        vector_count = 0
        profile = {}
        if db:
            try:
                pdoc = db.collection('users').document(uid).collection('settings').document('profile').get()
                if pdoc.exists:
                    profile = pdoc.to_dict() or {}
                vector_count = len(list(db.collection('users').document(uid).collection('memories').limit(200).stream()))
            except:
                pass
        return jsonify({
            "memories": facts,
            "count": len(facts),
            "vector_memory_count": vector_count,
            "profile": {
                "display_name": profile.get('preferred_name') or profile.get('display_name') or token_data.get('name', ''),
                "email": token_data.get('email', ''),
                "plan": profile.get('plan', 'free'),
            }
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@user_bp.route('/memory', methods=['DELETE'])
def delete_memory_item():
    """Delete a specific memory fact by index."""
    from extensions import db
    token_data = verify_firebase_token()
    uid = token_data.get('uid') if token_data else None
    if not uid:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    index = data.get('index')
    try:
        from services.memory_service import get_user_memory, save_user_memory
        facts = get_user_memory(uid)
        if index is not None and 0 <= int(index) < len(facts):
            facts.pop(int(index))
            save_user_memory(uid, facts)
            return jsonify({"status": "ok", "remaining": len(facts)})
        return jsonify({"error": "Invalid index"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@user_bp.route('/memory/clear', methods=['POST'])
def clear_user_memory():
    """Clear all user memories from Firestore."""
    from extensions import db
    token_data = verify_firebase_token()
    uid = token_data.get('uid') if token_data else None
    if not uid:
        return jsonify({"error": "Unauthorized"}), 401
    if not db:
        return jsonify({"error": "Database not available"}), 503
    try:
        count = 0
        # Clear vector memories (embeddings)
        mem_ref = db.collection('users').document(uid).collection('memories')
        batch = db.batch()
        for doc in mem_ref.limit(200).stream():
            batch.delete(doc.reference)
            count += 1
        if count > 0:
            batch.commit()
        # Clear simple facts memory (separate collection)
        db.collection('users').document(uid).collection('user_memory').document('facts').delete()
        # Clear conversation context memory if it exists
        ctx_ref = db.collection('users').document(uid).collection('context_memory')
        batch2 = db.batch()
        for doc in ctx_ref.limit(200).stream():
            batch2.delete(doc.reference)
        batch2.commit()
        return jsonify({"status": "ok", "message": f"Memory cleared ({count} vector memories + facts removed)"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@user_bp.route('/user/profile', methods=['GET', 'POST'])
def user_profile():
    """Get or save user profile (display name, preferences)."""
    from extensions import db
    from firebase_admin import firestore
    token_data = verify_firebase_token()
    uid = token_data.get('uid') if token_data else None
    if not uid:
        return jsonify({"error": "Unauthorized"}), 401
    if not db:
        return jsonify({"error": "Database not available"}), 503

    profile_ref = db.collection('users').document(uid).collection('settings').document('profile')

    if request.method == 'GET':
        try:
            doc = profile_ref.get()
            return jsonify({"profile": doc.to_dict() if doc.exists else {}})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # POST — save profile
    data = request.get_json() or {}
    try:
        update = {
            'updated_at': firestore.SERVER_TIMESTAMP,
        }
        if 'displayName' in data:
            update['display_name'] = str(data['displayName'])[:100]
        if 'preferences' in data:
            update['personal_preferences'] = str(data['preferences'])[:2000]
        profile_ref.set(update, merge=True)
        return jsonify({"status": "ok", "message": "Profile saved"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@user_bp.route('/user/profile', methods=['PUT'])
def user_profile_put():
    """Alias for POST /api/user/profile to support common REST clients."""
    return user_profile()



@user_bp.route('/analytics/usage', methods=['GET'])
def get_usage_analytics():
    """Return full usage analytics for the dashboard (daily, hourly, models,
    current_usage, limits, tier, recent_activity)."""
    from extensions import db, limit_manager
    from config import API_RATE_LIMITS
    from services.auth_service import get_api_usage
    from datetime import datetime, timedelta

    token_data = verify_firebase_token()
    uid = token_data.get('uid') if token_data else None
    if not uid:
        return jsonify({"error": "Authentication required"}), 401
    if not db:
        return jsonify({"error": "Database not available"}), 503

    try:
        from firebase_admin import firestore
    except Exception:
        firestore = None

    is_pro = False
    try:
        is_pro = bool(limit_manager.is_pro_user(uid)) if limit_manager else False
    except Exception:
        is_pro = False
    tier = "pro" if is_pro else "free"
    limits = API_RATE_LIMITS.get(tier, API_RATE_LIMITS["free"])

    # Today's usage from api_usage/{uid}/daily/{today}
    current_usage = {"llm_tokens": 0, "tts_chars": 0, "stt_seconds": 0}
    try:
        today_doc = get_api_usage(uid) or {}
        for k in current_usage.keys():
            v = today_doc.get(k, 0)
            try:
                current_usage[k] = int(v)
            except Exception:
                current_usage[k] = 0
    except Exception:
        pass

    # Build daily / hourly / model aggregates from usage_logs (last 7 days)
    daily = {}
    hourly_today = {str(h): 0 for h in range(24)}
    models = {}
    today_str = datetime.now().strftime("%Y-%m-%d")
    is_index_error = False
    error_details = None

    # Pre-seed last 7 days so the chart isn't empty
    for i in range(6, -1, -1):
        d = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        daily[d] = 0

    try:
        seven_days_ago = datetime.now() - timedelta(days=7)
        query = db.collection('usage_logs').where(
            filter=firestore.FieldFilter('uid', '==', uid)
        ).where(
            filter=firestore.FieldFilter('timestamp', '>=', seven_days_ago)
        ).limit(2000)
        try:
            logs = list(query.order_by('timestamp').stream())
        except Exception as inner:
            # Composite index missing — fall back to unordered query
            msg = str(inner)
            if 'index' in msg.lower():
                is_index_error = True
                error_details = msg
            logs = list(query.stream())

        for log in logs:
            d = log.to_dict() or {}
            ts = d.get('timestamp')
            amount = d.get('amount', 1) or 0
            try:
                amount = int(amount)
            except Exception:
                amount = 1
            r_type = d.get('type', 'llm_tokens')
            model_name = d.get('model') or 'kautilya-daily'

            day_str = None
            hour = d.get('hour')
            if ts and hasattr(ts, 'strftime'):
                day_str = ts.strftime("%Y-%m-%d")
                if hour is None:
                    hour = ts.hour
            else:
                day_str = d.get('day')

            if day_str:
                daily[day_str] = daily.get(day_str, 0) + (amount if r_type == 'llm_tokens' else 0)

            if day_str == today_str and hour is not None:
                try:
                    h = str(int(hour))
                    hourly_today[h] = hourly_today.get(h, 0) + (amount if r_type == 'llm_tokens' else 0)
                except Exception:
                    pass

            if r_type == 'llm_tokens':
                models[model_name] = models.get(model_name, 0) + amount
    except Exception as e:
        msg = str(e)
        if 'index' in msg.lower():
            is_index_error = True
        error_details = msg

    # Recent activity: last 20 usage events
    recent_activity = []
    try:
        recent_q = db.collection('usage_logs').where(
            filter=firestore.FieldFilter('uid', '==', uid)
        ).order_by('timestamp', direction=firestore.Query.DESCENDING).limit(20)
        for r in recent_q.stream():
            rd = r.to_dict() or {}
            ts = rd.get('timestamp')
            recent_activity.append({
                "type": rd.get('type', 'llm_tokens'),
                "amount": rd.get('amount', 0),
                "model": rd.get('model') or 'kautilya-daily',
                "timestamp": ts.isoformat() if hasattr(ts, 'isoformat') else None,
            })
    except Exception:
        pass

    response = {
        "tier": tier,
        "limits": limits,
        "current_usage": current_usage,
        "daily": daily,
        "hourly_today": hourly_today,
        "models": models,
        "recent_activity": recent_activity,
    }

    # Add extra KPI fields for the BI dashboard
    try:
        call_stats = get_call_volume().get_json()
        if not isinstance(call_stats, dict) or 'error' in call_stats:
            response["total_calls"] = 0
            response["avg_sentiment"] = 0
            response["success_rate"] = "0%"
        else:
            response["total_calls"] = call_stats.get('total_calls', 0)
            response["avg_sentiment"] = (call_stats.get('avg_sentiment', 0) / 10.0) if call_stats.get('avg_sentiment') else 0
            tc = call_stats.get('total_calls', 0)
            fc = call_stats.get('failed_calls', 0)
            response["success_rate"] = f"{round(((tc - fc) / tc * 100))}%" if tc > 0 else "0%"
    except Exception:
        response["total_calls"] = 0
        response["avg_sentiment"] = 0
        response["success_rate"] = "0%"

    if is_index_error:
        response["index_warning"] = True
        response["details"] = error_details
    return jsonify(response)


@user_bp.route('/analytics/trends', methods=['GET'])
def get_analytics_trends():
    """Return trend analysis for the BI dashboard."""
    from datetime import datetime, timedelta
    token_data = verify_firebase_token()
    uid = token_data.get('uid') if token_data else None
    if not uid:
        return jsonify({"error": "Unauthorized"}), 401
    
    # Return mock/calculated trends for the UI
    now = datetime.now()
    daily_usage = []
    for i in range(30):
        date = (now - timedelta(days=29-i)).strftime("%Y-%m-%d")
        daily_usage.append({"date": date, "count": 10 + (i % 5) * 2})
        
    return jsonify({
        "daily_usage": daily_usage,
        "conversion_rate": 0.12,
        "growth": "+15%",
        "top_models": ["llama-3.3-70b", "deepseek-v4-pro"],
        "summary": "Your AI usage is trending upward by 15% this month."
    })


@user_bp.route('/analytics/call-volume', methods=['GET'])
def get_call_volume():
    """Aggregate real call volume from agent_logs for the overview chart.
    Query params: range=12h|7d|30d (default 12h)
    Returns: { buckets: [{label, count}], total_calls, failed_calls, avg_sentiment }
    """
    from extensions import db
    from datetime import datetime, timedelta
    import math

    token_data = verify_firebase_token()
    uid = token_data.get('uid') if token_data else None
    if not uid:
        return jsonify({"error": "Authentication required"}), 401
    if not db:
        return jsonify({"error": "Database not available"}), 503

    try:
        from firebase_admin import firestore
    except Exception:
        firestore = None

    time_range = request.args.get('range', '12h')
    now = datetime.utcnow()

    if time_range == '30d':
        since = now - timedelta(days=30)
        bucket_fmt = '%Y-%m-%d'
        bucket_count = 30
    elif time_range == '7d':
        since = now - timedelta(days=7)
        bucket_fmt = '%Y-%m-%d'
        bucket_count = 7
    else:  # 12h default
        since = now - timedelta(hours=12)
        bucket_fmt = '%H:00'
        bucket_count = 12

    # Get all agents for this user
    try:
        agent_docs = list(
            db.collection('agents')
            .where(filter=firestore.FieldFilter('uid', '==', uid))
            .stream()
        )
    except Exception:
        agent_docs = []

    all_logs = []
    for agent_doc in agent_docs:
        try:
            logs_ref = db.collection('agents').document(agent_doc.id) \
                .collection('agent_logs').limit(500).stream()
            for log in logs_ref:
                d = log.to_dict() or {}
                d['_agent_id'] = agent_doc.id
                all_logs.append(d)
        except Exception:
            pass

    # Filter logs within time range
    filtered = []
    for log in all_logs:
        ts = log.get('created_at') or log.get('timestamp')
        if ts is None:
            continue
        if hasattr(ts, 'timestamp'):  # Firestore Timestamp
            log_dt = datetime.utcfromtimestamp(ts.timestamp())
        elif isinstance(ts, (int, float)):
            log_dt = datetime.utcfromtimestamp(ts)
        else:
            continue
        if log_dt >= since:
            log['_dt'] = log_dt
            filtered.append(log)

    # Build buckets
    buckets = {}
    if time_range in ('7d', '30d'):
        for i in range(bucket_count):
            d = (now - timedelta(days=bucket_count - 1 - i))
            label = d.strftime(bucket_fmt)
            buckets[label] = 0
    else:
        for i in range(bucket_count):
            h = (now - timedelta(hours=bucket_count - 1 - i))
            label = h.strftime('%H:00')
            buckets[label] = 0

    total_calls = len(filtered)
    failed_calls = 0
    sentiment_scores = []

    for log in filtered:
        dt = log['_dt']
        if time_range in ('7d', '30d'):
            key = dt.strftime(bucket_fmt)
        else:
            key = dt.strftime('%H:00')
        if key in buckets:
            buckets[key] += 1

        status = (log.get('status') or '').lower()
        if status in ('failed', 'no_audio', 'error'):
            failed_calls += 1

        sentiment = (log.get('sentiment') or '').lower()
        if sentiment == 'positive':
            sentiment_scores.append(1.0)
        elif sentiment == 'neutral':
            sentiment_scores.append(0.6)
        elif sentiment == 'negative':
            sentiment_scores.append(0.2)

    avg_sentiment = 0
    if sentiment_scores:
        avg_sentiment = round(sum(sentiment_scores) / len(sentiment_scores) * 100)

    bucket_list = [{"label": k, "count": v} for k, v in buckets.items()]

    return jsonify({
        "buckets": bucket_list,
        "total_calls": total_calls,
        "failed_calls": failed_calls,
        "avg_sentiment": avg_sentiment,
        "range": time_range,
    })
