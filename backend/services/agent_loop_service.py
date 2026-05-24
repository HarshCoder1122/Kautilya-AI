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

def agent_loop(messages, uid=None, model_choice='daily', user_ip=None, tools=None, tool_choice=None, max_thinking=False):
    """
    Agentic Loop: Thoughts -> Actions -> Observations -> Final Answer.
    Yields chunks of text OR special status JSONs.
    """
    from extensions import limit_manager, vector_store

    rag_context = ""
    location_context = ""
    last_user_msg = ""
    if messages and messages[-1]["role"] == "user":
        content = messages[-1].get("content", "")
        if isinstance(content, str):
            last_user_msg = content
        elif isinstance(content, list):
            last_user_msg = " ".join([p["text"] for p in content if p.get("type") == "text"])

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
                  'crm', 'hubspot', 'zoho', 'contact', 'lead', 'zapier', 'event',
                  'email', 'remind', 'follow up', 'follow-up', 'drive', 'file',
                  'files', 'document', 'documents', 'doc', 'docs', 'sheet', 'sheets',
                  'spreadsheet', 'spreadsheets')
    _msg_low = (last_user_msg or "").lower() if last_user_msg else ""
    if uid and any(k in _msg_low for k in _intent_kw):
        try:
            from services.integration_tools import available_tools
            specs = available_tools(uid)
            if specs:
                lines = ["\n\nAVAILABLE INTEGRATIONS (call exactly once when the user explicitly asks):"]
                for s in specs:
                    fn = s["function"]
                    req = fn.get("parameters", {}).get("required", [])
                    lines.append(f"- {fn['name']}({', '.join(req)}): {fn['description']}")
                lines.append("Syntax: [INTEGRATION: tool_name | {\"arg\": \"value\"}]  — JSON args, single line, double-quoted.")
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
        integration_context = _pre_fetch_integrations(uid, last_user_msg)
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

    MAX_TURNS = 3
    for turn in range(MAX_TURNS):
        print(f"[Agent] Turn {turn+1}/{MAX_TURNS}")

        max_tokens = _estimate_tokens(last_user_msg, model_choice)
        print(f"[Agent] Smart tokens: {max_tokens} (msg length: {len(last_user_msg)}, mode: {model_choice})")

        # Auto-detect image in last message
        has_image = False
        if current_messages and current_messages[-1].get("role") == "user":
            last_mc = current_messages[-1].get("content")
            if isinstance(last_mc, list) and any(p.get("type") == "image_url" for p in last_mc):
                has_image = True

        # Auto-toggle thinking: if the user didn't explicitly request max_thinking,
        # decide based on prompt complexity. Keeps simple questions fast and
        # routes hard questions into the reasoning path.
        effective_max_thinking = max_thinking or _should_auto_think(last_user_msg, model_choice)
        if effective_max_thinking and not max_thinking:
            print(f"[Agent] Auto-thinking enabled (heuristic match on prompt)")
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

        # --- ReAct Action Parsing ---
        # Detect tool call patterns from the accumulated response and emit
        # structured react_* events so the frontend can render a step timeline.
        action_found = False
        action_counter = 0  # reset per-conversation-turn, not per-call

        # 1. [SEARCH: query]
        search_match = re.search(r'\[SEARCH:\s*(.*?)\]', accumulated_response)
        if search_match:
            query = search_match.group(1).strip()
            action_counter += 1
            action_id = str(action_counter)

            # Announce the action visually in the UI
            yield json.dumps({
                "event": "react_action",
                "id": action_id,
                "tool": "web_search",
                "input": query,
                "status": "running"
            })

            from services.research_service import _gather_sources
            try:
                sources = _gather_sources([query])
                if sources:
                    obs_text = "SEARCH RESULTS:\n"
                    for i, s in enumerate(sources[:4], 1):
                        obs_text += f"[{i}] {s['title']} ({s['url']}): {s['snippet']}\n"
                    yield json.dumps({
                        "event": "react_action_done",
                        "id": action_id,
                        "status": "done",
                        "preview": f"Found {len(sources)} sources",
                        "sources": [{"title": s["title"], "url": s["url"]} for s in sources[:4]]
                    })
                    current_messages.append({"role": "assistant", "content": accumulated_response})
                    current_messages.append({"role": "user", "content": f"OBSERVATION: {obs_text}\n\nNow provide a final comprehensive answer using these findings. Do NOT use [SEARCH:] again."})
                else:
                    yield json.dumps({
                        "event": "react_action_done",
                        "id": action_id,
                        "status": "empty",
                        "preview": "No results found"
                    })
                    current_messages.append({"role": "assistant", "content": accumulated_response})
                    current_messages.append({"role": "user", "content": "OBSERVATION: No relevant results found. Answer from internal knowledge or state that you don't know."})
            except Exception as e:
                print(f"[Agent] Search failed: {e}")
                yield json.dumps({
                    "event": "react_action_done",
                    "id": action_id,
                    "status": "error",
                    "preview": str(e)[:80]
                })
                current_messages.append({"role": "assistant", "content": accumulated_response})
                current_messages.append({"role": "user", "content": f"OBSERVATION: Search service error: {e}. Continue without web results."})
            action_found = True

        # 2. [CALCULATE: expression]
        calc_match = re.search(r'\[CALCULATE:\s*(.*?)\]', accumulated_response)
        if calc_match and not action_found:
            expr = calc_match.group(1).strip()
            action_counter += 1
            action_id = str(action_counter)
            yield json.dumps({
                "event": "react_action",
                "id": action_id,
                "tool": "calculator",
                "input": expr,
                "status": "running"
            })
            try:
                # Safe eval for math expressions
                safe_globals = {"__builtins__": {}}
                import math
                safe_globals.update({k: getattr(math, k) for k in dir(math) if not k.startswith('_')})
                result = eval(expr, safe_globals)  # noqa: S307
                result_str = str(round(float(result), 8)) if isinstance(result, float) else str(result)
                yield json.dumps({
                    "event": "react_action_done",
                    "id": action_id,
                    "status": "done",
                    "preview": f"= {result_str}"
                })
                obs = f"CALCULATION RESULT: {expr} = {result_str}"
            except Exception as e:
                result_str = f"Error: {e}"
                yield json.dumps({
                    "event": "react_action_done",
                    "id": action_id,
                    "status": "error",
                    "preview": result_str
                })
                obs = f"CALCULATION ERROR: {e}"
            current_messages.append({"role": "assistant", "content": accumulated_response})
            current_messages.append({"role": "user", "content": f"OBSERVATION: {obs}\n\nContinue with your answer."})
            action_found = True

        # 3. [CALENDAR_CREATE: title | start | end | description?]
        cal_create_match = re.search(r'\[CALENDAR_CREATE:\s*(.*?)\]', accumulated_response, re.DOTALL)
        if cal_create_match and not action_found:
            parts = [p.strip() for p in cal_create_match.group(1).split('|')]
            title       = parts[0] if len(parts) > 0 else 'New Event'
            start_dt    = parts[1] if len(parts) > 1 else None
            end_dt      = parts[2] if len(parts) > 2 else None
            description = parts[3] if len(parts) > 3 else ''
            action_counter += 1
            action_id = str(action_counter)
            yield json.dumps({"event": "react_action", "id": action_id, "tool": "calendar", "input": title, "status": "running"})
            try:
                result = _calendar_create(uid, title, start_dt, end_dt, description)
                event_link = result.get('htmlLink', '')
                yield json.dumps({"event": "react_action_done", "id": action_id, "status": "done",
                                  "preview": f"Created: {title}", "sources": [{"title": "Open in Calendar", "url": event_link}] if event_link else []})
                obs = f"CALENDAR: Event '{title}' created successfully for {start_dt}. Link: {event_link}"
            except Exception as e:
                yield json.dumps({"event": "react_action_done", "id": action_id, "status": "error", "preview": str(e)[:100]})
                obs = f"CALENDAR ERROR: {e}"
            current_messages.append({"role": "assistant", "content": accumulated_response})
            current_messages.append({"role": "user", "content": f"OBSERVATION: {obs}\n\nConfirm the result to the user."})
            action_found = True

        # 3.5 [CALENDAR_DELETE: event_id_or_title_keyword]
        cal_del_match = re.search(r'\[CALENDAR_DELETE:\s*(.*?)\]', accumulated_response, re.DOTALL)
        if cal_del_match and not action_found:
            q = cal_del_match.group(1).strip()
            action_counter += 1
            action_id = str(action_counter)
            yield json.dumps({"event": "react_action", "id": action_id, "tool": "calendar", "input": f"Delete: {q}", "status": "running"})
            try:
                result = _calendar_delete(uid, q)
                deleted = result.get('deleted', [])
                if deleted:
                    obs = f"CALENDAR: Deleted {len(deleted)} event(s): {', '.join(deleted)}"
                    yield json.dumps({"event": "react_action_done", "id": action_id, "status": "done",
                                      "preview": f"Deleted: {', '.join(deleted)[:80]}"})
                else:
                    obs = f"CALENDAR: No event found matching '{q}' in the next 60 days."
                    yield json.dumps({"event": "react_action_done", "id": action_id, "status": "done",
                                      "preview": f"No match for '{q}'"})
            except Exception as e:
                yield json.dumps({"event": "react_action_done", "id": action_id, "status": "error", "preview": str(e)[:100]})
                obs = f"CALENDAR ERROR: {e}"
            current_messages.append({"role": "assistant", "content": accumulated_response})
            current_messages.append({"role": "user", "content": f"OBSERVATION: {obs}\n\nConfirm the result to the user."})
            action_found = True

        # 4. [CALENDAR_LIST: days]
        cal_list_match = re.search(r'\[CALENDAR_LIST:\s*(\d*)\]', accumulated_response)
        if cal_list_match and not action_found:
            days = int(cal_list_match.group(1) or 7)
            action_counter += 1
            action_id = str(action_counter)
            yield json.dumps({"event": "react_action", "id": action_id, "tool": "calendar", "input": f"Next {days} days", "status": "running"})
            try:
                events = _calendar_list(uid, days)
                # Structured payload for the UI card
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
                yield json.dumps({"event": "tool_result", "tool": "calendar_list",
                                  "data": {"events": card_events, "days": days}})
                if card_events:
                    lines = [f"- {ev['summary']} at {ev['start']}" for ev in card_events]
                    obs = f"CALENDAR EVENTS (next {days} days):\n" + "\n".join(lines)
                    yield json.dumps({"event": "react_action_done", "id": action_id, "status": "done",
                                      "preview": f"{len(card_events)} event(s) found"})
                else:
                    obs = f"CALENDAR: No events found in the next {days} days."
                    yield json.dumps({"event": "react_action_done", "id": action_id, "status": "done", "preview": "No events"})
            except Exception as e:
                yield json.dumps({"event": "react_action_done", "id": action_id, "status": "error", "preview": str(e)[:100]})
                obs = f"CALENDAR ERROR: {e}"
            current_messages.append({"role": "assistant", "content": accumulated_response})
            current_messages.append({"role": "user", "content": f"OBSERVATION: {obs}\n\nThe events are already shown to the user as cards — just give a one-line confirmation, no need to list them again."})
            action_found = True

        # 4.5 [GMAIL_SEND: to@email.com | Subject | Body]
        gm_send_match = re.search(r'\[GMAIL_SEND:\s*(.*?)\]', accumulated_response, re.DOTALL)
        if gm_send_match and not action_found:
            gm_parts = [p.strip() for p in gm_send_match.group(1).split('|', 2)]
            gm_to   = gm_parts[0] if len(gm_parts) > 0 else ''
            gm_subj = gm_parts[1] if len(gm_parts) > 1 else ''
            gm_body = gm_parts[2] if len(gm_parts) > 2 else ''
            action_counter += 1
            action_id = str(action_counter)
            yield json.dumps({"event": "react_action", "id": action_id, "tool": "gmail", "input": f"Email → {gm_to}", "status": "running"})
            try:
                _gmail_send(uid, gm_to, gm_subj, gm_body)
                yield json.dumps({"event": "react_action_done", "id": action_id, "status": "done",
                                  "preview": f"Sent to {gm_to}"})
                obs = f"GMAIL: Email sent to {gm_to} with subject '{gm_subj}'."
            except Exception as e:
                yield json.dumps({"event": "react_action_done", "id": action_id, "status": "error", "preview": str(e)[:100]})
                obs = f"GMAIL ERROR: {e}"
            current_messages.append({"role": "assistant", "content": accumulated_response})
            current_messages.append({"role": "user", "content": f"OBSERVATION: {obs}\n\nConfirm to the user."})
            action_found = True

        # 4.6 [GMAIL_LIST: max | optional_search_query]
        gm_list_match = re.search(r'\[GMAIL_LIST:\s*(.*?)\]', accumulated_response)
        if gm_list_match and not action_found:
            gm_parts = [p.strip() for p in gm_list_match.group(1).split('|', 1)]
            gm_max = int(gm_parts[0]) if gm_parts and gm_parts[0].isdigit() else 10
            gm_q   = gm_parts[1] if len(gm_parts) > 1 else ''
            action_counter += 1
            action_id = str(action_counter)
            yield json.dumps({"event": "react_action", "id": action_id, "tool": "gmail", "input": f"Inbox (last {gm_max})", "status": "running"})
            try:
                emails = _gmail_list(uid, gm_max, gm_q)
                yield json.dumps({"event": "tool_result", "tool": "gmail_list",
                                  "data": {"emails": emails or [], "query": gm_q}})
                if emails:
                    lines = []
                    for e in emails:
                        lines.append(f"- From: {e['from']} | Subject: {e['subject']} | {e['date']}\n  Snippet: {e['snippet']}")
                    obs = f"GMAIL INBOX ({len(emails)} message(s)):\n" + "\n".join(lines)
                    yield json.dumps({"event": "react_action_done", "id": action_id, "status": "done",
                                      "preview": f"{len(emails)} email(s)"})
                else:
                    obs = "GMAIL: No emails found."
                    yield json.dumps({"event": "react_action_done", "id": action_id, "status": "done", "preview": "Empty inbox"})
            except Exception as e:
                yield json.dumps({"event": "react_action_done", "id": action_id, "status": "error", "preview": str(e)[:100]})
                obs = f"GMAIL ERROR: {e}"
            current_messages.append({"role": "assistant", "content": accumulated_response})
            current_messages.append({"role": "user", "content": f"OBSERVATION: {obs}\n\nThe inbox is already shown to the user as styled email cards — give a one-line summary only, do not re-list emails."})
            action_found = True

        # 5. [WHATSAPP_SEND: number | message]
        wa_match = re.search(r'\[WHATSAPP_SEND:\s*(.*?)\]', accumulated_response, re.DOTALL)
        if wa_match and not action_found:
            wa_parts = [p.strip() for p in wa_match.group(1).split('|', 1)]
            wa_to  = wa_parts[0] if len(wa_parts) > 0 else ''
            wa_msg = wa_parts[1] if len(wa_parts) > 1 else ''
            action_counter += 1
            action_id = str(action_counter)
            yield json.dumps({"event": "react_action", "id": action_id, "tool": "whatsapp", "input": f"WhatsApp → {wa_to}", "status": "running"})
            try:
                _whatsapp_send(uid, wa_to, wa_msg)
                yield json.dumps({"event": "react_action_done", "id": action_id, "status": "done", "preview": f"Sent to {wa_to}"})
                obs = f"WHATSAPP: Message sent to {wa_to}."
            except Exception as e:
                yield json.dumps({"event": "react_action_done", "id": action_id, "status": "error", "preview": str(e)[:100]})
                obs = f"WHATSAPP ERROR: {e}"
            current_messages.append({"role": "assistant", "content": accumulated_response})
            current_messages.append({"role": "user", "content": f"OBSERVATION: {obs}\n\nConfirm to the user."})
            action_found = True

        # 6. [SLACK_POST: message]
        slack_match = re.search(r'\[SLACK_POST:\s*(.*?)\]', accumulated_response, re.DOTALL)
        if slack_match and not action_found:
            sl_msg = slack_match.group(1).strip()
            action_counter += 1
            action_id = str(action_counter)
            yield json.dumps({"event": "react_action", "id": action_id, "tool": "slack", "input": "Slack message", "status": "running"})
            try:
                _slack_post(uid, sl_msg)
                yield json.dumps({"event": "react_action_done", "id": action_id, "status": "done", "preview": "Message posted"})
                obs = "SLACK: Message posted successfully."
            except Exception as e:
                yield json.dumps({"event": "react_action_done", "id": action_id, "status": "error", "preview": str(e)[:100]})
                obs = f"SLACK ERROR: {e}"
            current_messages.append({"role": "assistant", "content": accumulated_response})
            current_messages.append({"role": "user", "content": f"OBSERVATION: {obs}\n\nConfirm to the user."})
            action_found = True

        # 7. [HUBSPOT_CREATE_CONTACT: email | firstname | lastname | company | phone]
        hs_match = re.search(r'\[HUBSPOT_CREATE_CONTACT:\s*(.*?)\]', accumulated_response, re.DOTALL)
        if hs_match and not action_found:
            hs_parts = [p.strip() for p in hs_match.group(1).split('|')]
            hs_email = hs_parts[0] if len(hs_parts) > 0 else ''
            hs_first = hs_parts[1] if len(hs_parts) > 1 else ''
            hs_last  = hs_parts[2] if len(hs_parts) > 2 else ''
            hs_co    = hs_parts[3] if len(hs_parts) > 3 else ''
            hs_ph    = hs_parts[4] if len(hs_parts) > 4 else ''
            action_counter += 1
            action_id = str(action_counter)
            yield json.dumps({"event": "react_action", "id": action_id, "tool": "hubspot", "input": f"HubSpot contact: {hs_email}", "status": "running"})
            try:
                result = _hubspot_create_contact(uid, hs_email, hs_first, hs_last, hs_co, hs_ph)
                contact_id = result.get('id', '')
                yield json.dumps({"event": "react_action_done", "id": action_id, "status": "done", "preview": f"Contact created: {hs_email}"})
                obs = f"HUBSPOT: Contact '{hs_email}' created (id: {contact_id})."
            except Exception as e:
                yield json.dumps({"event": "react_action_done", "id": action_id, "status": "error", "preview": str(e)[:100]})
                obs = f"HUBSPOT ERROR: {e}"
            current_messages.append({"role": "assistant", "content": accumulated_response})
            current_messages.append({"role": "user", "content": f"OBSERVATION: {obs}\n\nConfirm to the user."})
            action_found = True

        # 11. [RUN_PYTHON: ```code```] — sandboxed Python (pandas / matplotlib charts)
        py_match = re.search(r'\[RUN_PYTHON:\s*```(?:python)?\s*([\s\S]*?)```\s*\]', accumulated_response)
        if not py_match:
            # Permissive fallback: [RUN_PYTHON: ...code...] without fences
            py_match = re.search(r'\[RUN_PYTHON:\s*([\s\S]+?)\]\s*$', accumulated_response.strip())
        if py_match and not action_found:
            code = py_match.group(1).strip()
            action_counter += 1
            action_id = str(action_counter)
            yield json.dumps({"event": "react_action", "id": action_id, "tool": "python",
                              "input": code[:80] + ("…" if len(code) > 80 else ""), "status": "running"})
            try:
                py_res = _python_run(code)
                yield json.dumps({"event": "tool_result", "tool": "python_run",
                                  "data": {
                                      "code": code,
                                      "stdout": py_res["stdout"],
                                      "stderr": py_res["stderr"],
                                      "images": py_res["images"],
                                      "ok": py_res["ok"],
                                  }})
                if py_res["ok"]:
                    chart_note = f" (+{len(py_res['images'])} chart(s))" if py_res["images"] else ""
                    yield json.dumps({"event": "react_action_done", "id": action_id, "status": "done",
                                      "preview": f"Ran successfully{chart_note}"})
                    # Truncated output for the model's context (full version went to the UI card)
                    short_out = (py_res["stdout"] or "")[:1500]
                    obs = f"PYTHON EXECUTED OK.\nStdout (first 1500 chars):\n{short_out}"
                else:
                    yield json.dumps({"event": "react_action_done", "id": action_id, "status": "error",
                                      "preview": (py_res["stderr"] or "error")[:80]})
                    obs = f"PYTHON ERROR (exit {py_res['exit_code']}):\n{py_res['stderr'][:1500]}"
            except Exception as e:
                yield json.dumps({"event": "react_action_done", "id": action_id, "status": "error", "preview": str(e)[:100]})
                obs = f"PYTHON RUNNER ERROR: {e}"
            current_messages.append({"role": "assistant", "content": accumulated_response})
            current_messages.append({"role": "user", "content": f"OBSERVATION: {obs}\n\nThe code + output + any charts are already shown to the user. Give a one-line interpretation; do not re-paste code or output."})
            action_found = True

        # Generic integration tool dispatch (shared registry with voice agent).
        # Syntax: [INTEGRATION: tool_name | {"arg":"value",...}]
        # Tools available: send_whatsapp, post_slack, create_calendar_event,
        # lookup_crm_contact, log_crm_activity, trigger_zapier — only those whose
        # provider the user has connected.
        if not action_found:
            int_match = re.search(r'\[INTEGRATION:\s*([a-z0-9_]+)\s*\|\s*(\{.*?\})\s*\]', accumulated_response, re.DOTALL)
            if int_match:
                tool_name = int_match.group(1).strip()
                try:
                    tool_args = json.loads(int_match.group(2))
                except Exception:
                    tool_args = {}
                # MCP tools don't require uid (server-level creds); per-user integrations do.
                is_mcp = tool_name.startswith("mcp_")
                if is_mcp or uid:
                    action_counter += 1
                    action_id = str(action_counter)
                    yield json.dumps({"event": "react_action", "id": action_id, "tool": tool_name,
                                      "input": json.dumps(tool_args)[:80], "status": "running"})
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
                            yield json.dumps({"event": "react_action_done", "id": action_id,
                                              "status": "done", "preview": f"{tool_name} succeeded"})
                            obs = f"{label} RESULT ({tool_name}): {json.dumps(result)[:1500]}"
                        else:
                            yield json.dumps({"event": "react_action_done", "id": action_id,
                                              "status": "error", "preview": str(result.get('error', ''))[:80]})
                            obs = f"{label} ERROR ({tool_name}): {result.get('error', 'unknown')}"
                    except Exception as e:
                        yield json.dumps({"event": "react_action_done", "id": action_id,
                                          "status": "error", "preview": str(e)[:80]})
                        obs = f"TOOL EXCEPTION ({tool_name}): {e}"
                    current_messages.append({"role": "assistant", "content": accumulated_response})
                    current_messages.append({"role": "user", "content": f"OBSERVATION: {obs}\n\nSynthesize a concise user-facing answer from this result. Do not call [INTEGRATION:] again for the same action."})
                    action_found = True

        agent_loop._action_counter = action_counter

        # Signal synthesis phase if we just executed actions
        if action_found:
            yield json.dumps({"event": "react_synthesizing"})

        # If an action was performed, continue to the next turn for synthesis.
        # Otherwise, we are done.
        if not action_found:
            return


