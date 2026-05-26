"""
Kautilya AI — Agent Loop Service
Agentic loop: Think → Act → Observe → Answer.
"""
import re
import json
import time
import concurrent.futures

from services.llm_service import call_groq, call_nvidia


MODEL_ALIASES = {
    "kautilya-daily": "daily",
    "llama": "daily",
    "llama-3.3-70b-versatile": "daily",
    "kautilya-pro": "pro",
    "nemotron": "pro",
    "nvidia/nemotron-3-super-120b-a12b": "pro",
    "kautilya-coder": "coder",
    "qwen": "coder",
    "qwen-3": "coder",
    "qwen-3-coder-480b-a35b-instruct": "coder",
}


def normalize_model_choice(model, default="auto"):
    """Normalize UI/API aliases into the internal routing ids."""
    raw = str(model or default).strip().lower()
    if raw in ("auto", "daily", "pro", "coder", "research"):
        return raw
    return MODEL_ALIASES.get(raw, "auto")


# Shared executor to reduce overhead
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=10)
_loc_cache = {} # Cache for IP location lookups

def _ttime(label, start):
    """Latency-tracing helper; matches the [TIMING] format used in chat_routes."""
    try:
        elapsed_ms = int((time.time() - start) * 1000)
        if elapsed_ms >= 50:
            print(f"[TIMING] {label}: {elapsed_ms}ms")
    except Exception:
        pass


