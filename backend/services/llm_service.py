"""
Kautilya AI — LLM Service
Unified LLM call interface: Google Vertex AI (Gemini) for chat/completion,
plus OpenRouter as a standalone opt-in provider. NVIDIA NIM and Groq
text-completion were fully retired — see call_vertex_gemini().
"""
import os
import json
import time
import requests
import sqlite3
import hashlib
import threading
import contextvars
from requests.adapters import HTTPAdapter
from config import (
    OPENROUTER_API_KEY,
    CHAT_DATA_DIR,
)

def _make_pooled_session(pool_connections=20, pool_maxsize=50):
    """Session with connection pooling AND TCP_NODELAY so streaming SSE
    chunks flush immediately instead of waiting for Nagle's algorithm to
    coalesce them. Nagle adds 40-200ms of perceived latency to every token.
    """
    import socket
    from urllib3.poolmanager import PoolManager

    class _NoDelayAdapter(HTTPAdapter):
        def init_poolmanager(self, *args, **kwargs):
            kwargs['socket_options'] = [
                (socket.IPPROTO_TCP, socket.TCP_NODELAY, 1),  # flush each packet
                (socket.SOL_SOCKET,  socket.SO_KEEPALIVE, 1),  # keep socket warm
            ]
            super().init_poolmanager(*args, **kwargs)

    s = requests.Session()
    adapter = _NoDelayAdapter(
        pool_connections=pool_connections,
        pool_maxsize=pool_maxsize,
        max_retries=0,
    )
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    return s


# Shared session — module-level so OpenRouter calls reuse the same TLS pool.
_OPENROUTER_SESSION = _make_pooled_session()

# ── Per-request PRO flag ─────────────────────────────────────────────────
# Set once per request by the route handlers (set_request_pro). Vertex calls
# accept an explicit is_pro but don't currently act on it (no key-rotation
# lane to reserve with a single provider) — kept for interface parity and
# any future PRO-specific routing. Reads default to
# False (free). Note: ContextVars are per-thread — a PRO flag set in the
# request thread is visible to LLM calls made on that same thread (the normal
# streaming path), but NOT to calls offloaded onto a separate executor thread;
# those callers can pass is_pro explicitly to call_nvidia instead.
_request_is_pro = contextvars.ContextVar("kautilya_request_is_pro", default=False)


def set_request_pro(is_pro):
    """Mark the current request context as PRO (or not). Call once per request,
    before any LLM call, so reserved-key routing kicks in."""
    try:
        _request_is_pro.set(bool(is_pro))
    except Exception:
        pass


def build_capacity_event(is_pro=False):
    """Structured SSE event for 'we hit full capacity'. Free users get the
    PRO upsell (their requests would skip the queue on the reserved lane);
    PRO users — who already had the reserved lane and still failed — get a
    plain soft-retry with no upsell. The `chunk` keeps old clients working;
    `event: capacity` lets the frontend render the upgrade card + PRO button."""
    if is_pro:
        return {
            "event": "capacity", "upgrade": False,
            "chunk": "\n\n⚠️ Our AI is momentarily overloaded. Please try again in a few seconds.",
        }
    return {
        "event": "capacity", "upgrade": True,
        "chunk": ("\n\n⚡ We're at **full capacity** right now and free access is temporarily "
                  "throttled. **Upgrade to PRO** for priority access — PRO requests skip the "
                  "queue on a reserved lane."),
    }




# ==========================================
# Google Vertex AI (Gemini) — primary chat/completion provider
# ==========================================
_vertex_client = None
_vertex_client_lock = threading.Lock()


def _get_vertex_client():
    """Lazy singleton genai.Client wired to Vertex AI. Returns None if the
    google-genai SDK isn't installed or the project isn't configured."""
    global _vertex_client
    if _vertex_client is not None:
        return _vertex_client
    with _vertex_client_lock:
        if _vertex_client is not None:
            return _vertex_client
        try:
            from google import genai
            from config import VERTEX_PROJECT_ID, VERTEX_LOCATION, VERTEX_CREDENTIALS
            if not VERTEX_PROJECT_ID:
                print("[Vertex] VERTEX_PROJECT_ID not set — Vertex AI disabled")
                return None
            kwargs = {"vertexai": True, "project": VERTEX_PROJECT_ID, "location": VERTEX_LOCATION}
            if VERTEX_CREDENTIALS is not None:
                kwargs["credentials"] = VERTEX_CREDENTIALS
            _vertex_client = genai.Client(**kwargs)
            print(f"[Vertex] Client ready (project={VERTEX_PROJECT_ID}, location={VERTEX_LOCATION})")
        except Exception as e:
            print(f"[Vertex] Failed to initialize client: {e}")
            return None
    return _vertex_client


