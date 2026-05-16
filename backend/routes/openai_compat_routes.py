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

from flask import Blueprint, request, jsonify, Response

from config import NVIDIA_API_KEY
from services.auth_service import verify_api_key, record_usage
from services.llm_service import call_groq, call_nvidia
from system_prompts import DAILY_SYSTEM_PROMPT, PRO_SYSTEM_PROMPT, CODER_SYSTEM_PROMPT_PRO


# Per-model system prompts so external API callers get the Kautilya identity
# (same brand voice as the dashboard chat). The user's own system message,
# if any, is preserved and appended after the Kautilya master prompt.
_KAUTILYA_SYSTEM_PROMPTS = {
    "kautilya-daily": DAILY_SYSTEM_PROMPT,
    "kautilya-pro":   PRO_SYSTEM_PROMPT,
    "kautilya-coder": CODER_SYSTEM_PROMPT_PRO,
}


def _inject_kautilya_prompt(requested_model, messages):
    """Prepend the Kautilya system prompt for the requested model.
    If the caller already sent a system message, keep its content as an
    additional system message AFTER ours so user instructions still apply,
    but identity-leak prompts ('what model are you') return Kautilya."""
    base = _KAUTILYA_SYSTEM_PROMPTS.get(requested_model)
    if not base:
        return messages
    out = [{"role": "system", "content": base}]
    for m in messages:
        if m.get("role") == "system":
            content = m.get("content", "")
            if isinstance(content, list):
                content = "\n".join(p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text")
            if str(content).strip():
                out.append({"role": "system", "content": str(content)})
        else:
            out.append(m)
    return out

openai_compat_bp = Blueprint('openai_compat', __name__)


# ---------- model registry ----------
# These are the same backing models the dashboard chat uses (agent_loop_service.py).
KAUTILYA_MODEL_MAP = {
    "kautilya-coder":   "qwen/qwen3-coder-480b-a35b-instruct",
    "kautilya-pro":     "nvidia/nemotron-3-super-120b-a12b",
    "kautilya-daily":   "llama-3.3-70b-versatile",  # Groq
}

PUBLIC_MODELS = [
    {"id": "kautilya-coder",  "object": "model", "owned_by": "kautilya",
     "description": "Frontier code generation with extended thinking."},
    {"id": "kautilya-pro",    "object": "model", "owned_by": "kautilya",
     "description": "Strategic reasoning + Indian-context tuning."},
    {"id": "kautilya-daily",  "object": "model", "owned_by": "kautilya",
     "description": "Fast general chat, low latency."},
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
    requested_model = body.get('model') or 'kautilya-daily'
    # Only allow our published Kautilya model IDs — block raw passthrough.
    if requested_model not in KAUTILYA_MODEL_MAP:
        return jsonify({"error": {"message": f"Unknown model '{requested_model}'. Use kautilya-daily, kautilya-pro, or kautilya-coder.", "type": "invalid_request_error"}}), 400
    upstream_model = KAUTILYA_MODEL_MAP[requested_model]

    messages = body.get('messages') or []
    if not messages:
        return jsonify({"error": {"message": "messages is required", "type": "invalid_request_error"}}), 400

    # Inject Kautilya identity so model doesn't reveal Qwen/Nemotron underneath.
    messages = _inject_kautilya_prompt(requested_model, messages)

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

    # ---- NVIDIA path (qwen-coder / nemotron) ----
    if not NVIDIA_API_KEY:
        return jsonify({"error": {"message": "NVIDIA backend not configured", "type": "upstream_error"}}), 503

    # Same path the dashboard chat uses — call_nvidia handles streaming with
    # proper thinking/content separation for both qwen-coder and nemotron.
    rb = reasoning_budget if max_thinking else 0
    gen = call_nvidia(
        messages, stream=True, max_tokens=max_tokens,
        model=upstream_model, tools=tools, tool_choice=tool_choice,
        temperature=temperature, top_p=top_p,
        max_thinking=max_thinking, reasoning_budget=rb,
        expose_thinking=True,
    )
    if gen is None:
        return jsonify({"error": {"message": "Upstream unavailable", "type": "upstream_error"}}), 503

    if not stream:
        # Buffer the stream into a single completion envelope.
        full_content = ""
        full_thinking = ""
        tool_calls_out = None
        for ev in gen:
            if not isinstance(ev, dict):
                continue
            if ev.get("chunk"):
                full_content += ev["chunk"]
            elif ev.get("thinking"):
                full_thinking += ev["thinking"]
            elif ev.get("tool_calls"):
                tool_calls_out = ev["tool_calls"]
        envelope = _openai_completion_envelope(requested_model, full_content,
                                               tool_calls=tool_calls_out,
                                               reasoning=full_thinking or None)
        if uid:
            try:
                approx = max(1, (len(full_content) + len(full_thinking) + sum(len(str(m.get('content',''))) for m in messages)) // 4)
                record_usage(uid, 'llm_tokens', approx, model=requested_model)
            except Exception:
                pass
        return jsonify(envelope)

    # Streaming: convert call_nvidia events → OpenAI SSE chunks.
    def sse():
        cid = f"chatcmpl-{uuid.uuid4().hex[:24]}"
        created = int(time.time())
        first = True
        full_text = ""
        full_think = ""
        finish = "stop"
        for ev in gen:
            if not isinstance(ev, dict):
                continue
            delta = {}
            if ev.get("thinking"):
                delta["reasoning_content"] = ev["thinking"]
                full_think += ev["thinking"]
            elif ev.get("chunk"):
                delta["content"] = ev["chunk"]
                full_text += ev["chunk"]
            elif ev.get("tool_calls"):
                delta["tool_calls"] = ev["tool_calls"]
                finish = "tool_calls"
            elif ev.get("thinking_done"):
                continue  # internal signal, not surfaced to OpenAI clients
            else:
                continue
            if first:
                delta["role"] = "assistant"
                first = False
            yield _openai_stream_chunk(cid, created, requested_model, delta)
        yield _openai_stream_chunk(cid, created, requested_model, {}, finish_reason=finish)
        yield "data: [DONE]\n\n"
        if uid and (full_text or full_think):
            try:
                approx = max(1, (len(full_text) + len(full_think) + sum(len(str(m.get('content',''))) for m in messages)) // 4)
                record_usage(uid, 'llm_tokens', approx, model=requested_model)
            except Exception:
                pass

    return Response(sse(), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no', 'Connection': 'keep-alive'})


# ---------- helpers ----------
def _openai_completion_envelope(model, content, tool_calls=None, reasoning=None):
    msg = {"role": "assistant", "content": content}
    if tool_calls:
        msg["tool_calls"] = tool_calls
    if reasoning:
        msg["reasoning_content"] = reasoning
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
