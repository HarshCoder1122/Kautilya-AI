"""
Kautilya AI — LLM Service
Unified LLM call interface: Groq, NVIDIA NIM, OpenRouter, Gemini.
"""
import json
import time
import requests
import sqlite3
import hashlib
import threading
from requests.adapters import HTTPAdapter
from config import (
    GROQ_API_KEYS, GROQ_COOLDOWN_SECONDS,
    OPENROUTER_API_KEY, NVIDIA_API_KEY,
    NVIDIA_API_KEYS,
    GEMINI_API_KEYS,
    CHAT_DATA_DIR,
)

# Groq key rotation state
_groq_key_index = 0
_groq_key_cooldowns = {}
_gemini_key_index = 0


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


# Shared session — module-level so all NVIDIA calls reuse the same TLS pool.
_NVIDIA_SESSION = _make_pooled_session()
_GROQ_SESSION = _make_pooled_session()
_OPENROUTER_SESSION = _make_pooled_session()

# NVIDIA key rotation state
_nvidia_key_index = 0
_nvidia_key_cooldowns = {}

# NVIDIA key rotation function
def _get_available_nvidia_key():
    global _nvidia_key_index
    if not NVIDIA_API_KEYS:
        return None
    # Simple round-robin rotation
    key = NVIDIA_API_KEYS[_nvidia_key_index % len(NVIDIA_API_KEYS)]
    _nvidia_key_index = (_nvidia_key_index + 1) % len(NVIDIA_API_KEYS)
    return key


def _prewarm_nvidia():
    """Open a TLS connection to NVIDIA at module import so the first real
    user request doesn't pay the 200-400ms handshake. Fire-and-forget on
    a daemon thread — if it fails, real calls still work."""
    import threading
    def _go():
        try:
            _NVIDIA_SESSION.head("https://integrate.api.nvidia.com/v1/models",
                                 timeout=(2, 3))
        except Exception:
            pass
    threading.Thread(target=_go, daemon=True).start()

_prewarm_nvidia()


def get_gemini_key():
    global _gemini_key_index
    if not GEMINI_API_KEYS:
        return None
    key = GEMINI_API_KEYS[_gemini_key_index % len(GEMINI_API_KEYS)]
    _gemini_key_index += 1
    return key


def _get_available_groq_key():
    global _groq_key_index, _groq_key_cooldowns
    if not GROQ_API_KEYS:
        return None, -1
    now = time.time()
    _groq_key_cooldowns = {k: v for k, v in _groq_key_cooldowns.items() if v > now}
    for attempt in range(len(GROQ_API_KEYS)):
        idx = (_groq_key_index + attempt) % len(GROQ_API_KEYS)
        if idx not in _groq_key_cooldowns:
            _groq_key_index = (idx + 1) % len(GROQ_API_KEYS)
            return GROQ_API_KEYS[idx], idx
    soonest_idx = min(_groq_key_cooldowns, key=_groq_key_cooldowns.get)
    print(f"[Groq] All {len(GROQ_API_KEYS)} keys rate-limited. Soonest recovery: {int(_groq_key_cooldowns[soonest_idx] - now)}s")
    return None, -1


def _mark_groq_key_exhausted(key_index):
    global _groq_key_cooldowns
    _groq_key_cooldowns[key_index] = time.time() + GROQ_COOLDOWN_SECONDS
    print(f"[Groq] Key #{key_index + 1} rate-limited. Cooldown: {GROQ_COOLDOWN_SECONDS}s")