def agent_loop(messages, uid=None, model_choice='daily', user_ip=None, tools=None, tool_choice=None, max_thinking=False):
    """
    Agentic Loop: Thoughts -> Actions -> Observations -> Final Answer.
    Yields chunks of text OR special status JSONs.
    """
    from extensions import limit_manager, vector_store
    _t_loop_start = time.time()

    rag_context = ""
    location_context = ""
    last_user_msg = ""
    if messages and messages[-1]["role"] == "user":
        content = messages[-1].get("content", "")
        if isinstance(content, str):
            last_user_msg = content
        elif isinstance(content, list):
            last_user_msg = " ".join([p["text"] for p in content if p.get("type") == "text"])

    # Pre-warm the answer-size classifier in parallel with location / RAG /
    # MCP setup. By the time we need max_tokens for the LLM call (after
    # prompt assembly), the classifier has typically resolved and is in
    # the cache — so the synchronous _adaptive_max_tokens call below is
    # free. If the user is on Pro/coder and we hit this twice (turn 2+),
    # the cache hit makes the second call instant.
    if last_user_msg:
        _executor.submit(_classify_answer_size, last_user_msg, model_choice)

    # Fetch context in parallel
    def fetch_loc():
        if not user_ip or user_ip in ('127.0.0.1', 'localhost', '::1', 'unknown'):
            return ""
        # Check cache (1 hour TTL)
        now = time.time()
        if user_ip in _loc_cache:
            data, ts = _loc_cache[user_ip]
            if now - ts < 3600:
                return data
        try:
            import requests
            resp = requests.get(f"http://ip-api.com/json/{user_ip}", timeout=0.8)
            if resp.status_code == 200:
                data = resp.json()
                if data.get('status') == 'success':
                     loc_str = f"\n[System: User location: {data.get('city')}, {data.get('regionName')}]\n"
                     _loc_cache[user_ip] = (loc_str, now)
                     return loc_str
        except:
            pass
        return ""

    def fetch_rag():
        if not uid or not last_user_msg:
            return ""
        # Only RAG if query is meaningful (> 10 chars)
        if len(last_user_msg) > 10:
            try:
                hits = vector_store.search(uid, last_user_msg, top_k=2)
                if hits:
                    return "\n\nRELEVANT MEMORIES:\n" + "\n".join([f"- {h[1]}" for h in hits])
            except:
                pass
        return ""

    # TTFT optimization: previously these blocked for up to 1.9s pre-LLM.
    # Now we cap the wait at 250ms total — if context isn't ready, we send
    # without it. Both fetches still complete in the background; they just
    # don't gate the LLM call. RAG/location are nice-to-have, not critical.
    # Skip RAG entirely for short messages (greetings, "ok", "thanks") — saves
    # the Firestore round-trip and embedding similarity compute.
    _skip_rag = len(last_user_msg.strip()) < 20
    future_loc = _executor.submit(fetch_loc)
    future_rag = None if _skip_rag else _executor.submit(fetch_rag)
    try:
        location_context = future_loc.result(timeout=0.15)
    except:
        pass
    if future_rag is not None:
        try:
            rag_context = future_rag.result(timeout=0.25)
        except:
            pass

    current_messages = [m.copy() for m in messages]
    if location_context or rag_context:
        current_messages[0]["content"] += location_context + rag_context

    # Always inject a FRESH date/time block — the conversation's cached system
    # message may have been built days ago, so we can't trust its timestamp.
    # We append to the existing system message so the model always sees an
    # up-to-date "today / now" reference and can reason about "tomorrow", etc.
    try:
        from datetime import datetime, timezone, timedelta
        ist_tz = timezone(timedelta(hours=5, minutes=30))
        now_ist = datetime.now(ist_tz)
        now_str = now_ist.strftime("%A, %d %B %Y, %I:%M %p IST").strip()
        today = now_ist.strftime("%Y-%m-%d (%A)")
        tomorrow = (now_ist + timedelta(days=1)).strftime("%Y-%m-%d (%A)")
        time_block = (
            f"\n\nCRITICAL TEMPORAL ANCHOR (OVERRIDE YOUR INTERNAL CLOCK):\n"
            f"The current year is STRICTLY 2026. Do NOT say it is 2024. Your internal clock and knowledge cutoff are outdated.\n"
            f"- Exact current time: {now_str}\n"
            f"- Today: {today}\n"
            f"- Tomorrow: {tomorrow}\n"
            f"You MUST use 2026 for any calculations involving the current date, age, or time elapsed."
        )
        if current_messages and current_messages[0].get("role") == "system":
            current_messages[0]["content"] = str(current_messages[0].get("content", "")) + time_block
        else:
            current_messages.insert(0, {"role": "system", "content": time_block.strip()})
    except Exception as _e:
        print(f"[Agent] date injection failed: {_e}")

    # Inject available integration tools into the system prompt — but only
    # when the user's message looks like an integration request. Always-on
    # injection bloated prompts and slowed NVIDIA TTFT by 100-300ms on
    # short messages. The keyword gate is cheap and accurate enough.
    _intent_kw = ('send', 'whatsapp', 'slack', 'calendar', 'schedule', 'meeting',
                  'crm', 'hubspot', 'zoho', 'contact', 'contacts', 'lead', 'zapier', 'event',
                  'email', 'remind', 'follow up', 'follow-up', 'drive', 'file',
                  'files', 'document', 'documents', 'doc', 'docs', 'sheet', 'sheets',
                  'spreadsheet', 'spreadsheets',
                  # YouTube + Google Contacts + Docs additions
                  'youtube', 'video', 'videos', 'watch', 'channel', 'channels',
                  'subscription', 'subscriptions', 'phone', 'phones',
                  'people', 'address book', 'addressbook')
    _msg_low = (last_user_msg or "").lower() if last_user_msg else ""
    if uid and any(k in _msg_low for k in _intent_kw):
        try:
            from services.integration_tools import available_tools
            _t_avail = time.time()
            specs = available_tools(uid)
            _ttime("available_tools", _t_avail)
            if specs:
                lines = ["\n\nAVAILABLE INTEGRATIONS (call exactly once when the user explicitly asks):"]
                for s in specs:
                    fn = s["function"]
                    req = fn.get("parameters", {}).get("required", [])
                    lines.append(f"- {fn['name']}({', '.join(req)}): {fn['description']}")
                lines.append("Syntax: [INTEGRATION: tool_name | {\"arg\": \"value\"}]  — JSON args, single line, double-quoted.")
                lines.append(
                    "PREAMBLE + TAG RULE (UX-critical, both halves are MANDATORY): when you intend to call a tool, "
                    "your response MUST contain BOTH:\n"
                    "  (1) a SHORT (≤12 words) natural-language preamble announcing what you're about to do, AND\n"
                    "  (2) the actual [INTEGRATION: …] tag on the very next line — IN THE SAME RESPONSE.\n"
                    "The preamble alone is NOT a tool call. If you write 'Checking your YouTube subscriptions…' but no "
                    "[INTEGRATION:] tag follows, NOTHING runs and the user sees a useless half-response.\n"
                    "CORRECT examples:\n"
                    "  ✓ 'Searching GitHub for harshcoder1122…\\n[INTEGRATION: mcp_github_search_users | {\"q\":\"harshcoder1122\"}]'\n"
                    "  ✓ 'Pulling your YouTube subscriptions…\\n[INTEGRATION: list_youtube_subscriptions | {}]'\n"
                    "  ✓ 'Creating the Google Doc now…\\n[INTEGRATION: create_google_doc | {\"title\":\"…\"}]'\n"
                    "WRONG examples (DO NOT do this):\n"
                    "  ✗ 'Checking your YouTube subscriptions…' (no tag → nothing happens)\n"
                    "  ✗ Starting the response with `[INTEGRATION:` directly (no preamble → UI looks frozen)\n"
                    "If you genuinely cannot make the call yet (missing info, user must confirm), DO NOT write a "
                    "progressive preamble like 'Let me check…' — instead ask the question or state what's missing."
                )
                lines.append(
                    "WHEN TO USE INTEGRATIONS — minimal, intent-driven:\n"
                    "  • Call an integration ONLY when the user explicitly requests that exact action in THIS message (or directly references a previous request).\n"
                    "  • 'Remember it', 'note this', 'got it' are conversational — they DO NOT mean call any tool. Just acknowledge in text.\n"
                    "  • After a tool succeeds, the next turn should be PLAIN TEXT to the user. Do not auto-chain another integration (e.g. don't save a fetched profile to a doc unless asked).\n"
                    "PAYLOAD SIZE LIMIT: keep the JSON for any single [INTEGRATION:] call under ~1500 characters total. "
                    "If a tag exceeds the response token budget it is silently truncated and the user sees nothing happen.\n"
                    "GOOGLE DOCS WORKFLOW (only when user asks for a doc):\n"
                    "  • Body ≤ ~1200 chars: ONE call — [INTEGRATION: create_google_doc | {\"title\":\"...\", \"content\":\"...full body...\"}].\n"
                    "  • Body longer: create_google_doc with just title → wait for document_id → call append_google_doc with ≤1000-char chunks, one per turn.\n"
                    "  • Never inline a full report inside one append_google_doc text field."
                )
                lines.append(
                    "STRICT TOOL-SELECTION RULES (violating these is hallucination):\n"
                    "1. Use ONLY the tool whose name AND description exactly match the user's intent. Do NOT substitute a different tool because it's 'close enough'.\n"
                    "2. The tool name in [INTEGRATION: …] must be COPIED VERBATIM from the list above. Never invent a tool name (no 'youtube_search', no 'gdocs_create' — only what is listed).\n"
                    "3. If the user wants YouTube → use search_youtube / list_youtube_subscriptions. NEVER use list_drive_files or a web-search MCP for YouTube.\n"
                    "4. If the user wants Google Docs → use create_google_doc / read_google_doc / append_google_doc. NEVER append text via list_drive_files or append_sheet_row.\n"
                    "5. If the user wants Google Sheets → use append_sheet_row. NEVER use a Docs tool for spreadsheets.\n"
                    "6. If the user wants their Google Contacts → use search_google_contacts. NEVER guess phone numbers/emails from memory.\n"
                    "7. If NO listed tool matches the request, say so plainly — do NOT call a wrong tool and fabricate the result. Tell the user which integration they'd need to connect.\n"
                    "8. Never invent results. If a tool returns an error or empty, report that fact; do not pretend it succeeded."
                )
                if current_messages and current_messages[0].get("role") == "system":
                    current_messages[0]["content"] = str(current_messages[0].get("content", "")) + "\n".join(lines)
        except Exception as _e:
            print(f"[Agent] integration tool prompt injection failed: {_e}")

    # MCP tools: always advertise — gating by intent keywords misses queries like
    # "find me the latest paper on X" (no keyword match yet a web-search MCP would
    # answer it). Token cost is bounded since most deployments enable <10 servers.
    try:
        from services.mcp_client_service import available_mcp_tools
        mcp_specs = available_mcp_tools(uid=uid)
        if mcp_specs:
            mcp_lines = [f"\n\nAVAILABLE MCP TOOLS ({len(mcp_specs)} from connected servers). Use ONLY when the task genuinely needs external data/action — do NOT call for opinions, math, or general knowledge you already have:"]
            for s in mcp_specs:
                fn = s["function"]
                req = (fn.get("parameters") or {}).get("required", [])
                desc = (fn.get("description") or "")[:160]
                mcp_lines.append(f"- {fn['name']}({', '.join(req)}): {desc}")
            mcp_lines.append("Syntax: [INTEGRATION: mcp_<server>_<tool> | {\"arg\":\"value\"}]  — same dispatch format. Wait for OBSERVATION before continuing.")
            mcp_lines.append(
                "PRIORITY RULE: if a task is covered by an entry in AVAILABLE INTEGRATIONS above (Google Docs, Sheets, Tasks, Drive, Calendar, Contacts, YouTube, GitHub, CRM, WhatsApp, Slack), "
                "use THAT integration — do NOT route the same request through a generic MCP fetch/web/search server. MCP tools are only for tasks no integration covers.\n"
                "ONE-AND-DONE RULE: after an MCP tool returns a result, the next turn is PLAIN TEXT to the user. Do NOT chain another MCP call to 'save', 'remember', or 'process' the result unless the user explicitly asked for that follow-up in their original message. "
                "Keep [INTEGRATION:] JSON payloads under ~1500 chars total — never paste a full API response back into another tool call."
            )
            if current_messages and current_messages[0].get("role") == "system":
                current_messages[0]["content"] = str(current_messages[0].get("content", "")) + "\n".join(mcp_lines)
    except Exception as _e:
        print(f"[Agent] MCP tool prompt injection failed: {_e}")


    # Pre-fetch integration data based on intent BEFORE calling the LLM.
    # Gated by intent keywords so chitchat doesn't pay the HTTP round-trip
    # to Google/HubSpot — that was adding 400-800ms TTFT on every message.
    _prefetch_kw = ('calendar', 'schedule', 'meeting', 'event', 'crm', 'contact',
                    'lead', 'email', 'gmail', 'remind', 'agenda', 'tomorrow', 'today',
                    'drive', 'file', 'files', 'document', 'documents', 'doc', 'docs',
                    'sheet', 'sheets', 'spreadsheet', 'spreadsheets')
    if uid and last_user_msg and any(k in (last_user_msg or "").lower() for k in _prefetch_kw):
        # Tight 600ms cap — the model can ALWAYS fetch via a tool call if the
        # prefetch misses, so we'd rather lose the prefetch and ship the LLM
        # call than block the user for a full second on a slow Google API.
        # (Was 1500ms — too generous; on slow days that's an extra 1s of TTFT
        # for every calendar/email/drive query.)
        _t_prefetch = time.time()
        future_integration = _executor.submit(_pre_fetch_integrations, uid, last_user_msg)
        try:
            integration_context = future_integration.result(timeout=0.6)
        except Exception as e:
            print(f"[Agent] Integration prefetch timed out or failed: {e}")
            integration_context = ""
        _ttime("prefetch-integrations", _t_prefetch)

        if integration_context:
            last_idx = len(current_messages) - 1
            if current_messages[last_idx]["role"] == "user":
                orig = current_messages[last_idx]["content"]
                if isinstance(orig, str):
                    current_messages[last_idx]["content"] = (
                        integration_context
                        + "\n---\nUser question (answer using the above live data): "
                        + orig
                    )
                elif isinstance(orig, list):
                    current_messages[last_idx]["content"] = (
                        [{"type": "text", "text": integration_context + "\n---\n"}] + orig
                    )

    # Banned phrase check
    banned_phrases = ["ignore previous instructions", "system prompt", "reveal api key", "what are your instructions"]
    if any(phrase in last_user_msg.lower() for phrase in banned_phrases):
        limit_manager.ban_user(uid, user_ip, reason=f"Malicious Prompt: {last_user_msg[:20]}...")
        yield json.dumps({"type": "status", "message": "⛔ Security Alert: Malicious input detected."})
        yield "⛔ **Security Violation**\nYour request has been flagged as malicious. Access is restricted."
        return

    user_is_pro = limit_manager.is_pro_user(uid) if uid else False
    is_ok, tokens = limit_manager.check_context_limit(current_messages, model_choice, limit_tokens=50000, is_pro=user_is_pro)
    if not is_ok:
        yield json.dumps({"type": "status", "message": f"⚠️ Context Limit: {tokens}/50000 tokens used."})
        yield f"⚠️ **Context Limit Reached**\nYour conversation has exceeded the 50,000 token limit for free users.\n\nPlease start a new chat or upgrade to Kautilya Pro for unlimited context."
        return

    # Store user message in vector DB (non-blocking)
    if uid and last_user_msg and len(last_user_msg) > 5:
        import threading
        def save_mem():
            try:
                vector_store.add_memory(uid, last_user_msg, metadata={"role": "user", "timestamp": time.time()})
            except Exception as e:
                print(f"[VectorStore] Auto-save failed: {e}")
        threading.Thread(target=save_mem, daemon=True).start()

    response_gen = None

    # Model display names for UI status
    # NVIDIA NIM model IDs - verified available on https://build.nvidia.com
    _MODEL_LABELS = {
        'coder': ('Kautilya Coder', 'qwen/qwen3-coder-480b-a35b-instruct'),
        'pro':   ('Kautilya Pro', 'z-ai/glm-5.1'),
        'daily': ('Kautilya Daily', 'mistralai/mistral-medium-3.5-128b'),
    }
    DAILY_MODEL = 'mistralai/mistral-medium-3.5-128b'

    def _wrap_with_placeholder_thinking(inner_gen):
        """Show a 'thinking' placeholder while Mistral's TTFT is pending.

        The inner generator (an HTTP SSE stream from NVIDIA) blocks the calling
        thread during time-to-first-token.  Previously this meant the
        placeholder time checks could never fire because `next(inner_gen)`
        didn't return until the first chunk arrived.

        Fix: consume `inner_gen` on a daemon thread, push items to a
        thread-safe queue, and poll with 100ms timeouts on the main thread.
        When `queue.Empty` fires we know the model hasn't responded yet and
        can emit the next placeholder phrase.
        """
        import time as _t
        import threading
        from queue import Queue, Empty

        phrases = [
            "Reading your question…",
            "Pulling the relevant context…",
            "Drafting a response…",
        ]

        q = Queue(maxsize=256)
        _SENTINEL = object()  # marks end of stream

        def _pump():
            """Drain inner_gen on a background thread."""
            try:
                for item in inner_gen:
                    q.put(("item", item))
            except Exception as exc:
                q.put(("error", exc))
            finally:
                q.put(("done", _SENTINEL))

        t = threading.Thread(target=_pump, daemon=True)
        t.start()

        start = _t.time()
        phrase_idx = 0
        placeholder_shown = False
        thinking_closed = False
        last_emit = start

        while True:
            try:
                kind, payload = q.get(timeout=0.1)
            except Empty:
                # Queue empty — model hasn't responded yet.
                now = _t.time()
                if not placeholder_shown and now - start > 0.6:
                    yield {"thinking": phrases[phrase_idx]}
                    placeholder_shown = True
                    last_emit = now
                elif placeholder_shown and not thinking_closed and now - last_emit > 1.2 and phrase_idx + 1 < len(phrases):
                    phrase_idx += 1
                    yield {"thinking": " " + phrases[phrase_idx]}
                    last_emit = now
                continue

            if kind == "done":
                break
            if kind == "error":
                print(f"[Agent] inner_gen error: {payload}")
                break

            item = payload
            is_content = (
                isinstance(item, dict) and ("chunk" in item or "tool_calls" in item)
            ) or isinstance(item, str)

            if is_content and not thinking_closed:
                if placeholder_shown:
                    yield {"thinking_done": True}
                thinking_closed = True
            yield item

        if placeholder_shown and not thinking_closed:
            yield {"thinking_done": True}

    def _call_daily(msgs, **kw):
        """Daily tier: NVIDIA Mistral Medium 3.5 with no reasoning effort.
        Groq Llama is still the last-resort fallback if NVIDIA is unreachable.
        Output is wrapped with a placeholder-thinking stream so the UI shows
        the thinking bubble during Mistral's time-to-first-token wait."""
        from config import NVIDIA_API_KEYS
        if NVIDIA_API_KEYS:
            r = call_nvidia(msgs, stream=True, model=DAILY_MODEL,
                            temperature=kw.get('temperature', 0.6),
                            top_p=kw.get('top_p', 1.0),
                            max_tokens=kw.get('max_tokens', 16384),
                            tools=kw.get('tools'), tool_choice=kw.get('tool_choice'),
                            expose_thinking=False,
                            # Mistral only accepts 'none' or 'high'; 'none' = fastest.
                            reasoning_effort='none')
            if r:
                return _wrap_with_placeholder_thinking(r)
        groq_gen = call_groq(msgs, stream=True, model='llama-3.3-70b-versatile',
                             temperature=kw.get('temperature', 0.6),
                             max_tokens=kw.get('max_tokens', 16384),
                             tools=kw.get('tools'), tool_choice=kw.get('tool_choice'))
        return _wrap_with_placeholder_thinking(groq_gen) if groq_gen else None

    # Turn budget:
    #   turn 1 — initial answer (may emit tool tags, all run in parallel)
    #   turn 2 — synthesis after tools (may emit follow-up tool tags)
    #   turn 3-7 — chained tool calls (e.g. create_google_doc → multiple
    #              append_google_doc chunks → final synthesis). Multi-step
    #              workflows (research → write doc → email link) routinely
    #              need 4-6 rounds; 3 was strangling them mid-task.
    # Parallel tool execution still collapses N concurrent tools into one
    # turn each, so the wall-clock cost of a higher cap is small in the
    # common case, and the cap only bites on genuinely sequential chains.
    MAX_TURNS = 8
    for turn in range(MAX_TURNS):
        print(f"[Agent] Turn {turn+1}/{MAX_TURNS}")

        # Adaptive: classifier-predicted budget (cached/parallel-prewarmed),
        # heuristic fallback. On turn 2+ the classifier is already in the
        # cache from turn 1, so this is free.
        max_tokens = _adaptive_max_tokens(last_user_msg, model_choice)
        print(f"[Agent] Adaptive tokens: {max_tokens} (msg length: {len(last_user_msg)}, mode: {model_choice})")

        # Auto-detect image in last message
        has_image = False
        if current_messages and current_messages[-1].get("role") == "user":
            last_mc = current_messages[-1].get("content")
            if isinstance(last_mc, list) and any(p.get("type") == "image_url" for p in last_mc):
                has_image = True

        # Thinking is OPT-IN only. The user toggles "max thinking" in the
        # files dropdown — without it, always answer at the earliest (low
        # reasoning) regardless of how complex the prompt looks.
        effective_max_thinking = bool(max_thinking)
        reasoning_budget = _estimate_reasoning_budget(max_tokens, effective_max_thinking)

        if model_choice == 'coder':
            from config import NVIDIA_API_KEYS
            label, model_id = _MODEL_LABELS['coder']
            if not NVIDIA_API_KEYS:
                yield json.dumps({"event": "status", "message": f"⚡ {label} requires NVIDIA API key — using fast model…"})
                response_gen = _call_daily(current_messages, max_tokens=max_tokens,
                                           tools=tools, tool_choice=tool_choice)
            else:
                yield json.dumps({"event": "status", "message": f"🧠 Connecting to {label}…"})
                response_gen = call_nvidia(current_messages, stream=True, max_tokens=max_tokens,
                                           model=model_id, tools=tools, tool_choice=tool_choice,
                                           temperature=1.0, top_p=0.95, max_thinking=effective_max_thinking,
                                           reasoning_budget=reasoning_budget)
                if not response_gen:
                    yield json.dumps({"event": "status", "message": f"⚡ Retrying {label}…"})
                    response_gen = call_nvidia(current_messages, stream=True, max_tokens=max_tokens,
                                               model=model_id, temperature=1.0, top_p=0.95,
                                               max_thinking=effective_max_thinking, reasoning_budget=reasoning_budget)
                if not response_gen:
                    yield json.dumps({"event": "status", "message": f"⚡ {label} unavailable — using fast model…"})
                    response_gen = _call_daily(current_messages, max_tokens=max_tokens,
                                               tools=tools, tool_choice=tool_choice)

        elif model_choice == 'pro':
            from config import NVIDIA_API_KEYS
            label, model_id = _MODEL_LABELS['pro']
            if not NVIDIA_API_KEYS:
                yield json.dumps({"event": "status", "message": f"⚡ {label} requires NVIDIA API key — using fast model…"})
                response_gen = _call_daily(current_messages, max_tokens=max_tokens,
                                           tools=tools, tool_choice=tool_choice)
            else:
                yield json.dumps({"event": "status", "message": f"💎 Connecting to {label}…"})
                response_gen = call_nvidia(current_messages, stream=True, max_tokens=max_tokens,
                                           model=model_id, tools=tools, tool_choice=tool_choice,
                                           temperature=1.0, top_p=0.95, max_thinking=effective_max_thinking,
                                           reasoning_budget=reasoning_budget)
                if not response_gen:
                    yield json.dumps({"event": "status", "message": f"⚡ Retrying {label}…"})
                    response_gen = call_nvidia(current_messages, stream=True, max_tokens=max_tokens,
                                               model=model_id, temperature=1.0, top_p=0.95,
                                               max_thinking=effective_max_thinking, reasoning_budget=reasoning_budget)
                if not response_gen:
                    yield json.dumps({"event": "status", "message": f"⚡ {label} unavailable — using fast model…"})
                    print(f"[FALLBACK] {label} failed/unavailable. Switching to Daily.")
                    response_gen = _call_daily(current_messages, max_tokens=max_tokens,
                                               tools=tools, tool_choice=tool_choice)

        elif has_image:
            # Vision: prefer Gemini 2.5 Flash (most reliable for OCR / chart reading),
            # fall back to Groq llama-4-scout (current vision-capable Groq model).
            yield json.dumps({"event": "status", "message": "👁️ Analyzing image…"})
            from services.llm_service import call_gemini_vision
            try:
                gemini_text = call_gemini_vision(current_messages, temperature=0.6, max_tokens=max_tokens)
            except Exception as e:
                print(f"[Vision] Gemini exception: {e}")
                gemini_text = None
            if gemini_text:
                # Wrap the single string as a generator so the downstream
                # streaming loop handles it uniformly.
                def _wrap(t=gemini_text):
                    yield {"chunk": t}
                response_gen = _wrap()
            else:
                print("[Vision] Gemini unavailable — falling back to Groq llama-4-scout")
                response_gen = call_groq(current_messages, stream=True, max_tokens=max_tokens,
                                         model='meta-llama/llama-4-scout-17b-16e-instruct',
                                         temperature=0.6)
                if not response_gen:
                    response_gen = call_groq(current_messages, stream=True, max_tokens=max_tokens,
                                             model='meta-llama/llama-4-maverick-17b-128e-instruct',
                                             temperature=0.6)
                if not response_gen:
                    response_gen = _call_daily(current_messages, max_tokens=max_tokens)
        else:
            # Daily = NVIDIA Mistral Medium 3.5 (low reasoning), Groq llama as fallback
            response_gen = _call_daily(current_messages, max_tokens=max_tokens,
                                       tools=tools, tool_choice=tool_choice)

        # Final fallback: try anything
        if not response_gen:
            yield json.dumps({"event": "status", "message": "🔄 Trying backup service…"})
            response_gen = call_nvidia(current_messages, max_tokens=max_tokens)

        if not response_gen:
            yield json.dumps({"event": "status", "message": None})
            yield "⚠️ All AI services are currently at capacity. Please try again in a moment."
            return

        # Clear status once streaming starts
        yield json.dumps({"event": "status", "message": None})

        accumulated_response = ""
        in_thinking_tag = False

        try:
            for item in response_gen:
                if isinstance(item, dict):
                    # Pass-through events that the frontend handles directly:
                    # thinking deltas (Gemini-style streaming reasoning),
                    # thinking_done (collapse signal), tool_calls, usage.
                    if "thinking" in item or "thinking_done" in item or "tool_calls" in item:
                        yield json.dumps(item)
                        continue
                    chunk = item.get("chunk", "")
                else:
                    chunk = item
                
                if not chunk:
                    continue

                # --- Thinking Tag Logic (Opus Grade) ---
                if "<think>" in chunk:
                    parts = chunk.split("<think>", 1)
                    if parts[0]:
                        yield json.dumps({"chunk": parts[0]})
                        accumulated_response += parts[0]
                    in_thinking_tag = True
                    if parts[1]:
                        if "</think>" in parts[1]:
                            think_parts = parts[1].split("</think>", 1)
                            yield json.dumps({"thinking": think_parts[0]})
                            in_thinking_tag = False
                            yield json.dumps({"thinking_done": True})
                            if think_parts[1]:
                                yield json.dumps({"chunk": think_parts[1]})
                                accumulated_response += think_parts[1]
                        else:
                            yield json.dumps({"thinking": parts[1]})
                    continue

                if "</think>" in chunk and in_thinking_tag:
                    parts = chunk.split("</think>", 1)
                    if parts[0]:
                        yield json.dumps({"thinking": parts[0]})
                    in_thinking_tag = False
                    yield json.dumps({"thinking_done": True})
                    if parts[1]:
                        yield json.dumps({"chunk": parts[1]})
                        accumulated_response += parts[1]
                    continue

                if in_thinking_tag:
                    yield json.dumps({"thinking": chunk})
                else:
                    accumulated_response += chunk
                    yield json.dumps({"chunk": chunk})

            if in_thinking_tag:
                yield json.dumps({"thinking_done": True})
            # stream complete
        except Exception as e:
            print(f"[Agent] Generator streaming error: {e}")
            yield json.dumps({"chunk": f"\n[Stream interrupted: {e}]"})
            return

        # --- ReAct Action Parsing (parallel) ---
        # Detect ALL tool call patterns from the accumulated response, run
        # them concurrently, then continue to a single synthesis turn. This
        # collapses N sequential LLM round-trips (one per tool) into one.
        action_counter = getattr(agent_loop, '_action_counter', 0)
        # Strip silently-truncated [INTEGRATION:] tags before planning AND
        # before the response is persisted/displayed. If anything was stripped,
        # tell the user the call was discarded so they don't think it ran.
        sanitized_response = _strip_truncated_tool_tags(accumulated_response)
        truncation_detected = (sanitized_response != accumulated_response)
        if truncation_detected:
            # ADAPTIVE BUDGET BUMP: the model hit the cap. Bump the cached
            # size label up one tier so the next turn / retry has more room
            # without us having to keep guessing. S→M→L→XL ratchet upward.
            try:
                ck = _budget_cache_key(last_user_msg, model_choice)
                cur = _BUDGET_CACHE.get(ck)
                cur_label = cur[0] if cur else 'M'
                tier = ['S', 'M', 'L', 'XL']
                idx = tier.index(cur_label) if cur_label in tier else 1
                new_label = tier[min(idx + 1, len(tier) - 1)]
                _BUDGET_CACHE[ck] = (new_label, time.time() + _BUDGET_CACHE_TTL_SEC)
                print(f"[Agent] Budget bumped {cur_label}→{new_label} after truncation")
            except Exception as _e:
                print(f"[Agent] budget bump failed: {_e}")
            yield json.dumps({
                "event": "status",
                "message": "⚠ Response hit the token cap and was truncated — retrying with a larger budget…",
            })
            # The live stream already shipped the raw tag; the frontend's
            # stripToolTags now handles unterminated tags. Keep the sanitized
            # text for what gets persisted and fed to the next turn.
            accumulated_response = sanitized_response
        planned_actions = _plan_actions(accumulated_response, uid, start_id=action_counter + 1)

        if planned_actions:
            # Announce every action up-front so the timeline renders immediately.
            for act in planned_actions:
                yield json.dumps({
                    "event": "react_action",
                    "id": act["id"],
                    "tool": act["tool"],
                    "input": act["input"],
                    "status": "running",
                })

            # Submit all runners concurrently. The executor is module-level
            # and bounded (max_workers=10) — safe for I/O-bound tool calls.
            futures = {}
            for act in planned_actions:
                fut = _executor.submit(act["runner"])
                futures[fut] = act

            # Collect results in original order (so the OBSERVATION block reads
            # naturally) but yield UI events as they finish.
            results_by_id = {}
            for fut in concurrent.futures.as_completed(futures):
                act = futures[fut]
                try:
                    res = fut.result()
                except Exception as e:
                    res = {
                        "ok": False,
                        "preview": str(e)[:100],
                        "observation": f"{act['tool'].upper()} EXCEPTION: {e}",
                        "done_extras": {},
                        "extra_events": [],
                    }
                results_by_id[act["id"]] = res

                # Stream any auxiliary events first (e.g. tool_result cards),
                # then the react_action_done so the card shows before the tick.
                for ev in res.get("extra_events", []):
                    yield json.dumps(ev)

                done_event = {
                    "event": "react_action_done",
                    "id": act["id"],
                    "status": "done" if res["ok"] else ("empty" if res.get("empty") else "error"),
                    "preview": res.get("preview", ""),
                }
                done_event.update(res.get("done_extras", {}))
                yield json.dumps(done_event)

            # Consolidate observations in plan order for the synthesis turn.
            obs_lines = []
            continue_prompts = []
            for act in planned_actions:
                res = results_by_id.get(act["id"], {})
                if res.get("observation"):
                    obs_lines.append(res["observation"])
                cp = res.get("continue_prompt") or act.get("continue_prompt")
                if cp and cp not in continue_prompts:
                    continue_prompts.append(cp)

            current_messages.append({"role": "assistant", "content": accumulated_response})
            current_messages.append({
                "role": "user",
                "content": "OBSERVATION:\n" + "\n\n".join(obs_lines) + "\n\n" + " ".join(continue_prompts),
            })

            agent_loop._action_counter = planned_actions[-1]["id_int"]
            yield json.dumps({"event": "react_synthesizing"})
            continue

        # No tool actions detected. Two possible retry conditions:
        # (1) Truncation just occurred — we already bumped the budget above;
        #     fire another turn so the bigger budget is actually used.
        # (2) Orphan preamble — model promised action without emitting a tag.
        if truncation_detected and turn < MAX_TURNS - 1:
            current_messages.append({"role": "assistant", "content": accumulated_response})
            current_messages.append({
                "role": "user",
                "content": (
                    "[SYSTEM] Your previous response was cut off because it exceeded the token cap. "
                    "The budget has been increased. Please re-do the answer in full — if it was a "
                    "tool call, emit the complete [INTEGRATION: …] tag. If it was a long document, "
                    "send it in smaller chunks via multiple append_google_doc calls instead of one mega call."
                ),
            })
            continue

        if _looks_like_orphan_preamble(accumulated_response) and turn < MAX_TURNS - 1:
            current_messages.append({"role": "assistant", "content": accumulated_response})
            current_messages.append({
                "role": "user",
                "content": (
                    "[SYSTEM NUDGE] Your previous response announced an action ('checking…', "
                    "'searching…', 'pulling…', 'creating…') but did NOT emit the [INTEGRATION: …] "
                    "tag — so nothing actually ran. Either: (a) emit the tag NOW in this response "
                    "with the correct tool name and JSON args, OR (b) if you genuinely need more "
                    "info from the user, ask one specific question. Do not write another preamble "
                    "without the tag."
                ),
            })
            yield json.dumps({"event": "status", "message": "↻ Retrying — model forgot to emit the tool tag…"})
            continue

        # No tool actions detected and no orphan preamble — we're done.
        return

