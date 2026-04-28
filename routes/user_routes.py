"""
Kautilya AI — User Routes Blueprint
Handles /api/user/* endpoints (settings, integrations, account).
"""
from flask import Blueprint, request, jsonify

from services.auth_service import verify_firebase_token
from services.memory_service import record_user_session

user_bp = Blueprint('user', __name__)


@user_bp.route('/api/user/settings', methods=['GET'])
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


@user_bp.route('/api/user/settings', methods=['POST'])
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


@user_bp.route('/api/user/integrations', methods=['GET'])
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


@user_bp.route('/api/user/integrations', methods=['POST'])
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


@user_bp.route('/api/user/account', methods=['GET'])
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
        "sessions": [], "last_active_device": "Unknown"
    }
    if db:
        try:
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





@user_bp.route('/api/analytics/usage', methods=['GET'])
def get_usage_analytics():
    """Return usage data for graphs and stats."""
    from extensions import db
    from firebase_admin import firestore
    token_data = verify_firebase_token()
    uid = token_data.get('uid') if token_data else None
    if not uid:
        return jsonify({"error": "Authentication required"}), 401
    if not db:
        return jsonify({"error": "Database not available"}), 503
    try:
        from datetime import datetime, timedelta
        now = datetime.now()
        seven_days_ago = now - timedelta(days=7)
        logs = db.collection('usage_logs').where(filter=firestore.FieldFilter('uid', '==', uid))\
                 .where(filter=firestore.FieldFilter('timestamp', '>=', seven_days_ago))\
                 .order_by('timestamp').stream()
        daily_usage = {}
        for log in logs:
            d = log.to_dict()
            ts = d.get('timestamp')
            if ts:
                date_str = ts.strftime("%Y-%m-%d")
                daily_usage[date_str] = daily_usage.get(date_str, 0) + 1
        return jsonify({"daily_usage": daily_usage})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
