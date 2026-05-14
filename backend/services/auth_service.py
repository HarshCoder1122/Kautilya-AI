"""
Kautilya AI — Authentication Service
Firebase token verification, API key management, rate limiting.
SECURITY FIX: check_api_rate_limit now fails CLOSED.
"""
import time
import hashlib
import secrets
from flask import request
from config import API_KEY_PREFIX, API_RATE_LIMITS, KAUTILYA_API_KEY


def verify_firebase_token():
    """Verify Firebase ID token OR master API key.
    Supports standard Authorization header OR X-Firebase-Token (for private HF Spaces).
    """
    auth_header = request.headers.get('Authorization', '')
    fb_token_header = request.headers.get('X-Firebase-Token', '')
    
    token = None
    
    # 1. ALWAYS Prioritize X-Firebase-Token if it exists
    if fb_token_header:
        if fb_token_header.startswith('Bearer '):
            token = fb_token_header.split('Bearer ', 1)[1].strip()
        else:
            token = fb_token_header.strip()
    
    # 2. Fallback to Authorization ONLY if X-Firebase-Token is missing
    # (On Private HF Spaces, Authorization will contain the HF Token which would fail Firebase verification)
    if not token and auth_header.startswith('Bearer '):
        token = auth_header.split('Bearer ', 1)[1].strip()

    if not token:
        return None
    if KAUTILYA_API_KEY and token == KAUTILYA_API_KEY:
        return {"uid": "admin", "email": "system@revealiq.in", "provider": "system", "is_admin": True}
    from extensions import FIREBASE_AVAILABLE
    if not FIREBASE_AVAILABLE:
        print("[AUTH] ❌ Firebase not available. Returning 401.")
        return None
    try:
        from firebase_admin import auth as firebase_auth
        decoded = firebase_auth.verify_id_token(token)
        print(f"[AUTH] ✅ Firebase token verified for UID: {decoded.get('uid')}")
        fd = decoded.get('firebase', {})
        return {
            "uid": decoded.get('uid'),
            "email": decoded.get('email'),
            "name": decoded.get('name') or decoded.get('display_name'),
            "picture": decoded.get('picture'),
            "provider": fd.get('sign_in_provider', 'unknown'),
        }
    except Exception as e:
        print(f"[AUTH] ⚠️ Firebase token verification failed: {e}")
        try:
            ki = verify_api_key()
            if ki:
                print(f"[AUTH] ✅ API Key verified for UID: {ki['uid']}")
                return {"uid": ki['uid'], "email": "api@user.com", "provider": "api_key"}
        except:
            pass
        return None


def verify_api_key():
    """Verify API key from Authorization header."""
    from extensions import db, limit_manager
    if not db:
        return None
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer ' + API_KEY_PREFIX):
        return None
    raw_key = auth_header.split('Bearer ', 1)[1]
    key_hash = hash_api_key(raw_key)
    try:
        from firebase_admin import firestore
        doc = db.collection('api_keys').document(key_hash).get()
        if doc.exists:
            data = doc.to_dict()
            if not data.get('is_active', False):
                return None
            db.collection('api_keys').document(key_hash).update({'last_used': firestore.SERVER_TIMESTAMP})
            uid = data.get('uid')
            is_pro = limit_manager.is_pro_user(uid) if uid else False
            return {"uid": uid, "is_pro": is_pro, "key_hash": key_hash}
    except Exception as e:
        print(f"[API Key] Verification error: {e}")
    if KAUTILYA_API_KEY and raw_key == KAUTILYA_API_KEY:
        return {"uid": "admin", "is_pro": True, "key_hash": "admin_hash"}
    return None


def generate_api_key():
    return f"{API_KEY_PREFIX}{secrets.token_hex(32)}"


def hash_api_key(key):
    return hashlib.sha256(key.encode()).hexdigest()


def record_usage(uid, resource_type, amount, model=None):
    """Best-effort, non-blocking usage recorder.
    Increments api_usage/{uid}/daily/{today}.{resource_type} AND writes a
    usage_logs row. Never raises — errors are logged so the caller path keeps
    serving the user even if Firestore hiccups."""
    from extensions import db
    if not db or not uid:
        return
    try:
        amount = int(amount or 0)
    except Exception:
        amount = 0
    if amount <= 0:
        return
    try:
        from datetime import datetime
        from firebase_admin import firestore
        today = datetime.now().strftime("%Y-%m-%d")
        ref = db.collection('api_usage').document(uid).collection('daily').document(today)
        try:
            ref.set({resource_type: firestore.Increment(amount)}, merge=True)
        except Exception:
            doc = ref.get()
            current = (doc.to_dict() or {}).get(resource_type, 0) if doc.exists else 0
            ref.set({resource_type: int(current) + amount}, merge=True)
        log_usage_event(uid, resource_type, amount, model)
    except Exception as e:
        print(f"[record_usage] {resource_type} error: {e}")


def log_usage_event(uid, resource_type, amount, model=None):
    from extensions import db
    if not db or not uid:
        return
    try:
        from datetime import datetime
        from firebase_admin import firestore
        db.collection('usage_logs').add({
            "uid": uid, "type": resource_type, "amount": amount,
            "model": model, "timestamp": firestore.SERVER_TIMESTAMP,
            "hour": datetime.now().hour, "day": datetime.now().strftime("%Y-%m-%d")
        })
    except Exception as e:
        print(f"[Usage Log] Error: {e}")


def check_api_rate_limit(uid, resource_type, is_pro=False, amount=1, model=None):
    """SECURITY FIX: Fails CLOSED — returns False on error."""
    from extensions import db
    if not db:
        return False
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    tier = "pro" if is_pro else "free"
    limit = API_RATE_LIMITS[tier].get(resource_type, 100000)
    for attempt in range(2):
        try:
            usage_ref = db.collection('api_usage').document(uid).collection('daily').document(today)
            usage_doc = usage_ref.get()
            current = usage_doc.to_dict().get(resource_type, 0) if usage_doc.exists else 0
            if current >= limit:
                return False
            if usage_doc.exists:
                usage_ref.update({resource_type: current + amount})
            else:
                usage_ref.set({resource_type: amount})
            log_usage_event(uid, resource_type, amount, model)
            return True
        except Exception as e:
            print(f"[API Rate] Error (attempt {attempt + 1}): {e}")
            if attempt == 0:
                time.sleep(0.5)
    return False


def get_api_usage(uid):
    from extensions import db
    if not db:
        return {}
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        doc = db.collection('api_usage').document(uid).collection('daily').document(today).get()
        return doc.to_dict() if doc.exists else {}
    except:
        return {}