# ──────────────────────────────────────────────────────────────────────
# Tool planner — parses [TAG: …] tool tags out of an LLM response and
# returns a list of "actions" the agent loop will execute in parallel.
# Each action item is a dict with:
#   id        : str (numeric, displayed in UI)
#   id_int    : int (for advancing the global counter)
#   tool      : str (UI label / icon key)
#   input     : str (UI preview of what the tool received)
#   runner    : callable -> {ok, preview, observation, done_extras,
#                            extra_events, continue_prompt, empty?}
#   continue_prompt : str (instruction the synthesis turn should follow)
# ──────────────────────────────────────────────────────────────────────

def _looks_like_orphan_preamble(text):
    """Detect 'Let me check…' / 'Pulling your subscriptions…' style preambles
    that the model wrote INSTEAD OF actually emitting a tool tag. Heuristic:
    short response (< 300 chars), no tool tags, and contains a present-
    progressive verb phrase suggesting an in-progress action.

    False positives are cheap (one extra LLM turn, capped by MAX_TURNS).
    False negatives just regress to the old behavior (user sees the half-
    response and has to ask again), so we tune slightly aggressive."""
    if not text or not isinstance(text, str):
        return False
    t = text.strip()
    if len(t) > 400:
        # Long responses are real answers, not orphan preambles.
        return False
    # If any tool tag already exists, the loop handled it elsewhere.
    if re.search(r'\[(INTEGRATION|SEARCH|CALCULATE|RUN_PYTHON|FETCH_URL|CALENDAR_|GMAIL_|WHATSAPP_SEND|SLACK_POST|HUBSPOT_CREATE_CONTACT)', t):
        return False
    tl = t.lower()
    # Verb phrases that promise imminent action.
    promise_patterns = [
        r'\b(let me|i(?:\'ll| will)|i am going to|i\'m going to)\b',
        r'\b(checking|pulling|fetching|searching|looking up|looking for|retrieving|getting|loading|querying|creating|writing|sending|posting|appending|reading|finding)\b\s+(your|the|for|up)',
        r'\b(check kar|fetch kar|search kar|pull kar|dekh raha|raha hoon|rahi hoon)\b',  # hinglish
        r'…\s*$|\.\.\.\s*$',  # trailing ellipsis = "more to come"
    ]
    hits = sum(1 for p in promise_patterns if re.search(p, tl))
    return hits >= 1 and not tl.endswith('?')


