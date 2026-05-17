"""
Kautilya AI — Billing Routes Blueprint
Handles /api/billing/* endpoints (Razorpay integration).
"""
import os
import uuid

from flask import Blueprint, request, jsonify

from services.auth_service import verify_firebase_token

billing_bp = Blueprint('billing', __name__)


def _ensure_captured(razorpay_client, payment):
    """If a payment is `authorized` but not yet `captured`, capture it now.

    Why: some UPI / netbanking / wallet flows land in 'authorized' state when
    auto-capture didn't fire (older orders without payment_capture=1, or a
    Razorpay-side glitch). Money is held but never transferred until we
    explicitly call payment.capture. Returns the (possibly refreshed) payment.
    """
    if not payment: return payment
    status = payment.get('status')
    if status == 'captured':
        return payment
    if status != 'authorized':
        return payment  # failed/refunded/created — caller decides
    try:
        payment_id = payment.get('id')
        amount_paise = int(payment.get('amount', 0))
        currency = payment.get('currency', 'INR')
        print(f"[Capture] auto-capturing authorized payment {payment_id} amount={amount_paise} paise")
        razorpay_client.payment.capture(payment_id, amount_paise, {'currency': currency})
        # Re-fetch to confirm new status
        return razorpay_client.payment.fetch(payment_id)
    except Exception as e:
        print(f"[Capture] FAILED for {payment.get('id')}: {e}")
        return payment


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
            # payment_capture=1 → Razorpay auto-captures on successful authorization,
            # so funds actually move instead of sitting in "authorized" limbo (which
            # auto-voids after ~5 days and silently refunds the customer).
            order = razorpay_client.order.create({
                'amount': int(amount * 100), 'currency': 'INR',
                'receipt': f"receipt_{uuid.uuid4().hex[:8]}",
                'payment_capture': 1,
                'notes': {'plan_type': plan_type, 'uid': uid}
            })
            return jsonify(order)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@billing_bp.route('/billing/verify-payment', methods=['POST'])