def _estimate_tokens(user_msg, mode):
    """
    Smart token budget estimator.
    Returns None to allow maximum unlimited streaming response.
    """
    msg_lower = user_msg.lower().strip()
    msg_len = len(msg_lower)

    greetings = {'hi', 'hello', 'hey', 'yo', 'sup', 'namaste', 'thanks', 'ok', 'bye', 'okay'}
    if msg_lower in greetings or msg_len < 10:
        return 1024  # short reply for simple greetings

    return None # Return None to let model stream as much as it wants


def _estimate_reasoning_budget(max_tokens, max_thinking=False):
    """
    Derive a proportional reasoning budget from the answer token budget.
    Thinking should be ≥ answer budget to allow full deliberation.
    """
    if max_tokens is None:
        return 32768 if max_thinking else 8192

    if not max_thinking:
        # Light reasoning for standard calls
        return min(8192, max_tokens)
    # Deep thinking: up to 2× the answer budget, capped at 32k
    return min(32768, max_tokens * 2)


# Heuristic auto-thinking. Triggers when the prompt looks hard enough that
# reasoning tokens pay off (math, multi-step, code debugging, analysis).
# Cheap chitchat and lookups stay fast.
_AUTO_THINK_KEYWORDS = (
    "why", "how does", "how do", "explain", "analyze", "compare", "debug",
    "optimize", "refactor", "prove", "derive", "design", "architect",
    "step by step", "step-by-step", "reason", "trade-off", "tradeoff",
    "complex", "deep dive", "walk me through", "root cause", "edge case",
    "algorithm", "complexity", "big-o", "big o",
)
_AUTO_THINK_CODE_HINTS = (
    "bug", "stack trace", "traceback", "exception", "segfault",
    "race condition", "deadlock", "memory leak", "performance",
    "regex", "recursion", "concurrency",
)


