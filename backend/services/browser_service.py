"""
Kautilya AI — Browser Service (Kautilya Computer, live web browsing).

A real headless Chromium (Playwright) the agent can navigate and click
through, session-scoped so "visit X, then click Y" acts on the SAME page
across turns — mirrors computer_service.py's per-session model, but for a
live browser instead of a filesystem.

THREAD SAFETY: Playwright's async API objects (Browser/BrowserContext/Page)
must only be driven from the event loop that created them. The rest of this
codebase calls tools from an arbitrary ThreadPoolExecutor worker thread per
request, so a single dedicated background thread runs its own asyncio event
loop forever and owns the ONE shared Chromium process + all per-session
BrowserContexts. Callers use `navigate()`/`click()` (plain sync functions);
under the hood they hand a coroutine to that loop via
`asyncio.run_coroutine_threadsafe(...)` and block on the result — the
standard, safe way to bridge sync multi-threaded callers into one asyncio
loop running on another thread. Everything that touches `_sessions`/the
browser itself runs as a coroutine ON that one loop, so it's all
single-threaded from asyncio's point of view — no extra locking needed
beyond the one-time bootstrap of the loop thread.

RESOURCE CAPS: this process (one of several gunicorn WORKER PROCESSES, see
start.sh) launches its own Chromium if a browse call ever lands on it — one
shared browser process, up to BROWSER_MAX_SESSIONS lightweight contexts
(LRU-evicted beyond that). Kept deliberately low: worst case is
(gunicorn workers) x (one Chromium process each), which is real but bounded;
raise BROWSER_MAX_SESSIONS only after confirming the host has RAM to spare.

SECURITY: navigation targets are resolved and checked against
private/loopback/link-local/reserved ranges before every goto — same SSRF
posture as the Python sandbox's socket guard — so this can't be used to
reach internal services or the cloud metadata endpoint.
"""
from __future__ import annotations

import asyncio
import base64
import ipaddress
import os
import re
import socket
import threading
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

MAX_SESSIONS = int(os.environ.get("BROWSER_MAX_SESSIONS", "2"))
SESSION_TTL_SECONDS = 10 * 60
NAV_TIMEOUT_MS = 20_000
CLICK_TIMEOUT_MS = 8_000
MAX_TEXT_CHARS = 6_000
MAX_LINKS = 40

_boot_lock = threading.Lock()
_loop: Optional[asyncio.AbstractEventLoop] = None
_loop_ready = threading.Event()

# Only ever mutated/read from coroutines running ON _loop (single-threaded
# from asyncio's perspective) — see module docstring.
_sessions: Dict[str, Dict[str, Any]] = {}
_browser = None
_playwright = None


def _ensure_loop():
    global _loop
    if _loop is not None:
        return
    with _boot_lock:
        if _loop is not None:
            return

        def _runner():
            global _loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            _loop = loop
            _loop_ready.set()
            loop.run_forever()

        threading.Thread(target=_runner, daemon=True, name="kautilya-browser-loop").start()
        _loop_ready.wait(timeout=10)


def _run(coro, timeout=30):
    _ensure_loop()
    if _loop is None:
        raise RuntimeError("browser event loop failed to start")
    fut = asyncio.run_coroutine_threadsafe(coro, _loop)
    return fut.result(timeout=timeout)


def _is_blocked_host(host: str) -> bool:
    if not host:
        return True
    try:
        infos = socket.getaddrinfo(host, None)
    except Exception:
        return True  # can't resolve — block, safe default
    for info in infos:
        sockaddr = info[4]
        try:
            ip = ipaddress.ip_address(sockaddr[0])
        except Exception:
            continue
        if (ip.is_private or ip.is_loopback or ip.is_link_local
                or ip.is_reserved or ip.is_multicast or ip.is_unspecified):
            return True
    return False


def _normalize_url(url: str) -> str:
    url = (url or "").strip()
    if not re.match(r'^https?://', url, re.I):
        url = "https://" + url
    return url


def _check_url_allowed(url: str):
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise PermissionError(f"'{parsed.scheme}' URLs are not allowed — only http/https")
    if _is_blocked_host(parsed.hostname or ""):
        raise PermissionError(f"'{parsed.hostname}' resolves to a blocked/internal address")


async def _get_browser():
    global _browser, _playwright
    if _browser is not None:
        try:
            # Cheap liveness check — raises if the browser process died.
            _ = _browser.contexts
            return _browser
        except Exception:
            _browser = None
    from playwright.async_api import async_playwright
    if _playwright is None:
        _playwright = await async_playwright().start()
    _browser = await _playwright.chromium.launch(
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
    )
    return _browser


async def _close_session(key: str):
    entry = _sessions.pop(key, None)
    if entry:
        try:
            await entry["context"].close()
        except Exception:
            pass