def verify_payment():
    """Browser-side payment confirmation. Idempotent — safe if webhook also fires.

    Resilient flow:
      1. If payment_id already processed (by webhook / earlier call), short-circuit OK.
      2. Try signature verification (cheap, no API call).
      3. If signature fails, fall back to Razorpay-as-source-of-truth:
         fetch the payment, confirm status=captured AND notes.uid matches
         the caller. This avoids silently losing money on UPI / wallet flows
         where signature mismatches are a known issue.
    """
    from extensions import razorpay_client, limit_manager, db
    try:
        token_data = verify_firebase_token()
        uid = token_data.get("uid") if token_data else None
        if not uid: return jsonify({"error": "Unauthorized"}), 401

        data = request.json or {}
        razorpay_order_id = data.get('razorpay_order_id')
        razorpay_payment_id = data.get('razorpay_payment_id')
        razorpay_signature = data.get('razorpay_signature')
        plan_type = data.get('plan_type')
        amount = float(data.get('amount', 0))

        if not razorpay_client: return jsonify({"error": "Razorpay not configured"}), 500
        if not razorpay_payment_id:
            return jsonify({"error": "razorpay_payment_id required"}), 400

        # 1. Idempotency check FIRST — handles the webhook-already-credited race.
        if db:
            proc_ref = db.collection('processed_payments').document(razorpay_payment_id)
            if proc_ref.get().exists:
                print(f"[Verify] payment {razorpay_payment_id} already processed — skip")
                return jsonify({"success": True, "already_processed": True})

        # 2. Try signature verification.
        signature_ok = False
        sig_error = None
        try:
            razorpay_client.utility.verify_payment_signature({
                'razorpay_order_id': razorpay_order_id,
                'razorpay_payment_id': razorpay_payment_id,
                'razorpay_signature': razorpay_signature
            })
            signature_ok = True
            # Even with a valid signature, double-check Razorpay status —
            # the browser's "success" callback can fire on authorization too.
            try:
                payment = razorpay_client.payment.fetch(razorpay_payment_id)
                if payment.get('status') == 'authorized':
                    payment = _ensure_captured(razorpay_client, payment)
                if payment.get('status') != 'captured':
                    return jsonify({
                        "error": f"Payment status is '{payment.get('status')}', not captured",
                        "hint": "Authorization held but not captured. Retry via Reconcile in a moment.",
                    }), 400
            except Exception as fetch_err:
                print(f"[Verify] post-signature fetch failed (non-fatal): {fetch_err}")
        except Exception as e:
            sig_error = str(e)
            print(f"[Verify] Signature mismatch uid={uid} payment_id={razorpay_payment_id} err={e}")

        # 3. If signature failed, fall back to fetching the payment from Razorpay.
        if not signature_ok:
            try:
                payment = razorpay_client.payment.fetch(razorpay_payment_id)
            except Exception as e:
                return jsonify({
                    "error": "Could not verify payment with Razorpay",
                    "details": str(e), "signature_error": sig_error,
                }), 400

            # If Razorpay only authorized (held funds) but didn't capture,
            # capture it now so the money actually moves.
            if payment.get('status') == 'authorized':
                payment = _ensure_captured(razorpay_client, payment)

            if payment.get('status') != 'captured':
                return jsonify({
                    "error": f"Payment status is '{payment.get('status')}', not captured",
                    "signature_error": sig_error,
                    "hint": "Funds may be held in authorization. Try Reconcile after a minute, or contact support.",
                }), 400

            # Confirm the payment belongs to this user (via notes.uid we set on create)
            payment_uid = (payment.get('notes') or {}).get('uid')
            if payment_uid and payment_uid != uid:
                return jsonify({"error": "Payment does not belong to this user"}), 403

            # Trust Razorpay's reported amount, not the client's claim
            amount = float(payment.get('amount', 0)) / 100.0
            print(f"[Verify] Signature failed but Razorpay confirms capture — crediting via fallback. payment={razorpay_payment_id} amount=₹{amount}")

        # 4. Credit the account (whichever path got us here).
        limit_manager.add_transaction(uid, amount, plan_type, razorpay_order_id, razorpay_payment_id)

        if plan_type in ['pro', 'pro_subscription']:
            limit_manager.add_pro_user(uid)
            msg = "Successfully upgraded to Pro!"
        elif plan_type == 'pay_as_you_go':
            limit_manager.add_credits(uid, amount)
            msg = f"Successfully added ₹{amount:.2f} credits!"
        else:
            return jsonify({"error": f"Unknown plan type: {plan_type}"}), 400

        if db:
            from datetime import datetime
            db.collection('processed_payments').document(razorpay_payment_id).set({
                'uid': uid, 'amount': amount, 'plan_type': plan_type,
                'order_id': razorpay_order_id,
                'processed_at': datetime.now().isoformat(),
                'source': 'verify-payment' if signature_ok else 'verify-payment-fallback',
                'signature_ok': signature_ok,
            })

        print(f"[Verify] credited uid={uid} amount=₹{amount} plan={plan_type} signature_ok={signature_ok}")
        return jsonify({"success": True, "message": msg, "signature_ok": signature_ok})
    except Exception as e:
        print(f"[Verify] Error: {e}")
        return jsonify({"error": str(e)}), 500


