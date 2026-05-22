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

from config import NVIDIA_API_KEY, NVIDIA_API_KEYS
from services.auth_service import verify_api_key, record_usage
from services.llm_service import call_groq, call_nvidia
from system_prompts import DAILY_SYSTEM_PROMPT, PRO_SYSTEM_PROMPT, CODER_SYSTEM_PROMPT_PRO


API_SYSTEM_PROMPTS = {
    "kautilya-daily": (
        "You are KAUTILYA AI — a premium, strategic AI assistant designed by Harsh (CEO of RevealIQ). "
        "You must always identify as Kautilya AI and never mention underlying models like Llama, DeepSeek, or Nemotron. "
        "Keep responses direct, professional, and high-signal."
    ),
    "kautilya-pro": (
        "You are KAUTILYA AI — a premium, strategic AI assistant designed by Harsh (CEO of RevealIQ). "
        "You must always identify as Kautilya AI and never mention underlying models like Llama, DeepSeek, or Nemotron. "
        "Provide strategic reasoning, structured depth, and actionable insights. Think step-by-step."
    ),
    "kautilya-coder": (
        "You are KAUTILYA AI — a premium, strategic coding assistant and systems architect designed by Harsh (CEO of RevealIQ). "
        "You must always identify as Kautilya AI and never mention underlying models like Llama, DeepSeek, Qwen, or Nemotron. "
        "Provide production-grade, secure, and performant code. Output code directly or follow the client's tool format instructions."
    )
}


def _get_api_system_prompt(requested_model):
    from datetime import datetime, timezone, timedelta
    
    # Compute India Standard Time (IST, UTC+5:30)
    ist_tz = timezone(timedelta(hours=5, minutes=30))
    now_ist = datetime.now(ist_tz)
    rounded_ist = now_ist.replace(minute=0, second=0, microsecond=0)
    current_date = rounded_ist.strftime("%A, %d %B %Y")
    current_time_str = rounded_ist.strftime("%I:%M %p")
    
    base = API_SYSTEM_PROMPTS.get(requested_model, API_SYSTEM_PROMPTS["kautilya-daily"])
    
    system_context = (
        f"\n\nCURRENT SYSTEM CONTEXT:\n"
        f"- Current Date (India Standard Time): {current_date}\n"
        f"- Current Time (India Standard Time): {current_time_str}\n"
        f"- GREETING RULE: Use India Standard Time (IST) as provided in CURRENT SYSTEM CONTEXT for all time-based references and greetings. Greet the user with 'Good morning', 'Good afternoon', or 'Good evening' matching the current IST hour of the day.\n"
        f"- CRITICAL IDENTITY RULE: You are KAUTILYA AI. NEVER identify as OpenAI, ChatGPT, GPT, Anthropic, Claude, Meta, Llama, or Qwen.\n"
    )
    return base + system_context