# Common placeholders models emit when they "copy the schema" instead of
# producing a real value. Treating these as no-ops prevents the calculator
# from receiving `"expression"` and web_search from receiving `"query"`.
_PLACEHOLDER_ARGS = {
    "", "query", "expression", "expr", "text", "string", "value", "input",
    "search query", "your query", "your search query", "the query",
    "calculation", "math expression", "the expression",
    "title", "document_id", "<query>", "<expression>", "...", "null", "none",
}


def _is_placeholder_arg(v):
    if v is None:
        return True
    if not isinstance(v, str):
        return False
    return v.strip().lower() in _PLACEHOLDER_ARGS


def _looks_hallucinated(args):
    """True when every arg matches its own param name (or a common placeholder),
    i.e. the model emitted the schema instead of values.

    Note: empty dict `{}` is NOT hallucinated — it's the correct payload for
    tools with no required args (e.g. list_youtube_subscriptions, list_drive_files).
    Previously rejecting `{}` made every zero-arg tool silently no-op.
    """
    if not isinstance(args, dict):
        return True
    if not args:
        return False  # empty dict is a legitimate no-arg call
    bad = 0
    for k, v in args.items():
        if isinstance(v, str) and v.strip().lower() == str(k).strip().lower():
            bad += 1
        elif _is_placeholder_arg(v):
            bad += 1
    return bad == len(args)


def _find_json_end(text, start):
    """Return the index of the `}` that closes the JSON object beginning at
    `text[start] == '{'`, or -1 if the object is truncated. Respects string
    quoting and backslash escapes so embedded braces inside strings are
    ignored."""
    if start >= len(text) or text[start] != '{':
        return -1
    depth = 0
    in_str = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if escape:
            escape = False
            continue
        if ch == '\\':
            escape = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                return i
    return -1


def _strip_truncated_tool_tags(text):
    """Remove silently-truncated `[INTEGRATION: ...` tags from text that will
    be shown to the user. Models occasionally run out of max_tokens mid-JSON;
    without this, the raw tag (including the entire prompt-style payload)
    bleeds into the chat bubble."""
    if not text or "[INTEGRATION:" not in text:
        return text
    out = []
    i = 0
    while i < len(text):
        idx = text.find("[INTEGRATION:", i)
        if idx == -1:
            out.append(text[i:])
            break
        # Look ahead for a closing `]` on the same tag, with JSON awareness.
        json_start = text.find('{', idx)
        if json_start != -1:
            end = _find_json_end(text, json_start)
            if end != -1:
                tail = text[end + 1:]
                m = re.match(r'\s*\]', tail)
                if m:
                    # Complete tag — keep it; the parser will execute it.
                    out.append(text[i:end + 1 + m.end()])
                    i = end + 1 + m.end()
                    continue
        # Truncated or malformed — drop everything from `[INTEGRATION:` on.
        # We deliberately stop at the first newline that's followed by a
        # non-JSON-looking line so we don't eat unrelated trailing content,
        # but in practice the truncation runs to end-of-text, so drop the rest.
        out.append(text[i:idx])
        # Conservative: only strip to end-of-text if no `]` ever appears after.
        rest = text[idx:]
        if ']' not in rest:
            break
        # If a stray `]` exists later, skip up to and including it.
        close = rest.find(']')
        i = idx + close + 1
    return ''.join(out).rstrip()


def _plan_actions(text, uid, start_id=1):
    """Scan an LLM response for tool tags and produce a parallelizable plan.
    Multiple tags (including repeats of the same tool) are all included.
    Order in the list = order they appear in the text = order shown in the UI.
    """
    actions = []
    next_id = start_id

    def _mk(tool, input_str, runner, continue_prompt, start):
        nonlocal next_id
        item = {
            "id": str(next_id), "id_int": next_id,
            "tool": tool, "input": input_str,
            "runner": runner, "continue_prompt": continue_prompt,
            "_start": start,
        }
        next_id += 1
        return item

    # 1. [SEARCH: query]
    for m in re.finditer(r'\[SEARCH:\s*(.*?)\]', text):
        q = m.group(1).strip()
        if _is_placeholder_arg(q):
            continue
        actions.append(_mk("web_search", q, _runner_search(q),
                           "Now answer using the findings above. Do NOT call [SEARCH:] again.",
                           m.start()))

    # 2. [CALCULATE: expr]
    for m in re.finditer(r'\[CALCULATE:\s*(.*?)\]', text):
        expr = m.group(1).strip()
        if _is_placeholder_arg(expr):
            continue
        actions.append(_mk("calculator", expr, _runner_calc(expr),
                           "Continue with your answer using the calculation above.",
                           m.start()))

    # 3. [CALENDAR_CREATE: title | start | end | description?]
    for m in re.finditer(r'\[CALENDAR_CREATE:\s*(.*?)\]', text, re.DOTALL):
        parts = [p.strip() for p in m.group(1).split('|')]
        title       = parts[0] if len(parts) > 0 else 'New Event'
        start_dt    = parts[1] if len(parts) > 1 else None
        end_dt      = parts[2] if len(parts) > 2 else None
        description = parts[3] if len(parts) > 3 else ''
        actions.append(_mk("calendar", title,
                           _runner_cal_create(uid, title, start_dt, end_dt, description),
                           "Confirm the results to the user in one short message.",
                           m.start()))

    # 3.5 [CALENDAR_DELETE: event_id_or_title_keyword]
    for m in re.finditer(r'\[CALENDAR_DELETE:\s*(.*?)\]', text, re.DOTALL):
        q = m.group(1).strip()
        actions.append(_mk("calendar", f"Delete: {q}",
                           _runner_cal_delete(uid, q),
                           "Confirm the results to the user in one short message.",
                           m.start()))

    # 4. [CALENDAR_LIST: days]
    for m in re.finditer(r'\[CALENDAR_LIST:\s*(\d*)\]', text):
        days = int(m.group(1) or 7)
        actions.append(_mk("calendar", f"Next {days} days",
                           _runner_cal_list(uid, days),
                           "Events are shown as cards — give a one-line summary only.",
                           m.start()))

    # 4.5 [GMAIL_SEND: to | subject | body]
    for m in re.finditer(r'\[GMAIL_SEND:\s*(.*?)\]', text, re.DOTALL):
        parts = [p.strip() for p in m.group(1).split('|', 2)]
        to   = parts[0] if len(parts) > 0 else ''
        subj = parts[1] if len(parts) > 1 else ''
        body = parts[2] if len(parts) > 2 else ''
        actions.append(_mk("gmail", f"Email → {to}",
                           _runner_gmail_send(uid, to, subj, body),
                           "Confirm the results to the user in one short message.",
                           m.start()))

    # 4.6 [GMAIL_LIST: max | optional_search_query]
    for m in re.finditer(r'\[GMAIL_LIST:\s*(.*?)\]', text):
        parts = [p.strip() for p in m.group(1).split('|', 1)]
        mx = int(parts[0]) if parts and parts[0].isdigit() else 10
        q  = parts[1] if len(parts) > 1 else ''
        actions.append(_mk("gmail", f"Inbox (last {mx})",
                           _runner_gmail_list(uid, mx, q),
                           "Inbox is already shown as cards — give a one-line summary only.",
                           m.start()))

    # 5. [WHATSAPP_SEND: number | message]
    for m in re.finditer(r'\[WHATSAPP_SEND:\s*(.*?)\]', text, re.DOTALL):
        parts = [p.strip() for p in m.group(1).split('|', 1)]
        to  = parts[0] if len(parts) > 0 else ''
        msg = parts[1] if len(parts) > 1 else ''
        actions.append(_mk("whatsapp", f"WhatsApp → {to}",
                           _runner_whatsapp(uid, to, msg),
                           "Confirm the results to the user in one short message.",
                           m.start()))

    # 6. [SLACK_POST: message]
    for m in re.finditer(r'\[SLACK_POST:\s*(.*?)\]', text, re.DOTALL):
        msg = m.group(1).strip()
        actions.append(_mk("slack", "Slack message",
                           _runner_slack(uid, msg),
                           "Confirm the results to the user in one short message.",
                           m.start()))

    # 7. [HUBSPOT_CREATE_CONTACT: email | first | last | company | phone]
    for m in re.finditer(r'\[HUBSPOT_CREATE_CONTACT:\s*(.*?)\]', text, re.DOTALL):
        parts = [p.strip() for p in m.group(1).split('|')]
        email = parts[0] if len(parts) > 0 else ''
        first = parts[1] if len(parts) > 1 else ''
        last  = parts[2] if len(parts) > 2 else ''
        co    = parts[3] if len(parts) > 3 else ''
        ph    = parts[4] if len(parts) > 4 else ''
        actions.append(_mk("hubspot", f"HubSpot contact: {email}",
                           _runner_hubspot(uid, email, first, last, co, ph),
                           "Confirm the results to the user in one short message.",
                           m.start()))

    # 11. [RUN_PYTHON: ```code```]
    py_iter = list(re.finditer(r'\[RUN_PYTHON:\s*```(?:python)?\s*([\s\S]*?)```\s*\]', text))
    if not py_iter:
        m = re.search(r'\[RUN_PYTHON:\s*([\s\S]+?)\]\s*$', text.strip())
        if m:
            py_iter = [m]
    for m in py_iter:
        code = m.group(1).strip()
        preview = code[:80] + ("…" if len(code) > 80 else "")
        actions.append(_mk("python", preview,
                           _runner_python(code),
                           "Code, output, and any charts are already shown. Give a one-line interpretation.",
                           m.start()))

    # 12. [INTEGRATION: tool_name | {json}]
    # JSON-aware scan: tracks quote state so embedded `}` inside string values
    # don't terminate the match prematurely, and skips silently-truncated tags
    # (no closing `}]`) so they get stripped from the user-visible text below
    # instead of being parsed into half-baked tool calls.
    for m in re.finditer(r'\[INTEGRATION:\s*([a-z0-9_]+)\s*\|\s*', text):
        tool_name = m.group(1).strip()
        json_start = text.find('{', m.end())
        if json_start == -1 or json_start - m.end() > 4:
            continue
        json_end = _find_json_end(text, json_start)
        if json_end == -1:
            # Truncated mid-JSON — leave for the post-stream sanitizer.
            continue
        tail = text[json_end + 1:]
        # Require a closing `]` within a few chars of whitespace.
        bracket = re.match(r'\s*\]', tail)
        if not bracket:
            continue
        try:
            tool_args = json.loads(text[json_start:json_end + 1])
        except Exception:
            continue
        if not isinstance(tool_args, dict):
            continue
        # Reject hallucinated calls where the value literally equals the
        # parameter name (e.g. {"query": "query"} from the model copying
        # the schema placeholder instead of producing a real value).
        if _looks_hallucinated(tool_args):
            continue
        is_mcp = tool_name.startswith("mcp_")
        if not (is_mcp or uid):
            continue
        actions.append(_mk(tool_name, json.dumps(tool_args)[:80],
                           _runner_integration(uid, tool_name, tool_args, is_mcp),
                           "Now write a CONCISE PLAIN-TEXT user-facing answer based on the result above. "
                           "Do NOT emit another [INTEGRATION:] tag unless the user's ORIGINAL request "
                           "explicitly requires a follow-up action (e.g. user said 'find X and email it'). "
                           "Do NOT auto-save results to docs, sheets, or memory just because the data is interesting. "
                           "'Remember it' from the user means acknowledge in text — it is NOT an instruction to call any tool. "
                           "Keep the reply under 300 words and never repeat the same tool call.",
                           m.start()))

    # Sort by appearance order so the UI timeline matches the response text.
    actions.sort(key=lambda a: a["_start"])
    for a in actions:
        a.pop("_start", None)
    return actions