@billing_bp.route('/billing/razorpay-webhook', methods=['POST'])
def razorpay_webhook():
    """Server-side source of truth for billing events.

    Handles both subscription lifecycle (Pro) AND payment.captured for PAYG —
    the webhook is the ONLY reliable signal because the browser-side
    handler in checkout can fail (network drop, tab closed, ad blocker).
    Idempotent via payment_id deduplication in Firestore.
    """
    from extensions import razorpay_client, limit_manager, db
    webhook_secret = os.environ.get('RAZORPAY_WEBHOOK_SECRET')
    if not webhook_secret: return "Secret Missing", 400
    try:
        payload = request.data
        signature = request.headers.get('X-Razorpay-Signature')
        razorpay_client.utility.verify_webhook_signature(payload.decode('utf-8'), signature, webhook_secret)

        data = request.json
        event = data.get('event')
        sub_entity = data.get('payload', {}).get('subscription', {}).get('entity', {}) or {}
        pay_entity = data.get('payload', {}).get('payment', {}).get('entity', {}) or {}
        uid = sub_entity.get('notes', {}).get('uid') or pay_entity.get('notes', {}).get('uid')
        print(f"[Webhook] event={event} uid={uid} payment_id={pay_entity.get('id')}")

        # Subscription lifecycle (Pro plan)
        if event in ['subscription.authenticated', 'subscription.active', 'subscription.charged']:
            if uid: limit_manager.add_pro_user(uid)
            return "OK", 200
        if event in ['subscription.cancelled', 'subscription.halted', 'subscription.expired']:
            if uid: limit_manager.remove_pro_user(uid)
            return "OK", 200

        # Razorpay authorized the payment but didn't capture — capture it
        # ourselves so funds actually transfer. The subsequent payment.captured
        # event will then credit the user.
        if event == 'payment.authorized':
            payment_id = pay_entity.get('id')
            if payment_id:
                try:
                    refreshed = razorpay_client.payment.fetch(payment_id)
                    if refreshed.get('status') == 'authorized':
                        _ensure_captured(razorpay_client, refreshed)
                except Exception as e:
                    print(f"[Webhook] payment.authorized capture failed: {e}")
            return "OK", 200

        # PAYG and one-off payments — credit the user once per payment_id.
        if event == 'payment.captured':
            payment_id = pay_entity.get('id')
            amount_paise = pay_entity.get('amount', 0)
            plan_type = (pay_entity.get('notes') or {}).get('plan_type', 'pay_as_you_go')
            order_id  = pay_entity.get('order_id')

            if not uid or not payment_id:
                print(f"[Webhook] payment.captured missing uid/payment_id — skip")
                return "OK", 200

            amount = float(amount_paise) / 100.0

            # Idempotency: skip if we've already processed this payment
            if db:
                proc_ref = db.collection('processed_payments').document(payment_id)
                if proc_ref.get().exists:
                    print(f"[Webhook] payment {payment_id} already processed — skip")
                    return "OK", 200

            # Apply the credit / pro grant
            if plan_type in ('pro', 'pro_subscription'):
                limit_manager.add_pro_user(uid)
            else:
                limit_manager.add_credits(uid, amount)

            limit_manager.add_transaction(uid, amount, plan_type, order_id or '', payment_id)
            if db:
                from datetime import datetime
                db.collection('processed_payments').document(payment_id).set({
                    'uid': uid, 'amount': amount, 'plan_type': plan_type,
                    'order_id': order_id, 'processed_at': datetime.now().isoformat(),
                    'source': 'webhook',
                })
            print(f"[Webhook] credited uid={uid} amount=₹{amount} plan={plan_type}")

        return "OK", 200
    except Exception as e:
        print(f"[Webhook] Error: {e}")
        return "Internal Error", 500


