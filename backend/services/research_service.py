"""
Kautilya AI — Deep Research Service (analyst-grade, multi-round).

Goal: compress what a human analyst would spend weeks on into ~minutes —
plan, search broadly, READ, find the gaps, search again, then synthesise a
long-form, citation-dense report.

Pipeline (all streamed live to the UI):
  1. Plan            → LLM drafts a report outline + 5-6 diverse search queries
  2. Round-1 search  → parallel web search across all queries (SerpAPI/fallbacks)
  3. Read            → fetch + extract readable text from the top sources
  4. Gap analysis    → LLM reads excerpts, finds what's missing, drafts follow-ups
  5. Round-2 search  → fills the gaps with fresh, targeted sources
  6. Read            → fetch the new sources
  7. Synthesise      → one long, structured, [N]-cited report (with auto-continue
                       if the model hits its token ceiling mid-report)
  8. Bibliography    → a numbered "## Sources" section is appended so downloads
                       (PDF/DOCX) are fully self-contained

Event protocol (each yield is a dict — unchanged, the frontend already
understands all of these):
  { "event": "status",  "message": "..." }
  { "event": "query",   "queries": [...] }
  { "event": "sources", "sources": [{title, url, snippet, site, favicon}...] }
  { "thinking": "..." } / { "thinking_done": true }
  { "event": "chunk",   "chunk": "..." }
  { "event": "artifact", "artifactType": "document", "artifactTitle": "..." }
  { "event": "done" }
"""
from __future__ import annotations

import concurrent.futures
import json
import os
import re
import time
from datetime import datetime
from typing import Iterator, Dict, Any, List, Tuple
from urllib.parse import urlparse

import requests

from config import SERPAPI_API_KEY
from services.llm_service import call_groq, call_nvidia