def _messages_to_gemini(messages):
    """OpenAI-style messages -> (system_instruction: str|None, contents: list[dict]).

    Gemini has no "system" role in the turn sequence — system text is passed
    separately via GenerateContentConfig.system_instruction. "assistant"
    becomes "model". Multimodal content (image_url data: URIs) and native
    tool-calling messages (assistant tool_calls / role="tool" results) are
    translated to Gemini's function_call / function_response parts so the
    OpenAI-compatible proxy (Cline/Cursor/Continue) keeps working.
    """
    from google.genai import types

    system_parts = []
    contents = []
    # tool_call_id -> function name, so a later role="tool" message (which
    # OpenAI callers often omit the name on) can be matched back to it.
    call_id_to_name = {}

    for m in messages:
        role = m.get("role")
        content = m.get("content")

        if role == "system":
            if isinstance(content, str) and content.strip():
                system_parts.append(content)
            elif isinstance(content, list):
                for p in content:
                    if isinstance(p, dict) and p.get("type") == "text":
                        system_parts.append(p.get("text", ""))
            continue

        if role == "tool":
            name = m.get("name") or call_id_to_name.get(m.get("tool_call_id"), "tool_result")
            result_text = content if isinstance(content, str) else json.dumps(content, default=str)
            try:
                part = types.Part.from_function_response(name=name, response={"result": result_text})
                contents.append({"role": "user", "parts": [part]})
            except Exception:
                contents.append({"role": "user", "parts": [types.Part.from_text(text=f"[tool result: {name}] {result_text}")]})
            continue

        gemini_role = "model" if role == "assistant" else "user"
        parts = []

        if isinstance(content, str):
            if content:
                parts.append(types.Part.from_text(text=content))
        elif isinstance(content, list):
            for p in content:
                if not isinstance(p, dict):
                    continue
                ptype = p.get("type")
                if ptype == "text":
                    txt = p.get("text", "")
                    if txt:
                        parts.append(types.Part.from_text(text=txt))
                elif ptype == "image_url":
                    img_url = (p.get("image_url") or {}).get("url", "")
                    if img_url.startswith("data:"):
                        try:
                            header, b64data = img_url.split(",", 1)
                            mime = header.split(":")[1].split(";")[0]
                            import base64 as _b64
                            parts.append(types.Part.from_bytes(data=_b64.b64decode(b64data), mime_type=mime))
                        except Exception:
                            pass
                    elif img_url:
                        try:
                            parts.append(types.Part.from_uri(file_uri=img_url, mime_type="image/jpeg"))
                        except Exception:
                            pass

        # Assistant messages carrying OpenAI-style tool_calls -> function_call parts.
        for tc in (m.get("tool_calls") or []):
            if not isinstance(tc, dict):
                continue
            fn = tc.get("function") or {}
            name = fn.get("name")
            if not name:
                continue
            call_id_to_name[tc.get("id")] = name
            args = fn.get("arguments")
            if isinstance(args, str):
                try:
                    args = json.loads(args) if args.strip() else {}
                except Exception:
                    args = {}
            elif not isinstance(args, dict):
                args = {}
            try:
                fc_part = types.Part.from_function_call(name=name, args=args)
                # Gemini 3.x requires a `thought_signature` on every replayed
                # function_call part (its own signed reasoning continuity
                # token) or it 400s the whole request. OpenAI-format callers
                # (Cline/Cursor/Continue) have no field to carry that opaque
                # signature back to us, so we can never legitimately have the
                # real one here. Google's own documented escape hatch for
                # exactly this situation is this literal sentinel string as
                # the (unencoded) signature bytes — it tells the API "trust
                # this call, skip signature validation" instead of rejecting.
                fc_part.thought_signature = b"skip_thought_signature_validator"
                parts.append(fc_part)
            except Exception:
                pass

        if parts:
            contents.append({"role": gemini_role, "parts": parts})

    system_instruction = "\n\n".join(p for p in system_parts if p) or None
    return system_instruction, contents


