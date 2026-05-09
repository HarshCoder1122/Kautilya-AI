"""
Kautilya AI — Billing Routes Blueprint
Handles /api/billing/* endpoints (Razorpay integration).
"""
import os
import uuid

from flask import Blueprint, request, jsonify

from services.auth_service import verify_firebase_token

billing_bp = Blueprint('billing', __name__)


@billing_bp.route('/billing/create-order', methods=['POST'])
def create_billing_order():
    from extensions import razorpay_client, db
    try:
        data = request.json
        amount = data.get('amount')
        plan_type = data.get('plan_type')
        try: amount = float(amount)
        except: return jsonify({"error": "Invalid amount format"}), 400
        if amount <= 0: return jsonify({"error": "Invalid amount"}), 400
        if not razorpay_client: return jsonify({"error": "Razorpay not configured"}), 500
        
        token_data = verify_firebase_token()
        uid = token_data.get("uid") if token_data else None

        if plan_type == 'pro_subscription':
            plan_id = os.environ.get('RAZORPAY_PRO_PLAN_ID', 'plan_JarvisPro599')
            subscription = razorpay_client.subscription.create({
                'plan_id': plan_id, 'customer_notify': 1, 'total_count': 120,
                'notes': {'uid': uid, 'plan_type': 'pro'}
            })
            if uid and db:
                db.collection('users').document(uid).update({
                    'razorpay_subscription_id': subscription['id'], 'tier': 'pro_pending'
                })
            return jsonify(subscription)
        else:
            order = razorpay_client.order.create({
                'amount': int(amount * 100), 'currency': 'INR',
                'receipt': f"receipt_{uuid.uuid4().hex[:8]}",
                'notes': {'plan_type': plan_type, 'uid': uid}
            })
            return jsonify(order)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@billing_bp.route('/billing/verify-payment', methods=['POST'])
def verify_payment():
    from extensions import razorpay_client, limit_manager
    try:
        token_data = verify_firebase_token()
        uid = token_data.get("uid") if token_data else None
        if not uid: return jsonify({"error": "Unauthorized"}), 401
        
        data = request.json
        razorpay_order_id = data.get('razorpay_order_id')
        razorpay_payment_id = data.get('razorpay_payment_id')
        razorpay_signature = data.get('razorpay_signature')
        plan_type = data.get('plan_type')
        amount = float(data.get('amount', 0))
        
        if not razorpay_client: return jsonify({"error": "Razorpay not configured"}), 500
        
        try:
            razorpay_client.utility.verify_payment_signature({
                'razorpay_order_id': razorpay_order_id,
                'razorpay_payment_id': razorpay_payment_id,
                'razorpay_signature': razorpay_signature
            })
        except Exception as e:
            return jsonify({"error": "Invalid payment signature", "details": str(e)}), 400
            
        limit_manager.add_transaction(uid, amount, plan_type, razorpay_order_id, razorpay_payment_id)
        
        if plan_type in ['pro', 'pro_subscription']:
            limit_manager.add_pro_user(uid)
            return jsonify({"success": True, "message": "Successfully upgraded to Pro!"})
        elif plan_type == 'pay_as_you_go':
            limit_manager.add_credits(uid, amount)
            return jsonify({"success": True, "message": f"Successfully added {amount} credits!"})
            
        return jsonify({"error": "Unknown plan type"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@billing_bp.route('/billing/razorpay-webhook', methods=['POST'])
def razorpay_webhook():
    from extensions import razorpay_client, limit_manager
    webhook_secret = os.environ.get('RAZORPAY_WEBHOOK_SECRET')
    if not webhook_secret: return "Secret Missing", 400
    try:
        payload = request.data
        signature = request.headers.get('X-Razorpay-Signature')
        razorpay_client.utility.verify_webhook_signature(payload.decode('utf-8'), signature, webhook_secret)
        
        data = request.json
        event = data.get('event')
        uid = data.get('payload', {}).get('subscription', {}).get('entity', {}).get('notes', {}).get('uid')
        if not uid:
            uid = data.get('payload', {}).get('payment', {}).get('entity', {}).get('notes', {}).get('uid')
        if not uid: return "OK", 200
        
        if event in ['subscription.authenticated', 'subscription.active', 'subscription.charged']:
            limit_manager.add_pro_user(uid)
        elif event in ['subscription.cancelled', 'subscription.halted', 'subscription.expired']:
            limit_manager.remove_pro_user(uid)
            
        return "OK", 200
    except Exception as e:
        print(f"[Webhook] Error: {e}")
        return "Internal Error", 500


@billing_bp.route('/billing/transactions', methods=['GET'])
def get_user_transactions():
    from extensions import limit_manager
    try:
        token_data = verify_firebase_token()
        uid = token_data.get("uid") if token_data else None
        if not uid: return jsonify({"error": "Unauthorized"}), 401
        transactions = limit_manager.get_transactions(uid)
        return jsonify({"transactions": transactions})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@billing_bp.route('/billing/config', methods=['GET'])
def billing_config():
    """Return Razorpay public config plus the caller's tier & credits, so the
    Billing page can render the correct Pro/Free badge and balance."""
    from config import RAZORPAY_KEY_ID
    from extensions import limit_manager

    is_pro = False
    credits = 0.0
    try:
        token_data = verify_firebase_token()
        uid = token_data.get('uid') if token_data else None
        if uid and limit_manager:
            try:
                is_pro = bool(limit_manager.is_pro_user(uid))
            except Exception as e:
                print(f"[Billing Config] is_pro_user failed: {e}")
            try:
                credits = float(limit_manager.get_credits(uid) or 0.0)
            except Exception as e:
                print(f"[Billing Config] get_credits failed: {e}")
    except Exception as e:
        print(f"[Billing Config] Auth lookup failed: {e}")

    return jsonify({
        "razorpay_key_id": RAZORPAY_KEY_ID or os.environ.get('RAZORPAY_KEY_ID', ''),
        "is_pro": is_pro,
        "tier": "pro" if is_pro else "free",
        "credits": credits,
    })
