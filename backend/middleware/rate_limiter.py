"""
Kautilya AI — Rate Limiter Middleware
Per-minute burst + daily persistent limit checks.
Falls back to Pay-As-You-Go credits when daily quota is exhausted.
"""
import time
from config import _MESSAGE_RATE_LIMITS

_burst_limit_store = {}

# Price (INR) deducted from PAYG credits per message after daily quota is hit.
PAYG_PRICE_PER_MESSAGE = 0.50


def check_message_rate_limit(identifier, tier="guest"):
    """
    Check if user/IP can send a message.
    Returns (allowed: bool, error_msg: str|None).

    Behaviour:
      - Per-minute burst is always enforced (anti-abuse).
      - Daily limit is enforced for guest/free tier.
      - When a logged-in free user is over the daily limit BUT has PAYG credits,
        ₹{PAYG_PRICE_PER_MESSAGE} is deducted and the request is allowed.
      - Pro users have no daily cap.
    """
    global _burst_limit_store
    from extensions import limit_manager

    now = time.time()
    limits = _MESSAGE_RATE_LIMITS.get(tier, _MESSAGE_RATE_LIMITS["guest"])

    if identifier not in _burst_limit_store:
        _burst_limit_store[identifier] = []

    _burst_limit_store[identifier] = [t for t in _burst_limit_store[identifier] if now - t < 60]

    if len(_burst_limit_store[identifier]) >= limits["per_minute"]:
        wait = int(60 - (now - _burst_limit_store[identifier][0])) + 1
        return False, (
            f"⏳ You're sending messages too fast! "
            f"Limit: **{limits['per_minute']} messages/minute**.\n\n"
            f"Please wait **{wait} seconds** before trying again."
            + ("\n\n💡 *Upgrade to Pro for higher limits!*" if tier != "pro" else "")
        )

    is_pro = (tier == "pro")
    daily_limit = limits["per_day"]
    used_credits = False

    if daily_limit is not None:
        can_chat = limit_manager.check_chat_limit(identifier, is_pro=is_pro, limit_per_day=daily_limit)
        if not can_chat:
            # Daily quota exhausted — try Pay-As-You-Go fallback for logged-in users.
            if tier == "free":
                balance = limit_manager.get_credits(identifier)
                if balance >= PAYG_PRICE_PER_MESSAGE:
                    if limit_manager.deduct_credits(identifier, PAYG_PRICE_PER_MESSAGE):
                        used_credits = True
                    else:
                        return False, _quota_error(daily_limit, tier, balance)
                else:
                    return False, _quota_error(daily_limit, tier, balance)
            else:
                return False, _quota_error(daily_limit, tier, 0.0)

    _burst_limit_store[identifier].append(now)
    if not used_credits:
        limit_manager.increment_chat_count(identifier)

    if len(_burst_limit_store) > 5000:
        _burst_limit_store = {k: v for k, v in _burst_limit_store.items() if len(v) > 0}

    return True, None


def _quota_error(daily_limit, tier, balance):
    """Friendly daily-limit message, includes credits hint when relevant."""
    base = (
        f"📊 You've reached your daily message limit of **{daily_limit} messages/day**.\n\n"
        "Your limit resets at midnight."
    )
    if tier == "guest":
        return base + "\n\n💡 *Sign in for a higher limit, or add Pay-As-You-Go credits to keep going.*"
    # free tier
    if balance and balance > 0:
        return base + (
            f"\n\nYour Pay-As-You-Go balance is **₹{balance:.2f}** but a message costs "
            f"₹{PAYG_PRICE_PER_MESSAGE:.2f}. Please top up from **Dashboard → Billing**."
        )
    return base + (
        "\n\n💡 *Upgrade to Pro for unlimited daily messages, or top up Pay-As-You-Go "
        "credits from **Dashboard → Billing** to keep going today.*"
    )
