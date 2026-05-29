"""
Kautilya AI — User Routes Blueprint
Handles /api/user/* endpoints (settings, integrations, account).
"""
from flask import Blueprint, request, jsonify

from services.auth_service import verify_firebase_token
from services.memory_service import record_user_session
from services.email_service import send_welcome_email

user_bp = Blueprint('user', __name__)


@user_bp.route('/user/welcome-check', methods=['POST'])
def welcome_check():
    """Idempotent first-login hook.

    Called by the frontend right after Google sign-in. If we've never seen this
    uid before, write users/{uid}.welcomed_at and fire the welcome email. Safe
    to call on every login — only triggers once per user.
    """
    from extensions import db
    from firebase_admin import firestore
    token_data = verify_firebase_token()
    if not token_data:
        return jsonify({"error": "Unauthorized"}), 401
    uid = token_data.get('uid')
    email = token_data.get('email', '')
    name = token_data.get('name') or ''
    if not uid or not db:
        return jsonify({"welcomed": False, "skipped": True})
    try:
        ref = db.collection('users').document(uid)
        snap = ref.get()
        existing = snap.to_dict() or {} if snap.exists else {}
        already = bool(existing.get('welcomed_at'))
        if already:
            # Still update last_seen so miss-you scheduler has fresh data
            ref.set({'last_seen_at': firestore.SERVER_TIMESTAMP}, merge=True)
            return jsonify({"welcomed": False, "already": True})

        # Fallback: if token didn't carry email, try the Firestore record
        if not email:
            email = existing.get('email', '')
        # Last resort: try Firebase Admin Auth record
        if not email:
            try:
                from firebase_admin import auth as _fa
                user_record = _fa.get_user(uid)
                email = user_record.email or ''
                if not name:
                    name = user_record.display_name or ''
            except Exception:
                pass

        ref.set({
            'uid': uid, 'email': email, 'name': name,
            'welcomed_at': firestore.SERVER_TIMESTAMP,
            'first_seen_at': firestore.SERVER_TIMESTAMP,
            'last_seen_at': firestore.SERVER_TIMESTAMP,
        }, merge=True)

        if email:
            send_welcome_email(email, name)
            print(f"[welcome-check] sent welcome to {email}")
        else:
            print(f"[welcome-check] uid={uid} — no email found, skipping send")

        return jsonify({"welcomed": True})
    except Exception as e:
        print(f"[welcome-check] failed: {e}")
        return jsonify({"welcomed": False, "error": "internal"}), 200


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


@user_bp.route('/memory/refresh-from-chats', methods=['POST'])
def refresh_memory_from_chats():
    """Memory from Chats: scan recent conversation history and extract
    personalization facts (preferences, role, projects, habits) into the
    user's memory bank. Idempotent — dedupes against existing facts."""
    from extensions import db, FIREBASE_AVAILABLE
    token_data = verify_firebase_token()
    uid = token_data.get('uid') if token_data else None
    if not uid:
        return jsonify({"error": "Unauthorized"}), 401
    if not (FIREBASE_AVAILABLE and db):
        return jsonify({"error": "Database not available"}), 503
    try:
        from services.memory_service import (
            get_user_memory, save_user_memory, extract_memories,
        )
        limit = int((request.get_json(silent=True) or {}).get('session_limit') or 20)
        limit = max(1, min(limit, 50))

        existing = list(get_user_memory(uid))
        before = len(existing)

        # Collect recent (user, assistant) pairs from the most recent N sessions.
        sessions_ref = (db.collection('users').document(uid)
                          .collection('sessions')
                          .order_by('updated_at', direction='DESCENDING')
                          .limit(limit))
        pairs = []
        for sdoc in sessions_ref.stream():
            msgs_ref = (sdoc.reference.collection('messages')
                          .order_by('timestamp').limit(40))
            buf = []
            for m in msgs_ref.stream():
                d = m.to_dict() or {}
                role = d.get('role')
                content = d.get('content') or ''
                if role in ('user', 'assistant') and content:
                    buf.append((role, content))
            # Pair up consecutive user→assistant turns
            for i in range(len(buf) - 1):
                if buf[i][0] == 'user' and buf[i + 1][0] == 'assistant':
                    pairs.append((buf[i][1], buf[i + 1][1]))

        # Cap pairs to keep extraction fast.
        pairs = pairs[-60:]
        new_count = 0
        for user_text, assistant_text in pairs:
            try:
                new_facts = extract_memories(user_text, assistant_text, existing)
                for f in new_facts:
                    if f not in existing:
                        existing.append(f)
                        new_count += 1
            except Exception as e:
                print(f"[Memory] pair extract failed: {e}")
                continue

        save_user_memory(uid, existing)
        return jsonify({
            "status": "ok",
            "scanned_sessions": limit,
            "scanned_pairs": len(pairs),
            "added": new_count,
            "total": len(existing),
            "before": before,
        })
    except Exception as e:
        print(f"[Memory] refresh failed: {e}")
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



