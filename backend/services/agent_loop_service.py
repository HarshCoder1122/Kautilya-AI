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
        action_counter = getattr(agent_loop, '_action_counter', 0)

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

    # Fast-path for Daily model (Groq)
    if model == "daily" and "image" not in user_input_text.lower() and "picture" not in user_input_text.lower():
        def fast_generator():
            try:
                response_gen = call_groq(messages, stream=True, model='llama-3.3-70b-versatile',
                                         temperature=0.6, tools=tools, tool_choice=tool_choice)
                if not response_gen:
                    yield json.dumps({"chunk": "I am currently overloaded. Please try again."})
                    return
                for chunk in response_gen:
                    if isinstance(chunk, str):
                        yield json.dumps({"chunk": chunk})
                    elif isinstance(chunk, dict):
                        yield json.dumps(chunk)
            except Exception as e:
                yield json.dumps({"chunk": f" [Error: {str(e)}]"})
        return fast_generator()

    return agent_loop(messages, uid, model_choice=model, user_ip=user_ip, tools=tools, tool_choice=tool_choice, max_thinking=max_thinking)
