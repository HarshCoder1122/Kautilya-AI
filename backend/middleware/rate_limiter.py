"""
Kautilya AI — Rate Limiter Middleware
Per-minute burst + daily persistent limit checks.
"""
import time
from config import _MESSAGE_RATE_LIMITS

_burst_limit_store = {}


def check_message_rate_limit(identifier, tier="guest"):
    """
    Check if user/IP can send a message.
    Returns (allowed: bool, error_msg: str|None).
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

    if daily_limit is not None:
        can_chat = limit_manager.check_chat_limit(identifier, is_pro=is_pro, limit_per_day=daily_limit)
        if not can_chat:
            return False, (
                f"📊 You've reached your daily message limit of **{daily_limit} messages/day**.\n\n"
                "Your limit resets at midnight.\n\n"
                + ("💡 *Sign in for a higher limit!*" if tier == "guest"
                   else "💡 *Upgrade to Pro for unlimited daily messages!*")
            )

    _burst_limit_store[identifier].append(now)
    limit_manager.increment_chat_count(identifier)

    if len(_burst_limit_store) > 5000:
        _burst_limit_store = {k: v for k, v in _burst_limit_store.items() if len(v) > 0}

    return True, None