# @user_bp.route('/analytics/usage', methods=['GET'])
# def get_usage_analytics():
#     """Return full usage analytics for the dashboard (daily, hourly, models,
#     current_usage, limits, tier, recent_activity)."""
#     from extensions import db, limit_manager
#     from config import API_RATE_LIMITS
#     from services.auth_service import get_api_usage
#     from datetime import datetime, timedelta
# 
#     token_data = verify_firebase_token()
#     uid = token_data.get('uid') if token_data else None
#     if not uid:
#         return jsonify({"error": "Authentication required"}), 401
#     if not db:
#         return jsonify({"error": "Database not available"}), 503
# 
#     try:
#         from firebase_admin import firestore
#     except Exception:
#         firestore = None
# 
#     is_pro = False
#     try:
#         is_pro = bool(limit_manager.is_pro_user(uid)) if limit_manager else False
#     except Exception:
#         is_pro = False
#     tier = "pro" if is_pro else "free"
#     limits = API_RATE_LIMITS.get(tier, API_RATE_LIMITS["free"])
# 
#     # Today's usage from api_usage/{uid}/daily/{today}
#     current_usage = {"llm_tokens": 0, "tts_chars": 0, "stt_seconds": 0}
#     try:
#         today_doc = get_api_usage(uid) or {}
#         for k in current_usage.keys():
#             v = today_doc.get(k, 0)
#             try:
#                 current_usage[k] = int(v)
#             except Exception:
#                 current_usage[k] = 0
#     except Exception:
#         pass
# 
#     # Build daily / hourly / model aggregates from usage_logs (last 7 days)
#     daily = {}
#     hourly_today = {str(h): 0 for h in range(24)}
#     models = {}
#     today_str = datetime.now().strftime("%Y-%m-%d")
#     is_index_error = False
#     error_details = None
# 
#     # Pre-seed last 7 days so the chart isn't empty
#     for i in range(6, -1, -1):
#         d = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
#         daily[d] = 0
# 
#     try:
#         seven_days_ago = datetime.now() - timedelta(days=7)
#         query = db.collection('usage_logs').where(
#             filter=firestore.FieldFilter('uid', '==', uid)
#         ).where(
#             filter=firestore.FieldFilter('timestamp', '>=', seven_days_ago)
#         ).limit(2000)
#         try:
#             logs = list(query.order_by('timestamp').stream())
#         except Exception as inner:
#             # Composite index missing — fall back to unordered query
#             msg = str(inner)
#             if 'index' in msg.lower():
#                 is_index_error = True
#                 error_details = msg
#             logs = list(query.stream())
# 
#         for log in logs:
#             d = log.to_dict() or {}
#             ts = d.get('timestamp')
#             amount = d.get('amount', 1) or 0
#             try:
#                 amount = int(amount)
#             except Exception:
#                 amount = 1
#             r_type = d.get('type', 'llm_tokens')
#             model_name = d.get('model') or 'kautilya-daily'
# 
#             day_str = None
#             hour = d.get('hour')
#             if ts and hasattr(ts, 'strftime'):
#                 day_str = ts.strftime("%Y-%m-%d")
#                 if hour is None:
#                     hour = ts.hour
#             else:
#                 day_str = d.get('day')
# 
#             if day_str:
#                 daily[day_str] = daily.get(day_str, 0) + (amount if r_type == 'llm_tokens' else 0)
# 
#             if day_str == today_str and hour is not None:
#                 try:
#                     h = str(int(hour))
#                     hourly_today[h] = hourly_today.get(h, 0) + (amount if r_type == 'llm_tokens' else 0)
#                 except Exception:
#                     pass
# 
#             if r_type == 'llm_tokens':
#                 models[model_name] = models.get(model_name, 0) + amount
#     except Exception as e:
#         msg = str(e)
#         if 'index' in msg.lower():
#             is_index_error = True
#         error_details = msg
# 
#     # Recent activity: last 20 usage events
#     recent_activity = []
#     try:
#         recent_q = db.collection('usage_logs').where(
#             filter=firestore.FieldFilter('uid', '==', uid)
#         ).order_by('timestamp', direction=firestore.Query.DESCENDING).limit(20)
#         for r in recent_q.stream():
#             rd = r.to_dict() or {}
#             ts = rd.get('timestamp')
#             recent_activity.append({
#                 "type": rd.get('type', 'llm_tokens'),
#                 "amount": rd.get('amount', 0),
#                 "model": rd.get('model') or 'kautilya-daily',
#                 "timestamp": ts.isoformat() if hasattr(ts, 'isoformat') else None,
#             })
#     except Exception:
#         pass
# 
#     response = {
#         "tier": tier,
#         "limits": limits,
#         "current_usage": current_usage,
#         "daily": daily,
#         "hourly_today": hourly_today,
#         "models": models,
#         "recent_activity": recent_activity,
#     }
# 
#     # Add extra KPI fields for the BI dashboard
#     try:
#         call_stats = get_call_volume().get_json()
#         if not isinstance(call_stats, dict) or 'error' in call_stats:
#             response["total_calls"] = 0
#             response["avg_sentiment"] = 0
#             response["success_rate"] = "0%"
#         else:
#             response["total_calls"] = call_stats.get('total_calls', 0)
#             response["avg_sentiment"] = (call_stats.get('avg_sentiment', 0) / 10.0) if call_stats.get('avg_sentiment') else 0
#             tc = call_stats.get('total_calls', 0)
#             fc = call_stats.get('failed_calls', 0)
#             response["success_rate"] = f"{round(((tc - fc) / tc * 100))}%" if tc > 0 else "0%"
#     except Exception:
#         response["total_calls"] = 0
#         response["avg_sentiment"] = 0
#         response["success_rate"] = "0%"
# 
#     if is_index_error:
#         response["index_warning"] = True
#         response["details"] = error_details
#     return jsonify(response)