async def _sweep_idle():
    now = time.time()
    stale = [k for k, v in _sessions.items() if now - v["last_used"] > SESSION_TTL_SECONDS]
    for k in stale:
        await _close_session(k)


async def _get_session(uid: str, session_id: str) -> Dict[str, Any]:
    key = f"{uid}::{session_id}"
    entry = _sessions.get(key)
    if entry is not None:
        entry["last_used"] = time.time()
        return entry

    await _sweep_idle()
    while len(_sessions) >= MAX_SESSIONS:
        oldest = min(_sessions, key=lambda k: _sessions[k]["last_used"])
        await _close_session(oldest)

    browser = await _get_browser()
    context = await browser.new_context(
        viewport={"width": 1280, "height": 800},
        user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 KautilyaBot/1.0"),
    )
    context.set_default_navigation_timeout(NAV_TIMEOUT_MS)
    page = await context.new_page()
    entry = {"context": context, "page": page, "last_used": time.time(), "links": []}
    _sessions[key] = entry
    return entry


async def _extract_page(entry: Dict[str, Any], page) -> Dict[str, Any]:
    title = ""
    try:
        title = await page.title()
    except Exception:
        pass

    text = ""
    try:
        text = await page.inner_text("body")
        text = re.sub(r'\n{3,}', '\n\n', text or "").strip()[:MAX_TEXT_CHARS]
    except Exception:
        pass

    links: List[Dict[str, str]] = []
    try:
        raw_links = await page.eval_on_selector_all(
            "a[href]",
            "els => els.slice(0, 120).map(e => ({href: e.href, text: (e.innerText||e.textContent||'').trim()}))",
        )
        seen = set()
        for l in raw_links or []:
            href = l.get("href")
            text_l = (l.get("text") or "").strip()[:80]
            if not href or not text_l or href in seen or not href.startswith(("http://", "https://")):
                continue
            seen.add(href)
            links.append({"href": href, "text": text_l})
            if len(links) >= MAX_LINKS:
                break
    except Exception:
        pass
    entry["links"] = links

    screenshot_b64 = None
    try:
        buf = await page.screenshot(type="jpeg", quality=55, timeout=8000)
        screenshot_b64 = base64.b64encode(buf).decode("ascii")
    except Exception:
        pass

    return {
        "ok": True,
        "url": page.url,
        "title": title,
        "text": text,
        "links": links,
        "screenshot_b64": screenshot_b64,
    }


async def _navigate(uid: str, session_id: str, url: str) -> Dict[str, Any]:
    url = _normalize_url(url)
    _check_url_allowed(url)
    entry = await _get_session(uid, session_id)
    page = entry["page"]
    await page.goto(url, timeout=NAV_TIMEOUT_MS, wait_until="domcontentloaded")
    return await _extract_page(entry, page)


async def _click(uid: str, session_id: str, target: str) -> Dict[str, Any]:
    entry = await _get_session(uid, session_id)
    page = entry["page"]
    target_clean = (target or "").strip()
    if not target_clean:
        raise ValueError("no link text or number given")

    links = entry.get("links") or []
    href = None
    if target_clean.isdigit():
        idx = int(target_clean) - 1
        if 0 <= idx < len(links):
            href = links[idx]["href"]
    if href is None:
        tl = target_clean.lower()
        for l in links:
            if tl in (l.get("text") or "").lower():
                href = l["href"]
                break

    if href:
        _check_url_allowed(href)
        await page.goto(href, timeout=NAV_TIMEOUT_MS, wait_until="domcontentloaded")
    else:
        # Not in the last extracted link list (or points at JS, not an
        # href) — fall back to a real DOM click, which also handles
        # JS-driven buttons/nav a static <a href> scrape wouldn't capture.
        await page.get_by_text(target_clean, exact=False).first.click(timeout=CLICK_TIMEOUT_MS)
        await page.wait_for_load_state("domcontentloaded", timeout=NAV_TIMEOUT_MS)
        _check_url_allowed(page.url)

    return await _extract_page(entry, page)


# ── Public sync API (safe to call from any thread) ─────────────────────────

def navigate(uid: str, session_id: str, url: str, timeout: int = 30) -> Dict[str, Any]:
    try:
        return _run(_navigate(uid or "anon", session_id, url), timeout=timeout)
    except PermissionError:
        raise
    except Exception as e:
        return {"ok": False, "error": str(e)}


def click(uid: str, session_id: str, target: str, timeout: int = 30) -> Dict[str, Any]:
    try:
        return _run(_click(uid or "anon", session_id, target), timeout=timeout)
    except PermissionError:
        raise
    except Exception as e:
        return {"ok": False, "error": str(e)}
