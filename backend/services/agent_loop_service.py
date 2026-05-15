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
        if not uid or not messages:
            return ""
        last_msg = messages[-1]["content"]
        query_text = last_msg if isinstance(last_msg, str) else " ".join([p["text"] for p in last_msg if p.get("type") == "text"])
        # Only RAG if query is meaningful (> 10 chars)
        if len(query_text) > 10:
            try:
                hits = vector_store.search(uid, query_text, top_k=2)
                if hits:
                    return "\n\nRELEVANT MEMORIES:\n" + "\n".join([f"- {h[1]}" for h in hits])
            except:
                pass
        return ""

    future_loc = _executor.submit(fetch_loc)
    future_rag = _executor.submit(fetch_rag)
    
    try:
        location_context = future_loc.result(timeout=0.9)
    except:
        pass
    try:
        rag_context = future_rag.result(timeout=1.0)
    except:
        pass

    current_messages = [m.copy() for m in messages]
    if location_context or rag_context:
        current_messages[0]["content"] += location_context + rag_context

    MAX_TURNS = 3

    last_user_msg = ""
    if messages and messages[-1]["role"] == "user":
        content = messages[-1].get("content", "")
        if isinstance(content, str):
            last_user_msg = content
        elif isinstance(content, list):
            last_user_msg = " ".join([p["text"] for p in content if p.get("type") == "text"])

    # Pre-fetch integration data based on intent BEFORE calling the LLM.
    # This bypasses the unreliable ReAct token approach — the model gets
    # real live data injected into context and just needs to present it.
    if uid and last_user_msg:
        integration_context = _pre_fetch_integrations(uid, last_user_msg)
        if integration_context:
            current_messages[0]["content"] += integration_context

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
        'pro':   ('Kautilya Pro', 'nvidia/nemotron-3-super-120b-a12b'),
        'daily': ('Kautilya Daily', 'llama-3.3-70b-versatile'),
    }

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

        reasoning_budget = _estimate_reasoning_budget(max_tokens, max_thinking)

        if model_choice == 'coder':
            from config import NVIDIA_API_KEY
            label, model_id = _MODEL_LABELS['coder']
            if not NVIDIA_API_KEY:
                yield json.dumps({"event": "status", "message": f"⚡ {label} requires NVIDIA API key — using fast model…"})
                response_gen = call_groq(current_messages, stream=True, max_tokens=max_tokens,
                                         model='llama-3.3-70b-versatile', temperature=0.6)
            else:
                yield json.dumps({"event": "status", "message": f"🧠 Connecting to {label}…"})
                response_gen = call_nvidia(current_messages, stream=True, max_tokens=max_tokens,
                                           model=model_id, tools=tools, tool_choice=tool_choice,
                                           temperature=1.0, top_p=0.95, max_thinking=max_thinking,
                                           reasoning_budget=reasoning_budget)
                if not response_gen:
                    yield json.dumps({"event": "status", "message": f"⚡ Retrying {label}…"})
                    response_gen = call_nvidia(current_messages, stream=True, max_tokens=max_tokens,
                                               model=model_id, temperature=1.0, top_p=0.95,
                                               max_thinking=max_thinking, reasoning_budget=reasoning_budget)
                if not response_gen:
                    yield json.dumps({"event": "status", "message": f"⚡ {label} unavailable — using fast model…"})
                    response_gen = call_groq(current_messages, stream=True, max_tokens=max_tokens,
                                             model='llama-3.3-70b-versatile', temperature=0.6)

        elif model_choice == 'pro':
            from config import NVIDIA_API_KEY
            label, model_id = _MODEL_LABELS['pro']
            if not NVIDIA_API_KEY:
                yield json.dumps({"event": "status", "message": f"⚡ {label} requires NVIDIA API key — using fast model…"})
                response_gen = call_groq(current_messages, stream=True, max_tokens=max_tokens,
                                         model='llama-3.3-70b-versatile', temperature=0.6)
            else:
                yield json.dumps({"event": "status", "message": f"💎 Connecting to {label}…"})
                response_gen = call_nvidia(current_messages, stream=True, max_tokens=max_tokens,
                                           model=model_id, tools=tools, tool_choice=tool_choice,
                                           temperature=1.0, top_p=0.95, max_thinking=max_thinking,
                                           reasoning_budget=reasoning_budget)
                if not response_gen:
                    yield json.dumps({"event": "status", "message": f"⚡ Retrying {label}…"})
                    response_gen = call_nvidia(current_messages, stream=True, max_tokens=max_tokens,
                                               model=model_id, temperature=1.0, top_p=0.95,
                                               max_thinking=max_thinking, reasoning_budget=reasoning_budget)
                if not response_gen:
                    yield json.dumps({"event": "status", "message": f"⚡ {label} unavailable — using fast model…"})
                    print(f"[FALLBACK] {label} failed/unavailable. Switching to Groq.")
                    response_gen = call_groq(current_messages, stream=True, max_tokens=max_tokens,
                                             model='llama-3.3-70b-versatile', temperature=0.6)

        elif has_image:
            # Vision model
            yield json.dumps({"event": "status", "message": "👁️ Analyzing image…"})
            response_gen = call_groq(current_messages, stream=True, max_tokens=max_tokens,
                                     model='llama-3.2-11b-vision-preview', temperature=0.6)
            if not response_gen:
                response_gen = call_groq(current_messages, stream=True, max_tokens=max_tokens,
                                         model='llama-3.3-70b-versatile', temperature=0.6)
        else:
            # Daily = Groq Llama
            response_gen = call_groq(current_messages, stream=True, model='llama-3.3-70b-versatile',
                                     temperature=0.6, max_tokens=max_tokens, tools=tools, tool_choice=tool_choice)

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

        # 4. [CALENDAR_LIST: days]
        cal_list_match = re.search(r'\[CALENDAR_LIST:\s*(\d*)\]', accumulated_response)
        if cal_list_match and not action_found:
            days = int(cal_list_match.group(1) or 7)
            action_counter += 1
            action_id = str(action_counter)
            yield json.dumps({"event": "react_action", "id": action_id, "tool": "calendar", "input": f"Next {days} days", "status": "running"})
            try:
                events = _calendar_list(uid, days)
                if events:
                    lines = []
                    for e in events:
                        start = e.get('start', {}).get('dateTime') or e.get('start', {}).get('date', '')
                        lines.append(f"- {e.get('summary','Untitled')} at {start}")
                    obs = f"CALENDAR EVENTS (next {days} days):\n" + "\n".join(lines)
                    yield json.dumps({"event": "react_action_done", "id": action_id, "status": "done",
                                      "preview": f"{len(events)} event(s) found"})
                else:
                    obs = f"CALENDAR: No events found in the next {days} days."
                    yield json.dumps({"event": "react_action_done", "id": action_id, "status": "done", "preview": "No events"})
            except Exception as e:
                yield json.dumps({"event": "react_action_done", "id": action_id, "status": "error", "preview": str(e)[:100]})
                obs = f"CALENDAR ERROR: {e}"
            current_messages.append({"role": "assistant", "content": accumulated_response})
            current_messages.append({"role": "user", "content": f"OBSERVATION: {obs}\n\nReport the events to the user."})
            action_found = True

        # 5. [WHATSAPP_SEND: number | message]
        wa_match = re.search(r'\[WHATSAPP_SEND:\s*(.*?)\]', accumulated_response, re.DOTALL)
        if wa_match and not action_found:
            wa_parts = [p.strip() for p in wa_match.group(1).split('|', 1)]
            wa_to  = wa_parts[0] if len(wa_parts) > 0 else ''
            wa_msg = wa_parts[1] if len(wa_parts) > 1 else ''
            action_counter += 1
            action_id = str(action_counter)
            yield json.dumps({"event": "react_action", "id": action_id, "tool": "web_search", "input": f"WhatsApp → {wa_to}", "status": "running"})
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
            yield json.dumps({"event": "react_action", "id": action_id, "tool": "web_search", "input": "Slack message", "status": "running"})
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
            yield json.dumps({"event": "react_action", "id": action_id, "tool": "web_search", "input": f"HubSpot contact: {hs_email}", "status": "running"})
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
    Scales answer budget proportionally to message complexity and mode.
    Professional-level: longer/complex queries unlock more tokens for quality output.
    """
    msg_lower = user_msg.lower().strip()
    msg_len = len(msg_lower)

    greetings = {'hi', 'hello', 'hey', 'yo', 'sup', 'namaste', 'thanks', 'ok', 'bye', 'okay'}
    if msg_lower in greetings or msg_len < 10:
        return 256  # short reply for simple greetings

    # Complexity tiers by message length
    if msg_len < 80:
        complexity = 'low'
    elif msg_len < 400:
        complexity = 'medium'
    elif msg_len < 1200:
        complexity = 'high'
    else:
        complexity = 'very_high'

    # Token budgets per mode & complexity
    budgets = {
        'daily': {'low': 1024, 'medium': 2048, 'high': 3072, 'very_high': 4096},
        'coder': {'low': 4096, 'medium': 8192, 'high': 12288, 'very_high': 16384},
        'pro':   {'low': 4096, 'medium': 8192, 'high': 16384, 'very_high': 16384},
    }

    mode_key = mode if mode in budgets else 'daily'
    return budgets[mode_key][complexity]


def _estimate_reasoning_budget(max_tokens, max_thinking=False):
    """
    Derive a proportional reasoning budget from the answer token budget.
    Thinking should be ≥ answer budget to allow full deliberation.
    """
    if not max_thinking:
        # Light reasoning for standard calls
        return min(4096, max_tokens)
    # Deep thinking: up to 2× the answer budget, capped at 32k
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

    # ── Calendar: list/view intent ────────────────────────────────────────
    cal_view_kw  = {'calendar', 'schedule', 'meeting', 'meetings', 'event',
                    'events', 'appointment', 'appointments', 'agenda', 'remind'}
    cal_view_act = {'show', 'what', 'list', 'upcoming', 'check', 'see', 'any',
                    'today', 'tomorrow', 'week', 'do i have', 'tell me', 'get'}
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