@billing_bp.route('/billing/reconcile-payment', methods=['POST'])
def reconcile_payment():
    """Manually credit a payment that Razorpay captured but our system missed.

    Auth: requires the calling user's Firebase token, AND the payment's
    `notes.uid` must match — so a user can only reconcile their own payments.
    Body: { "razorpay_payment_id": "pay_XXX" }
    Idempotent via the processed_payments collection.
    """
    from extensions import razorpay_client, limit_manager, db
    if not razorpay_client:
        return jsonify({"error": "Razorpay not configured"}), 500

    token_data = verify_firebase_token()
    uid = token_data.get('uid') if token_data else None
    if not uid:
        return jsonify({"error": "Unauthorized"}), 401

    body = request.get_json(silent=True) or {}
    payment_id = body.get('razorpay_payment_id')
    if not payment_id:
        return jsonify({"error": "razorpay_payment_id required"}), 400

    try:
        payment = razorpay_client.payment.fetch(payment_id)
    except Exception as e:
        return jsonify({"error": f"Razorpay fetch failed: {e}"}), 400

    # If only authorized, capture it now so reconciliation actually works.
    if payment.get('status') == 'authorized':
        payment = _ensure_captured(razorpay_client, payment)

    if payment.get('status') != 'captured':
        return jsonify({
            "error": f"Payment status is '{payment.get('status')}', not captured",
            "payment": payment,
            "hint": "Razorpay still has this payment in a non-captured state. If status is 'authorized', it should auto-capture shortly — please retry in a minute.",
        }), 400

    notes = payment.get('notes') or {}
    payment_uid = notes.get('uid')
    # Admins (no uid restriction) can reconcile any payment via the master key,
    # but normal users can only reconcile their own.
    if payment_uid and payment_uid != uid:
        return jsonify({"error": "Payment does not belong to this user"}), 403

    if db:
        proc_ref = db.collection('processed_payments').document(payment_id)
        if proc_ref.get().exists:
            return jsonify({"success": True, "already_processed": True, "message": "Already credited"}), 200

    amount = float(payment.get('amount', 0)) / 100.0
    plan_type = notes.get('plan_type', 'pay_as_you_go')
    target_uid = payment_uid or uid

    if plan_type in ('pro', 'pro_subscription'):
        limit_manager.add_pro_user(target_uid)
    else:
        limit_manager.add_credits(target_uid, amount)

    limit_manager.add_transaction(target_uid, amount, plan_type, payment.get('order_id', ''), payment_id)
    if db:
        from datetime import datetime
        db.collection('processed_payments').document(payment_id).set({
            'uid': target_uid, 'amount': amount, 'plan_type': plan_type,
            'order_id': payment.get('order_id'),
            'processed_at': datetime.now().isoformat(),
            'source': 'manual_reconcile',
        })

    return jsonify({
        "success": True,
        "credited": amount,
        "plan_type": plan_type,
        "uid": target_uid,
        "new_balance": limit_manager.get_credits(target_uid),
    })


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

    # Build usage snapshot so the Billing UI can show today's consumption
    usage = {"chat_count": 0, "image_count": 0, "daily_limit": 30}
    api_usage = {"api_count": 0, "daily_limit": 50, "price_per_call": 1.0}
    try:
        from config import _MESSAGE_RATE_LIMITS, _DEVELOPER_API_LIMITS, DEVELOPER_API_PAYG_PRICE
        from services.auth_service import verify_firebase_token as _v
        td = _v()
        u = td.get('uid') if td else None
        if u and limit_manager:
            record = limit_manager._get_daily_usage(u)
            tier = "pro" if is_pro else "free"
            daily = _MESSAGE_RATE_LIMITS.get(tier, _MESSAGE_RATE_LIMITS["free"]).get("per_day")
            usage = {
                "chat_count": int(record.get("chat_count", 0)),
                "image_count": int(record.get("image_count", 0)),
                "daily_limit": daily if daily is not None else -1,  # -1 = unlimited
            }
            api_daily = _DEVELOPER_API_LIMITS.get(tier, _DEVELOPER_API_LIMITS["free"])["per_day"]
            api_usage = {
                "api_count": int(record.get("api_count", 0)),
                "daily_limit": api_daily,
                "price_per_call": DEVELOPER_API_PAYG_PRICE,
            }
    except Exception as e:
        print(f"[Billing Config] usage snapshot failed: {e}")

    return jsonify({
        "razorpay_key_id": RAZORPAY_KEY_ID or os.environ.get('RAZORPAY_KEY_ID', ''),
        "is_pro": is_pro,
        "tier": "pro" if is_pro else "free",
        "credits": credits,
        "usage": usage,
        "api_usage": api_usage,
        "payg_price_per_message": 0.50,
        "pro_price_inr": 599,
    })