def call_gemini_vision(messages, temperature=0.7, max_tokens=4096):
    """Call Gemini API for vision/image analysis."""
    api_key = get_gemini_key()
    if not api_key:
        return None
    gemini_contents = []
    for m in messages:
        role = "user" if m["role"] in ["user", "system"] else "model"
        content = m.get("content")
        if isinstance(content, list):
            parts = []
            for part in content:
                if part.get("type") == "text":
                    parts.append({"text": part["text"]})
                elif part.get("type") == "image_url":
                    img_url = part["image_url"]["url"]
                    if img_url.startswith("data:"):
                        header, b64data = img_url.split(",", 1)
                        mime = header.split(":")[1].split(";")[0]
                        parts.append({"inline_data": {"mime_type": mime, "data": b64data}})
            gemini_contents.append({"role": role, "parts": parts})
        elif isinstance(content, str) and content.strip():
            gemini_contents.append({"role": role, "parts": [{"text": content}]})
    if not gemini_contents:
        return None
    for attempt in range(len(GEMINI_API_KEYS)):
        try:
            resp = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}",
                headers={"Content-Type": "application/json"},
                json={"contents": gemini_contents, "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens}},
                timeout=60
            )
            if resp.status_code == 200:
                data = resp.json()
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    text_parts = [p["text"] for p in parts if "text" in p]
                    return "\n".join(text_parts) if text_parts else None
                return None
            elif resp.status_code == 429:
                api_key = get_gemini_key()
            else:
                print(f"[Gemini] Error {resp.status_code}: {resp.text[:200]}")
                return None
        except Exception as e:
            print(f"[Gemini] Exception: {e}")
            return None
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
_in_memory_cache = {}
_cache_init_done = False

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
    if cache_key in _in_memory_cache:
        print("[NVIDIA Cache] In-memory cache HIT!")
        return _in_memory_cache[cache_key]
    
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
                _in_memory_cache[cache_key] = (res_type, parsed)
                return res_type, parsed
    except Exception as e:
        print(f"[NVIDIA Cache] Error reading cache: {e}")
    return None

def _save_to_cache(cache_key, response_type, response_data):
    try:
        _in_memory_cache[cache_key] = (response_type, response_data if response_type == "string" else json.loads(response_data))
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

def _hash_payload(messages, model, temperature, max_tokens, tools, tool_choice, top_p, reasoning_budget, reasoning_effort):
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
            "reasoning_effort": reasoning_effort
        }
        payload_str = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(payload_str.encode('utf-8')).hexdigest()
    except Exception as e:
        print(f"[NVIDIA Cache] Error hashing payload: {e}")
        return hashlib.sha256(str(messages).encode('utf-8')).hexdigest()

def _hash_groq_payload(messages, model, temperature, max_tokens, tools, tool_choice):
    try:
        payload = {
            "model": str(model),
            "messages": messages,
            "temperature": float(temperature) if temperature is not None else 0.7,
            "max_tokens": int(max_tokens) if max_tokens is not None else None,
            "tools": tools,
            "tool_choice": tool_choice
        }
        payload_str = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(payload_str.encode('utf-8')).hexdigest()
    except Exception as e:
        print(f"[Groq Cache] Error hashing payload: {e}")
        return hashlib.sha256(str(messages).encode('utf-8')).hexdigest()

def generate_cached_stream(chunks, expose_thinking=True):
    for chunk in chunks:
        if "thinking" in chunk and not expose_thinking:
            continue
        if "thinking_done" in chunk and not expose_thinking:
            continue
        yield chunk
        time.sleep(0.001)