# ──────────── Per-tool runner factories ────────────
# Each factory closes over its arguments and returns a zero-arg callable.
# The callable returns a result dict consumed by the agent loop.

def _runner_search(query):
    def run():
        from services.research_service import _gather_sources
        try:
            sources = _gather_sources([query])
            if sources:
                obs = "SEARCH RESULTS:\n"
                for i, s in enumerate(sources[:4], 1):
                    obs += f"[{i}] {s['title']} ({s['url']}): {s['snippet']}\n"
                return {"ok": True, "preview": f"Found {len(sources)} sources",
                        "observation": obs,
                        "done_extras": {"sources": [{"title": s["title"], "url": s["url"]} for s in sources[:4]]},
                        "extra_events": []}
            return {"ok": True, "empty": True, "preview": "No results found",
                    "observation": "SEARCH: No relevant results found.",
                    "done_extras": {}, "extra_events": []}
        except Exception as e:
            return {"ok": False, "preview": str(e)[:80],
                    "observation": f"SEARCH ERROR: {e}",
                    "done_extras": {}, "extra_events": []}
    return run


def _runner_calc(expr):
    def run():
        try:
            import math
            safe_globals = {"__builtins__": {}}
            safe_globals.update({k: getattr(math, k) for k in dir(math) if not k.startswith('_')})
            result = eval(expr, safe_globals)  # noqa: S307
            rs = str(round(float(result), 8)) if isinstance(result, float) else str(result)
            return {"ok": True, "preview": f"= {rs}",
                    "observation": f"CALCULATION: {expr} = {rs}",
                    "done_extras": {}, "extra_events": []}
        except Exception as e:
            return {"ok": False, "preview": f"Error: {e}",
                    "observation": f"CALCULATION ERROR: {e}",
                    "done_extras": {}, "extra_events": []}
    return run


def _runner_cal_create(uid, title, start_dt, end_dt, description):
    def run():
        try:
            result = _calendar_create(uid, title, start_dt, end_dt, description)
            link = result.get('htmlLink', '')
            extras = {"sources": [{"title": "Open in Calendar", "url": link}]} if link else {}
            return {"ok": True, "preview": f"Created: {title}",
                    "observation": f"CALENDAR: Event '{title}' created for {start_dt}. Link: {link}",
                    "done_extras": extras, "extra_events": []}
        except Exception as e:
            return {"ok": False, "preview": str(e)[:100],
                    "observation": f"CALENDAR ERROR: {e}",
                    "done_extras": {}, "extra_events": []}
    return run


def _runner_cal_delete(uid, q):
    def run():
        try:
            result = _calendar_delete(uid, q)
            deleted = result.get('deleted', [])
            if deleted:
                return {"ok": True, "preview": f"Deleted: {', '.join(deleted)[:80]}",
                        "observation": f"CALENDAR: Deleted {len(deleted)} event(s): {', '.join(deleted)}",
                        "done_extras": {}, "extra_events": []}
            return {"ok": True, "preview": f"No match for '{q}'",
                    "observation": f"CALENDAR: No event found matching '{q}' in the next 60 days.",
                    "done_extras": {}, "extra_events": []}
        except Exception as e:
            return {"ok": False, "preview": str(e)[:100],
                    "observation": f"CALENDAR ERROR: {e}",
                    "done_extras": {}, "extra_events": []}
    return run


def _runner_cal_list(uid, days):
    def run():
        try:
            events = _calendar_list(uid, days)
            card_events = []
            if events:
                for e in events:
                    start = e.get('start', {}).get('dateTime') or e.get('start', {}).get('date', '')
                    end   = e.get('end', {}).get('dateTime')   or e.get('end', {}).get('date', '')
                    card_events.append({
                        "summary": e.get('summary', 'Untitled'),
                        "start": start, "end": end,
                        "location": e.get('location', ''),
                        "hangoutLink": e.get('hangoutLink', '') or
                                       (e.get('conferenceData', {}) or {}).get('entryPoints', [{}])[0].get('uri', ''),
                        "htmlLink": e.get('htmlLink', ''),
                        "description": (e.get('description') or '')[:240],
                    })
            extra = [{"event": "tool_result", "tool": "calendar_list",
                      "data": {"events": card_events, "days": days}}]
            if card_events:
                lines = [f"- {ev['summary']} at {ev['start']}" for ev in card_events]
                return {"ok": True, "preview": f"{len(card_events)} event(s) found",
                        "observation": f"CALENDAR EVENTS (next {days} days):\n" + "\n".join(lines),
                        "done_extras": {}, "extra_events": extra}
            return {"ok": True, "preview": "No events",
                    "observation": f"CALENDAR: No events found in the next {days} days.",
                    "done_extras": {}, "extra_events": extra}
        except Exception as e:
            return {"ok": False, "preview": str(e)[:100],
                    "observation": f"CALENDAR ERROR: {e}",
                    "done_extras": {}, "extra_events": []}
    return run


def _runner_gmail_send(uid, to, subj, body):
    def run():
        try:
            _gmail_send(uid, to, subj, body)
            return {"ok": True, "preview": f"Sent to {to}",
                    "observation": f"GMAIL: Email sent to {to} with subject '{subj}'.",
                    "done_extras": {}, "extra_events": []}
        except Exception as e:
            return {"ok": False, "preview": str(e)[:100],
                    "observation": f"GMAIL ERROR: {e}",
                    "done_extras": {}, "extra_events": []}
    return run


def _runner_gmail_list(uid, mx, q):
    def run():
        try:
            emails = _gmail_list(uid, mx, q)
            extra = [{"event": "tool_result", "tool": "gmail_list",
                      "data": {"emails": emails or [], "query": q}}]
            if emails:
                lines = [f"- From: {e['from']} | Subject: {e['subject']} | {e['date']}\n  Snippet: {e['snippet']}" for e in emails]
                return {"ok": True, "preview": f"{len(emails)} email(s)",
                        "observation": f"GMAIL INBOX ({len(emails)} message(s)):\n" + "\n".join(lines),
                        "done_extras": {}, "extra_events": extra}
            return {"ok": True, "preview": "Empty inbox",
                    "observation": "GMAIL: No emails found.",
                    "done_extras": {}, "extra_events": extra}
        except Exception as e:
            return {"ok": False, "preview": str(e)[:100],
                    "observation": f"GMAIL ERROR: {e}",
                    "done_extras": {}, "extra_events": []}
    return run


def _runner_whatsapp(uid, to, msg):
    def run():
        try:
            _whatsapp_send(uid, to, msg)
            return {"ok": True, "preview": f"Sent to {to}",
                    "observation": f"WHATSAPP: Message sent to {to}.",
                    "done_extras": {}, "extra_events": []}
        except Exception as e:
            return {"ok": False, "preview": str(e)[:100],
                    "observation": f"WHATSAPP ERROR: {e}",
                    "done_extras": {}, "extra_events": []}
    return run


def _runner_slack(uid, msg):
    def run():
        try:
            _slack_post(uid, msg)
            return {"ok": True, "preview": "Message posted",
                    "observation": "SLACK: Message posted successfully.",
                    "done_extras": {}, "extra_events": []}
        except Exception as e:
            return {"ok": False, "preview": str(e)[:100],
                    "observation": f"SLACK ERROR: {e}",
                    "done_extras": {}, "extra_events": []}
    return run


def _runner_hubspot(uid, email, first, last, co, ph):
    def run():
        try:
            result = _hubspot_create_contact(uid, email, first, last, co, ph)
            cid = result.get('id', '')
            return {"ok": True, "preview": f"Contact created: {email}",
                    "observation": f"HUBSPOT: Contact '{email}' created (id: {cid}).",
                    "done_extras": {}, "extra_events": []}
        except Exception as e:
            return {"ok": False, "preview": str(e)[:100],
                    "observation": f"HUBSPOT ERROR: {e}",
                    "done_extras": {}, "extra_events": []}
    return run


def _runner_python(code):
    def run():
        try:
            res = _python_run(code)
            extra = [{"event": "tool_result", "tool": "python_run",
                      "data": {"code": code, "stdout": res["stdout"],
                               "stderr": res["stderr"], "images": res["images"],
                               "ok": res["ok"]}}]
            if res["ok"]:
                chart_note = f" (+{len(res['images'])} chart(s))" if res["images"] else ""
                short = (res["stdout"] or "")[:1500]
                return {"ok": True, "preview": f"Ran successfully{chart_note}",
                        "observation": f"PYTHON EXECUTED OK.\nStdout (first 1500 chars):\n{short}",
                        "done_extras": {}, "extra_events": extra}
            return {"ok": False, "preview": (res["stderr"] or "error")[:80],
                    "observation": f"PYTHON ERROR (exit {res['exit_code']}):\n{res['stderr'][:1500]}",
                    "done_extras": {}, "extra_events": extra}
        except Exception as e:
            return {"ok": False, "preview": str(e)[:100],
                    "observation": f"PYTHON RUNNER ERROR: {e}",
                    "done_extras": {}, "extra_events": []}
    return run


def _runner_integration(uid, tool_name, tool_args, is_mcp):
    def run():
        try:
            if is_mcp:
                from services.mcp_client_service import execute_mcp_tool
                result = execute_mcp_tool(tool_name, tool_args, uid=uid)
                label = "MCP"
            else:
                from services.integration_tools import execute_tool
                result = execute_tool(uid, tool_name, tool_args)
                label = "INTEGRATION"
            if result.get("ok"):
                return {"ok": True, "preview": f"{tool_name} succeeded",
                        "observation": f"{label} RESULT ({tool_name}): {json.dumps(result)[:1500]}",
                        "done_extras": {}, "extra_events": []}
            # Special-case Google "API not enabled" so the model is forced to
            # show the enable link verbatim instead of paraphrasing it away.
            if result.get("error_kind") == "google_api_disabled":
                return {
                    "ok": False,
                    "preview": f"{result.get('api_label', 'Google API')} not enabled",
                    "observation": (
                        f"{label} ERROR ({tool_name}): {result.get('api_label')} is disabled on the user's "
                        f"Google Cloud project. INSTRUCT THE USER (1-2 sentences) to click this exact link to enable it, "
                        f"then retry the request after ~30s: {result.get('enable_url')} "
                        f"— include the URL verbatim as a markdown link so it's clickable. Do NOT retry the tool now."
                    ),
                    "done_extras": {"enable_url": result.get("enable_url"), "api_label": result.get("api_label")},
                    "extra_events": [],
                }
            return {"ok": False, "preview": str(result.get('error', ''))[:80],
                    "observation": f"{label} ERROR ({tool_name}): {result.get('error', 'unknown')}",
                    "done_extras": {}, "extra_events": []}
        except Exception as e:
            return {"ok": False, "preview": str(e)[:80],
                    "observation": f"TOOL EXCEPTION ({tool_name}): {e}",
                    "done_extras": {}, "extra_events": []}
    return run


