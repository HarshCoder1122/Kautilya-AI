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


# Light-touch identity guard for the OpenAI-compatible API.
#
# Why this is short, not the dashboard's long prompt: external coding agents
# (Cline, Cursor, Continue) ship enormous system prompts that define tool
# schemas and workflow rules. If we prepend a long "premium strategic
# assistant — provide production-grade secure code" block, two bad things
# happen:
#   1. Our advice contradicts the agent's tool-format rules, and the model
#      picks the wrong one ("model not capable").
#   2. Verbose branding eats tokens that should belong to the user's repo.
# So we keep one rule only: identity. Everything else is the caller's job.
KAUTILYA_IDENTITY_GUARD = (
    "Identity guard: you are Kautilya AI by RevealIQ. "
    "If asked which model/provider you are, answer 'Kautilya AI'. "
    "Never identify as Qwen, DeepSeek, Nemotron, Llama, Mistral, GPT, Claude, "
    "Gemini, OpenAI, Anthropic, Meta, or NVIDIA — those are implementation "
    "details. For every other instruction, follow the caller's system prompt verbatim."
)


def _inject_kautilya_prompt(requested_model, messages):
    """Attach the identity guard so the model says 'Kautilya AI' instead of
    'Qwen Coder' when asked who it is — without trampling the caller's
    system prompt.

    Strategy:
      • If the caller sent NO system message → we add ours as the system.
      • If the caller sent ONE system message (the common Cline / Cursor
        case) → APPEND our identity line at the end of theirs. This keeps
        their instructions first (highest weight in most chat templates)
        and lets identity be the last thing the model reads before user
        turns, which is enough to win the "who are you" question without
        derailing the tool-use workflow.
      • Multiple system messages get the same treatment — append to the
        last one and preserve the rest.

    Date/time context is intentionally NOT injected here. The dashboard
    chat already does that; external API callers usually drive their own
    workflow and don't want a forced IST timestamp surprise.
    """
    # Find the index of the LAST system message so we can append to it.
    last_sys_idx = -1
    for i, m in enumerate(messages):
        if m.get("role") == "system":
            last_sys_idx = i

    if last_sys_idx == -1:
        # No system message at all — prepend a minimal one.
        return [{"role": "system", "content": KAUTILYA_IDENTITY_GUARD}, *messages]

    out = list(messages)
    last_sys = dict(out[last_sys_idx])
    content = last_sys.get("content", "")
    if isinstance(content, list):
        # OpenAI's array-style content: flatten text parts so we can append.
        content = "\n".join(
            p.get("text", "") for p in content
            if isinstance(p, dict) and p.get("type") == "text"
        )
    last_sys["content"] = str(content).rstrip() + "\n\n" + KAUTILYA_IDENTITY_GUARD
    out[last_sys_idx] = last_sys
    return out


