"""
Kautilya AI — OpenAI-compatible proxy endpoints.

Exposes `/v1/models` and `/v1/chat/completions` so external tools (Cline,
Continue, Cursor, OpenAI SDK clients, LiteLLM) can talk to Kautilya as if
it were an OpenAI-compatible provider.

Auth: `Authorization: Bearer kautilya-...` — the same API keys issued
by /api/keys/create. The master KAUTILYA_API_KEY also works.

Under the hood requests are forwarded to NVIDIA NIM with the appropriate
Kautilya model mapping and thinking-toggle logic:

    kautilya-coder  → deepseek-ai/deepseek-v4-pro
    kautilya-pro    → nvidia/nemotron-3-super-120b-a12b
    kautilya-daily  → (falls back to Groq llama-3.3-70b-versatile)

Requests may also pass the raw NVIDIA model id directly.
The `max_thinking` toggle can be requested via:
  - `extra_body.max_thinking: true`
  - `extra_body.chat_template_kwargs.enable_thinking: true`  (nemotron)
  - `extra_body.chat_template_kwargs.thinking: true`         (deepseek)
"""
import json
import time
import uuid
import requests

from flask import Blueprint, request, jsonify, Response

from config import NVIDIA_API_KEY
from services.auth_service import verify_api_key, record_usage
from services.llm_service import call_groq

openai_compat_bp = Blueprint('openai_compat', __name__)


# ---------- model registry ----------
KAUTILYA_MODEL_MAP = {
    "kautilya-coder":   "deepseek-ai/deepseek-v4-pro",
    "kautilya-pro":     "nvidia/nemotron-3-super-120b-a12b",
    "kautilya-daily":   "llama-3.3-70b-versatile",  # Groq
    # Raw passthroughs
    "deepseek-ai/deepseek-v4-pro":        "deepseek-ai/deepseek-v4-pro",
    "nvidia/nemotron-3-super-120b-a12b":  "nvidia/nemotron-3-super-120b-a12b",
}

PUBLIC_MODELS = [
    {"id": "kautilya-coder",  "object": "model", "owned_by": "kautilya",
     "description": "DeepSeek V4 Pro — frontier code generation, 128k context, toggleable thinking."},
    {"id": "kautilya-pro",    "object": "model", "owned_by": "kautilya",
     "description": "Nemotron-3 Super 120B — strategic reasoning + Indian-context tuning."},
    {"id": "kautilya-daily",  "object": "model", "owned_by": "kautilya",
     "description": "Llama 3.3 70B — fast general chat, optimized for low latency."},
]


def _auth():
    """Verify bearer API key. Returns dict with uid/is_pro or None."""
    return verify_api_key()


@openai_compat_bp.route('/v1/models', methods=['GET'])
def list_models():
    if not _auth():
        return jsonify({"error": {"message": "Invalid API key", "type": "authentication_error"}}), 401
    now = int(time.time())
    data = [{**m, "created": now} for m in PUBLIC_MODELS]
    return jsonify({"object": "list", "data": data})