def _tools_to_gemini(tools):
    """OpenAI tool schema (list of {"type":"function","function":{...}}) ->
    a single google.genai.types.Tool with function declarations. OpenAI's
    `parameters` is already JSON Schema, so it maps straight onto
    FunctionDeclaration.parametersJsonSchema — no schema-object translation
    needed."""
    from google.genai import types
    decls = []
    for t in (tools or []):
        if not isinstance(t, dict):
            continue
        fn = t.get("function") or t
        name = fn.get("name")
        if not name:
            continue
        try:
            decls.append(types.FunctionDeclaration(
                name=name,
                description=fn.get("description") or "",
                parametersJsonSchema=fn.get("parameters") or {"type": "object", "properties": {}},
            ))
        except Exception as e:
            print(f"[Vertex] Skipping malformed tool schema for {name}: {e}")
    if not decls:
        return None
    return [types.Tool(functionDeclarations=decls)]


def _gemini_function_call_to_delta(fc, index):
    """A Gemini function_call part -> one OpenAI-style streamed tool_calls
    delta entry. Gemini hands back complete (non-fragmented) args, so this
    is emitted as a single whole-argument chunk rather than char-by-char."""
    import uuid as _uuid
    try:
        args = dict(fc.args) if fc.args else {}
    except Exception:
        args = {}
    return [{
        "index": index,
        "id": f"call_{_uuid.uuid4().hex[:24]}",
        "type": "function",
        "function": {"name": fc.name, "arguments": json.dumps(args)},
    }]