@user_bp.route('/user/consent', methods=['POST'])
def record_consent():
    """Record user's age confirmation and marketing consent (DPDP Act 2023).
    Called once at first login from the age gate modal.
    Body: { age_confirmed: bool, marketing_opt_in: bool }
    """
    from extensions import db
    from firebase_admin import firestore
    token_data = verify_firebase_token()
    uid = token_data.get('uid') if token_data else None
    if not uid: return jsonify({"error": "Unauthorized"}), 401
    if not db: return jsonify({"error": "Database not available"}), 503
    data = request.get_json(silent=True) or {}
    age_confirmed = bool(data.get('age_confirmed', False))
    marketing_opt_in = bool(data.get('marketing_opt_in', False))
    if not age_confirmed:
        return jsonify({"error": "Age confirmation required"}), 400
    try:
        db.collection('users').document(uid).set({
            'age_confirmed': True,
            'age_confirmed_at': firestore.SERVER_TIMESTAMP,
            'marketing_opt_in': marketing_opt_in,
            'marketing_consent_at': firestore.SERVER_TIMESTAMP,
            'consent_version': '2026-05-29',
        }, merge=True)
        return jsonify({"status": "ok", "marketing_opt_in": marketing_opt_in})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@user_bp.route('/user/unsubscribe', methods=['POST', 'GET'])