@openai_compat_bp.route('/v1/chat/completions', methods=['POST'])
def chat_completions():
    key_info = _auth()
    if not key_info:
        return jsonify({"error": {"message": "Invalid API key", "type": "authentication_error"}}), 401

    uid = key_info.get('uid')
    body = request.get_json(silent=True) or {}
    requested_model = body.get('model') or 'kautilya-pro'
    upstream_model = KAUTILYA_MODEL_MAP.get(requested_model, requested_model)

    messages = body.get('messages') or []
    if not messages:
        return jsonify({"error": {"message": "messages is required", "type": "invalid_request_error"}}), 400

    stream = bool(body.get('stream', False))
    temperature = body.get('temperature', 0.7)
    top_p = body.get('top_p', 0.95)
    max_tokens = body.get('max_tokens', 16384)
    tools = body.get('tools')
    tool_choice = body.get('tool_choice')

    # Thinking toggle resolution
    extra = body.get('extra_body') or {}
    ctk = extra.get('chat_template_kwargs') or body.get('chat_template_kwargs') or {}
    max_thinking = bool(
        extra.get('max_thinking')
        or body.get('max_thinking')
        or ctk.get('enable_thinking')
        or ctk.get('thinking')
    )
    reasoning_budget = extra.get('reasoning_budget') or body.get('reasoning_budget')

    print(f"[OpenAI Compat] {requested_model} → {upstream_model} | stream={stream} | uid={uid}")

    # ---- Groq path for daily / llama models ----
    if 'llama' in upstream_model.lower() and 'nemotron' not in upstream_model.lower():
        gen = call_groq(messages, stream=stream, model=upstream_model,
                        temperature=temperature, max_tokens=max_tokens,
                        tools=tools, tool_choice=tool_choice)
        if gen is None:
            print(f"[OpenAI Compat] Groq returned None for {upstream_model}")
            return jsonify({"error": {"message": "Upstream unavailable — Groq keys exhausted or model error", "type": "upstream_error"}}), 503
        if not stream:
            # gen can be a str (plain content) or dict (when tools are used)
            if isinstance(gen, str):
                content = gen
                tool_calls_out = None
            elif isinstance(gen, dict):
                content = gen.get("content") or ""
                tool_calls_out = gen.get("tool_calls")
            else:
                content = ""
                tool_calls_out = None
            envelope = _openai_completion_envelope(requested_model, content, tool_calls=tool_calls_out)
            print(f"[OpenAI Compat] Non-stream response: {len(content)} chars")
            return jsonify(envelope)

        def sse():
            cid = f"chatcmpl-{uuid.uuid4().hex[:24]}"
            created = int(time.time())
            first = True
            full = ""
            for chunk in gen:
                piece = chunk if isinstance(chunk, str) else (chunk.get('chunk') if isinstance(chunk, dict) else "")
                if not piece:
                    continue
                full += piece
                delta = {"content": piece}
                if first:
                    delta["role"] = "assistant"
                    first = False
                yield _openai_stream_chunk(cid, created, requested_model, delta)
            yield _openai_stream_chunk(cid, created, requested_model, {}, finish_reason="stop")
            yield "data: [DONE]\n\n"
            if uid and full:
                try:
                    record_usage(uid, 'llm_tokens', max(1, (len(full) + sum(len(str(m.get('content',''))) for m in messages)) // 4), model=requested_model)
                except Exception:
                    pass

        return Response(sse(), mimetype='text/event-stream',
                        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})

    # ---- NVIDIA path (deepseek / nemotron) ----
    if not NVIDIA_API_KEY:
        return jsonify({"error": {"message": "NVIDIA backend not configured", "type": "upstream_error"}}), 503

    clean_messages = []
    for m in messages:
        content = m.get('content', '')
        if isinstance(content, list):
            text_parts = [p.get('text', '') for p in content if isinstance(p, dict) and p.get('type') == 'text']
            content = "\n".join(text_parts)
        clean_messages.append({"role": m.get('role', 'user'), "content": str(content)})

    payload = {
        "model": upstream_model,
        "messages": clean_messages,
        "temperature": temperature,
        "top_p": top_p,
        "max_tokens": max_tokens,
        "stream": stream,
    }
    if tools:
        payload["tools"] = tools
    if tool_choice:
        payload["tool_choice"] = tool_choice

    mlow = upstream_model.lower()
    if 'nemotron' in mlow:
        payload["chat_template_kwargs"] = {"enable_thinking": bool(max_thinking)}
        payload["reasoning_budget"] = reasoning_budget or (16384 if max_thinking else 1024)
    elif 'deepseek' in mlow:
        payload["chat_template_kwargs"] = {"thinking": bool(max_thinking)}
        if max_thinking and reasoning_budget:
            payload["reasoning_budget"] = reasoning_budget

    headers = {
        "Authorization": f"Bearer {NVIDIA_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream" if stream else "application/json",
    }

    try:
        upstream = requests.post(
            "https://integrate.api.nvidia.com/v1/chat/completions",
            headers=headers, json=payload, timeout=600, stream=stream,
        )
    except Exception as e:
        return jsonify({"error": {"message": f"Upstream error: {e}", "type": "upstream_error"}}), 502

    if upstream.status_code != 200:
        detail = upstream.text[:500]
        return jsonify({"error": {"message": f"Upstream {upstream.status_code}: {detail}",
                                   "type": "upstream_error"}}), upstream.status_code

    if not stream:
        data = upstream.json()
        try:
            data["model"] = requested_model  # present Kautilya id to caller
        except Exception:
            pass
        if uid:
            try:
                usage = data.get('usage') or {}
                total = int(usage.get('total_tokens') or 0)
                if total:
                    record_usage(uid, 'llm_tokens', total, model=requested_model)
            except Exception:
                pass
        return jsonify(data)

    # streaming — forward SSE with minimal rewriting (hide upstream model id)
    def passthrough():
        full_text = ""
        try:
            for raw in upstream.iter_lines():
                if not raw:
                    # preserve SSE empty separator lines
                    yield "\n"
                    continue
                line = raw.decode('utf-8', errors='replace')
                if not line.startswith('data: '):
                    yield line + "\n"
                    continue
                json_str = line[6:]
                if json_str.strip() == '[DONE]':
                    yield "data: [DONE]\n\n"
                    break
                try:
                    obj = json.loads(json_str)
                    obj['model'] = requested_model
                    # track chunk text for usage estimation
                    try:
                        d = obj.get('choices', [{}])[0].get('delta', {})
                        c = d.get('content')
                        if c:
                            full_text += c
                    except Exception:
                        pass
                    yield f"data: {json.dumps(obj)}\n\n"
                except Exception:
                    yield line + "\n"
        finally:
            upstream.close()
            if uid and full_text:
                try:
                    approx = max(1, (len(full_text) + sum(len(m.get('content', '')) for m in clean_messages)) // 4)
                    record_usage(uid, 'llm_tokens', approx, model=requested_model)
                except Exception:
                    pass

    return Response(passthrough(), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no', 'Connection': 'keep-alive'})


# ---------- helpers ----------
def _openai_completion_envelope(model, content, tool_calls=None):
    msg = {"role": "assistant", "content": content}
    if tool_calls:
        msg["tool_calls"] = tool_calls
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:24]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [{
            "index": 0,
            "message": msg,
            "finish_reason": "tool_calls" if tool_calls else "stop",
        }],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


def _openai_stream_chunk(cid, created, model, delta, finish_reason=None):
    obj = {
        "id": cid,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
    }
    return f"data: {json.dumps(obj)}\n\n"
