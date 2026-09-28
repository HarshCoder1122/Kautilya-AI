"""Keep-warm pinger for our free HF CPU Spaces.

Free HF Spaces cold-start (and unload their model) when idle, so we ping each
one's /health periodically. The catch: gunicorn runs many workers (12 by
default) and each worker used to spawn its OWN warmup thread — and STT and TTS
each spawned one even though they share the SAME Space. That was 12 × 2 = 24
pingers hammering /health (~6 hits/min). This service replaces all of that with
EXACTLY ONE pinger for the whole deployment, single-flighted across workers via
an exclusive file lock, that pings every target Space once per interval.

Targets (all overridable by env; ping is skipped for any that's blank):
  • STT_SPACE_BASE    — RevealIQ-ASR Space (STT + TTS live here together)
  • VOICE_SPACE_URL   — the KautilyaVoice / LiveKit agent Space (keep it started)
  • WARMUP_EXTRA_URLS — comma-separated extra full health URLs
"""
import os
import time
import threading
import logging

import requests

logger = logging.getLogger(__name__)

_INTERVAL_SEC = int(os.environ.get("WARMUP_INTERVAL_SEC", "300"))  # 5 min — plenty
_started = False
_lock_fh = None  # held for the process lifetime so the flock isn't released


def _targets():
    """Build the list of (health_url, headers) to ping."""
    hf_token = os.environ.get("REVEALIQ_HF_TOKEN") or os.environ.get("HF_TOKEN")
    headers = {"Authorization": f"Bearer {hf_token}"} if hf_token else {}
    out = []

    asr = (os.environ.get("STT_SPACE_BASE")
           or "https://HarshSharma1212-RevealIQ-ASR.hf.space").rstrip("/")
    if asr:
        out.append((f"{asr}/health", headers))

    # KautilyaVoice / LiveKit agent Space — keep it always started. Default is a
    # best guess from the Space name; override with VOICE_SPACE_URL if different.
    voice = (os.environ.get("VOICE_SPACE_URL")
             or "https://HarshSharma1212-KautilyaVoice.hf.space").rstrip("/")
    if voice:
        out.append((f"{voice}/health", headers))

    for u in (os.environ.get("WARMUP_EXTRA_URLS") or "").split(","):
        u = u.strip()
        if u:
            out.append((u, headers))
    return out


def _loop():
    targets = _targets()
    logger.info("[Warmup] keeper active — pinging %d space(s) every %ds",
                len(targets), _INTERVAL_SEC)
    while True:
        for url, headers in targets:
            try:
                requests.get(url, headers=headers, timeout=10)
            except Exception:
                pass  # cold/asleep Spaces are exactly why we ping; never crash
        time.sleep(_INTERVAL_SEC)


def start_warmup_once():
    """Start the keep-warm loop in EXACTLY ONE process across all gunicorn
    workers. The worker that grabs the exclusive lock runs the pinger; the rest
    return immediately. Safe to call from every worker on import."""
    global _started, _lock_fh
    if _started:
        return
    if os.environ.get("DISABLE_WARMUP") == "1":
        return

    # Cross-worker single-flight via a non-blocking exclusive lock. fcntl is
    # POSIX-only — on Windows dev boxes we just skip (no reason to ping prod
    # Spaces from a laptop).
    try:
        import fcntl
    except ImportError:
        return
    try:
        lock_path = os.environ.get("WARMUP_LOCK_PATH", "/tmp/revealiq_warmup.lock")
        fh = open(lock_path, "w")
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        _lock_fh = fh  # keep the fd open for the process lifetime
    except (OSError, IOError):
        return  # another worker is already the keeper

    _started = True
    threading.Thread(target=_loop, daemon=True, name="space-warmup").start()