def _trim_to_context_window(messages, max_tokens=32000):
    """
    Trim conversation history to fit within max_tokens (sliding context window).
    Always preserve all system messages at the beginning of the context.

    Tool-protocol invariants we MUST respect or NVIDIA / Groq returns 400:
      • A `role: "tool"` message has no meaning without the assistant message
        that emitted the matching `tool_calls[*].id`. Cutting one without the
        other causes "tool_call_id ... was not found in the conversation".
      • Likewise, an assistant message with `tool_calls` is incomplete
        without its tool responses unless it is the LAST assistant turn
        (which means the conversation is about to ask the tools to run).
    Strategy: collect from the tail, but if including a `tool` message
    would require its assistant predecessor and we can't afford that
    predecessor, skip the orphan instead of breaking the protocol.
    """
    system_messages = []
    other_messages = []
    for m in messages:
        if m.get("role") == "system":
            system_messages.append(m)
        else:
            other_messages.append(m)

    system_chars = sum(len(str(m.get("content", "") or "")) for m in system_messages)
    system_tokens = max(1, system_chars // 4)

    if system_tokens >= max_tokens:
        return system_messages

    allowed_other_tokens = max_tokens - system_tokens

    def _msg_token_estimate(m):
        content = m.get("content", "") or ""
        m_chars = 0
        if isinstance(content, str):
            m_chars = len(content)
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict):
                    m_chars += len(str(part.get("text", "")))
        if m.get("tool_calls"):
            try:
                m_chars += len(json.dumps(m["tool_calls"]))
            except Exception:
                pass
        return max(1, m_chars // 4)

    # Walk from the tail, grouping tool messages with the assistant turn
    # that produced their tool_call_id. We add either the whole group or
    # nothing — never half.
    trimmed_others = []
    current_tokens = 0
    i = len(other_messages) - 1
    while i >= 0:
        m = other_messages[i]
        # If this is a tool message, collect all consecutive tool messages
        # and their parent assistant tool-call turn into one atomic group.
        if m.get("role") == "tool":
            group = [m]
            j = i - 1
            while j >= 0 and other_messages[j].get("role") == "tool":
                group.insert(0, other_messages[j])
                j -= 1
            if j >= 0 and other_messages[j].get("role") == "assistant" and other_messages[j].get("tool_calls"):
                group.insert(0, other_messages[j])
                j -= 1
            group_tokens = sum(_msg_token_estimate(g) for g in group)
            if current_tokens + group_tokens <= allowed_other_tokens:
                trimmed_others = group + trimmed_others
                current_tokens += group_tokens
                i = j
                continue
            # Can't fit the whole group — skip ALL of it (don't strand
            # orphan tool messages). Stop walking older history; older
            # turns won't fit either and we'd break temporal order.
            break
        # Regular user / assistant turn.
        m_tokens = _msg_token_estimate(m)
        if current_tokens + m_tokens <= allowed_other_tokens:
            trimmed_others.insert(0, m)
            current_tokens += m_tokens
            i -= 1
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

# Per-model context windows. Match each upstream model's actual capability so
# Cline/Cursor users on Pro/Coder don't see silently-truncated context (which
# was making the model "hallucinate / not understand complex tasks" — it was
# being fed only the last 64k of what the client sent).
# Free tier gets a smaller share to keep latency/cost predictable.
KAUTILYA_MODEL_CONTEXT = {
    "kautilya-coder":   {"free":  64_000, "pro": 256_000},
    "kautilya-pro":     {"free":  64_000, "pro": 128_000},
    "kautilya-daily":   {"free":  32_000, "pro":  64_000},
}

# Non-standard capability flags that LiteLLM / OpenRouter-style clients
# (and Cline's "openai-compatible" provider when set to auto-detect) read
# to decide whether to enable tool-use, vision, etc. The OpenAI spec
# itself ignores them, so plain OpenAI SDK clients see them as harmless
# extra keys.
PUBLIC_MODELS = [
    {"id": "kautilya-coder",  "object": "model", "owned_by": "kautilya",
     "description": "Frontier code generation. Tool use supported.",
     "context_window": 256_000,
     "max_output_tokens": 32_768,
     "supports_function_calling": True,
     "supports_tool_choice": True,
     "supports_parallel_function_calling": True,
     "supports_vision": False,
     "supports_system_messages": True,
     "supports_prompt_cache": False},
    {"id": "kautilya-pro",    "object": "model", "owned_by": "kautilya",
     "description": "Strategic reasoning + extended thinking.",
     "context_window": 128_000,
     "max_output_tokens": 16_384,
     "supports_function_calling": True,
     "supports_tool_choice": True,
     "supports_parallel_function_calling": True,
     "supports_vision": False,
     "supports_system_messages": True,
     "supports_reasoning": True,
     "supports_prompt_cache": False},
    {"id": "kautilya-daily",  "object": "model", "owned_by": "kautilya",
     "description": "Fast general chat, low latency.",
     "context_window": 64_000,
     "max_output_tokens": 8_192,
     "supports_function_calling": True,
     "supports_tool_choice": True,
     "supports_parallel_function_calling": True,
     "supports_vision": False,
     "supports_system_messages": True,
     "supports_prompt_cache": False},
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

    # Trim messages to fit within the context window for this (model, tier).
    # The Pro/Coder windows now match the underlying model's real native
    # context — Cline/Cursor users were losing context to a hard 64k cap.
    tier_key = "pro" if is_pro else "free"
    max_context_tokens = KAUTILYA_MODEL_CONTEXT.get(requested_model, {}).get(tier_key, 32_000)
    messages = _trim_to_context_window(messages, max_tokens=max_context_tokens)

    stream = bool(body.get('stream', False))
    # Cline + Continue often pass temperature=0 for deterministic tool-use.
    # Honour exactly what they sent (including 0) rather than treating
    # falsy as missing.
    temperature = body['temperature'] if 'temperature' in body else 0.7
    top_p = body['top_p'] if 'top_p' in body else 0.95
    # OpenAI spec: prefer max_completion_tokens (newer field), fall back to
    # max_tokens. If neither is provided, the coder model is asked for a
    # generous default — Cline expects long code blocks back.
    max_tokens = body.get('max_completion_tokens') or body.get('max_tokens') or (
        16384 if requested_model == "kautilya-coder" else 4096
    )
    tools = body.get('tools')
    tool_choice = body.get('tool_choice')
    # Validate the tool envelope so upstream doesn't reject the whole call.
    # Cline always wraps tools with {type: "function", function: {...}} —
    # accept that exactly, drop malformed entries silently rather than 400.
    if tools is not None:
        if not isinstance(tools, list):
            tools = None
        else:
            tools = [t for t in tools if isinstance(t, dict) and (t.get("function") or t.get("type") == "function")]
            if not tools:
                tools = None

    # Reasoning effort + thinking toggle resolution.
    # Honors the OpenAI top-level `reasoning_effort` field (low|medium|high|none)
    # so Cline/Cursor's standard reasoning slider just works.
    extra = body.get('extra_body') or {}
    ctk = extra.get('chat_template_kwargs') or body.get('chat_template_kwargs') or {}
    reasoning_effort = (
        body.get('reasoning_effort')
        or extra.get('reasoning_effort')
        or None
    )
    if isinstance(reasoning_effort, str):
        reasoning_effort = reasoning_effort.strip().lower() or None
    # `max_thinking` is the on/off switch we pass to call_nvidia. Treat
    # high effort OR an explicit toggle as "on"; anything else (low / none /
    # unspecified) means "answer at earliest" so external clients aren't
    # silently paying for reasoning latency they didn't ask for.
    max_thinking = bool(
        extra.get('max_thinking')
        or body.get('max_thinking')
        or ctk.get('enable_thinking')
        or ctk.get('thinking')
        or (reasoning_effort == 'high')
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
            had_tool_calls = False
            length_capped = False
            for chunk in gen:
                if isinstance(chunk, str):
                    piece = chunk
                    if not piece:
                        continue
                    full += piece
                    delta = {"content": piece}
                elif isinstance(chunk, dict):
                    if chunk.get("_finish_reason") == "length":
                        length_capped = True
                        continue
                    if chunk.get("tool_calls"):
                        normalized = []
                        for i, tc in enumerate(chunk["tool_calls"]):
                            if not isinstance(tc, dict):
                                continue
                            out = dict(tc)
                            if "index" not in out:
                                out["index"] = tc.get("index", i)
                            fn = out.get("function") or {}
                            if isinstance(fn, dict):
                                args = fn.get("arguments")
                                if args is not None and not isinstance(args, str):
                                    try:
                                        fn["arguments"] = json.dumps(args)
                                    except Exception:
                                        fn["arguments"] = str(args)
                                out["function"] = fn
                            if "type" not in out:
                                out["type"] = "function"
                            normalized.append(out)
                        if not normalized:
                            continue
                        delta = {"tool_calls": normalized}
                        had_tool_calls = True
                    elif chunk.get("chunk"):
                        piece = chunk["chunk"]
                        full += piece
                        delta = {"content": piece}
                    else:
                        continue
                else:
                    continue
                if first:
                    delta["role"] = "assistant"
                    first = False
                yield _openai_stream_chunk(cid, created, requested_model, delta)
            finish_r = "tool_calls" if had_tool_calls else ("length" if length_capped else "stop")
            yield _openai_stream_chunk(cid, created, requested_model, {}, finish_reason=finish_r)
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
    # for Mistral (kautilya-daily). Daily tier always uses lowest effort so
    # Cline/Cursor stay snappy.
    is_daily = 'mistral' in upstream_model.lower()
    # Qwen3-Coder is NOT a reasoning model — it doesn't accept
    # reasoning_effort or chat_template_kwargs.thinking. Passing either
    # makes NVIDIA reject the whole request with a 400 ("invalid field"),
    # which Cline surfaces as "model not capable". Treat the coder model as
    # a plain non-reasoning chat model regardless of the OpenAI-style
    # reasoning_effort the client sent.
    is_qwen_coder = 'qwen' in upstream_model.lower() and 'coder' in upstream_model.lower()
    rb = reasoning_budget if (max_thinking and not is_daily and not is_qwen_coder) else 0
    # Map OpenAI-style reasoning_effort to the upstream value:
    #   high → enable thinking path (handled via max_thinking above)
    #   low / medium / none / unspecified → fastest path, no reasoning tokens
    if is_qwen_coder:
        upstream_effort = None  # never send reasoning_effort to a coder model
        thinking_on = False
        expose_thinking_flag = False
    elif is_daily:
        # Mistral only accepts 'none' or 'high'.
        upstream_effort = 'high' if max_thinking else 'none'
        thinking_on = False  # max_thinking on Mistral is handled via reasoning_effort
        # When the caller asked for high reasoning we DO want to expose the
        # reasoning_content deltas back to them so the UI can render a
        # thinking panel — otherwise the 'high' effort is invisible.
        expose_thinking_flag = bool(max_thinking)
    else:
        # For nemotron / glm we use max_thinking to decide; pass effort hint
        # through only when explicitly low/medium so the model can dial it down.
        if max_thinking:
            upstream_effort = None  # default high path via reasoning_budget
        elif reasoning_effort in ('low', 'medium', 'none'):
            upstream_effort = reasoning_effort
        else:
            upstream_effort = 'low'  # default: answer at earliest
        thinking_on = max_thinking
        expose_thinking_flag = True
    gen = call_nvidia(
        messages, stream=True, max_tokens=max_tokens,
        model=upstream_model, tools=tools, tool_choice=tool_choice,
        temperature=temperature, top_p=top_p,
        max_thinking=thinking_on, reasoning_budget=rb,
        expose_thinking=expose_thinking_flag,
        reasoning_effort=upstream_effort,
    )
    if gen is None:
        return jsonify({"error": {"message": "Upstream unavailable", "type": "upstream_error"}}), 503

    if not stream:
        # Buffer the stream into a single completion envelope.
        full_content = ""
        full_thinking = ""
        tool_calls_out = None
        length_capped = False
        for ev in gen:
            if not isinstance(ev, dict):
                continue
            if ev.get("_finish_reason") == "length":
                length_capped = True
                continue
            if ev.get("chunk"):
                full_content += ev["chunk"]
            elif ev.get("thinking"):
                full_thinking += ev["thinking"]
            elif ev.get("tool_calls"):
                # Accumulate streamed tool_call deltas into a single list so
                # the non-streaming envelope reports one complete call set.
                if tool_calls_out is None:
                    tool_calls_out = []
                for i, tc in enumerate(ev["tool_calls"]):
                    if not isinstance(tc, dict):
                        continue
                    idx = tc.get("index", i)
                    while len(tool_calls_out) <= idx:
                        tool_calls_out.append({"index": len(tool_calls_out),
                                               "type": "function",
                                               "function": {"name": "", "arguments": ""}})
                    slot = tool_calls_out[idx]
                    if tc.get("id"):
                        slot["id"] = tc["id"]
                    if tc.get("type"):
                        slot["type"] = tc["type"]
                    fn = tc.get("function") or {}
                    if isinstance(fn, dict):
                        if fn.get("name"):
                            slot["function"]["name"] = fn["name"]
                        a = fn.get("arguments")
                        if a is not None:
                            slot["function"]["arguments"] += a if isinstance(a, str) else json.dumps(a)
        finish_r = "tool_calls" if tool_calls_out else ("length" if length_capped else "stop")
        envelope = _openai_completion_envelope(requested_model, full_content,
                                               tool_calls=tool_calls_out,
                                               reasoning=full_thinking or None,
                                               finish_reason=finish_r)
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
        had_tool_calls = False
        length_capped = False
        for ev in gen:
            if not isinstance(ev, dict):
                continue
            # Internal sentinel from llm_service: provider sent
            # finish_reason="length". Mark it so the final SSE chunk tells
            # Cline / Cursor to keep going instead of believing the answer
            # ended naturally.
            if ev.get("_finish_reason") == "length":
                length_capped = True
                continue
            delta = {}
            if ev.get("thinking"):
                delta["reasoning_content"] = ev["thinking"]
                full_think += ev["thinking"]
            elif ev.get("chunk"):
                delta["content"] = ev["chunk"]
                full_text += ev["chunk"]
            elif ev.get("tool_calls"):
                # Re-shape into strict OpenAI streaming format. Each delta
                # tool-call entry MUST have an `index` (so the client can
                # accumulate arguments across chunks) and `function.arguments`
                # MUST be a string. Upstream models sometimes emit a dict
                # for arguments on the first chunk — coerce to JSON string.
                normalized = []
                for i, tc in enumerate(ev["tool_calls"]):
                    if not isinstance(tc, dict):
                        continue
                    out = dict(tc)
                    if "index" not in out:
                        out["index"] = tc.get("index", i)
                    fn = out.get("function") or {}
                    if isinstance(fn, dict):
                        args = fn.get("arguments")
                        if args is not None and not isinstance(args, str):
                            try:
                                fn["arguments"] = json.dumps(args)
                            except Exception:
                                fn["arguments"] = str(args)
                        out["function"] = fn
                    if "type" not in out:
                        out["type"] = "function"
                    normalized.append(out)
                if not normalized:
                    continue
                delta["tool_calls"] = normalized
                had_tool_calls = True
            elif ev.get("thinking_done"):
                continue  # internal signal, not surfaced to OpenAI clients
            else:
                continue
            if first:
                delta["role"] = "assistant"
                first = False
            yield _openai_stream_chunk(cid, created, requested_model, delta)
        # Pick the strictly-correct OpenAI finish_reason. "length" must win
        # over "stop" so the agent retries; "tool_calls" wins over both
        # when tools were emitted.
        if length_capped and not had_tool_calls:
            finish = "length"
        elif had_tool_calls:
            finish = "tool_calls"
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
def _normalize_tool_calls(tool_calls):
    """Coerce upstream tool-call output into the strict OpenAI shape Cline /
    Cursor / LangChain / LiteLLM expect: each entry has `id`, `type:
    "function"`, `function.name`, and `function.arguments` as a STRING.

    Most upstreams already comply, but Qwen / Nemotron occasionally:
      • emit `arguments` as a dict instead of a JSON string
      • omit `type`
      • omit `id` (clients then can't reference the call from a tool turn)
    """
    if not tool_calls:
        return None
    if not isinstance(tool_calls, list):
        return None
    out = []
    for i, tc in enumerate(tool_calls):
        if not isinstance(tc, dict):
            continue
        norm = dict(tc)
        if "type" not in norm:
            norm["type"] = "function"
        if not norm.get("id"):
            norm["id"] = f"call_{uuid.uuid4().hex[:12]}"
        fn = norm.get("function") or {}
        if isinstance(fn, dict):
            args = fn.get("arguments")
            if args is not None and not isinstance(args, str):
                try:
                    fn["arguments"] = json.dumps(args)
                except Exception:
                    fn["arguments"] = str(args)
            norm["function"] = fn
        out.append(norm)
    return out or None


def _openai_completion_envelope(model, content, tool_calls=None, reasoning=None, finish_reason=None):
    tool_calls = _normalize_tool_calls(tool_calls)
    msg = {"role": "assistant", "content": content if content else None}
    if tool_calls:
        msg["tool_calls"] = tool_calls
    if reasoning:
        msg["reasoning_content"] = reasoning
    if finish_reason is None:
        finish_reason = "tool_calls" if tool_calls else "stop"
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:24]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [{
            "index": 0,
            "message": msg,
            "finish_reason": finish_reason,
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