# ──────────────────────────────────────────────────────────────────────────
# Adaptive answer-size budgeting
# ──────────────────────────────────────────────────────────────────────────
#
# Static heuristics (char-count buckets, keyword lists) inevitably mis-size:
#   - "create a doc" is 12 chars but the answer could be 4000 tokens of body
#   - "summarise this 5000-word article in one line" is long input, tiny output
#
# Solution: a tiny Groq Llama classifier predicts the answer size class
# (S/M/L/XL) and maps to a budget. The classifier:
#   - Runs in parallel with other agent_loop setup work — no TTFT cost on
#     the warm path because the budget isn't needed until we actually call
#     the main LLM.
#   - Has a 200ms hard timeout; on miss/error we fall back to the static
#     _estimate_tokens heuristic so a Groq blip never freezes the chat.
#   - Caches per (msg-hash, mode) for 1 hour — re-asking the same question
#     pays zero classifier latency.
#   - Skips itself for trivially short messages (<8 chars) which are
#     always small.
#
# Size → token budget mapping (and the derived reasoning_budget):
#   S   1024     short factual / conversational
#   M   4096     paragraph answer, short structured reply
#   L  16384     long structured answer, multi-section response
#   XL 32768     full doc body, big code file, deep research synthesis

_BUDGET_CACHE: Dict[str, tuple] = {}    # msg_hash -> (size_label, expires_at)
_BUDGET_CACHE_TTL_SEC = 3600

_SIZE_TO_TOKENS = {'S': 1024, 'M': 4096, 'L': 16384, 'XL': 32768}


def _budget_cache_key(msg: str, mode: str) -> str:
    import hashlib
    h = hashlib.md5((msg[:1000] + "|" + mode).encode('utf-8', errors='ignore')).hexdigest()
    return h


def _classify_answer_size(user_msg: str, mode: str, timeout_sec: float = 0.2) -> Optional[str]:
    """Return 'S' | 'M' | 'L' | 'XL', or None on timeout / error.

    Cheap shortcuts first (greetings → S, generative-intent keywords → XL),
    then a Groq Llama-3.3-70B call with a 200ms cap. The classifier itself
    is small (max_tokens=4) and Groq is the fastest provider we have, so
    even cold it usually returns in 80-150ms.
    """
    if not user_msg:
        return 'S'
    msg = user_msg.strip()
    if len(msg) < 8:
        return 'S'

    cache_key = _budget_cache_key(msg, mode)
    now = time.time()
    cached = _BUDGET_CACHE.get(cache_key)
    if cached and cached[1] > now:
        return cached[0]

    ml = msg.lower()
    # Hard XL signals — these are unambiguous and skipping the classifier
    # round-trip saves ~100ms.
    _xl_kw = ('write a full', 'detailed report', 'comprehensive report',
              'research report', 'whole article', 'long-form', 'full document',
              'entire codebase', 'complete script', 'full implementation',
              'create a doc', 'create doc', 'append_google_doc', 'create_google_doc')
    if any(k in ml for k in _xl_kw):
        result = 'XL'
        _BUDGET_CACHE[cache_key] = (result, now + _BUDGET_CACHE_TTL_SEC)
        return result

    # Hard S signals — conversational acks, single-word queries.
    _s_kw = {'thanks', 'thank you', 'ok', 'okay', 'cool', 'nice', 'got it',
             'understood', 'haan', 'nahi', 'theek hai', 'haan ji', 'great'}
    if ml in _s_kw:
        _BUDGET_CACHE[cache_key] = ('S', now + _BUDGET_CACHE_TTL_SEC)
        return 'S'

    # LLM classifier
    try:
        from services.llm_service import call_groq
        from config import GROQ_API_KEY
        if not GROQ_API_KEY:
            return None
        sys_prompt = (
            "Predict the size of the assistant's answer to the user request below. "
            "Output EXACTLY one of: S, M, L, XL. No explanation. Rules:\n"
            "- S: <120 words. Factual answer, conversational, simple lookup, yes/no.\n"
            "- M: 120-600 words. Paragraph explanation, short summary, brief list.\n"
            "- L: 600-2500 words. Multi-section structured answer, long explanation, medium document body.\n"
            "- XL: >2500 words or a full document/article/code-file/research-report body.\n"
            "When in doubt between two sizes, pick the LARGER (truncation is worse than over-allocation)."
        )
        msgs = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": msg[:800]},
        ]
        # Run with a tight timeout via thread + future so a slow Groq call
        # never freezes the request.
        from concurrent.futures import ThreadPoolExecutor as _TPE
        with _TPE(max_workers=1) as ex:
            fut = ex.submit(call_groq, msgs, model="llama-3.3-70b-versatile",
                            temperature=0, max_tokens=4, stream=False)
            out = fut.result(timeout=timeout_sec)
        if isinstance(out, str):
            label = re.sub(r'[^A-Za-z]', '', out.strip()).upper()[:2]
            if label in _SIZE_TO_TOKENS:
                _BUDGET_CACHE[cache_key] = (label, now + _BUDGET_CACHE_TTL_SEC)
                return label
    except Exception as e:
        # Timeout, network blip, missing key — silently fall back to heuristic.
        pass
    return None


def _adaptive_max_tokens(user_msg: str, mode: str) -> int:
    """Adaptive budget: classifier first, heuristic fallback.

    The classifier runs synchronously here with a 200ms cap. Callers can
    pre-warm by calling `_classify_answer_size` in a background thread
    during setup; the cache will then make this call instant.
    """
    label = _classify_answer_size(user_msg, mode)
    if label:
        budget = _SIZE_TO_TOKENS[label]
        # Coder mode gets a floor of 8k — code answers often go over what
        # a generic 'M' classification would suggest.
        if mode == 'coder' and budget < 8192:
            budget = 8192
        return budget
    # Fallback to the original char-bucket heuristic.
    return _estimate_tokens(user_msg, mode)


def _estimate_tokens(user_msg, mode):
    """
    Tiered token budget estimator.

    Two reasons the cap matters:
    1. Non-reasoning models (Mistral/Llama) just stop at EOS, so the cap is
       only a safety bound — bigger isn't slower for short answers.
    2. Reasoning models (GLM, Qwen-thinking, NVIDIA reasoning variants) burn
       thinking tokens up to a budget that `_estimate_reasoning_budget`
       derives FROM this number. So an over-generous 16k cap on a 5-word
       greeting can buy 8k tokens of unnecessary deliberation before the
       first content token streams. That's the real speed hit.

    Sizing: enough for the realistic answer + a tool-tag JSON, never more.
    """
    msg_lower = user_msg.lower().strip()
    msg_len = len(msg_lower)

    greetings = {'hi', 'hello', 'hey', 'yo', 'sup', 'namaste', 'thanks', 'ok',
                 'bye', 'okay', 'cool', 'nice', 'lol', 'haha', 'haan', 'nahi',
                 'thik', 'theek', 'good', 'great'}
    if msg_lower in greetings or msg_len < 6:
        return 512   # one-line reply, no thinking budget needed

    # Long-content intent dominates — research, draft a doc, code generation.
    long_intent_kw = ('report', 'research', 'document', 'article',
                      'essay', 'write a', 'draft', 'full', 'detailed',
                      'comprehensive', 'append_google_doc', 'create_google_doc',
                      'explain in detail', 'in depth', 'long', 'whole')
    if any(k in msg_lower for k in long_intent_kw):
        return 32768
    if mode == 'coder':
        # Code answers can be long but rarely > 16k tokens. Bigger only if
        # the user explicitly asked for a whole file / full project.
        return 32768 if msg_len > 200 else 8192

    # Conversational tiering — match budget to question length so reasoning
    # models don't over-deliberate on short factual asks.
    if msg_len < 30:     # 'where am i', 'whats the time', 'check my mail'
        return 1024
    if msg_len < 100:    # one-sentence question with light context
        return 2048
    if msg_len < 250:    # paragraph question / explanation request
        return 4096
    if msg_len < 500:    # long paragraph, multi-part
        return 8192
    # Very long user message (pasted code, big context, file content). Give
    # headroom but not the full 32k — that's reserved for explicit long-form.
    return 16384