def _envint(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except Exception:
        return default


# ---- Depth knobs (env-tunable so depth can be dialled up without code edits) --
MAX_SOURCES        = _envint("RESEARCH_MAX_SOURCES", 22)     # final cap fed to synthesis
PER_QUERY_RESULTS  = _envint("RESEARCH_PER_QUERY", 6)        # results per search query
MAX_QUERIES_R1     = _envint("RESEARCH_QUERIES_R1", 6)       # round-1 query count
MAX_FOLLOWUPS      = _envint("RESEARCH_FOLLOWUPS", 5)        # round-2 gap-fill queries
PER_DOMAIN_CAP     = _envint("RESEARCH_PER_DOMAIN", 3)       # diversity: max sources / site
FETCH_TIMEOUT      = _envint("RESEARCH_FETCH_TIMEOUT", 7)
MAX_DOC_CHARS      = _envint("RESEARCH_DOC_CHARS", 6000)     # readable text kept per source
SYNTH_MAX_TOKENS   = _envint("RESEARCH_SYNTH_TOKENS", 16000)
MAX_CONTINUATIONS  = _envint("RESEARCH_CONTINUATIONS", 2)    # auto-continue on truncation
DEADLINE_S         = _envint("RESEARCH_DEADLINE_S", 540)     # stay under gunicorn 600s

# Second search pass (gap-fill round) — on by default; can be disabled via env.
SEARCH_ROUNDS_ENABLED = os.getenv("RESEARCH_SECOND_PASS", "1") not in ("0", "false", "False")

# Synthesis runs on GLM (z-ai/glm-5.1) — stronger long-form report writing than
# Nemotron for this task. Routed through call_nvidia (NVIDIA NIM endpoint).
SYNTH_MODEL = os.getenv("RESEARCH_SYNTH_MODEL", "z-ai/glm-5.1")
PLANNER_MODEL = os.getenv("RESEARCH_PLANNER_MODEL", "llama-3.3-70b-versatile")


def _favicon(url: str) -> str:
    try:
        return f"https://www.google.com/s2/favicons?sz=64&domain={urlparse(url).netloc}"
    except Exception:
        return ""


def _extract_json(text: str):
    """Pull the first JSON array/object out of an LLM response."""
    if not isinstance(text, str):
        return None
    m = re.search(r'(\[[\s\S]*\]|\{[\s\S]*\})', text)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except Exception:
        # Best effort: strip trailing commas
        try:
            cleaned = re.sub(r',\s*([\]}])', r'\1', m.group(1))
            return json.loads(cleaned)
        except Exception:
            return None


# =====================================================================
# Planning
# =====================================================================

def _plan_research(question: str) -> Tuple[List[str], List[str]]:
    """Return (initial_queries, outline_sections).

    The planner thinks like a research lead: it decomposes the question into a
    report outline AND a diverse set of search queries that, together, give
    both breadth and depth.
    """
    year = datetime.now().year
    sys = (
        "You are the lead planner for a deep-research report. Decompose the user's "
        "question into a rigorous research plan.\n"
        f"Return RAW JSON (no markdown, no prose) shaped exactly:\n"
        '{ "queries": ["...", "..."], "outline": ["Section title", "..."] }\n'
        f"- queries: {MAX_QUERIES_R1} short, DIVERSE web-search queries covering different "
        "angles — fundamentals/definitions, the latest developments (include the year "
        f"{year} where recency matters), key players/competitors, hard data & statistics / "
        "market size, expert analysis & contrarian views, and risks/criticisms. Add an "
        "India-specific angle when the topic plausibly has one.\n"
        "- outline: 5-8 section titles for a thorough analyst report on this question."
    )
    msgs = [{"role": "system", "content": sys},
            {"role": "user", "content": question.strip()[:800]}]
    try:
        resp = call_groq(msgs, model=PLANNER_MODEL, temperature=0.3,
                         max_tokens=600, stream=False)
        data = _extract_json(resp) if resp else None
        if isinstance(data, dict):
            qs = [str(x).strip() for x in (data.get("queries") or []) if str(x).strip()]
            outline = [str(x).strip() for x in (data.get("outline") or []) if str(x).strip()]
            qs = qs[:MAX_QUERIES_R1]
            if qs:
                return qs, outline[:8]
    except Exception as e:
        print(f"[Research] planning failed: {e}")
    return [question.strip()], []


def _find_gaps(question: str, outline: List[str], sources: List[Dict[str, Any]],
               bodies: List[str]) -> List[str]:
    """After round 1, decide what's still under-covered and draft follow-up
    queries that target those gaps (this is the 'second pass' a human does)."""
    excerpts = []
    for s, b in zip(sources, bodies):
        snip = (b or s.get("snippet", ""))[:600]
        excerpts.append(f"- {s['title']} ({s['site']}): {snip}")
    excerpts_blob = "\n".join(excerpts[:18])
    outline_blob = "; ".join(outline) if outline else "(none)"
    sys = (
        "You are a meticulous research auditor. Given the question, the intended report "
        "outline, and excerpts already gathered, identify what is STILL missing, weak, or "
        "uncorroborated (e.g. missing numbers, only one viewpoint, no recent data, no "
        f"counter-evidence). Output RAW JSON: a list of up to {MAX_FOLLOWUPS} NEW, specific "
        "search queries that would close those gaps. No duplicates of obvious earlier "
        "searches. No prose, JSON array only."
    )
    user = (f"QUESTION: {question}\n\nINTENDED OUTLINE: {outline_blob}\n\n"
            f"ALREADY GATHERED:\n{excerpts_blob}")
    try:
        resp = call_groq([{"role": "system", "content": sys},
                          {"role": "user", "content": user[:6000]}],
                         model=PLANNER_MODEL, temperature=0.4,
                         max_tokens=400, stream=False)
        data = _extract_json(resp) if resp else None
        if isinstance(data, list):
            qs = [str(x).strip() for x in data if str(x).strip()]
            return qs[:MAX_FOLLOWUPS]
    except Exception as e:
        print(f"[Research] gap analysis failed: {e}")
    return []


# =====================================================================
# Search
# =====================================================================

def _serpapi_search(query: str, k: int = PER_QUERY_RESULTS) -> List[Dict[str, Any]]:
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


def _googlesearch_fallback(query: str, k: int = PER_QUERY_RESULTS) -> List[Dict[str, Any]]:
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


def _search_round(queries: List[str]) -> List[Dict[str, Any]]:
    """Run all queries in parallel and flatten results (not yet deduped)."""
    if not queries:
        return []
    searcher = _serpapi_search if SERPAPI_API_KEY else _googlesearch_fallback
    out: List[Dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(2, len(queries))) as ex:
        for res in ex.map(searcher, queries):
            out.extend(res or [])
    if not out:  # last-ditch
        for q in queries:
            out.extend(_wikipedia_fallback(q))
    return out


def _merge_sources(existing: List[Dict[str, Any]], new: List[Dict[str, Any]],
                   cap: int) -> List[Dict[str, Any]]:
    """Dedupe by URL, enforce a per-domain cap for diversity, keep order so
    citation numbering stays stable across rounds."""
    seen_urls = {s["url"] for s in existing}
    domain_counts: Dict[str, int] = {}
    for s in existing:
        domain_counts[s["site"]] = domain_counts.get(s["site"], 0) + 1
    merged = list(existing)
    for it in new:
        u = it.get("url")
        if not u or u in seen_urls:
            continue
        dom = it.get("site") or urlparse(u).netloc
        if domain_counts.get(dom, 0) >= PER_DOMAIN_CAP:
            continue
        seen_urls.add(u)
        domain_counts[dom] = domain_counts.get(dom, 0) + 1
        merged.append(it)
        if len(merged) >= cap:
            break
    return merged


# =====================================================================
# Reading
# =====================================================================

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


def _read_sources(sources: List[Dict[str, Any]]) -> List[str]:
    if not sources:
        return []
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(10, len(sources))) as ex:
        return list(ex.map(_fetch_readable, [s["url"] for s in sources]))