def call_nvidia(messages, temperature=0.7, max_tokens=16384, stream=True,
                model="nvidia/nemotron-3-super-120b-a12b", tools=None, tool_choice=None,
                expose_thinking=True, max_thinking=False, top_p=0.9,
                reasoning_budget=None, reasoning_effort=None):
    """Call NVIDIA NIM API with tool support.

    Streaming protocol:
      • `{"thinking": "<token>"}` — a delta of the model's reasoning trace.
        The frontend renders these into a Gemini-style collapsible
        "Thinking…" bubble that updates live as tokens arrive.
      • `{"chunk": "<token>"}`   — a delta of the final answer (content).
      • `{"thinking_done": True}` — emitted once when reasoning ends and
        the model starts emitting actual content. The UI uses this to
        collapse the thinking bubble and switch focus to the answer.

    Pass `expose_thinking=False` to silently drop reasoning deltas (useful
    for non-chat call sites such as post-call NIM analysis where we just
    want a final string).
    """
    if not NVIDIA_API_KEYS:
        return None

    # Compute cache key and check Kautilya Heavy Caching Engine
    cache_key = _hash_payload(messages, model, temperature, max_tokens, tools, tool_choice, top_p, reasoning_budget, reasoning_effort)
    cached_val = _get_from_cache(cache_key)
    if cached_val is not None:
        res_type, res_data = cached_val
        if res_type == "stream":
            if stream:
                return generate_cached_stream(res_data, expose_thinking=expose_thinking)
            else:
                full_text = ""
                for chunk in res_data:
                    if "chunk" in chunk:
                        full_text += chunk["chunk"]
                return full_text
        else:
            if stream:
                def _stream_str():
                    yield {"chunk": res_data}
                return _stream_str()
            else:
                return res_data

    try:
        clean_messages = []
        has_dropped_image = False
        for m in messages:
            content = m.get("content", "")
            if isinstance(content, list):
                text_parts = [p["text"] for p in content if p.get("type") == "text"]
                # If user attached an image, NVIDIA's text-only endpoints can't
                # see it — surface that fact to the model rather than silently
                # losing it.
                if any(p.get("type") == "image_url" for p in content):
                    has_dropped_image = True
                    text_parts.append("[NOTE: An image was attached but this model is text-only. "
                                      "Tell the user the image is unavailable on this tier and "
                                      "suggest they retry — vision routing will pick a vision model.]")
                content = "\n".join(text_parts)
            # Preserve the OpenAI tool-use schema: assistant messages may
            # carry `tool_calls`, tool messages carry `tool_call_id`, named
            # function messages carry `name`. Previously we kept only
            # role+content — that wiped tool-call history, so Cline / any
            # coding agent's follow-up tool turns saw "tool result" with no
            # link to the call that produced it. Result: model refuses to
            # continue or hallucinates a different call. Now we forward the
            # full envelope and let the upstream model decide.
            entry = {"role": m["role"]}
            # Content can legitimately be None for assistant-with-tool_calls
            # turns — only stringify when actually present.
            if content is not None and content != "":
                entry["content"] = str(content) if not isinstance(content, (list, dict)) else content
            else:
                # OpenAI permits null content on assistant tool-call turns.
                entry["content"] = None if m.get("tool_calls") else ""
            for k in ("tool_calls", "tool_call_id", "name"):
                if m.get(k) is not None:
                    entry[k] = m[k]
            clean_messages.append(entry)
        if has_dropped_image:
            print(f"[NVIDIA] Image dropped — model {model} is text-only")
        payload = {"model": model, "messages": clean_messages, "temperature": temperature,
                   "top_p": top_p, "stream": stream}
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if tools:
            payload["tools"] = tools
        if tool_choice:
            payload["tool_choice"] = tool_choice
        # Extended thinking — payload shape depends on model family.
        # GLM (z-ai/glm-*) uses {enable_thinking, clear_thinking}; thinking is
        # always-on when expose_thinking is true since GLM has no budget knob.
        # Qwen3/Nemotron use {thinking: {type, budget_tokens}} and only enable
        # when a budget is explicitly requested.
        if expose_thinking:
            if model.startswith("z-ai/glm"):
                payload["chat_template_kwargs"] = {"enable_thinking": True, "clear_thinking": False}
            elif reasoning_budget and reasoning_budget > 0:
                payload["chat_template_kwargs"] = {"thinking": {"type": "enabled", "budget_tokens": reasoning_budget}}
        # Mistral-style top-level reasoning toggle (low|medium|high)
        if reasoning_effort:
            payload["reasoning_effort"] = reasoning_effort
        # Latency optimizations:
        #   • Shared Session keeps TLS handshake amortized across calls
        #   • Accept-Encoding: identity → no gzip buffering on the SSE stream
        #     (gzip would batch tokens until enough bytes accumulate for a frame)
        #   • Connection: keep-alive lets urllib3 hold the socket open
        #   • Lower connect timeout fails fast if NVIDIA edge is dead
        # Get available NVIDIA key using rotation
        nvidia_api_key = _get_available_nvidia_key() or NVIDIA_API_KEY
        headers = {
            "Authorization": f"Bearer {nvidia_api_key}",
            "Content-Type": "application/json",
            "Connection": "keep-alive",
        }
        if stream:
            headers["Accept"] = "text/event-stream"
            headers["Accept-Encoding"] = "identity"
        else:
            headers["Accept"] = "application/json"
        resp = _NVIDIA_SESSION.post(
            "https://integrate.api.nvidia.com/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=(5, 3600),  # (connect, read) — fail fast on connect, no timeout on streaming reads
            stream=stream,
        )
        if resp.status_code == 200:
            print(f"[NVIDIA] Success (model: {model})")
            if stream:
                def generate():
                    try:
                        thinking_active = False
                        collected_chunks = []
                        has_tool_calls = False
                        finish_reason = None
                        for line in resp.iter_lines():
                            if not line:
                                continue
                            line = line.decode('utf-8', errors='replace')
                            if not line.startswith('data: '):
                                continue
                            json_str = line[6:]
                            if json_str.strip() == '[DONE]':
                                if thinking_active:
                                    collected_chunks.append({"thinking_done": True})
                                    yield {"thinking_done": True}
                                break
                            try:
                                data = json.loads(json_str)
                                choices = data.get("choices", [])
                                if not choices: continue
                                delta = choices[0].get("delta", {})
                                # Capture finish_reason — "length" means max_tokens
                                # was hit and the answer was truncated mid-flight.
                                fr = choices[0].get("finish_reason")
                                if fr:
                                    finish_reason = fr
                            except Exception:
                                continue

                            reasoning = delta.get("reasoning_content")
                            if reasoning:
                                if expose_thinking:
                                    thinking_active = True
                                    collected_chunks.append({"thinking": reasoning})
                                    yield {"thinking": reasoning}
                                continue

                            if "tool_calls" in delta:
                                has_tool_calls = True
                                collected_chunks.append({"tool_calls": delta["tool_calls"]})
                                yield {"tool_calls": delta["tool_calls"]}
                                continue

                            content = delta.get("content")
                            if content is not None:
                                if thinking_active:
                                    collected_chunks.append({"thinking_done": True})
                                    yield {"thinking_done": True}
                                    thinking_active = False
                                collected_chunks.append({"chunk": content})
                                yield {"chunk": content}

                        # Surface mid-stream truncation so the agent loop can
                        # auto-continue with a bigger budget. Sentinel only —
                        # NOT cached (the cached stream should be the complete
                        # one after the continuation merges in).
                        if finish_reason == "length":
                            yield {"_finish_reason": "length"}

                        # Save successful non-tool, non-truncated generation
                        # to cache. Truncated streams would poison the cache
                        # with cut-off answers on the next identical request.
                        if (not has_tool_calls
                                and collected_chunks
                                and finish_reason != "length"):
                            _save_to_cache(cache_key, "stream", json.dumps(collected_chunks))
                    finally:
                        resp.close()
                return generate()
            else:
                content = resp.json()["choices"][0]["message"].get("content", "")
                if content:
                    _save_to_cache(cache_key, "string", content)
                return content
        else:
            print(f"[NVIDIA] Error {resp.status_code}: {resp.text[:200]}")
            return None
    except Exception as e:
        print(f"[NVIDIA] Exception: {e}")
        return None


