"""
Kautilya AI — Fast Response Cache

Two-tier latency optimization for trivial chat traffic. Trivial = greetings,
acknowledgments, identity questions, single-word emoji replies. Without this,
"hi" still pays for a full agent-loop turn (~1-2 s of LLM round-trip on a
cold key) when a canned answer is indistinguishable to the user.

Tier 1 — Canned responses (~5 ms end-to-end)
    Exact-match table of common trivial inputs to short, on-brand replies.
    Covers English + Hinglish greetings, thanks/bye acknowledgments, and the
    most frequent "who are you / what can you do" first-questions.

Tier 2 — Short-query LRU (~5 ms on hit, full LLM on miss)
    Time-bounded LRU keyed by (normalized_message, model). If two users (or
    the same user twice) ask the same short question within an hour, the
    second one is served from memory.

Both tiers are intentionally narrow: they only fire for messages ≤ 60 chars
after normalization. Anything longer goes through the real agent loop —
caching long-form generation is a different problem (semantic similarity,
risk of stale personalization) and out of scope.

Wired into chat_routes.jarvis_stream → fast-path response before the
conversation build / agent loop kicks in.
"""
import re
import time
from collections import OrderedDict
from threading import Lock


# ---------- Tier 1: canned replies ----------
# Keyed by the message normalized via `_normalize` (lowercased, punctuation
# stripped, whitespace collapsed). Values are short, KAUTILYA-branded replies
# that read naturally as the first message of a conversation.
_GREETING_REPLIES = {
    # English greetings
    "hi":             "Hi! I'm Kautilya. What can I help you with today?",
    "hii":            "Hi! What can I do for you?",
    "hiii":           "Hi! What can I do for you?",
    "hello":          "Hello! I'm Kautilya. What can I help you with today?",
    "helo":           "Hello! What can I help with?",
    "hey":            "Hey! How can I help?",
    "heyy":           "Hey! How can I help?",
    "yo":             "Yo! What's up?",
    "sup":            "Hey, what's up?",
    "hi there":       "Hi there! What's on your mind?",
    "hello there":    "Hello there! How can I help?",
    "good morning":   "Good morning! What can I help you with today?",
    "good afternoon": "Good afternoon! What can I help you with today?",
    "good evening":   "Good evening! What can I help you with today?",
    "good night":     "Good night! Catch you later.",
    "gm":             "Good morning!",
    "gn":             "Good night!",

    # Hindi / Hinglish
    "namaste":        "Namaste! Main Kautilya hoon. Kaise madad karu?",
    "namaskar":       "Namaskar! Aaj kaise madad karu?",
    "kaise ho":       "Main bilkul theek hoon — aap batao, kya madad chahiye?",
    "kya haal":       "Sab badhiya! Aap batao.",

    # Acknowledgments / closers
    "ok":         "Got it.",
    "okay":       "Got it.",
    "k":          "Got it.",
    "kk":         "Got it.",
    "okk":        "Got it.",
    "ok thanks":  "You're welcome!",
    "ok thank you": "You're welcome!",
    "thanks":     "You're welcome!",
    "thank you":  "You're welcome!",
    "thx":        "You're welcome!",
    "ty":         "You're welcome!",
    "tysm":       "You're welcome!",
    "shukriya":   "Koi baat nahi!",
    "dhanyavaad": "Aapka swagat hai!",

    "bye":     "Bye! Talk soon.",
    "goodbye": "Goodbye!",
    "cya":     "See you later!",
    "ttyl":    "Talk to you later!",

    "cool":    "👍",
    "nice":    "👍",
    "great":   "Great!",
    "awesome": "Awesome!",
    "perfect": "Perfect!",
    "got it":  "👍",

    # Identity (most-frequent first questions)
    "who are you":          "I'm Kautilya AI — your strategic AI assistant built by Harsh at RevealIQ.",
    "what are you":         "I'm Kautilya AI — your strategic AI assistant built by Harsh at RevealIQ.",
    "what is your name":    "I'm Kautilya AI.",
    "whats your name":      "I'm Kautilya AI.",
    "your name":            "Kautilya AI.",
    "who made you":         "I was built by Harsh at RevealIQ.",
    "who created you":      "I was built by Harsh at RevealIQ.",
    "what can you do":      ("I can chat, write code, research the web, send emails and "
                             "calendar invites, run analytics on your data, and act through "
                             "voice agents over the phone. What would you like to start with?"),
    "help":                 ("Sure — I can chat, code, research, send emails / calendar "
                             "invites, run analytics, and place voice calls. What do you "
                             "want to do?"),
}


# ---------- Tier 2: short-query LRU ----------
_LRU_MAX = 1000
_LRU_TTL_SEC = 3600   # 1 hour — long enough to amortize repeat traffic,
                      # short enough to avoid stale "what's the date" answers.
_MAX_QUERY_LEN = 60   # only cache trivially short queries
_MAX_RESPONSE_LEN = 1200

_lru = OrderedDict()  # key=(norm_msg, model) -> (response_text, ts)
_lru_lock = Lock()


def _normalize(text):
    """Lowercase, strip punctuation, collapse whitespace. Used as the cache
    key — so 'Hi!' and 'hi.' and '  HI ' all hit the same canned reply."""
    if not text or not isinstance(text, str):
        return ""
    s = text.lower().strip()
    s = re.sub(r"[^\w\s]", "", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def try_canned_reply(message):
    """Tier 1: exact match against the greeting table.
    Returns the canned reply string, or None if no match."""
    norm = _normalize(message)
    if not norm or len(norm) > _MAX_QUERY_LEN:
        return None
    return _GREETING_REPLIES.get(norm)


def cache_get(message, model, uid=None):
    """Tier 2: read from the short-query LRU.
    UID is included in the key so each user has an independent cache slot —
    without it, user A's non-personalized response would be served to user B.
    Returns the cached response, or None on miss / expiry / out-of-range."""
    norm = _normalize(message)
    if not norm or len(norm) > _MAX_QUERY_LEN:
        return None
    key = (uid or "anon", norm, model or "auto")
    with _lru_lock:
        item = _lru.get(key)
        if not item:
            return None
        response, ts = item
        if time.time() - ts > _LRU_TTL_SEC:
            _lru.pop(key, None)
            return None
        _lru.move_to_end(key)  # mark recent
        return response


def cache_put(message, model, response, uid=None):
    """Tier 2: store a fresh response. Only writes for short queries and
    short responses — long-form generation isn't a good cache target.
    UID is included in the key to keep each user's cache independent."""
    if not message or not response:
        return
    norm = _normalize(message)
    if not norm or len(norm) > _MAX_QUERY_LEN:
        return
    if len(response) > _MAX_RESPONSE_LEN:
        return
    key = (uid or "anon", norm, model or "auto")
    with _lru_lock:
        _lru[key] = (response, time.time())
        _lru.move_to_end(key)
        while len(_lru) > _LRU_MAX:
            _lru.popitem(last=False)


def stats():
    """Diagnostics for the dashboard / debug endpoints."""
    with _lru_lock:
        return {
            "canned_patterns": len(_GREETING_REPLIES),
            "lru_size": len(_lru),
            "lru_max": _LRU_MAX,
            "lru_ttl_sec": _LRU_TTL_SEC,
        }