# =====================================================================
# Synthesis prompt
# =====================================================================

def _build_system_prompt(outline: List[str]) -> str:
    outline_hint = ""
    if outline:
        outline_hint = (
            "\nUse this outline as a backbone (adapt/rename/merge as the evidence "
            "demands, drop sections with no support):\n- " + "\n- ".join(outline) + "\n"
        )
    return (
        "You are KAUTILYA DEEP RESEARCH — a senior analyst producing a definitive, "
        "publication-grade report. You have been given a numbered SET OF SOURCES. Write the "
        "kind of report a human would take weeks to assemble: comprehensive, structured, "
        "evidence-dense, and decision-ready.\n\n"
        "NON-NEGOTIABLE RULES:\n"
        "- LANGUAGE: Write the ENTIRE report — title, section headings, and body — in the SAME "
        "language and script as the USER QUESTION. If the user asks in Hindi, write the whole "
        "report in fluent Hindi (Devanagari); same for Tamil, Telugu, Marathi, Bengali, Gujarati, "
        "etc. Keep proper nouns, brand names, technical terms and the [N] citation markers as-is. "
        "Only default to English when the question itself is in English.\n"
        "- Ground EVERY non-trivial claim in the sources with inline citations like [3] or "
        "[3][7]. Use ONLY source numbers that exist. Never invent citations or facts.\n"
        "- Prefer concrete specifics — numbers, dates, names, $/₹ figures, percentages — over "
        "vague generalities. Pull the actual data out of the sources.\n"
        "- When sources disagree, surface the disagreement explicitly and weigh it.\n"
        "- Be honest about gaps: if the evidence is thin on something important, say so.\n"
        "- No filler, no 'Sure, here is', no apologising. Start directly with the title line.\n\n"
        "REQUIRED REPORT STRUCTURE (rich markdown — use ##/### headings, **bold**, bullet "
        "lists, and markdown TABLES wherever comparison or data warrants):\n"
        "# <Sharp, specific report title>\n\n"
        "## Executive Summary\n"
        "4-6 tight sentences giving the bottom line a busy decision-maker needs.\n\n"
        "## Key Findings\n"
        "6-10 bullets, each a substantive finding carrying [N] citations.\n\n"
        f"{outline_hint}"
        "## Deep Analysis\n"
        "Several well-developed subsections (use ### headings) that unpack the topic in depth — "
        "mechanisms, drivers, comparisons, market/competitive landscape, regional nuance. "
        "Include at least one markdown table summarising key data or a comparison.\n\n"
        "## Data & Evidence\n"
        "The hard numbers, organised — a table is ideal — each row/point cited [N].\n\n"
        "## Risks, Caveats & Open Questions\n"
        "What could go wrong, what the evidence can't yet settle, and where reasonable people "
        "disagree.\n\n"
        "## Outlook\n"
        "Where this is heading over the next 1-3 years, with the reasoning behind each call.\n\n"
        "## Recommendations\n"
        "Concrete, prioritised, actionable next steps for the reader.\n\n"
        "Write thoroughly — depth and specificity are the whole point. Do NOT append your own "
        "'Sources' list; that is added automatically."
    )