def email_unsubscribe():
    """Unsubscribe user from marketing emails.
    Accepts token from email links (GET ?token=<uid_hash>) or auth header (POST).
    This endpoint must work WITHOUT auth header for email link clicks.
    """
    import hashlib, hmac as _hmac
    from extensions import db
    from firebase_admin import firestore

    uid = None
    # GET path: unsubscribe via email link token (no auth required)
    token_param = request.args.get('token', '') or (request.get_json(silent=True) or {}).get('token', '')
    if token_param and db:
        # token = SHA-256(uid) truncated to 32 chars — enumerate-resistant
        try:
            docs = db.collection('users').stream()
            for doc in docs:
                d = doc.to_dict() or {}
                candidate_hash = hashlib.sha256(doc.id.encode()).hexdigest()[:32]
                if _hmac.compare_digest(candidate_hash, token_param[:32]):
                    uid = doc.id
                    break
        except Exception as e:
            print(f"[unsubscribe] token lookup error: {e}")

    # POST path: authenticated (from settings page)
    if not uid:
        token_data = verify_firebase_token()
        uid = token_data.get('uid') if token_data else None

    if not uid:
        return ("<html><body style='font-family:sans-serif;text-align:center;padding:60px;'>"
                "<h2>Link expired or invalid.</h2>"
                "<p>Please log in and go to <b>Settings → My Data</b> to manage email preferences.</p>"
                "</body></html>"), 400, {'Content-Type': 'text/html'}
    try:
        db.collection('users').document(uid).set(
            {'marketing_opt_in': False, 'unsubscribed_at': firestore.SERVER_TIMESTAMP},
            merge=True
        )
        if request.method == 'GET':
            return ("<html><body style='font-family:sans-serif;text-align:center;padding:60px;"
                    "background:#0d1117;color:#e6edf3;'>"
                    "<h2 style='color:#FF6D3F;'>You have been unsubscribed.</h2>"
                    "<p>You will no longer receive marketing emails from Kautilya AI.</p>"
                    "<p style='color:#8b949e;font-size:13px;'>You will still receive important transactional emails "
                    "(billing receipts, security alerts).</p>"
                    "<a href='https://ai.revealiq.in' style='display:inline-block;margin-top:24px;"
                    "padding:10px 20px;background:#FF6D3F;color:#fff;border-radius:8px;"
                    "text-decoration:none;font-weight:600;'>Return to Kautilya AI</a>"
                    "</body></html>"), 200, {'Content-Type': 'text/html'}
        return jsonify({"status": "ok", "message": "Unsubscribed from marketing emails"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@user_bp.route('/user/data-deletion', methods=['POST'])
def request_data_deletion():
    """Request complete account and data deletion (DPDP Act 2023 Right to Erasure).
    Marks account for deletion; actual purge runs within 7 business days.
    Keeps billing records for 7 years (GST law) and security logs for 5 years (CERT-In).
    """
    from extensions import db
    from firebase_admin import firestore
    token_data = verify_firebase_token()
    uid = token_data.get('uid') if token_data else None
    if not uid: return jsonify({"error": "Unauthorized"}), 401
    if not db: return jsonify({"error": "Database not available"}), 503
    data = request.get_json(silent=True) or {}
    reason = str(data.get('reason', ''))[:500]
    try:
        db.collection('users').document(uid).set({
            'deletion_requested': True,
            'deletion_requested_at': firestore.SERVER_TIMESTAMP,
            'deletion_reason': reason,
            'deletion_status': 'pending',
        }, merge=True)
        # Log the request for compliance audit trail
        db.collection('data_deletion_requests').add({
            'uid': uid,
            'requested_at': firestore.SERVER_TIMESTAMP,
            'reason': reason,
            'status': 'pending',
        })
        # Immediately soft-delete chat history to honour the intent quickly
        try:
            sessions_ref = db.collection('users').document(uid).collection('sessions').limit(100).stream()
            for s in sessions_ref:
                msgs_ref = s.reference.collection('messages').limit(500).stream()
                batch = db.batch()
                for m in msgs_ref:
                    batch.delete(m.reference)
                batch.commit()
        except Exception as e:
            print(f"[data-deletion] chat soft-delete error: {e}")
        return jsonify({
            "status": "ok",
            "message": "Your data deletion request has been recorded. We will complete the deletion within 7 business days and email you a confirmation.",
            "reference": uid[:8],
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@user_bp.route('/user/my-data', methods=['GET'])
def get_my_data():
    """Return a summary of all personal data held for the user (DPDP Act Right to Access)."""
    from extensions import db
    token_data = verify_firebase_token()
    uid = token_data.get('uid') if token_data else None
    if not uid: return jsonify({"error": "Unauthorized"}), 401
    if not db: return jsonify({"error": "Database not available"}), 503
    try:
        user_doc = db.collection('users').document(uid).get()
        user_data = user_doc.to_dict() or {} if user_doc.exists else {}
        settings_doc = db.collection('users').document(uid).collection('settings').document('profile').get()
        settings = settings_doc.to_dict() or {} if settings_doc.exists else {}
        api_keys_count = sum(1 for _ in db.collection('api_keys').where(
            filter=__import__('firebase_admin').firestore.FieldFilter('uid', '==', uid)
        ).where(
            filter=__import__('firebase_admin').firestore.FieldFilter('is_active', '==', True)
        ).stream())
        session_count = sum(1 for _ in db.collection('users').document(uid).collection('sessions').limit(500).stream())
        return jsonify({
            "profile": {
                "name": user_data.get('name', ''),
                "email": user_data.get('email', ''),
                "joined_at": user_data.get('welcomed_at').isoformat() if user_data.get('welcomed_at') else None,
                "last_seen": user_data.get('last_seen_at').isoformat() if user_data.get('last_seen_at') else None,
            },
            "consent": {
                "age_confirmed": user_data.get('age_confirmed', False),
                "marketing_opt_in": user_data.get('marketing_opt_in', False),
                "consent_version": user_data.get('consent_version'),
            },
            "data_held": {
                "chat_sessions": session_count,
                "api_keys_active": api_keys_count,
                "preferences_stored": bool(settings),
                "voice_data_retained": False,
            },
            "deletion_requested": user_data.get('deletion_requested', False),
            "deletion_status": user_data.get('deletion_status'),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


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