def call_vertex_gemini(messages, temperature=0.7, max_tokens=16384, stream=True,
                       model="gemini-3.1-pro-preview", tools=None, tool_choice=None,
                       expose_thinking=True, max_thinking=False, top_p=0.9,
                       reasoning_budget=None, reasoning_effort=None, is_pro=None,
                       read_timeout=None, json_mode=False):
    """Call Google Vertex AI (Gemini). Drop-in replacement for call_nvidia —
    same streaming-dict-yield contract:

      • `{"thinking": "<token>"}`   — a delta of the model's reasoning trace.
      • `{"chunk": "<token>"}`      — a delta of the final answer.
      • `{"thinking_done": True}`   — emitted once reasoning ends.
      • `{"tool_calls": [...]}`     — OpenAI-shaped tool-call deltas.
      • `{"_finish_reason": "length"}` — sentinel: truncated by max_tokens.

    Non-streaming calls return a plain string (or None on failure/no client).
    `reasoning_effort`/`is_pro` are accepted for interface parity with
    call_nvidia but unused here (Vertex has no key-rotation or per-provider
    effort string — thinking is controlled by max_thinking / reasoning_budget
    alone). `read_timeout` (seconds) DOES bound the real HTTP request via
    GenerateContentConfig.http_options — important for timing-critical
    callers (e.g. LiveKit post-call analysis right before shutdown).
    """
    if model_circuit_open(model):
        print(f"[Vertex] Circuit OPEN for {model} — skipping")
        return None

    client = _get_vertex_client()
    if client is None:
        return None

    cache_key = _hash_payload(messages, model, temperature, max_tokens, tools, tool_choice, top_p, reasoning_budget, reasoning_effort, json_mode)
    cached_val = _get_from_cache(cache_key)
    if cached_val is not None:
        res_type, res_data = cached_val
        if res_type == "stream":
            if stream:
                return generate_cached_stream(res_data, expose_thinking)
        else:
            if not stream:
                return res_data

    try:
        from google.genai import types
        system_instruction, contents = _messages_to_gemini(messages)
        if not contents:
            return None

        cfg_kwargs = {
            "temperature": temperature,
            "max_output_tokens": max_tokens,
            "top_p": top_p,
        }
        if system_instruction:
            cfg_kwargs["system_instruction"] = system_instruction
        cfg_kwargs["thinking_config"] = types.ThinkingConfig(
            include_thoughts=bool(max_thinking and expose_thinking),
            thinking_budget=(reasoning_budget or 8192) if max_thinking else 0,
        )
        gemini_tools = _tools_to_gemini(tools)
        if gemini_tools:
            cfg_kwargs["tools"] = gemini_tools
        if json_mode:
            cfg_kwargs["response_mime_type"] = "application/json"
        if read_timeout:
            # Bounds the actual HTTP socket read, not just the asyncio-level
            # await. Callers on a tight shutdown deadline (e.g. LiveKit's
            # post-call analysis, which SIGKILLs the whole worker if a
            # blocking thread outlives the room-teardown window) need the
            # underlying request itself to die on time — asyncio.wait_for()
            # alone only abandons the await, it can't kill an OS thread stuck
            # in a slow read.
            cfg_kwargs["http_options"] = types.HttpOptions(timeout=int(read_timeout * 1000))
        config = types.GenerateContentConfig(**cfg_kwargs)
    except Exception as e:
        print(f"[Vertex] Request build failed: {e}")
        return None

    _t0 = time.time()

    if stream:
        def generate():
            thinking_active = False
            collected_chunks = []
            has_tool_calls = False
            finish_reason = None
            tc_index = 0
            try:
                resp_stream = client.models.generate_content_stream(
                    model=model, contents=contents, config=config)
                for chunk in resp_stream:
                    cands = getattr(chunk, "candidates", None)
                    if not cands:
                        continue
                    cand = cands[0]
                    fr = getattr(cand, "finish_reason", None)
                    if fr:
                        finish_reason = str(fr)
                    content_obj = cand.content
                    if not content_obj or not content_obj.parts:
                        continue
                    for part in content_obj.parts:
                        fc = getattr(part, "function_call", None)
                        if fc and getattr(fc, "name", None):
                            has_tool_calls = True
                            delta = _gemini_function_call_to_delta(fc, tc_index)
                            tc_index += 1
                            collected_chunks.append({"tool_calls": delta})
                            yield {"tool_calls": delta}
                            continue
                        text = getattr(part, "text", None)
                        if not text:
                            continue
                        if getattr(part, "thought", False):
                            if expose_thinking:
                                thinking_active = True
                                collected_chunks.append({"thinking": text})
                                yield {"thinking": text}
                        else:
                            if thinking_active:
                                collected_chunks.append({"thinking_done": True})
                                yield {"thinking_done": True}
                                thinking_active = False
                            collected_chunks.append({"chunk": text})
                            yield {"chunk": text}

                if thinking_active:
                    collected_chunks.append({"thinking_done": True})
                    yield {"thinking_done": True}

                record_model_result(model, True, latency_ms=(time.time() - _t0) * 1000)

                truncated = bool(finish_reason and "MAX_TOKENS" in finish_reason.upper())
                if truncated:
                    yield {"_finish_reason": "length"}

                if not has_tool_calls and collected_chunks and not truncated:
                    _save_to_cache(cache_key, "stream", json.dumps(collected_chunks))
            except Exception as e:
                record_model_result(model, False, error=e)
                print(f"[Vertex] Streaming exception ({model}): {e}")
        return generate()
    else:
        try:
            resp = client.models.generate_content(model=model, contents=contents, config=config)
            record_model_result(model, True, latency_ms=(time.time() - _t0) * 1000)
            text = getattr(resp, "text", None) or ""
            if text:
                _save_to_cache(cache_key, "string", text)
            return text
        except Exception as e:
            record_model_result(model, False, error=e)
            print(f"[Vertex] Exception ({model}): {e}")
            return None


