"""
Kautilya AI — Deep Research Service (Perplexity-grade).

Streaming flow:
  1. Query expansion          → LLM rewrites question into 3-4 search queries
  2. Parallel web search      → SerpAPI (fallback: googlesearch, wikipedia)
  3. Source cards emitted     → frontend renders citation cards immediately
  4. Parallel content fetch   → readable text from top-N sources
  5. Direct streaming synth   → tokens flow to UI in real-time (no draft phase)

Event protocol (each yield is a dict):
  { "event": "query",   "queries": [...] }
  { "event": "sources", "sources": [{title, url, snippet, site, favicon}...] }
  { "event": "status",  "message": "..." }
  { "thinking": "..." }              (reasoning trace)
  { "thinking_done": true }
  { "event": "chunk",   "chunk": "..." }   (visible answer tokens)
  { "event": "artifact", artifactType, artifactTitle }
  { "event": "done" }
"""
from __future__ import annotations

import concurrent.futures
import json
import re
import time
from typing import Iterator, Dict, Any, List
from urllib.parse import urlparse

import requests

from config import SERPAPI_API_KEY
from services.llm_service import call_groq, call_nvidia

MAX_SOURCES = 8
FETCH_TIMEOUT = 6
MAX_DOC_CHARS = 4000


def _favicon(url: str) -> str:
    try:
        return f"https://www.google.com/s2/favicons?sz=64&domain={urlparse(url).netloc}"
    except Exception:
        return ""


def _expand_queries(question: str) -> List[str]:
    """Generate 3-4 diversified search queries via Groq Llama (fast)."""
    prompt = [
        {"role": "system", "content":
         "You are a research query planner. Given a user question, output 3-4 short, diverse search queries "
         "that together give broad and deep coverage. Use different angles (definitions, recent news, "
         "comparisons, statistics, expert opinions). Return a RAW JSON array of strings. No prose. No markdown."},
        {"role": "user", "content": question.strip()[:600]},
    ]
    try:
        resp = call_groq(prompt, model="llama-3.3-70b-versatile",
                         temperature=0.2, max_tokens=240, stream=False)
        if isinstance(resp, str):
            m = re.search(r'\[[\s\S]+?\]', resp)
            if m:
                arr = json.loads(m.group(0))
                if isinstance(arr, list):
                    qs = [str(x).strip() for x in arr if str(x).strip()][:4]
                    if qs:
                        return qs
    except Exception as e:
        print(f"[Research] query expansion failed: {e}")
    return [question.strip()]


def _serpapi_search(query: str, k: int = 6) -> List[Dict[str, Any]]:
    if not SERPAPI_API_KEY:
        return []
    try:
        params = {"q": query, "api_key": SERPAPI_API_KEY, "num": k, "hl": "en"}
        try:
            from serpapi import GoogleSearch
            data = GoogleSearch(params).get_dict()
        except Exception as sdk_error:
            print(f"[Research] serpapi sdk err, trying HTTP fallback: {sdk_error}")
            resp = requests.get("https://serpapi.com/search.json", params=params, timeout=FETCH_TIMEOUT)
            if resp.status_code != 200:
                print(f"[Research] serpapi HTTP {resp.status_code}: {resp.text[:200]}")
                return []
            data = resp.json()
        results = []
        for r in (data.get("organic_results") or [])[:k]:
            url = r.get("link")
            if not url:
                continue
            results.append({
                "title": r.get("title") or url,
                "url": url,
                "snippet": r.get("snippet", ""),
                "site": urlparse(url).netloc,
                "favicon": _favicon(url),
            })
        return results
    except Exception as e:
        print(f"[Research] serpapi err: {e}")
        return []


def _googlesearch_fallback(query: str, k: int = 6) -> List[Dict[str, Any]]:
    try:
        from googlesearch import search as gs
        results = []
        for r in list(gs(query, num_results=k, advanced=True, lang="en"))[:k]:
            url = getattr(r, 'url', None) or getattr(r, 'link', None) or str(r)
            if not url:
                continue
            results.append({
                "title": getattr(r, 'title', '') or url,
                "url": url,
                "snippet": getattr(r, 'description', '') or '',
                "site": urlparse(url).netloc,
                "favicon": _favicon(url),
            })
        return results
    except Exception as e:
        print(f"[Research] googlesearch err: {e}")
        return []


