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
    "deepseek": "coder",
    "deepseek-ai/deepseek-v4-pro": "coder",
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
        'coder': ('DeepSeek V4 Pro', 'deepseek-ai/deepseek-v4-pro'),
        'pro':   ('Nemotron-3 Super 120B', 'nvidia/nemotron-3-super-120b-a12b'),
        'daily': ('Llama 3.3 70B', 'llama-3.3-70b-versatile'),
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

        if model_choice == 'coder':
            # Coder = DeepSeek-v4-Pro via NVIDIA NIM
            from config import NVIDIA_API_KEY
            label, model_id = _MODEL_LABELS['coder']
            if not NVIDIA_API_KEY:
                yield json.dumps({"type": "status", "message": f"⚡ {label} requires NVIDIA API key — using fast model…"})
                response_gen = call_groq(current_messages, stream=True, max_tokens=max_tokens,
                                         model='llama-3.3-70b-versatile', temperature=0.6)
            else:
                yield json.dumps({"type": "status", "message": f"🧠 Connecting to {label}…"})
                response_gen = call_nvidia(current_messages, stream=True, max_tokens=max_tokens,
                                           model=model_id, tools=tools, tool_choice=tool_choice,
                                           temperature=1.0, top_p=0.95, max_thinking=max_thinking)
                if not response_gen:
                    # Retry once
                    yield json.dumps({"type": "status", "message": f"⚡ Retrying {label}…"})
                    response_gen = call_nvidia(current_messages, stream=True, max_tokens=max_tokens,
                                               model=model_id, temperature=1.0, top_p=0.95, max_thinking=max_thinking)
                if not response_gen:
                    yield json.dumps({"type": "status", "message": f"⚡ {label} unavailable — using fast model…"})
                    response_gen = call_groq(current_messages, stream=True, max_tokens=max_tokens,
                                             model='llama-3.3-70b-versatile', temperature=0.6)

        elif model_choice == 'pro':
            # Pro = Nemotron-3-Super-120B via NVIDIA NIM
            from config import NVIDIA_API_KEY
            label, model_id = _MODEL_LABELS['pro']
            if not NVIDIA_API_KEY:
                yield json.dumps({"type": "status", "message": f"⚡ {label} requires NVIDIA API key — using fast model…"})
                response_gen = call_groq(current_messages, stream=True, max_tokens=max_tokens,
                                         model='llama-3.3-70b-versatile', temperature=0.6)
            else:
                yield json.dumps({"type": "status", "message": f"💎 Connecting to {label}…"})
                response_gen = call_nvidia(current_messages, stream=True, max_tokens=max_tokens,
                                           model=model_id, tools=tools, tool_choice=tool_choice,
                                           temperature=1.0, top_p=0.95, max_thinking=max_thinking,
                                           reasoning_budget=16384 if max_thinking else 1024)
                if not response_gen:
                    yield json.dumps({"type": "status", "message": f"⚡ Retrying {label}…"})
                    response_gen = call_nvidia(current_messages, stream=True, max_tokens=max_tokens,
                                               model=model_id, temperature=1.0, top_p=0.95, max_thinking=max_thinking)
                if not response_gen:
                    yield json.dumps({"type": "status", "message": f"⚡ {label} unavailable — using fast model…"})
                    response_gen = call_groq(current_messages, stream=True, max_tokens=max_tokens,
                                             model='llama-3.3-70b-versatile', temperature=0.6)

        elif has_image:
            # Vision model
            yield json.dumps({"type": "status", "message": "👁️ Analyzing image…"})
            response_gen = call_groq(current_messages, stream=True, max_tokens=max_tokens,
                                     model='llama-3.2-11b-vision-preview', temperature=0.6)
            if not response_gen:
                response_gen = call_groq(current_messages, stream=True, max_tokens=max_tokens,
                                         model='llama-3.3-70b-versatile', temperature=0.6)
        else:
            # Daily = Groq Llama
            response_gen = call_groq(current_messages, stream=True, model='llama-3.3-70b-versatile',
                                     temperature=0.6, tools=tools, tool_choice=tool_choice)

        # Final fallback: try anything
        if not response_gen:
            yield json.dumps({"type": "status", "message": "🔄 Trying backup service…"})
            response_gen = call_nvidia(current_messages, max_tokens=max_tokens)

        if not response_gen:
            yield json.dumps({"type": "status", "message": None})
            yield "⚠️ All AI services are currently at capacity. Please try again in a moment."
            return

        # Clear status once streaming starts
        yield json.dumps({"type": "status", "message": None})

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

        if not accumulated_response:
            yield json.dumps({"chunk": "I apologize, but I couldn't generate a response. Please try again."})
        return


def _estimate_tokens(user_msg, mode):
    msg_lower = user_msg.lower().strip()
    msg_len = len(msg_lower)
    if mode == 'pro':
        return 16384
    greetings = ['hi', 'hello', 'hey', 'yo', 'sup', 'namaste', 'hola', 'thanks', 'thank you',
                 'ok', 'okay', 'bye', 'good morning', 'good night', 'good evening', 'gm', 'gn']
    if msg_lower in greetings or msg_len < 10:
        return 512
    simple_keywords = ['what is', 'who is', 'when is', 'where is', 'how are', 'what time',
                       'tell me a joke', 'meaning of', 'define ']
    if any(msg_lower.startswith(k) for k in simple_keywords) and msg_len < 60:
        return 2048
    complex_keywords = ['write', 'code', 'create', 'build', 'implement', 'explain in detail',
                        'essay', 'article', 'compare', 'analyze', 'list all', 'step by step',
                        'debug', 'fix this', 'refactor', 'convert', 'generate', 'design',
                        'full', 'complete', 'detailed', 'comprehensive', 'script', 'function',
                        'class', 'regex', 'sql', 'css', 'html', 'javascript', 'python',
                        'error', 'exception', 'test', 'docker', 'api', 'json']
    if any(k in msg_lower for k in complex_keywords) or msg_len > 200:
        return 16384
    return 4096


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
