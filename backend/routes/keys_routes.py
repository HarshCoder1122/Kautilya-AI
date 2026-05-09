"""
Kautilya AI — Keys Routes Blueprint
Handles /api/keys/* endpoints (API key generation & management).
"""
from flask import Blueprint, request, jsonify

from config import MAX_KEYS_PER_USER, API_RATE_LIMITS
from services.auth_service import verify_firebase_token, generate_api_key, hash_api_key, get_api_usage

keys_bp = Blueprint('keys', __name__)


@keys_bp.route('/keys/create', methods=['POST'])
def api_key_create():
    from extensions import db
    from firebase_admin import firestore
    token_data = verify_firebase_token()
    uid = token_data.get('uid') if token_data else None
    if not uid: return jsonify({"error": "Authentication required"}), 401
    if not db: return jsonify({"error": "Database not available"}), 503
    
    data = request.get_json() or {}
    key_name = data.get('name', 'Default Key')[:50]
    
    try:
        existing = db.collection('api_keys').where(filter=firestore.FieldFilter('uid', '==', uid))\
                     .where(filter=firestore.FieldFilter('is_active', '==', True)).stream()
        if sum(1 for _ in existing) >= MAX_KEYS_PER_USER:
            return jsonify({"error": f"Maximum {MAX_KEYS_PER_USER} keys allowed"}), 400
    except Exception as e:
        print(f"[API Key] Count check error: {e}")
    
    raw_key = generate_api_key()
    key_hash = hash_api_key(raw_key)
    
    db.collection('api_keys').document(key_hash).set({
        'uid': uid, 'name': key_name, 'key_preview': '...' + raw_key[-6:],
        'created_at': firestore.SERVER_TIMESTAMP, 'last_used': None, 'is_active': True
    })
    
    try:
        db.collection('users').document(uid).set({'active_api_key': raw_key}, merge=True)
    except: pass
    
    return jsonify({"key": raw_key, "key_id": key_hash[:16], "name": key_name, "message": "API key created!"})


@keys_bp.route('/keys/list', methods=['GET'])
def api_key_list():
    from extensions import db, limit_manager
    from firebase_admin import firestore
    token_data = verify_firebase_token()
    uid = token_data.get('uid') if token_data else None
    if not uid: return jsonify({"error": "Authentication required"}), 401
    if not db: return jsonify({"error": "Database not available"}), 503
    
    try:
        docs = db.collection('api_keys').where(filter=firestore.FieldFilter('uid', '==', uid))\
                 .where(filter=firestore.FieldFilter('is_active', '==', True)).stream()
        keys = []
        for doc in docs:
            d = doc.to_dict()
            keys.append({
                "key_id": doc.id[:16], "key_hash": doc.id, "name": d.get('name', 'Unnamed'),
                "preview": d.get('key_preview', ''),
                "created_at": d.get('created_at').isoformat() if d.get('created_at') else None,
                "last_used": d.get('last_used').isoformat() if d.get('last_used') else None,
            })
        
        usage = get_api_usage(uid)
        tier = "pro" if limit_manager.is_pro_user(uid) else "free"
        limits = API_RATE_LIMITS[tier]
        
        active_key = None
        try:
            user_doc = db.collection('users').document(uid).get()
            if user_doc.exists: active_key = user_doc.to_dict().get('active_api_key')
        except: pass
        
        return jsonify({"keys": keys, "usage": usage, "limits": limits, "tier": tier, "active_key": active_key})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@keys_bp.route('/keys/revoke', methods=['POST'])
def api_key_revoke():
    from extensions import db
    token_data = verify_firebase_token()
    uid = token_data.get('uid') if token_data else None
    if not uid: return jsonify({"error": "Authentication required"}), 401
    if not db: return jsonify({"error": "Database not available"}), 503
    
    key_hash = (request.get_json() or {}).get('key_hash', '')
    if not key_hash: return jsonify({"error": "No key_hash provided"}), 400
    
    try:
        doc = db.collection('api_keys').document(key_hash).get()
        if doc.exists and doc.to_dict().get('uid') == uid:
            db.collection('api_keys').document(key_hash).update({'is_active': False})
            return jsonify({"status": "ok", "message": "Key revoked"})
        return jsonify({"error": "Key not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500