def call_openrouter(messages, temperature=0.7, max_tokens=16384, stream=True, model="qwen/qwen3-coder:free"):
    """Call OpenRouter API."""
    if not OPENROUTER_API_KEY:
        return None
    try:
        clean_messages = []
        for m in messages:
            content = m.get("content", "")
            if isinstance(content, list):
                clean_messages.append({"role": m["role"], "content": content})
            else:
                clean_messages.append({"role": m["role"], "content": str(content)})
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://jarvis-ai.onrender.com",
            "X-Title": "KAUTILYA AI Assistant",
            "Connection": "keep-alive",
        }
        if stream:
            headers["Accept-Encoding"] = "identity"
        resp = _OPENROUTER_SESSION.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json={"model": model, "messages": clean_messages, "temperature": temperature, "max_tokens": max_tokens, "stream": stream},
            timeout=(5, 60), stream=stream
        )
        if resp.status_code == 200:
            if stream:
                def generate():
                    for line in resp.iter_lines():
                        if line:
                            line = line.decode('utf-8')
                            if line.startswith('data: '):
                                try:
                                    json_str = line[6:]
                                    if json_str.strip() == '[DONE]':
                                        break
                                    data = json.loads(json_str)
                                    content = data["choices"][0].get("delta", {}).get("content")
                                    if content:
                                        yield {"chunk": content}
                                except:
                                    pass
                return generate()
            else:
                return resp.json()["choices"][0]["message"].get("content", "")
        else:
            print(f"[OpenRouter] Error {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        print(f"[OpenRouter] Failed: {e}")
    return None


# ==========================================
# Kautilya AI Heavy Caching Engine
# ==========================================
_db_lock = threading.Lock()
# Bounded LRU. Previously a plain dict that NEVER evicted — keyed by the full
# payload hash and holding entire response bodies, it grew without limit for
# every distinct prompt until the worker OOM'd. OrderedDict + a hard cap keeps
# the hot-path accelerator fast while bounding RSS; the SQLite table remains
# the durable cache, so an eviction just costs one disk read on the next hit.
from collections import OrderedDict
_IN_MEMORY_CACHE_MAX = int(os.environ.get("LLM_MEMCACHE_MAX", "500"))
_in_memory_cache = OrderedDict()
_mem_cache_lock = threading.Lock()
_cache_init_done = False


def _memcache_get(key):
    with _mem_cache_lock:
        if key in _in_memory_cache:
            _in_memory_cache.move_to_end(key)  # mark most-recently-used
            return _in_memory_cache[key]
    return None


def _memcache_put(key, value):
    with _mem_cache_lock:
        _in_memory_cache[key] = value
        _in_memory_cache.move_to_end(key)
        while len(_in_memory_cache) > _IN_MEMORY_CACHE_MAX:
            _in_memory_cache.popitem(last=False)  # evict least-recently-used

def _get_cache_db():
    import os
    db_path = os.path.join(CHAT_DATA_DIR, "llm_cache.db")
    conn = sqlite3.connect(db_path, timeout=15.0)
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
    except Exception:
        pass
    conn.execute("""
        CREATE TABLE IF NOT EXISTS nvidia_cache (
            cache_key TEXT PRIMARY KEY,
            response_type TEXT,
            response_data TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    return conn

def _init_cache_db_safe():
    global _cache_init_done
    if _cache_init_done:
        return True
    try:
        conn = _get_cache_db()
        conn.close()
        _cache_init_done = True
        return True
    except Exception as e:
        print(f"[NVIDIA Cache] SQLite initialization failed, using in-memory only: {e}")
        return False

def _get_from_cache(cache_key):
    cached = _memcache_get(cache_key)
    if cached is not None:
        print("[NVIDIA Cache] In-memory cache HIT!")
        return cached

    if not _init_cache_db_safe():
        return None

    try:
        with _db_lock:
            conn = _get_cache_db()
            cursor = conn.cursor()
            cursor.execute("SELECT response_type, response_data FROM nvidia_cache WHERE cache_key = ?", (cache_key,))
            row = cursor.fetchone()
            conn.close()
            if row:
                res_type, res_data = row
                print("[NVIDIA Cache] SQLite cache HIT!")
                if res_type == "stream":
                    parsed = json.loads(res_data)
                else:
                    parsed = res_data
                _memcache_put(cache_key, (res_type, parsed))
                return res_type, parsed
    except Exception as e:
        print(f"[NVIDIA Cache] Error reading cache: {e}")
    return None

def _save_to_cache(cache_key, response_type, response_data):
    try:
        _memcache_put(cache_key, (response_type, response_data if response_type == "string" else json.loads(response_data)))
    except Exception:
        pass
    
    if not _init_cache_db_safe():
        return
        
    try:
        with _db_lock:
            conn = _get_cache_db()
            conn.execute(
                "INSERT OR REPLACE INTO nvidia_cache (cache_key, response_type, response_data) VALUES (?, ?, ?)",
                (cache_key, response_type, response_data)
            )
            conn.commit()
            conn.close()
            print("[NVIDIA Cache] Saved to SQLite cache!")
    except Exception as e:
        print(f"[NVIDIA Cache] Error writing cache: {e}")

def _hash_payload(messages, model, temperature, max_tokens, tools, tool_choice, top_p, reasoning_budget, reasoning_effort, json_mode=False):
    try:
        payload = {
            "model": str(model),
            "messages": messages,
            "temperature": float(temperature) if temperature is not None else 0.7,
            "max_tokens": int(max_tokens) if max_tokens is not None else None,
            "tools": tools,
            "tool_choice": tool_choice,
            "top_p": float(top_p) if top_p is not None else 0.9,
            "reasoning_budget": reasoning_budget,
            "reasoning_effort": reasoning_effort,
            "json_mode": bool(json_mode),
        }
        payload_str = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(payload_str.encode('utf-8')).hexdigest()
    except Exception as e:
        print(f"[NVIDIA Cache] Error hashing payload: {e}")
        return hashlib.sha256(str(messages).encode('utf-8')).hexdigest()

def generate_cached_stream(chunks, expose_thinking=True):
    for chunk in chunks:
        if "thinking" in chunk and not expose_thinking:
            continue
        if "thinking_done" in chunk and not expose_thinking:
            continue
        yield chunk
        time.sleep(0.001)


# ==========================================
# Self-healing model mesh — per-model circuit breaker
# ==========================================
# Every upstream call records its outcome here. After N consecutive failures
# a model's circuit OPENS: callers skip it instantly (no 5s connect timeout
# burned per request) and their existing fallback chains kick in immediately.
# When the cooldown lapses the circuit half-opens — the next request probes
# the model and a single success snaps everything back to healthy.
# Live state is exposed at /api/health/llm.
_MODEL_HEALTH_LOCK = threading.Lock()
_MODEL_HEALTH = {}
_CB_FAILURE_THRESHOLD = max(1, int(os.environ.get("LLM_CB_FAILURE_THRESHOLD", "3")))
_CB_COOLDOWN_SECONDS = max(5, int(os.environ.get("LLM_CB_COOLDOWN_SECONDS", "45")))


def _health_entry(model):
    e = _MODEL_HEALTH.get(model)
    if e is None:
        e = {"consecutive_failures": 0, "cooldown_until": 0.0,
             "total_calls": 0, "total_failures": 0,
             "last_error": None, "last_latency_ms": None,
             "last_success_ts": None, "last_failure_ts": None}
        _MODEL_HEALTH[model] = e
    return e


def model_circuit_open(model):
    """True → model is cooling down after repeated failures: skip the call.
    Returns False again once the cooldown lapses (half-open probe)."""
    with _MODEL_HEALTH_LOCK:
        return time.time() < _health_entry(model)["cooldown_until"]


def record_model_result(model, ok, latency_ms=None, error=None):
    with _MODEL_HEALTH_LOCK:
        e = _health_entry(model)
        e["total_calls"] += 1
        now = time.time()
        if ok:
            e["consecutive_failures"] = 0
            e["cooldown_until"] = 0.0
            e["last_success_ts"] = now
            if latency_ms is not None:
                e["last_latency_ms"] = round(latency_ms)
        else:
            e["total_failures"] += 1
            e["consecutive_failures"] += 1
            e["last_failure_ts"] = now
            e["last_error"] = str(error)[:200] if error else None
            if e["consecutive_failures"] >= _CB_FAILURE_THRESHOLD:
                e["cooldown_until"] = now + _CB_COOLDOWN_SECONDS
                print(f"[ModelMesh] {model} circuit OPEN for {_CB_COOLDOWN_SECONDS}s "
                      f"({e['consecutive_failures']} consecutive failures; last: {e['last_error']})")


def llm_health_snapshot():
    """Read-only mesh state for /api/health/llm."""
    now = time.time()
    out = {}
    with _MODEL_HEALTH_LOCK:
        for model, e in _MODEL_HEALTH.items():
            cooling = now < e["cooldown_until"]
            out[model] = {
                "status": "cooling_down" if cooling else (
                    "degraded" if e["consecutive_failures"] > 0 else "healthy"),
                "consecutive_failures": e["consecutive_failures"],
                "cooldown_remaining_s": max(0, round(e["cooldown_until"] - now)) if cooling else 0,
                "total_calls": e["total_calls"],
                "total_failures": e["total_failures"],
                "last_latency_ms": e["last_latency_ms"],
                "last_error": e["last_error"],
            }
    return {
        "object": "llm.health",
        "circuit_breaker": {"failure_threshold": _CB_FAILURE_THRESHOLD,
                            "cooldown_seconds": _CB_COOLDOWN_SECONDS},
        "models": out,
    }

