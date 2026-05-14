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
MAX_DOC_CHARS = 2000


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
    """Streaming generator for Kautilya Deep Research.
    
    Architecture:
    1. Query expansion via Llama-3.
    2. Parallel search via SerpAPI/Google.
    3. Content extraction.
    4. Phase 1 (Reasoning): Stream deep thinking via NVIDIA Nemotron-3 (120b) or DeepSeek-R1.
    5. Phase 2 (Synthesis): Generate high-signal report via GPT-OSS-120b.
    """
    queries = _expand_queries(question)
    yield {"event": "query", "queries": queries}

    sources = _gather_sources(queries)
    if not sources:
        yield {"event": "chunk", "chunk": "I couldn't find relevant sources for this question. Try rephrasing."}
        yield {"event": "done"}
        return

    yield {"event": "sources", "sources": sources}

    # Fetch in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(6, len(sources))) as ex:
        bodies = list(ex.map(_fetch_readable, [s["url"] for s in sources]))

    ctx_lines = []
    for i, (s, body) in enumerate(zip(sources, bodies), 1):
        body = body or s.get("snippet", "")
        ctx_lines.append(f"SOURCE [{i}]: {s['title']} ({s['url']})\nCONTENT: {body[:MAX_DOC_CHARS]}")
    context = "\n\n".join(ctx_lines)

    # PHASE 1: Initial Synthesis using GPT-OSS-120B (OpenAI's open-weight 120B MoE, available on Groq)
    # Best for: structured extraction, reasoning, tool-use-style analysis at low cost
    yield {"event": "status", "message": "🔬 Phase 1 — GPT-OSS-120B extracting key facts…"}

    draft_system = (
        "You are a Senior Research Analyst. Your job is to extract key facts, data points, and arguments from the provided sources "
        "and produce a structured preliminary report. Use chain-of-thought reasoning. "
        "Organize your output under: Background, Key Data Points, Arguments For/Against, and Open Questions. "
        "This draft will be refined into a final report by a Lead Analyst."
    )
    draft_messages = [
        {"role": "system", "content": draft_system},
        {"role": "user", "content": f"QUESTION: {question}\n\nSOURCES:\n{context}"}
    ]

    draft_parts = []
    try:
        # openai/gpt-oss-120b: OpenAI's open-weight 120B MoE model on Groq (day-zero support)
        draft_gen = call_groq(draft_messages, stream=True, model="openai/gpt-oss-120b",
                             temperature=0.7, max_tokens=2048)
        if not draft_gen:
            draft_gen = call_groq(draft_messages, stream=True, model="llama-3.3-70b-versatile",
                                 temperature=0.7, max_tokens=2048)
        
        if draft_gen:
            for item in draft_gen:
                if "chunk" in item:
                    draft_parts.append(item["chunk"])
                    # We don't stream the draft chunks to the user yet, 
                    # as it's an internal step for the final reasoning.
    except Exception as e:
        print(f"[Research] Phase 1 Draft Failed: {e}")
        draft_parts = ["No preliminary draft available due to service error."]

    initial_draft = "".join(draft_parts)

    # PHASE 2: Heavy Reasoning & Refinement
    # Now use Kautilya Pro (Nemotron) to reason over the draft + sources and generate the final report.
    yield {"event": "status", "message": "Applying Kautilya Pro Heavy Reasoning & Refinement..."}

    system = (
        "You are KAUTILYA Lead Research Analyst. Your goal is to produce a 'Claude-level' high-signal research report.\n\n"
        "REASONING PROTOCOL:\n"
        "1. Review the initial draft provided below.\n"
        "2. Cross-reference it with the original sources to identify gaps or inaccuracies.\n"
        "3. Apply deep reasoning to provide strategic implications and critical insights.\n"
        "4. Produce the final report in clean, high-signal Markdown.\n\n"
        "STRICT STRUCTURE:\n"
        "## Executive Summary\n"
        "## Key Findings (with [N] citations)\n"
        "## Strategic Implications\n"
        "## Critical Uncertainties\n\n"
        "RULES:\n"
        "- NO '????' or placeholders.\n"
        "- Cite sources using [1], [2], etc.\n"
        "- Stream your reasoning trace before the final answer."
    )
    
    user_prompt = (
        f"QUESTION: {question}\n\n"
        f"INITIAL DRAFT:\n{initial_draft[:4000]}\n\n"
        f"ORIGINAL SOURCES:\n{context[:6000]}"
    )
    
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user_prompt}]

    full_report_content = []
    try:
        # Final Reasoning & Synthesis: NVIDIA Nemotron (with fallback to Groq)
        gen = call_nvidia(
            messages,
            model="nvidia/nemotron-3-super-120b-a12b",
            temperature=0.7,
            stream=True,
            expose_thinking=True,
            max_tokens=6000
        )

        if not gen:
            # Fallback to Groq Llama for synthesis
            gen = call_groq(messages, stream=True, model="llama-3.3-70b-versatile",
                           temperature=0.7, max_tokens=4096)

        if gen:
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
                    chunk = chunk.replace("\ufffd", "")
                    full_report_content.append(chunk)
                    yield {"event": "chunk", "chunk": chunk}

            # ARTIFACT GENERATION \u2014 send a special artifact marker (no content duplication)
            # The frontend will detect this tag and open the Canvas with the full collected content.
            final_report = "".join(full_report_content)
            if len(final_report) > 300:
                artifact_title = f"Deep Research: {question[:50]}..."
                # Send a lightweight artifact open-tag so frontend knows to display in canvas
                # The actual content is already in fullContent on the frontend side
                yield {"event": "artifact", "artifactType": "document", "artifactTitle": artifact_title}
        else:
            yield {"event": "chunk", "chunk": "Research refinement unavailable. Here is the initial draft:\n\n" + initial_draft}

    except Exception as e:
        yield {"event": "chunk", "chunk": f"\n\n[Reasoning Error: {e}]"}

    yield {"event": "done"}