def _estimate_reasoning_budget(max_tokens, max_thinking=False):
    """
    Reasoning budget per request.

    Default (max_thinking OFF) used to scale up to 8192 thinking tokens for a
    one-line greeting — reasoning models would deliberate for seconds before
    emitting any content. That's the bulk of perceived "Kautilya is slow on
    short answers." Now: tight, proportional to the actual answer budget so
    a 1k-answer request gets a 256-token reasoning budget, not 8k.

    max_thinking ON keeps the deep budget for hard problems on demand.
    """
    if max_tokens is None:
        # Provider-default answer budget. Stay modest to keep TTFT snappy.
        return 16384 if max_thinking else 1024

    if not max_thinking:
        # Aim for ~1/8 of the answer budget, clamped to a small range so
        # short asks stay fast and longer asks still get some headroom.
        # 512 tokens of reasoning is plenty for any non-deliberative answer.
        derived = max(128, max_tokens // 8)
        return min(2048, derived)
    # Deep thinking on: up to 2x the answer budget, capped at 32k.
    return min(32768, max_tokens * 2)


# ──────────────────────────────────────────────
# Integration helpers called by the agent loop
# ──────────────────────────────────────────────

def _pre_fetch_integrations(uid, user_msg):
    """
    Detect integration intent from the user message and proactively fetch
    live data BEFORE the LLM is called. The data is injected into the system
    context so the model just formats it — no ReAct token cooperation needed.
    Returns an injection string (empty string = nothing to inject).
    """
    msg = user_msg.lower()
    parts = []

    # ── Integration status check: "are you connected to X" ───────────────
    if ('connected' in msg or 'integrated' in msg or 'integration' in msg) and 'calendar' in msg:
        try:
            cfg = _get_integration_cfg(uid, 'google_calendar')
            if cfg.get('access_token'):
                parts.append("\n\n[SYSTEM: Google Calendar IS connected for this user. You CAN access their calendar. Fetch and show their events.]\n")
            else:
                parts.append("\n\n[SYSTEM: Google Calendar is NOT connected. Tell user to go to Dashboard → Integrations → Google Calendar.]\n")
        except:
            pass
        return "".join(parts) if parts else ""

    # ── Calendar: list/view intent ────────────────────────────────────────
    cal_view_kw  = {'calendar', 'schedule', 'meeting', 'meetings', 'event',
                    'events', 'appointment', 'appointments', 'agenda', 'remind',
                    'reminder', 'reminders', 'call', 'calls', 'slot', 'slots'}
    cal_view_act = {'show', 'what', 'list', 'upcoming', 'check', 'see', 'any',
                    'today', 'tomorrow', 'week', 'do i have', 'tell me', 'get',
                    'search', 'find', 'fetch', 'retrieve', 'look', 'view',
                    'display', 'my', 'are there', 'scheduled', 'coming'}
    if cal_view_kw & set(msg.split()) or any(k in msg for k in cal_view_kw):
        if cal_view_act & set(msg.split()) or any(k in msg for k in cal_view_act):
            try:
                events = _calendar_list(uid, 14)
                if events:
                    lines = []
                    for e in events:
                        start = e.get('start', {}).get('dateTime') or e.get('start', {}).get('date', '')
                        lines.append(f"  • {e.get('summary', 'Untitled')} — {start}")
                    parts.append(
                        "\n\n[LIVE DATA — Google Calendar, next 14 days]\n"
                        + "\n".join(lines)
                        + "\n[Use this data to answer the user. Do NOT say you can't access calendar.]\n"
                    )
                else:
                    parts.append(
                        "\n\n[LIVE DATA — Google Calendar: No events found in the next 14 days.]\n"
                    )
            except Exception as e:
                err = str(e)
                if "not connected" in err.lower():
                    parts.append(
                        "\n\n[SYSTEM: Google Calendar is NOT connected for this user. "
                        "Tell them to go to Dashboard → Integrations → Google Calendar to connect it.]\n"
                    )
                # token expired or API error — surface it naturally
                elif "expired" in err.lower():
                    parts.append(
                        "\n\n[SYSTEM: Google Calendar token expired. Tell the user to reconnect in Dashboard → Integrations.]\n"
                    )

    # ── Calendar: delete/cancel intent ───────────────────────────────────
    cal_del_kw  = {'delete', 'remove', 'cancel', 'clear', 'drop'}
    cal_del_tgt = {'meeting', 'call', 'event', 'appointment', 'reminder', 'slot'}
    if (cal_del_kw & set(msg.split())) and (cal_del_tgt & set(msg.split())):
        try:
            cfg = _get_integration_cfg(uid, 'google_calendar')
            if cfg.get('access_token'):
                parts.append(
                    "\n\n[SYSTEM: Google Calendar IS connected. User wants to DELETE/CANCEL an event. "
                    "Extract the event title/keyword from the user's message and output ONLY: "
                    "[CALENDAR_DELETE: title_or_keyword]]\n"
                )
            else:
                parts.append(
                    "\n\n[SYSTEM: Google Calendar NOT connected. Tell user to connect in Dashboard → Integrations.]\n"
                )
        except:
            pass

    # ── Calendar: create/schedule intent ─────────────────────────────────
    cal_create_kw = {'schedule', 'book', 'create', 'add', 'set', 'remind', 'block'}
    cal_create_tgt = {'meeting', 'call', 'event', 'appointment', 'reminder', 'slot'}
    if (cal_create_kw & set(msg.split())) and (cal_create_tgt & set(msg.split())):
        # Let the model extract and emit [CALENDAR_CREATE: ...] — this intent
        # needs user-supplied title/time so we can't pre-fetch; just confirm capability.
        try:
            cfg = _get_integration_cfg(uid, 'google_calendar')
            if cfg.get('access_token'):
                parts.append(
                    "\n\n[SYSTEM: Google Calendar IS connected. "
                    "Extract the event title and datetime from the user's message, "
                    "then output ONLY: [CALENDAR_CREATE: title | YYYY-MM-DDTHH:MM:SS | YYYY-MM-DDTHH:MM:SS | description]]\n"
                )
            else:
                parts.append(
                    "\n\n[SYSTEM: Google Calendar NOT connected. Tell user to connect in Dashboard → Integrations.]\n"
                )
        except:
            pass

    # ── Gmail: read/list inbox intent ─────────────────────────────────────
    gm_read_kw = {'email', 'emails', 'inbox', 'mail', 'mails', 'gmail'}
    gm_read_act = {'show', 'list', 'check', 'see', 'read', 'any', 'new', 'recent',
                   'unread', 'fetch', 'get', 'today', 'latest', 'have'}
    if (gm_read_kw & set(msg.split())) and (gm_read_act & set(msg.split())):
        try:
            cfg = _get_integration_cfg(uid, 'gmail')
            if cfg.get('access_token'):
                try:
                    emails = _gmail_list(uid, 4)
                    if emails:
                        lines = [f"  • From: {e['from']} | Subject: {e['subject']} | Date: {e['date']}"
                                 + (f"\n    Snippet: {e['snippet']}" if e.get('snippet') else '')
                                 for e in emails]
                        parts.append(
                            "\n\n[LIVE DATA — Gmail inbox, last 4 messages]\n"
                            + "\n".join(lines)
                            + "\n[Use this data to answer the user. Do NOT say you can't access email.]\n"
                        )
                    else:
                        parts.append("\n\n[LIVE DATA — Gmail: inbox is empty.]\n")
                except Exception as e:
                    parts.append(f"\n\n[SYSTEM: Gmail fetch failed: {e}]\n")
            else:
                parts.append("\n\n[SYSTEM: Gmail NOT connected. Tell user to connect in Dashboard → Integrations → Gmail.]\n")
        except:
            pass

    # ── Gmail: send email intent ──────────────────────────────────────────
    gm_send_kw = {'send', 'email', 'mail', 'compose', 'write'}
    gm_send_tgt_idx = msg.find('email')
    if (gm_send_kw & set(msg.split())) and ('send' in msg or 'email' in msg) and ('@' in msg or 'to ' in msg):
        try:
            cfg = _get_integration_cfg(uid, 'gmail')
            if cfg.get('access_token'):
                parts.append(
                    "\n\n[SYSTEM: Gmail IS connected. User wants to SEND an email. "
                    "Extract recipient email, subject, and body from the user's message, "
                    "then output ONLY: [GMAIL_SEND: recipient@email.com | Subject | Body text]]\n"
                )
            else:
                parts.append("\n\n[SYSTEM: Gmail NOT connected. Tell user to connect in Dashboard → Integrations → Gmail.]\n")
        except:
            pass

    # ── WhatsApp send intent ──────────────────────────────────────────────
    if 'whatsapp' in msg or ('send' in msg and ('message' in msg or 'text' in msg or 'msg' in msg)):
        try:
            cfg = _get_integration_cfg(uid, 'whatsapp')
            if cfg.get('access_token') and cfg.get('phone_number_id'):
                parts.append(
                    "\n\n[SYSTEM: WhatsApp IS connected. "
                    "Extract phone number and message text, then output ONLY: "
                    "[WHATSAPP_SEND: +phonenumber | message text]]\n"
                )
            else:
                parts.append(
                    "\n\n[SYSTEM: WhatsApp NOT connected. Tell user to connect in Dashboard → Integrations.]\n"
                )
        except:
            pass

    # ── Slack post intent ─────────────────────────────────────────────────
    if 'slack' in msg:
        try:
            cfg = _get_integration_cfg(uid, 'slack')
            if cfg.get('webhook_url'):
                parts.append(
                    "\n\n[SYSTEM: Slack IS connected. "
                    "Extract the message to post, then output ONLY: [SLACK_POST: message text]]\n"
                )
            else:
                parts.append(
                    "\n\n[SYSTEM: Slack NOT connected. Tell user to connect in Dashboard → Integrations.]\n"
                )
        except:
            pass

    # ── HubSpot create contact intent ─────────────────────────────────────
    if 'hubspot' in msg or ('contact' in msg and ('add' in msg or 'create' in msg or 'save' in msg)):
        try:
            cfg = _get_integration_cfg(uid, 'hubspot')
            if cfg.get('access_token'):
                parts.append(
                    "\n\n[SYSTEM: HubSpot IS connected. "
                    "Extract contact details, then output ONLY: "
                    "[HUBSPOT_CREATE_CONTACT: email | firstname | lastname | company | phone]]\n"
                )
            else:
                parts.append(
                    "\n\n[SYSTEM: HubSpot NOT connected. Tell user to connect in Dashboard → Integrations.]\n"
                )
        except:
            pass

    # ── Google Drive: list/view files intent ──────────────────────────────
    drive_view_kw  = {'drive', 'file', 'files', 'document', 'documents', 'doc', 'docs', 'sheet', 'sheets', 'spreadsheet', 'spreadsheets'}
    drive_view_act = {'show', 'what', 'list', 'check', 'see', 'any', 'get', 'search', 'find', 'fetch', 'retrieve', 'look', 'view', 'display', 'my', 'are there'}
    
    if (drive_view_kw & set(msg.split())) or any(k in msg for k in drive_view_kw):
        if (drive_view_act & set(msg.split())) or any(k in msg for k in drive_view_act) or 'google drive' in msg or 'my drive' in msg:
            try:
                from services.integration_tools import execute_tool
                res = execute_tool(uid, 'list_drive_files', {"page_size": 15})
                if res.get('ok'):
                    files = res.get('files', [])
                    if files:
                        lines = []
                        for f in files:
                            lines.append(f"  • {f.get('name')} (ID: {f.get('id')} | Type: {f.get('mimeType')} | Size: {f.get('size', 'N/A')} bytes | Link: {f.get('webViewLink')})")
                        parts.append(
                            "\n\n[LIVE DATA — Google Drive, recent files]\n"
                            + "\n".join(lines)
                            + "\n[Use this data to answer the user. Do NOT say you can't access drive/files.]\n"
                        )
                    else:
                        parts.append(
                            "\n\n[LIVE DATA — Google Drive: No files found in the user's Google Drive.]\n"
                        )
                else:
                    err = res.get('error', 'unknown error')
                    if "not connected" in err.lower():
                        parts.append(
                            "\n\n[SYSTEM: Google Drive is NOT connected for this user. "
                            "Tell them to go to Dashboard → Integrations → Google Drive to connect it.]\n"
                        )
                    else:
                        parts.append(
                            f"\n\n[SYSTEM: Google Drive fetch failed: {err}]\n"
                        )
            except Exception as e:
                parts.append(f"\n\n[SYSTEM: Google Drive fetch exception: {e}]\n")

    return "".join(parts)


def _get_integration_cfg(uid, provider):
    from extensions import db
    if not db or not uid:
        return {}
    try:
        doc = db.collection('users').document(uid).collection('integrations').document(provider).get()
        return doc.to_dict() or {} if doc.exists else {}
    except Exception:
        return {}


def _refresh_oauth_token(uid, provider):
    """Refresh an expired OAuth access token using the stored refresh_token.
    Returns updated config dict, or raises Exception on failure."""
    import requests as _req
    cfg = _get_integration_cfg(uid, provider)
    refresh_token = cfg.get('refresh_token')
    client_id = cfg.get('client_id')
    client_secret = cfg.get('client_secret')
    if not refresh_token or not client_id or not client_secret:
        raise Exception(f"{provider} not connected or missing credentials — reconnect in Dashboard → Integrations.")

    token_urls = {
        'google_calendar': 'https://oauth2.googleapis.com/token',
        'gmail': 'https://oauth2.googleapis.com/token',
        'hubspot': 'https://api.hubapi.com/oauth/v1/token',
    }
    token_url = token_urls.get(provider)
    if not token_url:
        raise Exception(f"Token refresh not supported for {provider}")

    r = _req.post(token_url, data={
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token,
        'client_id': client_id,
        'client_secret': client_secret,
    }, timeout=15)
    if not r.ok:
        raise Exception(f"{provider} token refresh failed: {r.text[:200]}")
    data = r.json()
    new_token = data.get('access_token')
    if not new_token:
        raise Exception(f"{provider} refresh returned no access_token")
    # Persist updated token
    from extensions import db
    db.collection('users').document(uid).collection('integrations').document(provider).set({
        'access_token': new_token,
        'obtained_at': int(time.time()),
        'expires_in': data.get('expires_in', 3600),
    }, merge=True)
    cfg['access_token'] = new_token
    cfg['obtained_at'] = int(time.time())
    return cfg


def _get_valid_token(uid, provider):
    """Get a valid access token, auto-refreshing if expired (1hr TTL)."""
    cfg = _get_integration_cfg(uid, provider)
    if not cfg.get('access_token'):
        raise Exception(f"{provider} not connected — go to Dashboard → Integrations to connect it.")
    obtained_at = cfg.get('obtained_at', 0)
    expires_in = cfg.get('expires_in', 3600)
    # Refresh if within 5 minutes of expiry
    if time.time() > obtained_at + expires_in - 300:
        try:
            cfg = _refresh_oauth_token(uid, provider)
        except Exception as e:
            # If refresh fails but token might still work, continue with it
            print(f"[OAuth] Refresh failed for {provider}: {e}")
    return cfg.get('access_token')


def _calendar_create(uid, title, start_dt, end_dt, description='', tz='Asia/Kolkata'):
    import requests as _req
    token = _get_valid_token(uid, 'google_calendar')
    if not start_dt or not end_dt:
        raise Exception("Start and end datetime are required (ISO 8601 format).")
    body = {
        "summary": title,
        "description": description,
        "start": {"dateTime": start_dt, "timeZone": tz},
        "end":   {"dateTime": end_dt,   "timeZone": tz},
    }
    r = _req.post(
        "https://www.googleapis.com/calendar/v3/calendars/primary/events",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=body, timeout=15,
    )
    if r.status_code == 401:
        # Token refresh might have failed — tell user to reconnect
        raise Exception("Google Calendar token expired — please reconnect in Dashboard → Integrations.")
    if not r.ok:
        raise Exception(f"Calendar API error {r.status_code}: {r.text[:200]}")
    return r.json()


def _calendar_list(uid, days=7, tz='Asia/Kolkata'):
    import requests as _req
    from datetime import datetime, timedelta, timezone as _tz
    token = _get_valid_token(uid, 'google_calendar')
    now = datetime.now(_tz.utc)
    r = _req.get(
        "https://www.googleapis.com/calendar/v3/calendars/primary/events",
        headers={"Authorization": f"Bearer {token}"},
        params={
            "timeMin": now.isoformat(),
            "timeMax": (now + timedelta(days=days)).isoformat(),
            "orderBy": "startTime",
            "singleEvents": "true",
            "maxResults": 15,
        },
        timeout=15,
    )
    if r.status_code == 401:
        # Try one explicit refresh then retry
        try:
            cfg = _refresh_oauth_token(uid, 'google_calendar')
            token = cfg['access_token']
            r = _req.get(
                "https://www.googleapis.com/calendar/v3/calendars/primary/events",
                headers={"Authorization": f"Bearer {token}"},
                params={
                    "timeMin": now.isoformat(),
                    "timeMax": (now + timedelta(days=days)).isoformat(),
                    "orderBy": "startTime",
                    "singleEvents": "true",
                    "maxResults": 15,
                },
                timeout=15,
            )
        except Exception:
            raise Exception("Google Calendar token expired — please reconnect in Dashboard → Integrations.")
    if not r.ok:
        raise Exception(f"Calendar API error {r.status_code}")
    return r.json().get('items', [])


def _calendar_delete(uid, query, tz='Asia/Kolkata'):
    """Delete a calendar event. `query` is either:
      - An event ID (starts with hex/alphanumeric, no spaces), OR
      - A keyword/title to search for (case-insensitive match against summary).
    Returns dict with 'deleted' (list of deleted titles) and 'matched_count'.
    """
    import requests as _req
    from datetime import datetime, timedelta, timezone as _tz
    token = _get_valid_token(uid, 'google_calendar')
    q = (query or '').strip()
    if not q:
        raise Exception("Event title or ID required.")

    deleted = []
    # First, list upcoming events to find the one(s) matching the query.
    now = datetime.now(_tz.utc)
    r = _req.get(
        "https://www.googleapis.com/calendar/v3/calendars/primary/events",
        headers={"Authorization": f"Bearer {token}"},
        params={
            "timeMin": (now - timedelta(days=1)).isoformat(),
            "timeMax": (now + timedelta(days=60)).isoformat(),
            "orderBy": "startTime",
            "singleEvents": "true",
            "maxResults": 50,
            "q": q,  # Google Calendar text search
        },
        timeout=15,
    )
    if r.status_code == 401:
        raise Exception("Google Calendar token expired — please reconnect in Dashboard → Integrations.")
    if not r.ok:
        raise Exception(f"Calendar API error {r.status_code}: {r.text[:200]}")
    events = r.json().get('items', [])

    # Filter: prefer events whose summary contains the query (case-insensitive).
    q_lower = q.lower()
    matches = [e for e in events if q_lower in (e.get('summary', '') or '').lower()]
    if not matches:
        matches = events  # Fall back to whatever Google's text search returned.

    if not matches:
        return {"deleted": [], "matched_count": 0}

    for ev in matches[:5]:  # Safety cap at 5 deletions per call
        eid = ev.get('id')
        title = ev.get('summary', 'Untitled')
        if not eid:
            continue
        dr = _req.delete(
            f"https://www.googleapis.com/calendar/v3/calendars/primary/events/{eid}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        if dr.status_code in (200, 204):
            deleted.append(title)
        elif dr.status_code == 410:
            deleted.append(title)  # Already gone
        else:
            print(f"[Calendar Delete] {eid} failed: {dr.status_code} {dr.text[:120]}")

    return {"deleted": deleted, "matched_count": len(matches)}


def _gmail_send(uid, to, subject, body):
    """Send an email via Gmail API. Body is plain text."""
    import requests as _req
    import base64
    from email.mime.text import MIMEText
    token = _get_valid_token(uid, 'gmail')
    if not to or not subject:
        raise Exception("Recipient and subject are required.")
    msg = MIMEText(body or '', 'plain', 'utf-8')
    msg['to'] = to
    msg['subject'] = subject
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode('utf-8')
    r = _req.post(
        "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"raw": raw}, timeout=15,
    )
    if r.status_code == 401:
        raise Exception("Gmail token expired — please reconnect in Dashboard → Integrations.")
    if not r.ok:
        raise Exception(f"Gmail API error {r.status_code}: {r.text[:200]}")
    return r.json()


def _python_run(code, timeout_sec=15):
    """Execute a Python snippet in a sandboxed subprocess.

    Returns: {"stdout": str, "stderr": str, "images": [data_url, ...], "ok": bool}

    Safety:
      - 15s hard wall-clock timeout
      - 256MB RSS limit (Linux only)
      - Networking restricted via env (HTTPS_PROXY=127.0.0.1:1) — best-effort
      - Runs in a fresh tempdir; matplotlib PNGs created there are captured
    """
    import os as _os, sys as _sys, subprocess, tempfile, base64 as _b64, json as _json, textwrap, glob, shutil
    result = {"stdout": "", "stderr": "", "images": [], "ok": False, "exit_code": None}
    if not code or not isinstance(code, str):
        result["stderr"] = "No code provided"
        return result

    workdir = tempfile.mkdtemp(prefix="kpy_")
    try:
        # Wrap user code: force matplotlib to headless + auto-save figures
        wrapper = textwrap.dedent(f"""
            import os, sys, json, traceback
            os.chdir({workdir!r})
            try:
                import matplotlib
                matplotlib.use('Agg')
            except Exception:
                pass
            try:
                import pandas as pd
                pd.set_option('display.max_columns', 30)
                pd.set_option('display.width', 200)
            except Exception:
                pass
            try:
{textwrap.indent(code, '                ')}
            except SystemExit:
                pass
            except Exception:
                print('--- TRACEBACK ---', file=sys.stderr)
                traceback.print_exc()
                sys.exit(1)
            # Auto-save any open matplotlib figures
            try:
                import matplotlib.pyplot as plt
                for i, num in enumerate(plt.get_fignums()):
                    fig = plt.figure(num)
                    fig.savefig(f'chart_{{i+1}}.png', dpi=130, bbox_inches='tight')
                plt.close('all')
            except Exception:
                pass
        """)
        script_path = _os.path.join(workdir, '_run.py')
        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(wrapper)

        env = {
            "PATH": _os.environ.get("PATH", ""),
            "HOME": workdir,
            "TMPDIR": workdir,
            "MPLBACKEND": "Agg",
            "HTTPS_PROXY": "127.0.0.1:1",   # best-effort network block
            "HTTP_PROXY":  "127.0.0.1:1",
            "PYTHONDONTWRITEBYTECODE": "1",
        }

        # Best-effort Linux resource caps
        def _preexec():
            try:
                import resource
                resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024, 256 * 1024 * 1024))
                resource.setrlimit(resource.RLIMIT_CPU, (timeout_sec, timeout_sec))
            except Exception:
                pass

        try:
            proc = subprocess.run(
                [_sys.executable, '-I', script_path],
                cwd=workdir, env=env,
                capture_output=True, text=True,
                timeout=timeout_sec,
                preexec_fn=_preexec if _os.name == 'posix' else None,
            )
            result["stdout"] = (proc.stdout or "")[-12_000:]
            result["stderr"] = (proc.stderr or "")[-4_000:]
            result["exit_code"] = proc.returncode
            result["ok"] = proc.returncode == 0
        except subprocess.TimeoutExpired:
            result["stderr"] = f"Execution exceeded {timeout_sec}s timeout."
            result["exit_code"] = -1

        # Pick up any chart PNGs
        for png_path in sorted(glob.glob(_os.path.join(workdir, '*.png'))):
            try:
                with open(png_path, 'rb') as f:
                    b64 = _b64.b64encode(f.read()).decode('utf-8')
                result["images"].append(f"data:image/png;base64,{b64}")
            except Exception:
                continue
    finally:
        try:
            shutil.rmtree(workdir, ignore_errors=True)
        except Exception:
            pass
    return result