def _should_auto_think(user_msg: str, model_choice: str) -> bool:
    """Decide whether to flip on deep thinking based on the prompt itself.
    Only applies to reasoning-capable modes (pro / coder). Daily stays fast.
    """
    if model_choice not in ('pro', 'coder'):
        return False
    if not user_msg:
        return False
    text = user_msg.lower()
    # Long prompts almost always need real reasoning.
    if len(text) > 400:
        return True
    # Multi-question prompts ("X? Y? Z?")
    if text.count("?") >= 2:
        return True
    # Code presence + a "why/bug/explain" signal → think
    has_code_block = "```" in user_msg or user_msg.count("\n") >= 6
    if has_code_block and any(k in text for k in _AUTO_THINK_CODE_HINTS + _AUTO_THINK_KEYWORDS):
        return True
    # Plain keyword match anywhere
    if any(k in text for k in _AUTO_THINK_KEYWORDS):
        return True
    return False


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
                    emails = _gmail_list(uid, 10)
                    if emails:
                        lines = [f"  • From: {e['from']} | Subject: {e['subject']} | Date: {e['date']}"
                                 + (f"\n    Snippet: {e['snippet']}" if e.get('snippet') else '')
                                 for e in emails]
                        parts.append(
                            "\n\n[LIVE DATA — Gmail inbox, last 10 messages]\n"
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
                [_sys.executable, '-I', '-S', script_path],
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
    for m in items[:max_results]:
        try:
            mid = m['id']
            dr = _req.get(
                f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{mid}",
                headers={"Authorization": f"Bearer {token}"},
                params={"format": "metadata", "metadataHeaders": ["From", "Subject", "Date"]},
                timeout=10,
            )
            if not dr.ok:
                continue
            md = dr.json()
            headers = {h['name']: h['value'] for h in md.get('payload', {}).get('headers', [])}
            out.append({
                "id": mid,
                "from": headers.get('From', ''),
                "subject": headers.get('Subject', '(no subject)'),
                "date": headers.get('Date', ''),
                "snippet": md.get('snippet', '')[:160],
            })
        except Exception:
            continue
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
