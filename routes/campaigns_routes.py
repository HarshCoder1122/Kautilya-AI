"""
Kautilya AI — Campaigns Routes Blueprint
Handles /api/campaigns/* endpoints (Outbound Dialer Campaigns).
"""
from flask import Blueprint, request, jsonify

from services.auth_service import verify_firebase_token

campaigns_bp = Blueprint('campaigns', __name__)


@campaigns_bp.route('/api/campaigns', methods=['GET'])
def api_campaigns_get():
    from extensions import db
    from firebase_admin import firestore
    token_data = verify_firebase_token()
    uid = token_data.get('uid') if token_data else None
    if not uid: return jsonify({"error": "Auth required"}), 401
    if not db: return jsonify({"campaigns": []})
    
    try:
        campaigns = []
        docs = db.collection('users').document(uid).collection('campaigns')\
                 .order_by('created_at', direction=firestore.Query.DESCENDING).stream()
        for doc in docs:
            d = doc.to_dict()
            d['id'] = doc.id
            if 'created_at' in d and hasattr(d['created_at'], 'timestamp'):
                d['created_timestamp'] = d['created_at'].timestamp()
                del d['created_at']
            campaigns.append(d)
        return jsonify({"campaigns": campaigns})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@campaigns_bp.route('/api/campaigns/create', methods=['POST'])
def api_campaigns_create():
    from extensions import db
    from firebase_admin import firestore
    token_data = verify_firebase_token()
    uid = token_data.get('uid') if token_data else None
    if not uid: return jsonify({"error": "Auth required"}), 401
    
    data = request.get_json() or {}
    name = data.get('name', 'Unammed Campaign')
    agent_id = data.get('agent_id')
    numbers = data.get('numbers', [])
    
    if not agent_id or not numbers:
        return jsonify({"error": "Agent ID and Numbers list required"}), 400
        
    try:
        camp_data = {
            "name": name, "agent_id": agent_id, "numbers": numbers,
            "status": "pending", "progress": 0, "total": len(numbers),
            "created_at": firestore.SERVER_TIMESTAMP, "uid": uid
        }
        doc_ref = db.collection('users').document(uid).collection('campaigns').add(camp_data)
        return jsonify({"status": "ok", "campaign_id": doc_ref[1].id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@campaigns_bp.route('/api/campaigns/<camp_id>/start', methods=['POST'])
@campaigns_bp.route('/api/campaigns/<camp_id>/resume', methods=['POST'])
def api_campaigns_start(camp_id):
    from extensions import db
    token_data = verify_firebase_token()
    uid = token_data.get('uid') if token_data else None
    if not uid: return jsonify({"error": "Auth required"}), 401
    try:
        camp_ref = db.collection('users').document(uid).collection('campaigns').document(camp_id)
        if not camp_ref.get().exists: return jsonify({"error": "Campaign not found"}), 404
        camp_ref.update({"status": "running"})
        return jsonify({"status": "ok", "message": "Campaign started"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@campaigns_bp.route('/api/campaigns/<camp_id>/stop', methods=['POST'])
@campaigns_bp.route('/api/campaigns/<camp_id>/pause', methods=['POST'])
def api_campaigns_stop(camp_id):
    from extensions import db
    token_data = verify_firebase_token()
    uid = token_data.get('uid') if token_data else None
    if not uid: return jsonify({"error": "Auth required"}), 401
    try:
        camp_ref = db.collection('users').document(uid).collection('campaigns').document(camp_id)
        if not camp_ref.get().exists: return jsonify({"error": "Campaign not found"}), 404
        camp_ref.update({"status": "paused"})
        return jsonify({"status": "ok", "message": "Campaign stopped"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@campaigns_bp.route('/api/campaigns/<camp_id>', methods=['DELETE'])
def api_campaigns_delete(camp_id):
    from extensions import db
    token_data = verify_firebase_token()
    uid = token_data.get('uid') if token_data else None
    if not uid: return jsonify({"error": "Auth required"}), 401
    try:
        camp_ref = db.collection('users').document(uid).collection('campaigns').document(camp_id)
        if not camp_ref.get().exists: return jsonify({"error": "Campaign not found"}), 404
        camp_ref.delete()
        return jsonify({"status": "ok", "message": "Campaign deleted"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@campaigns_bp.route('/api/campaigns/upload', methods=['POST'])
def api_campaigns_upload():
    """Upload a CSV/Excel file, parse phone numbers, and create a campaign."""
    from extensions import db
    from firebase_admin import firestore
    import re
    import csv
    import io
    
    token_data = verify_firebase_token()
    uid = token_data.get('uid') if token_data else None
    if not uid: return jsonify({"error": "Auth required"}), 401
    
    agent_id = request.form.get('agent_id')
    name = request.form.get('name', 'CSV Campaign')
    
    if not agent_id:
        return jsonify({"error": "agent_id is required"}), 400
        
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
        
    file = request.files['file']
    if not file.filename:
        return jsonify({"error": "Empty filename"}), 400
        
    try:
        content = file.read().decode('utf-8')
        numbers = []
        
        if file.filename.endswith('.csv'):
            reader = csv.reader(io.StringIO(content))
            for row in reader:
                for col in row:
                    clean = re.sub(r'[^\d+]', '', col)
                    if len(clean) >= 10:
                        numbers.append(clean)
        else:
            # Simple text parsing fallback
            for line in content.splitlines():
                clean = re.sub(r'[^\d+]', '', line)
                if len(clean) >= 10:
                    numbers.append(clean)
                    
        # Remove duplicates
        numbers = list(set(numbers))
        
        if not numbers:
            return jsonify({"error": "No valid phone numbers found in file"}), 400
            
        camp_data = {
            "name": name, "agent_id": agent_id, "numbers": numbers,
            "status": "pending", "progress": 0, "total": len(numbers),
            "created_at": firestore.SERVER_TIMESTAMP, "uid": uid
        }
        doc_ref = db.collection('users').document(uid).collection('campaigns').add(camp_data)
        
        return jsonify({
            "status": "ok", 
            "campaign_id": doc_ref[1].id,
            "message": f"Campaign created with {len(numbers)} numbers",
            "numbers_count": len(numbers)
        })
    except Exception as e:
        return jsonify({"error": f"Failed to process file: {str(e)}"}), 500


@campaigns_bp.route('/api/campaigns/<camp_id>/status', methods=['GET'])
def api_campaigns_status(camp_id):
    """Get the live status and dial results of a specific campaign."""
    from extensions import db
    token_data = verify_firebase_token()
    uid = token_data.get('uid') if token_data else None
    if not uid: return jsonify({"error": "Auth required"}), 401
    
    try:
        camp_ref = db.collection('users').document(uid).collection('campaigns').document(camp_id)
        camp_doc = camp_ref.get()
        if not camp_doc.exists:
            return jsonify({"error": "Campaign not found"}), 404
            
        data = camp_doc.to_dict()
        data['id'] = camp_id
        
        # Format timestamp
        if 'created_at' in data and hasattr(data['created_at'], 'timestamp'):
            data['created_timestamp'] = data['created_at'].timestamp()
            del data['created_at']
            
        # Optional: could query campaign_logs subcollection here for per-number details
        # For now just returning the main doc which campaign_worker updates with results
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
