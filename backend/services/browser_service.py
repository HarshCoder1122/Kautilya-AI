"""
Kautilya AI — Browser Service (Kautilya Computer, live web browsing).

A real headless Chromium (Playwright) the agent can navigate, click, and
type into — ONE persistent tab per USER (see `_session_key`), not per chat.
This is meant to actually be "Kautilya Computer": the same machine whichever
conversation you're in, so a login done in one chat is STILL logged in when
you open a brand new chat and ask it to keep going — unlike
computer_service.py's file workspace, which today is still scoped per CHAT
session, not per user (a difference worth reconciling later for the same
"one persistent computer" story, but out of scope for this specific fix).

THREAD SAFETY: Playwright's async API objects (Browser/BrowserContext/Page)
must only be driven from the event loop that created them. The rest of this
codebase calls tools from an arbitrary ThreadPoolExecutor worker thread per
request, so a single dedicated background thread runs its own asyncio event
loop forever and owns the ONE shared Chromium process + all per-session
BrowserContexts. Callers use `navigate()`/`click()`/`type_text()` (plain
sync functions); under the hood they hand a coroutine to that loop via
`asyncio.run_coroutine_threadsafe(...)` and block on the result — the
standard, safe way to bridge sync multi-threaded callers into one asyncio
loop running on another thread. Everything that touches `_sessions`/the
browser itself runs as a coroutine ON that one loop, so it's all
single-threaded from asyncio's point of view — no extra locking needed
beyond the one-time bootstrap of the loop thread.

HANG-PROOFING: every Playwright call carries an explicit timeout, the
context has a blanket default timeout as a backstop, AND the outer sync
wrapper cancels the asyncio future if it ever runs past its own timeout —
so a wedged page can't block the shared loop thread (and therefore every
OTHER session on this worker) forever. Any exception during a session's
operation closes that session's context so the NEXT call starts a fresh
page instead of retrying against something possibly broken.

STEALTH: default headless Chromium is trivially fingerprinted (the #1 tell
is `navigator.webdriver === true`) and gets blocked by ordinary bot/CAPTCHA
walls before the agent can do anything useful. An init script + launch args
below patch the well-known automation tells — this is NOT a guarantee
against dedicated anti-bot vendors (Cloudflare/hCaptcha challenges can still
trigger), but it clears the common case of a site simply refusing headless
browsers outright.

RESOURCE CAPS: this process (one of several gunicorn WORKER PROCESSES, see
start.sh) launches its own Chromium if a browse call ever lands on it — one
shared browser process, up to BROWSER_MAX_SESSIONS lightweight contexts —
now one per USER rather than per chat, so this is "how many distinct users
can be actively browsing at once on this worker" (LRU-evicted beyond that,
oldest-idle-user first). Kept deliberately low: worst case is (gunicorn
workers) x (one Chromium process each), which is real but bounded; raise
BROWSER_MAX_SESSIONS only after confirming the host has RAM to spare.

SECURITY: navigation targets are resolved and checked against
private/loopback/link-local/reserved ranges before every goto/click/type —
same SSRF posture as the Python sandbox's socket guard — so this can't be
used to reach internal services or the cloud metadata endpoint.
"""
from __future__ import annotations

import asyncio
import base64
import concurrent.futures
import ipaddress
import os
import queue
import re
import socket
import threading
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

MAX_SESSIONS = int(os.environ.get("BROWSER_MAX_SESSIONS", "2"))
# One browser per USER (see _session_key) means this now represents "how
# long before Kautilya Computer logs you out of a site from inactivity" —
# a real personal-computer-ish expectation, not a throwaway per-chat
# resource, hence longer than the old 5 min per-chat default.
SESSION_TTL_SECONDS = int(os.environ.get("BROWSER_SESSION_TTL_S", str(30 * 60)))   # 30 min idle
JANITOR_INTERVAL_S = 60          # how often the background sweep runs
NAV_TIMEOUT_MS = 20_000
ACTION_TIMEOUT_MS = 10_000       # click/fill/wait_for_load_state backstop
OUTER_TIMEOUT_S = 60             # hard ceiling on the whole bridged call
SETTLE_NETWORK_IDLE_MS = 6_000   # post-click/type: let an SPA's login/API call finish
NAV_SETTLE_NETWORK_IDLE_MS = 15_000  # post-navigate: a fresh "workspace bootstrap" can
                                      # legitimately take longer than a click's response
