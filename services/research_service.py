"""
Kautilya AI — Deep Research Service.

Perplexity-style multi-source research:
  1. Query expansion    → LLM rewrites user question into 2-3 search queries
  2. Parallel search    → SerpAPI (fallback: googlesearch, wikipedia)
  3. URL fetch          → pull readable content from top-N results
  4. Synthesis          → LLM writes structured report with [N] citations
  5. Stream back        → emit source cards first, then report tokens

Each result yield is one of:
  { "event": "query",   "queries": [...] }
  { "event": "sources", "sources": [{title, url, snippet, site}...] }
  { "event": "chunk",   "chunk": "..." }
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

MAX_SOURCES = 6
FETCH_TIMEOUT = 6
MAX_DOC_CHARS = 5000


def _expand_queries(question: str) -> List[str]:
    """Ask the LLM to generate 2-3 diversified search queries."""
    prompt = [
        {"role": "system", "content":
         "You are a research query planner. Given a user question, output 2-3 short search queries that together cover the topic. "
         "Return a raw JSON array of strings. No prose. No markdown."},
        {"role": "user", "content": question.strip()[:600]},
    ]
    try:
        resp = call_groq(prompt, model="llama-3.3-70b-versatile",
                         temperature=0.2, max_tokens=200, stream=False)
        if isinstance(resp, str):
            m = re.search(r'\[[^\]]+\]', resp)
            if m:
                arr = json.loads(m.group(0))
                if isinstance(arr, list):
                    return [str(x).strip() for x in arr if str(x).strip()][:3]
    except Exception as e:
        print(f"[Research] query expansion failed: {e}")
    return [question.strip()]


def _serpapi_search(query: str, k: int = 6) -> List[Dict[str, Any]]:
    if not SERPAPI_API_KEY:
        return []
    try:
        from serpapi import GoogleSearch
        params = {"q": query, "api_key": SERPAPI_API_KEY, "num": k, "hl": "en"}
        data = GoogleSearch(params).get_dict()
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

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(queries)) as ex:
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
        # Lightweight HTML → text (avoid heavy deps)
        from html.parser import HTMLParser

        class TextExtractor(HTMLParser):
            def __init__(self):
                super().__init__()
                self.parts = []
                self._skip = 0
            def handle_starttag(self, tag, _attrs):
                if tag in ('script', 'style', 'nav', 'footer', 'header', 'aside'):
                    self._skip += 1
            def handle_endtag(self, tag):
                if tag in ('script', 'style', 'nav', 'footer', 'header', 'aside') and self._skip:
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
    """Streaming generator. Yields dicts with `event` key."""
    queries = _expand_queries(question)
    yield {"event": "query", "queries": queries}

    sources = _gather_sources(queries)
    if not sources:
        yield {"event": "chunk", "chunk": "I couldn't find relevant sources for this question. "
                                           "Try rephrasing or be more specific."}
        yield {"event": "done"}
        return

    yield {"event": "sources", "sources": sources}

    # Fetch all pages in parallel (bounded)
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(6, len(sources))) as ex:
        bodies = list(ex.map(_fetch_readable, [s["url"] for s in sources]))

    # Build the research context for the LLM
    ctx_lines = []
    for i, (s, body) in enumerate(zip(sources, bodies), 1):
        body = body or s.get("snippet", "")
        ctx_lines.append(f"[{i}] {s['title']} — {s['url']}\n{body[:MAX_DOC_CHARS]}")
    context = "\n\n".join(ctx_lines)

    system = (
        "You are KAUTILYA Deep Research. Write a structured, concise research report.\n\n"
        "STRICT FORMAT:\n"
        "## Summary\nOne paragraph. The most important finding up front.\n\n"
        "## Findings\nBulleted. Each bullet MUST cite sources like [1] or [2,3].\n\n"
        "## Implications\n2-4 bullets. So-what.\n\n"
        "## Open Questions\n1-3 bullets. What remains uncertain.\n\n"
        "Rules:\n"
        "- Only use facts that appear in the Sources section below.\n"
        "- If sources disagree, say so explicitly.\n"
        "- No filler. No preamble. No 'I will now…' statements. Just the report.\n"
        "- Every non-trivial claim MUST have a [N] citation.\n"
    )
    user = f"QUESTION:\n{question}\n\nSOURCES:\n{context}\n\nWrite the report now."
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]

    try:
        # Primary: NVIDIA Nemotron-3-Super-120B for deep research synthesis
        gen = call_nvidia(messages, stream=True, max_tokens=4096,
                          model="nvidia/nemotron-3-super-120b-a12b",
                          temperature=0.3, expose_thinking=False)
        if gen is None:
            # Fallback to Groq only if NVIDIA unavailable
            gen = call_groq(messages, stream=True, model="llama-3.3-70b-versatile",
                            temperature=0.3, max_tokens=4096)
        if gen is None:
            yield {"event": "chunk", "chunk": "Research synthesis LLM unavailable."}
            yield {"event": "done"}
            return

        for item in gen:
            if isinstance(item, str):
                yield {"event": "chunk", "chunk": item}
            elif isinstance(item, dict):
                if "chunk" in item:
                    yield {"event": "chunk", "chunk": item["chunk"]}
                # Silently drop thinking during research synthesis
    except Exception as e:
        yield {"event": "chunk", "chunk": f"\n\n[synthesis error: {e}]"}

    yield {"event": "done"}