def _gmail_list(uid, max_results=10, query=''):
    """List recent emails. Returns list of {from, subject, snippet, date, id}."""
    import requests as _req
    import concurrent.futures
    token = _get_valid_token(uid, 'gmail')
    params = {"maxResults": min(int(max_results or 10), 25)}
    if query:
        params["q"] = query
    r = _req.get(
        "https://gmail.googleapis.com/gmail/v1/users/me/messages",
        headers={"Authorization": f"Bearer {token}"},
        params=params, timeout=15,
    )
    if r.status_code == 401:
        raise Exception("Gmail token expired — please reconnect in Dashboard → Integrations.")
    if not r.ok:
        raise Exception(f"Gmail API error {r.status_code}: {r.text[:200]}")
    items = r.json().get('messages', [])
    out = []

    def fetch_email_detail(m):
        try:
            mid = m['id']
            dr = _req.get(
                f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{mid}",
                headers={"Authorization": f"Bearer {token}"},
                params={"format": "metadata", "metadataHeaders": ["From", "Subject", "Date"]},
                timeout=10,
            )
            if not dr.ok:
                return None
            md = dr.json()
            headers = {h['name']: h['value'] for h in md.get('payload', {}).get('headers', [])}
            return {
                "id": mid,
                "from": headers.get('From', ''),
                "subject": headers.get('Subject', '(no subject)'),
                "date": headers.get('Date', ''),
                "snippet": md.get('snippet', '')[:160],
            }
        except Exception:
            return None

    # Parallelize fetches using ThreadPoolExecutor to prevent blocking sequential latency
    max_workers = min(len(items[:max_results]) or 1, 8)
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(fetch_email_detail, m) for m in items[:max_results]]
        for fut in concurrent.futures.as_completed(futures):
            res = fut.result()
            if res:
                out.append(res)

    return out


def _whatsapp_send(uid, to, message):
    import requests as _req
    cfg = _get_integration_cfg(uid, 'whatsapp')
    token    = cfg.get('access_token')
    phone_id = cfg.get('phone_number_id')
    if not token or not phone_id:
        raise Exception("WhatsApp not connected — go to Dashboard → Integrations to add your access_token and phone_number_id.")
    r = _req.post(
        f"https://graph.facebook.com/v20.0/{phone_id}/messages",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"messaging_product": "whatsapp", "to": to, "type": "text", "text": {"body": message}},
        timeout=15,
    )
    if not r.ok:
        raise Exception(f"WhatsApp API error {r.status_code}: {r.text[:200]}")
    return r.json()


def _slack_post(uid, message, channel=None):
    import requests as _req
    cfg = _get_integration_cfg(uid, 'slack')
    webhook = cfg.get('webhook_url')
    if not webhook:
        raise Exception("Slack not connected — go to Dashboard → Integrations to add your webhook URL.")
    body = {"text": message}
    if channel:
        body["channel"] = channel
    r = _req.post(webhook, json=body, timeout=10)
    if not r.ok:
        raise Exception(f"Slack error {r.status_code}: {r.text[:100]}")
    return True


def _hubspot_create_contact(uid, email, firstname='', lastname='', company='', phone=''):
    import requests as _req
    token = _get_valid_token(uid, 'hubspot')
    props = {"email": email}
    if firstname: props["firstname"] = firstname
    if lastname:  props["lastname"]  = lastname
    if company:   props["company"]   = company
    if phone:     props["phone"]     = phone
    r = _req.post(
        "https://api.hubapi.com/crm/v3/objects/contacts",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"properties": props}, timeout=15,
    )
    if not r.ok:
        raise Exception(f"HubSpot error {r.status_code}: {r.text[:200]}")
    return r.json()


def get_llm_response(messages, uid=None, model="daily", user_ip=None, tools=None, tool_choice=None, max_thinking=False):
    """Entry point for chat. Routes to fast-path, orchestrator, or agent_loop."""
    model = normalize_model_choice(model)

    # Multi-agent auto-routing
    if model == "auto":
        from services.orchestrator_service import run as orchestrator_run
        return orchestrator_run(messages, uid=uid, user_ip=user_ip, max_thinking=max_thinking)

    user_input_text = ""
    if messages and messages[-1]["role"] == "user":
        luc = messages[-1]["content"]
        if isinstance(luc, str):
            user_input_text = luc
        elif isinstance(luc, list):
            user_input_text = " ".join([p["text"] for p in luc if p.get("type") == "text"])

    # Pro and Coder ALWAYS go through agent_loop for NVIDIA NIM + thinking support
    if model in ('pro', 'coder'):
        return agent_loop(messages, uid, model_choice=model, user_ip=user_ip, tools=tools, tool_choice=tool_choice, max_thinking=max_thinking)

    # All models (including daily) go through agent_loop so ReAct tools are processed
    return agent_loop(messages, uid, model_choice=model, user_ip=user_ip, tools=tools, tool_choice=tool_choice, max_thinking=max_thinking)