def _wikipedia_fallback(query: str) -> List[Dict[str, Any]]:
    try:
        import wikipedia
        titles = wikipedia.search(query, results=3)
        out = []
        for t in titles:
            try:
                summary = wikipedia.summary(t, sentences=3)
                page = wikipedia.page(t).url
                out.append({
                    "title": t, "url": page,
                    "snippet": summary, "site": "en.wikipedia.org",
                    "favicon": _favicon(page),
                })
            except Exception:
                pass
        return out
    except Exception:
        return []


def _gather_sources(queries: List[str]) -> List[Dict[str, Any]]:
    seen = set()
    merged: List[Dict[str, Any]] = []

    def dedupe_add(items):
        for it in items:
            u = it["url"]
            if u in seen:
                continue
            seen.add(u)
            merged.append(it)

    with concurrent.futures.ThreadPoolExecutor(max_workers=max(2, len(queries))) as ex:
        if SERPAPI_API_KEY:
            results = list(ex.map(_serpapi_search, queries))
        else:
            results = list(ex.map(_googlesearch_fallback, queries))
        for r in results:
            dedupe_add(r)

    if not merged:
        for q in queries:
            dedupe_add(_wikipedia_fallback(q))

    return merged[:MAX_SOURCES]


def _fetch_readable(url: str) -> str:
    try:
        resp = requests.get(url, timeout=FETCH_TIMEOUT, headers={
            "User-Agent": "Mozilla/5.0 (KautilyaAI/1.0 research-bot)"
        })
        if resp.status_code != 200:
            return ""
        from html.parser import HTMLParser

        class TextExtractor(HTMLParser):
            def __init__(self):
                super().__init__()
                self.parts = []
                self._skip = 0
            def handle_starttag(self, tag, _attrs):
                if tag in ('script', 'style', 'nav', 'footer', 'header', 'aside', 'noscript', 'svg', 'form'):
                    self._skip += 1
            def handle_endtag(self, tag):
                if tag in ('script', 'style', 'nav', 'footer', 'header', 'aside', 'noscript', 'svg', 'form') and self._skip:
                    self._skip -= 1
            def handle_data(self, data):
                if not self._skip:
                    self.parts.append(data)

        te = TextExtractor()
        try: te.feed(resp.text)
        except Exception: pass
        text = re.sub(r'\s+', ' ', ' '.join(te.parts)).strip()
        return text[:MAX_DOC_CHARS]
    except Exception:
        return ""


