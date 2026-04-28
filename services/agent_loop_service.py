"""
Kautilya AI — Agent Loop Service
Agentic loop: Think → Act → Observe → Answer.
"""
import re
import json
import time
import concurrent.futures

from config import GROQ_API_KEY, SERPAPI_API_KEY
from services.llm_service import call_groq, call_nvidia


def agent_loop(messages, uid=None, model_choice='daily', user_ip=None, tools=None, tool_choice=None):
    """
    Agentic Loop: Thoughts -> Actions -> Observations -> Final Answer.
    Yields chunks of text OR special status JSONs.
    """
    from extensions import limit_manager, vector_store

    rag_context = ""
    location_context = ""

    with concurrent.futures.ThreadPoolExecutor() as executor:
        def fetch_loc():
            if not user_ip or user_ip in ('127.0.0.1', 'localhost', '::1'):
                return ""
            try:
                import requests
                resp = requests.get(f"http://ip-api.com/json/{user_ip}", timeout=1.0)
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get('status') == 'success':
                        return f"\n[System: User is currently located in {data.get('city')}, {data.get('regionName')}. Use this to personalize greetings!]\n"
            except:
                pass
            return ""

        def fetch_rag():
            if not uid:
                return ""
            last_msg = messages[-1]["content"]
            query_text = last_msg if isinstance(last_msg, str) else " ".join([p["text"] for p in last_msg if p.get("type") == "text"])
            if query_text:
                hits = vector_store.search(uid, query_text, top_k=2)
                if hits:
                    return "\n\nRELEVANT MEMORIES:\n" + "\n".join([f"- {h[1]}" for h in hits])
            return ""

        future_loc = executor.submit(fetch_loc)
        future_rag = executor.submit(fetch_rag)
        try:
            location_context = future_loc.result(timeout=1.0)
        except:
            pass
        try:
            rag_context = future_rag.result(timeout=1.5)
        except:
            print("[Agent] RAG search timed out.")

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

    for turn in range(MAX_TURNS):
        print(f"[Agent] Turn {turn+1}/{MAX_TURNS}")

        max_tokens = _estimate_tokens(last_user_msg, model_choice)
        print(f"[Agent] Smart tokens: {max_tokens} (msg length: {len(last_user_msg)}, mode: {model_choice})")

        if model_choice == 'coder':
            response_gen = call_nvidia(current_messages, stream=True, max_tokens=max_tokens,
                                       model='nvidia/nemotron-3-super-120b-a12b', tools=tools, tool_choice=tool_choice)
        elif model_choice == 'pro':
            response_gen = call_groq(current_messages, stream=True, model='deepseek-r1-distill-llama-70b',
                                     temperature=0.6, tools=tools, tool_choice=tool_choice)
        else:
            response_gen = call_groq(current_messages, stream=True, model='llama-3.3-70b-versatile',
                                     temperature=0.6, tools=tools, tool_choice=tool_choice)

        # Auto-detect image
        has_image = False
        if current_messages and current_messages[-1].get("role") == "user":
            last_mc = current_messages[-1].get("content")
            if isinstance(last_mc, list) and any(p.get("type") == "image_url" for p in last_mc):
                has_image = True

        if not response_gen and model_choice != 'daily' and not has_image:
            response_gen = call_groq(current_messages, stream=True, max_tokens=max_tokens, model='llama-3.3-70b-versatile')
        elif not response_gen and has_image:
            response_gen = call_groq(current_messages, stream=True, max_tokens=max_tokens, model='llama-3.2-11b-vision-preview')

        if not response_gen:
            response_gen = call_nvidia(current_messages, max_tokens=max_tokens)

        if not response_gen:
            yield "⚠️ All AI services are currently at capacity. Please try again in a moment."
            return

        buffer = ""
        is_command_mode = False
        accumulated_response = ""

        try:
            for item in response_gen:
                if isinstance(item, dict):
                    chunk = item.get("chunk", "")
                    usage = item.get("usage")
                    if usage:
                        yield json.dumps({"usage": usage})
                        continue
                else:
                    chunk = item
                if not chunk:
                    continue
                accumulated_response += chunk
                buffer += chunk
                if "[" in buffer and "]" not in buffer:
                    if any(cmd in buffer.upper() for cmd in ["[SEARCH:", "[IMAGE:", "[WEATHER:", "[NEWS:", "[STOCK:", "[PREDICT_STOCK:", "[CRYPTO:", "[MOVIE:", "[CALCULATE:", "[QUOTE:", "[FACT:", "[DEFINE:", "[TRANSLATE:", "[CONVERT:", "[CURRENCY:", "[WIKI:", "[HOROSCOPE:", "[RECIPE:"]):
                        continue
                    else:
                        yield json.dumps({"chunk": buffer})
                        buffer = ""
                elif "[" in buffer and "]" in buffer:
                    if re.search(r'\[(SEARCH|IMAGE|WEATHER|NEWS|STOCK|PREDICT_STOCK|CRYPTO|MOVIE|CALCULATE|QUOTE|FACT|DEFINE|TRANSLATE|CONVERT|CURRENCY|WIKI|HOROSCOPE|RECIPE)(?::\s*[^\]]*?)?\]', buffer):
                        is_command_mode = True
                        break
                    else:
                        yield json.dumps({"chunk": buffer})
                        buffer = ""
                else:
                    yield json.dumps({"chunk": buffer})
                    buffer = ""
            if buffer and not is_command_mode:
                yield json.dumps({"chunk": buffer})
                buffer = ""
        except Exception as e:
            print(f"[Agent] Generator streaming error: {e}")
            yield json.dumps({"chunk": f"\n[Stream interrupted: {e}]"})
            return

        if not accumulated_response and not is_command_mode:
            yield json.dumps({"chunk": "I apologize, but I couldn't generate a response. Please try again."})

        if is_command_mode:
            full_response = accumulated_response
            search_match = re.search(r'\[SEARCH:\s*(.+?)\]', full_response)
            if search_match:
                query = search_match.group(1).strip()
                yield json.dumps({"type": "status", "message": f"Searching: {query}"})
                try:
                    obs = _perform_search(query)
                    current_messages.append({"role": "assistant", "content": full_response})
                    current_messages.append({"role": "user", "content": f"Here are the search results for '{query}':\n{obs}\n\nUsing these results, please answer my original question."})
                    yield json.dumps({"type": "status", "message": None})
                    yield " "
                    continue
                except Exception as e:
                    yield f" [Error: {e}]"
                    return
            if "[IMAGE:" in full_response:
                yield buffer
                return
        else:
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