def _build_context(sources: List[Dict[str, Any]], bodies: List[str]) -> str:
    lines = []
    for i, (s, body) in enumerate(zip(sources, bodies), 1):
        body = (body or s.get("snippet", "")).strip()
        lines.append(
            f"SOURCE [{i}] — {s['title']} ({s['site']})\nURL: {s['url']}\n"
            f"CONTENT: {body[:MAX_DOC_CHARS]}"
        )
    return "\n\n".join(lines)


def _bibliography_md(sources: List[Dict[str, Any]]) -> str:
    out = ["", "", "## Sources", ""]
    for i, s in enumerate(sources, 1):
        title = s.get("title") or s.get("url")
        out.append(f"{i}. {title} — {s['url']}")
    return "\n".join(out)


# =====================================================================
# Orchestration
# =====================================================================

def deep_research_stream(question: str, depth: str = "standard") -> Iterator[Dict[str, Any]]:
    """Stream an analyst-grade, multi-round deep-research report.

    `depth` tunes breadth/effort:
      • quick      — single search pass, fewer sources, shorter report (fast)
      • standard   — full multi-round pipeline (default)
      • exhaustive — widest source net + second pass + longest report
    """
    t0 = time.time()
    def time_left() -> float:
        return DEADLINE_S - (time.time() - t0)

    prof = {
        "quick":      {"max_sources": 8,                     "second": False, "tokens": 7000},
        "standard":   {"max_sources": MAX_SOURCES,           "second": SEARCH_ROUNDS_ENABLED, "tokens": SYNTH_MAX_TOKENS},
        "exhaustive": {"max_sources": max(MAX_SOURCES, 30),  "second": True,  "tokens": SYNTH_MAX_TOKENS},
    }.get((depth or "standard").lower(), None)
    if prof is None:
        prof = {"max_sources": MAX_SOURCES, "second": SEARCH_ROUNDS_ENABLED, "tokens": SYNTH_MAX_TOKENS}
    max_sources = prof["max_sources"]
    second_pass = prof["second"]
    synth_tokens = prof["tokens"]

    # ---- 1. Plan -----------------------------------------------------------
    yield {"event": "status", "message": "🧭 Planning the research — outline & angles…"}
    queries, outline = _plan_research(question)
    yield {"event": "query", "queries": queries}
    if outline:
        yield {"thinking": "Planned report sections: " + " · ".join(outline)}

    # ---- 2. Round-1 search -------------------------------------------------
    yield {"event": "status", "message": f"🔎 Searching the web — {len(queries)} angles in parallel…"}
    raw1 = _search_round(queries)
    sources = _merge_sources([], raw1, cap=max_sources)

    if not sources:
        yield {"event": "chunk", "chunk":
               "I couldn't find relevant sources for this question. Try rephrasing or adding more specifics."}
        yield {"event": "done"}
        return

    yield {"event": "sources", "sources": sources}

    # ---- 3. Read round-1 ---------------------------------------------------
    yield {"event": "status", "message": f"📑 Reading {len(sources)} sources in depth…"}
    bodies = _read_sources(sources)

    # ---- 4 & 5. Gap analysis + round-2 search ------------------------------
    if time_left() > 120 and second_pass:
        yield {"event": "status", "message": "🧩 Auditing coverage & chasing the gaps…"}
        followups = _find_gaps(question, outline, sources, bodies)
        if followups:
            yield {"event": "query", "queries": followups}
            yield {"event": "status", "message": f"🔎 Second pass — {len(followups)} targeted searches…"}
            raw2 = _search_round(followups)
            before = len(sources)
            sources = _merge_sources(sources, raw2, cap=max_sources)
            new_sources = sources[before:]
            if new_sources:
                # Emit the full cumulative list so citation numbering is final
                # and complete, then read only the newly added sources.
                yield {"event": "sources", "sources": sources}
                yield {"event": "status", "message": f"📑 Reading {len(new_sources)} more sources…"}
                bodies = bodies + _read_sources(new_sources)

    # ---- 6. Build context --------------------------------------------------
    # Guard against any length mismatch between sources and bodies.
    if len(bodies) < len(sources):
        bodies = bodies + [""] * (len(sources) - len(bodies))
    context = _build_context(sources, bodies)

    # ---- 7. Synthesis (with auto-continue on truncation) -------------------
    yield {"event": "status", "message": f"🧠 Synthesising the report from {len(sources)} sources…"}

    system = _build_system_prompt(outline)
    user_prompt = (f"USER QUESTION: {question}\n\n"
                   f"Write the full report now, citing the numbered sources below.\n\n"
                   f"SOURCES:\n{context}")
    messages = [{"role": "system", "content": system},
                {"role": "user", "content": user_prompt}]

    full_report: List[str] = []
    streamed_anything = False

    def _run(call_messages, max_tokens):
        """Generator: yields events from one NVIDIA synthesis call and RETURNS
        whether the model was truncated (hit its token ceiling). Consumed with
        `yield from`, which both streams the events and captures the return."""
        nonlocal streamed_anything
        truncated = False
        try:
            gen = call_nvidia(call_messages, model=SYNTH_MODEL, temperature=0.45,
                              stream=True, expose_thinking=True, max_tokens=max_tokens)
        except Exception as e:
            print(f"[Research] NVIDIA synth failed: {e}")
            gen = None
        if not gen:
            return truncated
        try:
            for item in gen:
                if isinstance(item, dict):
                    if item.get("_finish_reason") == "length":
                        truncated = True
                        continue
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
        except Exception as e:
            print(f"[Research] NVIDIA stream error: {e}")
        return truncated

    # Primary synthesis + up to MAX_CONTINUATIONS continuations if the model
    # hits its token ceiling mid-report (so long reports aren't cut off).
    continuation = 0
    cur_messages = messages
    while True:
        truncated = yield from _run(cur_messages, synth_tokens if continuation == 0 else 8000)
        if (truncated and streamed_anything
                and continuation < MAX_CONTINUATIONS
                and time_left() > 60):
            continuation += 1
            partial = "".join(full_report)
            cur_messages = messages + [
                {"role": "assistant", "content": partial[-6000:]},
                {"role": "user", "content":
                 "Continue the report from exactly where you stopped. Do not repeat any "
                 "content already written, do not restart sections, and keep the same "
                 "citation style. If the report is complete, end cleanly."},
            ]
            continue
        break

    # ---- Fallback to Groq if NVIDIA produced nothing -----------------------
    if not streamed_anything:
        try:
            gq_gen = call_groq(messages, stream=True, model=PLANNER_MODEL,
                               temperature=0.4, max_tokens=4096)
            if gq_gen:
                for item in gq_gen:
                    chunk = item.get("chunk", "") if isinstance(item, dict) else item
                    if chunk:
                        full_report.append(chunk)
                        streamed_anything = True
                        yield {"event": "chunk", "chunk": chunk}
        except Exception as e:
            print(f"[Research] Groq fallback failed: {e}")

    if not streamed_anything:
        yield {"event": "chunk", "chunk":
               "I gathered sources but the synthesis step is temporarily unavailable. "
               "Please try again in a moment."}

    # ---- 8. Bibliography (so PDF/DOCX downloads are self-contained) --------
    final = "".join(full_report)
    if streamed_anything and sources:
        biblio = _bibliography_md(sources)
        full_report.append(biblio)
        yield {"event": "chunk", "chunk": biblio}

    if len(final) > 400:
        yield {"event": "artifact",
               "artifactType": "document",
               "artifactTitle": f"Deep Research: {question[:60]}"}

    elapsed = round(time.time() - t0, 1)
    yield {"event": "status",
           "message": f"✓ Done in {elapsed}s · {len(sources)} sources · {len(final):,} chars"}
    yield {"event": "done"}
