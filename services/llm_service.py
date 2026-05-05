"""
Kautilya AI — LLM Service
Unified LLM call interface: Groq, NVIDIA NIM, OpenRouter, Gemini.
"""
import json
import time
import requests
from config import (
    GROQ_API_KEYS, GROQ_COOLDOWN_SECONDS,
    OPENROUTER_API_KEY, NVIDIA_API_KEY,
    GEMINI_API_KEYS,
)

# Groq key rotation state
_groq_key_index = 0
_groq_key_cooldowns = {}
_gemini_key_index = 0


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
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json",
                     "HTTP-Referer": "https://jarvis-ai.onrender.com", "X-Title": "KAUTILYA AI Assistant"},
            json={"model": model, "messages": clean_messages, "temperature": temperature, "max_tokens": max_tokens, "stream": stream},
            timeout=60, stream=stream
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


def call_nvidia(messages, temperature=0.7, max_tokens=16384, stream=True,
                model="nvidia/nemotron-3-super-120b-a12b", tools=None, tool_choice=None,
                expose_thinking=True, max_thinking=False, top_p=0.9,
                reasoning_budget=None):
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
    if not NVIDIA_API_KEY:
        return None
    try:
        clean_messages = []
        for m in messages:
            content = m.get("content", "")
            if isinstance(content, list):
                text_parts = [p["text"] for p in content if p.get("type") == "text"]
                content = "\n".join(text_parts)
            clean_messages.append({"role": m["role"], "content": str(content)})
        payload = {"model": model, "messages": clean_messages, "temperature": temperature,
                   "max_tokens": max_tokens, "top_p": top_p, "stream": stream}
        if tools:
            payload["tools"] = tools
        if tool_choice:
            payload["tool_choice"] = tool_choice
        model_lower = model.lower()
        # Nemotron uses `enable_thinking`; DeepSeek-v4 uses `thinking`.
        if "nemotron" in model_lower:
            payload["chat_template_kwargs"] = {"enable_thinking": bool(max_thinking)}
            if max_thinking:
                payload["reasoning_budget"] = reasoning_budget or 16384
            else:
                payload["reasoning_budget"] = reasoning_budget or 1024
        elif "deepseek" in model_lower:
            payload["chat_template_kwargs"] = {"thinking": bool(max_thinking)}
            if max_thinking and reasoning_budget:
                payload["reasoning_budget"] = reasoning_budget
        resp = requests.post(
            "https://integrate.api.nvidia.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {NVIDIA_API_KEY}",
                     "Accept": "text/event-stream" if stream else "application/json",
                     "Content-Type": "application/json"},
            json=payload, timeout=600, stream=stream
        )
        if resp.status_code == 200:
            if stream:
                def generate():
                    try:
                        thinking_active = False
                        for line in resp.iter_lines():
                            if not line:
                                continue
                            line = line.decode('utf-8')
                            if not line.startswith('data: '):
                                continue
                            json_str = line[6:]
                            if json_str.strip() == '[DONE]':
                                if thinking_active:
                                    yield {"thinking_done": True}
                                break
                            try:
                                data = json.loads(json_str)
                                delta = data["choices"][0].get("delta", {})
                            except Exception:
                                continue

                            reasoning = delta.get("reasoning_content")
                            if reasoning:
                                if expose_thinking:
                                    thinking_active = True
                                    yield {"thinking": reasoning}
                                # Always 'continue' — never mix reasoning into chunks
                                continue

                            if "tool_calls" in delta:
                                yield {"tool_calls": delta["tool_calls"]}
                                continue

                            content = delta.get("content")
                            if content:
                                if thinking_active:
                                    # Reasoning is over — let the UI collapse the
                                    # thinking bubble before content tokens start.
                                    yield {"thinking_done": True}
                                    thinking_active = False
                                yield {"chunk": content}
                    finally:
                        resp.close()
                return generate()
            else:
                return resp.json()["choices"][0]["message"].get("content", "")
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
                    continue
            else:
                text_parts = [p["text"] for p in content if p.get("type") == "text"]
                combined_text = "\n".join(text_parts).strip()
                if combined_text:
                    new_m["content"] = combined_text
                else:
                    continue
        else:
            new_m["content"] = content
        if new_m.get("content"):
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
                       "max_tokens": max_tokens, "stream": stream}
            if stream:
                payload["stream_options"] = {"include_usage": True}
            if tools:
                payload["tools"] = tools
            if tool_choice:
                payload["tool_choice"] = tool_choice
            resp = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload, timeout=120, stream=stream
            )
            if resp.status_code == 200:
                print(f"[Groq] Success with {key_label} (model: {model})")
                if not stream:
                    msg = resp.json()["choices"][0]["message"]
                    if tools:
                        return {"content": msg.get("content", ""), "tool_calls": msg.get("tool_calls")}
                    return msg.get("content", "")

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
                                    usage = data.get("usage")
                                    if usage:
                                        yield {"usage": usage}
                                        continue
                                    content = data["choices"][0]["delta"].get("content", "")
                                    if content:
                                        yield {"chunk": content}
                                    tool_calls = data["choices"][0]["delta"].get("tool_calls")
                                    if tool_calls:
                                        yield {"tool_calls": tool_calls}
                                except GeneratorExit:
                                    return
                                except Exception:
                                    pass
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