def deep_research_stream(question: str) -> Iterator[Dict[str, Any]]:
    """Stream a Perplexity-style deep research answer.

    Single-phase streaming synthesis: we expand queries → gather sources →
    fetch pages in parallel → stream the final report directly to the UI.
    No hidden "draft" phase that buffers tokens server-side; every visible
    chunk reaches the user as soon as the LLM emits it.
    """
    t0 = time.time()
    yield {"event": "status", "message": "🧭 Planning search queries…"}
    queries = _expand_queries(question)
    yield {"event": "query", "queries": queries}

    yield {"event": "status", "message": "🔎 Searching the web in parallel…"}
    sources = _gather_sources(queries)
    if not sources:
        yield {"event": "chunk", "chunk": "I couldn't find relevant sources for this question. Try rephrasing or adding more specifics."}
        yield {"event": "done"}
        return

    yield {"event": "sources", "sources": sources}

    yield {"event": "status", "message": f"📑 Reading {len(sources)} sources…"}
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, len(sources))) as ex:
        bodies = list(ex.map(_fetch_readable, [s["url"] for s in sources]))

    ctx_lines = []
    for i, (s, body) in enumerate(zip(sources, bodies), 1):
        body = body or s.get("snippet", "")
        ctx_lines.append(
            f"SOURCE [{i}] — {s['title']} ({s['site']})\nURL: {s['url']}\nCONTENT: {body[:MAX_DOC_CHARS]}"
        )
    context = "\n\n".join(ctx_lines)

    yield {"event": "status", "message": "🧠 Synthesizing answer…"}

    system = (
        "You are KAUTILYA Deep Research — a Perplexity-grade research analyst. "
        "Produce a thorough, high-signal answer using ONLY the SOURCES provided. "
        "Cite every non-trivial claim inline as [1], [2], etc. matching the source numbers.\n\n"
        "REQUIRED STRUCTURE (markdown):\n"
        "## TL;DR\n"
        "Two-sentence direct answer to the user's question.\n\n"
        "## Key Findings\n"
        "- 4-7 bullet points, each with [N] citations.\n\n"
        "## Detailed Analysis\n"
        "2-4 short paragraphs unpacking the nuances, trade-offs, and context. "
        "Compare/contrast sources when they disagree.\n\n"
        "## Numbers & Facts\n"
        "Tight bulleted list of concrete data points (stats, dates, prices, names) with [N].\n\n"
        "## Caveats & Open Questions\n"
        "Honest limitations of the available evidence.\n\n"
        "RULES:\n"
        "- Never invent citations. Only use [N] numbers that exist in SOURCES.\n"
        "- Prefer specific data over vague generalities.\n"
        "- If sources conflict, say so explicitly.\n"
        "- No filler. No 'Sure, here is...' preamble. Start directly with `## TL;DR`."
    )
    user_prompt = f"USER QUESTION: {question}\n\nSOURCES:\n{context}"
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user_prompt}]

    full_report = []
    streamed_anything = False

    def _emit_from(gen):
        nonlocal streamed_anything
        for item in gen:
            if isinstance(item, dict):
                if "thinking" in item:
                    yield {"thinking": item["thinking"]}
                    continue
                if "thinking_done" in item:
                    yield {"thinking_done": True}
                    continue
                chunk = item.get("chunk", "")
            else:
                chunk = item
            if chunk:
                chunk = chunk.replace("�", "")
                full_report.append(chunk)
                streamed_anything = True
                yield {"event": "chunk", "chunk": chunk}

    # Primary synthesis: NVIDIA Nemotron — heavy reasoning, much higher
    # output quality and depth than Groq Llama for research-grade tasks.
    # Thinking trace is streamed live so the user sees the reasoning unfold
    # while the final answer is being composed. Groq is the fallback if the
    # NVIDIA edge is unavailable.
    gen = None
    try:
        gen = call_nvidia(
            messages,
            model="nvidia/nemotron-3-super-120b-a12b",
            temperature=0.5,
            stream=True,
            expose_thinking=True,
            max_tokens=8000,
        )
    except Exception as e:
        print(f"[Research] NVIDIA synth failed: {e}")

    if gen:
        try:
            for ev in _emit_from(gen):
                yield ev
        except Exception as e:
            print(f"[Research] NVIDIA stream error: {e}")

    # Fallback to Groq Llama if NVIDIA produced nothing
    if not streamed_anything:
        try:
            gq_gen = call_groq(messages, stream=True, model="llama-3.3-70b-versatile",
                               temperature=0.4, max_tokens=4096)
            if gq_gen:
                for ev in _emit_from(gq_gen):
                    yield ev
        except Exception as e:
            print(f"[Research] Groq fallback failed: {e}")

    if not streamed_anything:
        yield {"event": "chunk", "chunk":
               "I gathered sources but the synthesis step is temporarily unavailable. "
               "Please try again in a moment."}

    final = "".join(full_report)
    if len(final) > 400:
        yield {"event": "artifact",
               "artifactType": "document",
               "artifactTitle": f"Deep Research: {question[:60]}"}

    elapsed = round(time.time() - t0, 1)
    yield {"event": "status", "message": f"✓ Done in {elapsed}s · {len(sources)} sources"}
    yield {"event": "done"}