def _perform_search(query):
    """Perform web search with fallback chain: SerpApi → Google → Wikipedia."""
    import requests
    obs = ""
    # 1. SerpApi
    if SERPAPI_API_KEY:
        try:
            from serpapi import GoogleSearch
            results = GoogleSearch({"q": query, "api_key": SERPAPI_API_KEY, "num": 5}).get_dict()
            organic = results.get("organic_results", [])
            if organic:
                obs_list = [f"- {r.get('title', 'Result')}: {r.get('snippet', '')} ({r.get('link', '')})" for r in organic if r.get('snippet')]
                if obs_list:
                    return "Observation (SerpApi): " + "\n".join(obs_list[:3])
        except Exception as e:
            print(f"[Agent] SerpApi Search failed: {e}")
    # 2. Google fallback
    if not obs and not SERPAPI_API_KEY:
        try:
            from googlesearch import search as google_search
            g_results = list(google_search(query, num_results=5, advanced=True, lang="en"))
            if g_results:
                obs_list = [f"- {getattr(r, 'title', 'Result')}: {getattr(r, 'description', str(r))}" for r in g_results if len(getattr(r, 'description', '')) > 20]
                if obs_list:
                    return "Observation (Google): " + "\n".join(obs_list[:3])
        except Exception as e:
            print(f"[Agent] Google Search failed: {e}")
    # 3. Wikipedia fallback
    try:
        import wikipedia
        wiki_res = wikipedia.summary(query, sentences=3)
        if wiki_res:
            return f"Observation (Wikipedia): {wiki_res}"
    except Exception as e:
        print(f"[Agent] Wikipedia failed: {e}")
    return "Observation: Search engines returned no results. Please try a different query."


def get_llm_response(messages, uid=None, model="daily", user_ip=None, tools=None, tool_choice=None):
    """Entry point for chat. Routes to fast-path or agent_loop."""
    user_input_text = ""
    if messages and messages[-1]["role"] == "user":
        luc = messages[-1]["content"]
        if isinstance(luc, str):
            user_input_text = luc
        elif isinstance(luc, list):
            user_input_text = " ".join([p["text"] for p in luc if p.get("type") == "text"])

    # Fast-path for Daily model
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

    lower_text = user_input_text.lower()
    if "create" in lower_text and ("image" in lower_text or "picture" in lower_text or "drawing" in lower_text):
        messages.append({"role": "system", "content": "The user is requesting an image. You MUST include the [IMAGE: prompt] command in your response."})

    return agent_loop(messages, uid, model_choice=model, user_ip=user_ip, tools=tools, tool_choice=tool_choice)