SETTLE_MIN_MS = 700              # then a beat for the client-side re-render off it
MAX_TEXT_CHARS = 6_000
MAX_LINKS = 40

# Genuinely live viewing (CDP screencast), not a polled screenshot — Chrome
# streams frames continuously via Page.startScreencast while at least one
# viewer is connected; started/stopped lazily so a session nobody's watching
# doesn't pay the encoding overhead.
SCREENCAST_QUALITY = 45
SCREENCAST_MAX_WIDTH = 1024
SCREENCAST_MAX_HEIGHT = 640
SCREENCAST_MIN_FRAME_INTERVAL_S = 0.12   # ~8fps cap — CDP has no built-in rate limit

_boot_lock = threading.Lock()
_loop: Optional[asyncio.AbstractEventLoop] = None
_loop_ready = threading.Event()

# Only ever mutated/read from coroutines running ON _loop (single-threaded
# from asyncio's perspective) — see module docstring.
_sessions: Dict[str, Dict[str, Any]] = {}
_browser = None
_playwright = None

# Patches the handful of properties naive bot-detection scripts check.
# Hand-rolled (no extra pip dependency) from the well-documented set of
# headless "tells" — not a silver bullet against dedicated anti-bot vendors.
_STEALTH_INIT_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
window.chrome = window.chrome || { runtime: {} };
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
const _origQuery = window.navigator.permissions && window.navigator.permissions.query;
if (_origQuery) {
    window.navigator.permissions.query = (params) => (
        params.name === 'notifications'
            ? Promise.resolve({ state: Notification.permission })
            : _origQuery(params)
    );
}
// Some SPAs gate expensive init work (workspace/dashboard bootstrap) behind
// the Page Visibility API, treating a headless/background tab as "don't
// bother yet" — this was directly observed causing an infinite "Preparing
// your workspace..." spinner. Report the tab as always visible/focused.
Object.defineProperty(document, 'visibilityState', { get: () => 'visible' });
Object.defineProperty(document, 'hidden', { get: () => false });
document.hasFocus = () => true;
"""

_REALISTIC_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")


def _janitor_loop():
    """Runs for the lifetime of this worker process once browsing is first
    used — closes idle sessions on its OWN schedule instead of relying on
    some future browse call to trigger the sweep. Without this, a session
    nobody ever revisits (chat abandoned, tab closed) keeps its Chromium
    context — and the RAM it holds — alive indefinitely, since nothing else
    would ever call `_sweep_idle()` again."""
    while True:
        time.sleep(JANITOR_INTERVAL_S)
        try:
            _run(_sweep_idle(), timeout=15)
        except Exception:
            pass  # never let a sweep hiccup kill the janitor thread


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
        threading.Thread(target=_janitor_loop, daemon=True, name="kautilya-browser-janitor").start()


def _run(coro, timeout=OUTER_TIMEOUT_S):
    """Bridge a coroutine onto the dedicated Playwright loop and block for
    the result. If it overruns, CANCEL it rather than just giving up on
    waiting — an uncancelled coroutine keeps running on the shared loop and
    would stall every other session on this worker process behind it."""
    _ensure_loop()
    if _loop is None:
        raise RuntimeError("browser event loop failed to start")
    fut = asyncio.run_coroutine_threadsafe(coro, _loop)
    try:
        return fut.result(timeout=timeout)
    except concurrent.futures.TimeoutError:
        fut.cancel()
        raise TimeoutError(f"Browser operation exceeded {timeout}s and was cancelled")


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
        args=[
            "--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu",
            "--disable-blink-features=AutomationControlled",
        ],
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


def _session_key(uid: str, session_id: str = None) -> str:
    """ONE browser per USER, not per chat — this is meant to be "Kautilya
    Computer": a persistent machine that's always yours, the same one
    regardless of which chat you're in, not something that resets (losing
    any login) the moment you open a new conversation. `session_id` is kept
    as a parameter for API stability with agent_loop_service.py's callers
    but deliberately NOT part of the key."""
    return str(uid or "anon")


async def _get_session(uid: str, session_id: str) -> Dict[str, Any]:
    key = _session_key(uid)
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
        user_agent=_REALISTIC_UA,
        locale="en-US",
    )
    # Blanket backstop for EVERY action/assertion on this context (fill,
    # click, wait_for_*, …), not just navigation — belt-and-suspenders
    # against any Playwright call site that might otherwise fall back to
    # its own much longer default timeout.
    context.set_default_timeout(ACTION_TIMEOUT_MS)
    context.set_default_navigation_timeout(NAV_TIMEOUT_MS)
    await context.add_init_script(_STEALTH_INIT_SCRIPT)
    page = await context.new_page()
    entry = {
        "context": context, "page": page, "last_used": time.time(), "links": [],
        # Diagnostics for exactly the "stuck loading, no visible cause" case:
        # without these the model can only guess by clicking blindly. Capped
        # ring-buffers, read (and cleared on a fresh navigate) in
        # _extract_page()/_navigate().
        "console_errors": [], "failed_requests": [],
        # Live screencast state (see _ensure_cdp / _start_screencast_if_needed).
        "cdp": None, "screencast_active": False,
        "frame_subscribers": set(), "last_frame_sent": 0.0,
    }
    _wire_diagnostics(entry)
    _sessions[key] = entry
    return entry


def _wire_diagnostics(entry: Dict[str, Any]):
    """Attach console/pageerror/response listeners so a stuck-workspace-style
    failure (silent JS exception, a blocked/failed API call, a 401/403/500
    on the init request) shows up in the observation instead of the model
    having to guess by clicking around. Listener callbacks run ON the
    dedicated Playwright loop (Playwright dispatches them there), so plain
    list mutation is safe — same single-threaded-from-asyncio's-view
    reasoning as the rest of this module."""
    page = entry["page"]

    def _on_console(msg):
        try:
            if msg.type in ("error", "warning"):
                errs = entry["console_errors"]
                errs.append(f"[console.{msg.type}] {msg.text}"[:300])
                del errs[:-20]
        except Exception:
            pass

    def _on_pageerror(exc):
        try:
            errs = entry["console_errors"]
            errs.append(f"[uncaught exception] {exc}"[:300])
            del errs[:-20]
        except Exception:
            pass

    def _on_requestfailed(request):
        try:
            fr = entry["failed_requests"]
            failure = request.failure
            reason = failure.get("errorText") if isinstance(failure, dict) else str(failure)
            fr.append(f"{request.method} {request.url} — {reason}"[:200])
            del fr[:-20]
        except Exception:
            pass

    def _on_response(response):
        try:
            if response.status >= 400:
                fr = entry["failed_requests"]
                fr.append(f"HTTP {response.status} — {response.url}"[:200])
                del fr[:-20]
        except Exception:
            pass

    def _on_websocket(ws):
        # A stuck "workspace loading" screen with NO console error and NO
        # failed HTTP request is exactly the signature of a real-time
        # backend (WebSocket/SSE) that the page is silently waiting on
        # forever — invisible to the listeners above since a WS connection
        # isn't a "request" that fails/succeeds the normal way. Recording
        # that one was even OPENED, and whether it then closed/errored, is
        # the one diagnostic angle those listeners can't cover.
        try:
            fr = entry["failed_requests"]
            fr.append(f"WEBSOCKET opened: {ws.url}"[:200])
            del fr[:-20]

            def _ws_closed():
                try:
                    fr.append(f"WEBSOCKET closed: {ws.url}"[:200])
                    del fr[:-20]
                except Exception:
                    pass

            def _ws_error(err=None):
                try:
                    fr.append(f"WEBSOCKET error: {ws.url} — {err}"[:200])
                    del fr[:-20]
                except Exception:
                    pass

            ws.on("close", lambda: _ws_closed())
            ws.on("socketerror", _ws_error)
        except Exception:
            pass

    page.on("console", _on_console)
    page.on("pageerror", _on_pageerror)
    page.on("requestfailed", _on_requestfailed)
    page.on("response", _on_response)
    page.on("websocket", _on_websocket)


async def _ensure_cdp(entry: Dict[str, Any]):
    """Lazily create the CDP session for this page and wire the screencast
    frame handler ONCE — the handler itself decides per-frame whether a
    screencast is even running (frames only arrive while one is)."""
    if entry["cdp"] is not None:
        return entry["cdp"]
    page = entry["page"]
    cdp = await page.context.new_cdp_session(page)
    entry["cdp"] = cdp

    def _on_frame(params):
        # ACK immediately — fire-and-forget — or Chrome stalls and stops
        # sending further frames waiting for the ack that never comes.
        cdp_session_id = params.get("sessionId")
        if cdp_session_id is not None:
            asyncio.ensure_future(cdp.send("Page.screencastFrameAck", {"sessionId": cdp_session_id}))
        now = time.time()
        if now - entry["last_frame_sent"] < SCREENCAST_MIN_FRAME_INTERVAL_S:
            return  # throttled — still ack'd above, just not forwarded to viewers
        frame_b64 = params.get("data")
        if not frame_b64:
            return
        entry["last_frame_sent"] = now
        dead = []
        for q in entry["frame_subscribers"]:
            try:
                q.put_nowait(frame_b64)
            except Exception:
                dead.append(q)  # a full/broken queue — drop it, its consumer will time out
        for q in dead:
            entry["frame_subscribers"].discard(q)

    cdp.on("Page.screencastFrame", _on_frame)
    return cdp


async def _start_screencast_if_needed(entry: Dict[str, Any]):
    if entry["screencast_active"]:
        return
    cdp = await _ensure_cdp(entry)
    try:
        await cdp.send("Page.startScreencast", {
            "format": "jpeg", "quality": SCREENCAST_QUALITY,
            "maxWidth": SCREENCAST_MAX_WIDTH, "maxHeight": SCREENCAST_MAX_HEIGHT,
            "everyNthFrame": 1,
        })
        entry["screencast_active"] = True
    except Exception:
        pass  # a live view failing to start shouldn't break browsing itself


async def _stop_screencast_if_idle(entry: Dict[str, Any]):
    """Stop encoding frames the moment nobody's watching — screencast has
    real CPU cost even with no viewers if left running."""
    if not entry["screencast_active"] or entry["frame_subscribers"]:
        return
    cdp = entry.get("cdp")
    if cdp is None:
        return
    try:
        await cdp.send("Page.stopScreencast")
    except Exception:
        pass
    entry["screencast_active"] = False


async def _subscribe_screencast(uid: str):
    key = _session_key(uid)
    entry = _sessions.get(key)
    if entry is None:
        return None
    entry["last_used"] = time.time()
    # maxsize small on purpose: a live view should show the LATEST frame, not
    # queue up a backlog of stale ones if the consumer falls behind.
    q: "queue.Queue" = queue.Queue(maxsize=4)
    entry["frame_subscribers"].add(q)
    await _start_screencast_if_needed(entry)
    return q


async def _unsubscribe_screencast(uid: str, q):
    key = _session_key(uid)
    entry = _sessions.get(key)
    if entry is None:
        return
    entry["frame_subscribers"].discard(q)
    await _stop_screencast_if_idle(entry)


async def _settle_after_action(page, network_idle_timeout_ms=SETTLE_NETWORK_IDLE_MS):
    """After a click/type that MIGHT be an SPA login/form-submit rather than
    a real page navigation: `wait_for_load_state("domcontentloaded")` is a
    no-op here — that event already fired when the page first loaded, ages
    before this click. The actual login/API request is an in-page fetch/XHR
    with no navigation at all, so without this, `_extract_page()` runs
    before that request (and the error toast / redirect / re-render it
    triggers) has happened — which is exactly why a failed login looked
    like "nothing happened, no error visible": the DOM was read too early.

    `networkidle` catches the request finishing; the fixed beat after it
    catches a client-side re-render that lands slightly after the network
    settles (React state update, toast animation, etc.)."""
    try:
        await page.wait_for_load_state("networkidle", timeout=network_idle_timeout_ms)
    except Exception:
        pass  # persistent polling/websockets/SSE never go idle — fine, move on
    try:
        await page.wait_for_timeout(SETTLE_MIN_MS)
    except Exception:
        pass


async def _extract_page(entry: Dict[str, Any], page) -> Dict[str, Any]:
    title = ""
    try:
        title = await page.title()
    except Exception:
        pass

    text = ""
    try:
        text = await page.inner_text("body", timeout=5000)
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
        # See _wire_diagnostics — surfaces the actual cause of a stuck/broken
        # page (JS exception, failed/blocked API call, 4xx/5xx response)
        # instead of leaving the model to guess by clicking blindly.
        "console_errors": list(entry.get("console_errors") or []),
        "failed_requests": list(entry.get("failed_requests") or []),
    }


async def _navigate(uid: str, session_id: str, url: str) -> Dict[str, Any]:
    url = _normalize_url(url)
    _check_url_allowed(url)
    entry = await _get_session(uid, session_id)
    page = entry["page"]
    # Fresh page load — start this page's diagnostic slate clean so a stale
    # error from wherever the session was before doesn't get reported as if
    # it were caused by the page we're about to land on.
    entry["console_errors"] = []
    entry["failed_requests"] = []
    await page.goto(url, timeout=NAV_TIMEOUT_MS, wait_until="domcontentloaded")
    # Give the SPA's post-navigation bootstrap (auth check, workspace init,
    # first data fetch) a chance to finish or fail before reading the page —
    # same reasoning as _settle_after_action, just for the initial load, and
    # with more patience: a fresh workspace bootstrap legitimately takes
    # longer than a click's response.
    await _settle_after_action(page, network_idle_timeout_ms=NAV_SETTLE_NETWORK_IDLE_MS)
    return await _extract_page(entry, page)


async def _click(uid: str, session_id: str, target: str) -> Dict[str, Any]:
    entry = await _get_session(uid, session_id)
    page = entry["page"]
    target_clean = (target or "").strip()
    if not target_clean:
        raise ValueError("no link text or number given")

    # Accept "19" or "#19" as the same numeric index — a model that follows
    # the prompt's literal "#N" syntax would otherwise never match here
    # (the string wouldn't be all-digits) and always fall through to a text
    # search for the literal "#19", which can never exist on a real page.
    digit_part = target_clean.lstrip('#').strip()

    links = entry.get("links") or []
    href = None
    if digit_part.isdigit():
        idx = int(digit_part) - 1
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
        # Multiple strategies, cheapest/most-specific first: a single
        # get_by_text(exact=False) call used to be the ONLY fallback, so
        # any paraphrased target ("the Sign in button" instead of "Sign
        # in") died on one bare timeout with nothing else tried. All of
        # these pierce same- and cross-origin iframes automatically
        # (Playwright operates at the CDP level), so they still reach
        # embedded auth-widget buttons.
        candidates = [target_clean]
        stripped = re.sub(r'(?i)^(the|click|press|tap)\s+|\s+(button|link|icon)$', '', target_clean).strip()
        if stripped and stripped.lower() != target_clean.lower():
            candidates.append(stripped)

        clicked = False
        last_err = None
        for i, cand in enumerate(candidates):
            is_last_candidate = (i == len(candidates) - 1)
            strategies = [
                lambda c=cand: page.get_by_role("button", name=c, exact=False),
                lambda c=cand: page.get_by_role("link", name=c, exact=False),
                lambda c=cand: page.get_by_text(c, exact=False),
            ]
            for j, make_locator in enumerate(strategies):
                # Quick probes for the cheaper role-based strategies; the
                # final text-match attempt on the last candidate gets the
                # full timeout since it's the last real chance to succeed.
                is_last_strategy = is_last_candidate and (j == len(strategies) - 1)
                probe_timeout = ACTION_TIMEOUT_MS if is_last_strategy else 1500
                try:
                    await make_locator().first.click(timeout=probe_timeout)
                    clicked = True
                    break
                except Exception as e:
                    last_err = e
            if clicked:
                break
        if not clicked:
            # ValueError (not the raw Playwright TimeoutError) deliberately —
            # _guarded() below treats ValueError/PermissionError as an
            # ordinary, recoverable miss and leaves the session alone, but
            # any OTHER exception type is treated as "the browser context
            # itself is broken" and gets the whole session closed. A click
            # that simply couldn't find its target (by far the most common
            # failure — a paraphrased or slightly-off target) is completely
            # recoverable and must NOT nuke cookies/login state/everything
            # browsed so far just because one guess missed.
            raise ValueError(f"couldn't find a clickable element matching '{target_clean}': {last_err}")
        await _settle_after_action(page)
        _check_url_allowed(page.url)

    return await _extract_page(entry, page)


async def _type(uid: str, session_id: str, field: str, value: str) -> Dict[str, Any]:
    entry = await _get_session(uid, session_id)
    page = entry["page"]
    field_clean = (field or "").strip()
    if not field_clean:
        raise ValueError("no field description given")

    # Try the common ways a form field is identified, in order of how
    # reliably each one pins down a SINGLE field. All of these pierce
    # iframes automatically (same CDP-level reasoning as _click above),
    # which is what makes typing into embedded auth widgets work.
    locator_attempts = [
        lambda: page.get_by_label(field_clean, exact=False),
        lambda: page.get_by_placeholder(field_clean, exact=False),
        lambda: page.get_by_role("textbox", name=field_clean, exact=False),
        lambda: page.locator(
            f'input[name*="{field_clean}" i], input[id*="{field_clean}" i], '
            f'input[aria-label*="{field_clean}" i]'
        ),
    ]
    # A bare "password"/"email" ask should also match the input TYPE even
    # when there's no matching label/placeholder text at all.
    fl = field_clean.lower()
    if "password" in fl:
        locator_attempts.append(lambda: page.locator('input[type="password"]'))
    if "email" in fl:
        locator_attempts.append(lambda: page.locator('input[type="email"]'))

    last_err = None
    for make_locator in locator_attempts:
        try:
            loc = make_locator().first
            await loc.wait_for(state="visible", timeout=3000)
            await loc.fill(value, timeout=ACTION_TIMEOUT_MS)
            return await _extract_page(entry, page)
        except Exception as e:
            last_err = e
            continue
    raise ValueError(f"couldn't find a field matching '{field_clean}': {last_err}")


async def _current_screenshot(uid: str) -> Dict[str, Any]:
    """Lightweight sibling of `_current_state` for FREQUENT polling — just
    the screenshot + url, skipping title/inner_text/link-scraping (each an
    extra CDP round-trip `_extract_page` normally does). This is what makes
    the Computer panel's Browser tab feel genuinely live: the frontend polls
    this every ~1s while that tab is visible, so the screen updates as the
    agent works instead of only once per completed tool call. Screenshots
    interleave safely with an in-flight navigate/click on the SAME page —
    everything runs on the one dedicated loop, so this just captures
    whatever the page looks like at that exact moment, mid-action or not."""
    key = _session_key(uid)
    entry = _sessions.get(key)
    if entry is None:
        return {"ok": False, "error": "no active browser session"}
    entry["last_used"] = time.time()
    page = entry["page"]
    try:
        buf = await page.screenshot(type="jpeg", quality=45, timeout=4000)
        return {"ok": True, "url": page.url, "screenshot_b64": base64.b64encode(buf).decode("ascii")}
    except Exception as e:
        return {"ok": False, "error": str(e)}


async def _current_state(uid: str) -> Dict[str, Any]:
    """Read-only: the CURRENT page's title/url/screenshot/links for this
    user's persistent browser, without navigating anywhere. Used so opening
    the Computer panel in a DIFFERENT chat than the one that did the
    browsing still shows the real, current state of the one shared browser
    — not "nothing happened yet in this chat", which would be misleading
    now that the browser is per-user, not per-chat."""
    key = _session_key(uid)
    entry = _sessions.get(key)
    if entry is None:
        return {"ok": False, "error": "no active browser session"}
    entry["last_used"] = time.time()
    return await _extract_page(entry, entry["page"])


# ── Public sync API (safe to call from any thread) ─────────────────────────

def get_current_state(uid: str, timeout: int = 15) -> Dict[str, Any]:
    try:
        return _run(_current_state(uid or "anon"), timeout=timeout)
    except Exception as e:
        return {"ok": False, "error": str(e)}


def get_screenshot(uid: str, timeout: int = 8) -> Dict[str, Any]:
    try:
        return _run(_current_screenshot(uid or "anon"), timeout=timeout)
    except Exception as e:
        return {"ok": False, "error": str(e)}


def open_live_view(uid: str, timeout: int = 10):
    """Start (or join) the live CDP screencast for this user's browser and
    return a thread-safe queue.Queue the CALLER reads directly (plain
    blocking .get(timeout=...) — no need to bridge back through _run for
    that part, queue.Queue is safe to read from any thread). Returns None
    if there's no active browser session to watch. ALWAYS pair with
    close_live_view() (e.g. in a try/finally) once the caller is done
    streaming, or the screencast keeps encoding frames for a viewer that
    already left."""
    return _run(_subscribe_screencast(uid or "anon"), timeout=timeout)


def close_live_view(uid: str, q, timeout: int = 10):
    try:
        _run(_unsubscribe_screencast(uid or "anon", q), timeout=timeout)
    except Exception:
        pass


def _guarded(coro_factory, uid, session_id, timeout=OUTER_TIMEOUT_S):
    """Run one browser op; on ANY unexpected failure (not our own
    PermissionError/ValueError), close the session so the next call gets a
    fresh page instead of retrying against something possibly wedged."""
    try:
        return _run(coro_factory(), timeout=timeout)
    except (PermissionError, ValueError):
        raise
    except Exception as e:
        key = _session_key(uid)
        try:
            _run(_close_session(key), timeout=10)
        except Exception:
            pass
        return {"ok": False, "error": str(e)}


def navigate(uid: str, session_id: str, url: str, timeout: int = OUTER_TIMEOUT_S) -> Dict[str, Any]:
    return _guarded(lambda: _navigate(uid or "anon", session_id, url), uid, session_id, timeout)


def click(uid: str, session_id: str, target: str, timeout: int = OUTER_TIMEOUT_S) -> Dict[str, Any]:
    return _guarded(lambda: _click(uid or "anon", session_id, target), uid, session_id, timeout)


def type_text(uid: str, session_id: str, field: str, value: str, timeout: int = OUTER_TIMEOUT_S) -> Dict[str, Any]:
    return _guarded(lambda: _type(uid or "anon", session_id, field, value), uid, session_id, timeout)


def close_session(uid: str, session_id: str = None, timeout: int = 10) -> None:
    """Explicitly close a user's persistent browser (frees that Chromium
    context's memory immediately rather than waiting for the janitor's next
    sweep or the idle TTL). Safe to call even if no session exists — no-op.
    Not currently wired to anything automatic (there's one browser per USER,
    not per chat, so "closing a chat" is never the right trigger for this —
    see _session_key) — available for an explicit "log out of Kautilya
    Computer" action if one gets added; until then the background janitor
    thread (`_janitor_loop`) is what guarantees an abandoned browser
    doesn't linger forever."""
    key = _session_key(uid)
    try:
        _run(_close_session(key), timeout=timeout)
    except Exception:
        pass