def call_groq(messages, temperature=0.7, max_tokens=4096, stream=False,
              model="llama-3.3-70b-versatile", tools=None, tool_choice=None):
    """Call Groq API with automatic multi-key rotation and 429 handling."""
    if not GROQ_API_KEYS:
        return None

    # Compute cache key and check Kautilya Heavy Caching Engine
    cache_key = _hash_groq_payload(messages, model, temperature, max_tokens, tools, tool_choice)
    cached_val = _get_from_cache(cache_key)
    if cached_val is not None:
        res_type, res_data = cached_val
        if res_type == "stream":
            if stream:
                return generate_cached_stream(res_data)
            else:
                full_text = ""
                for chunk in res_data:
                    if "chunk" in chunk:
                        full_text += chunk["chunk"]
                if tools:
                    return {"content": full_text, "tool_calls": None}
                return full_text
        else:
            if stream:
                def _stream_str():
                    yield {"chunk": res_data}
                return _stream_str()
            else:
                if tools:
                    return {"content": res_data, "tool_calls": None}
                return res_data

    is_vision = "vision" in model.lower() or "scout" in model.lower()
    clean_messages = []
    image_count = 0
    MAX_IMAGES = 2
    for m in reversed(messages):
        content = m.get("content")
        new_m = {"role": m["role"]}
        if isinstance(content, list):
            if is_vision:
                new_content = []
                for p in content:
                    if p.get("type") == "image_url":
                        if image_count < MAX_IMAGES:
                            new_content.append(p)
                            image_count += 1
                    else:
                        new_content.append(p)
                if new_content:
                    new_m["content"] = new_content
            else:
                text_parts = [p["text"] for p in content if p.get("type") == "text"]
                combined_text = "\n".join(text_parts).strip()
                if combined_text:
                    new_m["content"] = combined_text
        elif content is not None:
            new_m["content"] = content
        # Preserve tool-protocol fields so multi-turn tool-use conversations
        # (Cline / Cursor / Continue) actually thread correctly upstream.
        # Without these, an assistant tool-call turn would arrive at Groq
        # with no `tool_calls` and the matching tool-result turn would arrive
        # with no `tool_call_id` — the model can't reconcile them.
        for k in ("tool_calls", "tool_call_id", "name"):
            if m.get(k) is not None:
                new_m[k] = m[k]
        # Keep a message if it has content OR carries tool-protocol data
        # (assistant turns with only tool_calls are legitimate; tool turns
        # without content are not, but we keep them so the upstream can
        # reject explicitly rather than have us silently swallow them).
        if new_m.get("content") or new_m.get("tool_calls") or new_m["role"] == "tool":
            # OpenAI allows null content on assistant tool-call turns.
            if "content" not in new_m and new_m.get("tool_calls"):
                new_m["content"] = None
            clean_messages.append(new_m)
    clean_messages.reverse()
    if not clean_messages:
        return None
    tried_keys = 0
    while tried_keys < len(GROQ_API_KEYS):
        api_key, key_idx = _get_available_groq_key()
        if api_key is None:
            return None
        tried_keys += 1
        key_label = f"Key#{key_idx + 1}"
        try:
            payload = {"model": model, "messages": clean_messages, "temperature": temperature,
                       "stream": stream}
            
            # Use max_completion_tokens only for O1 models
            if "o1-" in model:
                if max_tokens is not None:
                    payload["max_completion_tokens"] = max_tokens
                payload["reasoning_effort"] = "medium"
            else:
                if max_tokens is not None:
                    payload["max_tokens"] = max_tokens

            if stream:
                payload["stream_options"] = {"include_usage": True}
            if tools:
                payload["tools"] = tools
            if tool_choice:
                payload["tool_choice"] = tool_choice
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Connection": "keep-alive",
            }
            if stream:
                headers["Accept-Encoding"] = "identity"
            resp = _GROQ_SESSION.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers=headers,
                json=payload, timeout=(5, 3600), stream=stream
            )
            if resp.status_code == 200:
                is_classifier = max_tokens <= 20 and stream is False if max_tokens else False
                tag = "[Classifier]" if is_classifier else "[Groq]"
                print(f"{tag} Success with {key_label} (model: {model})")
                if not stream:
                    msg = resp.json()["choices"][0]["message"]
                    content = msg.get("content", "")
                    t_calls = msg.get("tool_calls")
                    if tools:
                        if not t_calls and content:
                            _save_to_cache(cache_key, "string", content)
                        return {"content": content, "tool_calls": t_calls}
                    if content:
                        _save_to_cache(cache_key, "string", content)
                    return content

                def generate():
                    collected_chunks = []
                    has_tool_calls = False
                    finish_reason = None
                    for line in resp.iter_lines():
                        if line:
                            line = line.decode('utf-8')
                            if line.startswith('data: '):
                                try:
                                    json_str = line[6:]
                                    if json_str.strip() == '[DONE]':
                                        break
                                    data = json.loads(json_str)
                                    usage = data.get("usage")
                                    if usage:
                                        yield {"usage": usage}
                                        continue
                                    choice = data["choices"][0]
                                    fr = choice.get("finish_reason")
                                    if fr:
                                        finish_reason = fr
                                    content = choice["delta"].get("content", "")
                                    if content:
                                        collected_chunks.append({"chunk": content})
                                        yield {"chunk": content}
                                    tool_calls = choice["delta"].get("tool_calls")
                                    if tool_calls:
                                        has_tool_calls = True
                                        collected_chunks.append({"tool_calls": tool_calls})
                                        yield {"tool_calls": tool_calls}
                                except GeneratorExit:
                                    return
                                except Exception:
                                    pass
                    if finish_reason == "length":
                        yield {"_finish_reason": "length"}
                    # Don't cache truncated answers — they'd serve cut-off
                    # responses to identical follow-up prompts.
                    if (not has_tool_calls
                            and collected_chunks
                            and finish_reason != "length"):
                        _save_to_cache(cache_key, "stream", json.dumps(collected_chunks))
                return generate()
            elif resp.status_code == 429:
                _mark_groq_key_exhausted(key_idx)
                continue
            elif resp.status_code == 400:
                print(f"[Groq] {key_label} Bad Request (400): {resp.text[:200]}")
                return None
            else:
                print(f"[Groq] {key_label} Error {resp.status_code}: {resp.text[:200]}")
                if resp.status_code >= 500:
                    continue
                return None
        except requests.exceptions.Timeout:
            print(f"[Groq] {key_label} Timeout. Trying next key...")
            continue
        except Exception as e:
            print(f"[Groq] {key_label} Failed: {e}")
            return None
    print(f"[Groq] All {tried_keys} key attempts exhausted")
    return None