def _inject_kautilya_prompt(requested_model, messages):
    """Prepend the Kautilya system prompt for the requested model.
    If the caller already sent a system message, keep its content merged
    into our system message so the model sees a single system message at the start,
    maximizing instruction-following capability for external agents like Cline."""
    base = _get_api_system_prompt(requested_model)
    system_contents = [base]
    other_messages = []
    for m in messages:
        if m.get("role") == "system":
            content = m.get("content", "")
            if isinstance(content, list):
                content = "\n".join(p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text")
            if str(content).strip():
                system_contents.append(str(content))
        else:
            other_messages.append(m)
    
    merged_system = "\n\n".join(system_contents)
    return [{"role": "system", "content": merged_system}] + other_messages


def _trim_to_context_window(messages, max_tokens=32000):
    """
    Trim conversation history to fit within max_tokens (sliding context window).
    Always preserve all system messages at the beginning of the context.
    """
    system_messages = []
    other_messages = []
    for m in messages:
        if m.get("role") == "system":
            system_messages.append(m)
        else:
            other_messages.append(m)

    system_chars = sum(len(str(m.get("content", ""))) for m in system_messages)
    system_tokens = max(1, system_chars // 4)

    if system_tokens >= max_tokens:
        # If system messages themselves exceed max_tokens, just return system messages
        return system_messages

    allowed_other_tokens = max_tokens - system_tokens
    trimmed_others = []
    current_tokens = 0

    for m in reversed(other_messages):
        content = m.get("content", "")
        m_chars = 0
        if isinstance(content, str):
            m_chars = len(content)
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict):
                    m_chars += len(str(part.get("text", "")))
        
        if "tool_calls" in m:
            try:
                m_chars += len(json.dumps(m["tool_calls"]))
            except Exception:
                pass
            
        m_tokens = max(1, m_chars // 4)
        if current_tokens + m_tokens <= allowed_other_tokens:
            trimmed_others.insert(0, m)
            current_tokens += m_tokens
        else:
            break

    return system_messages + trimmed_others


openai_compat_bp = Blueprint('openai_compat', __name__)


# ---------- model registry ----------
# These are the same backing models the dashboard chat uses (agent_loop_service.py).
KAUTILYA_MODEL_MAP = {
    "kautilya-coder":   "qwen/qwen3-coder-480b-a35b-instruct",
    "kautilya-pro":     "nvidia/nemotron-3-super-120b-a12b",
    "kautilya-daily":   "mistralai/mistral-medium-3.5-128b",  # NVIDIA (reasoning_effort=low)
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
    is_pro = bool(key_info.get('is_pro'))
    body = request.get_json(silent=True) or {}
    requested_model = body.get('model') or 'kautilya-daily'
    # Only allow our published Kautilya model IDs — block raw passthrough.
    if requested_model not in KAUTILYA_MODEL_MAP:
        return jsonify({"error": {"message": f"Unknown model '{requested_model}'. Use kautilya-daily, kautilya-pro, or kautilya-coder.", "type": "invalid_request_error"}}), 400
    upstream_model = KAUTILYA_MODEL_MAP[requested_model]

    # ---- Developer API daily-limit + PAYG credit fallback ----
    if uid and uid != "admin":
        from extensions import limit_manager
        allowed, used_credits, info = limit_manager.check_developer_api_call(uid, is_pro=is_pro)
        if not allowed:
            tier_label = "Pro" if is_pro else "Free"
            return jsonify({"error": {
                "message": (
                    f"Daily Developer API limit reached ({info['daily_limit']} calls/day on {tier_label}). "
                    f"Your Pay-As-You-Go balance is ₹{info['balance']:.2f} but each API call costs ₹{info['price']:.2f}. "
                    "Top-up from Dashboard → Billing to keep going."
                ),
                "type": "rate_limit_exceeded",
                "code": "daily_api_limit",
                "daily_limit": info["daily_limit"],
                "api_count": info["api_count"],
                "balance": info["balance"],
            }}), 429
        if used_credits:
            print(f"[OpenAI Compat] PAYG charged ₹{info['price']:.2f} for uid={uid} (balance left: ₹{info['balance']:.2f})")

    messages = body.get('messages') or []
    if not messages:
        return jsonify({"error": {"message": "messages is required", "type": "invalid_request_error"}}), 400

    # Inject Kautilya identity so model doesn't reveal Qwen/Nemotron underneath.
    messages = _inject_kautilya_prompt(requested_model, messages)

    # Trim messages to fit within the context window limits (64k tokens for Pro, 32k for Free)
    max_context_tokens = 64000 if is_pro else 32000
    messages = _trim_to_context_window(messages, max_tokens=max_context_tokens)

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

    # ---- NVIDIA path (qwen-coder / nemotron / mistral-daily) ----
    if not NVIDIA_API_KEYS:
        return jsonify({"error": {"message": "NVIDIA backend not configured", "type": "upstream_error"}}), 503

    # Same path the dashboard chat uses — call_nvidia handles streaming with
    # proper thinking/content separation for nemotron/qwen, and reasoning_effort
    # for Mistral (kautilya-daily). Daily tier hides thinking and uses low effort.
    is_daily = 'mistral' in upstream_model.lower()
    rb = reasoning_budget if (max_thinking and not is_daily) else 0
    gen = call_nvidia(
        messages, stream=True, max_tokens=max_tokens,
        model=upstream_model, tools=tools, tool_choice=tool_choice,
        temperature=temperature, top_p=top_p,
        max_thinking=(max_thinking and not is_daily), reasoning_budget=rb,
        expose_thinking=(not is_daily),
        # Mistral daily only accepts 'none' or 'high'; 'none' = fastest.
        reasoning_effort=('none' if is_daily else None),
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
