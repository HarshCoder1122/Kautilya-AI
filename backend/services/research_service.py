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

from config import SERPAPI_API_KEY, TAVILY_API_KEY
from services.llm_service import call_vertex_gemini, model_circuit_open, build_capacity_event


def _envint(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except Exception:
        return default


# ---- Depth knobs (env-tunable so depth can be dialled up without code edits) --
# Input-token budget is the binding constraint: NVIDIA/Groq throttle per-minute
# tokens (TPM), and ONE synthesis request packs sources×chars. At 22×6000 that's
# ~33k input tokens — which alone busts low free-tier TPM limits (Groq returned
# HTTP 413 "Request too large, TPM limit 12000"). So sources×chars is kept small
# by default; dial up via env only on an account with headroom.
MAX_SOURCES        = _envint("RESEARCH_MAX_SOURCES", 12)     # final cap fed to synthesis
PER_QUERY_RESULTS  = _envint("RESEARCH_PER_QUERY", 6)        # results per search query
MAX_QUERIES_R1     = _envint("RESEARCH_QUERIES_R1", 6)       # round-1 query count
MAX_FOLLOWUPS      = _envint("RESEARCH_FOLLOWUPS", 5)        # round-2 gap-fill queries
PER_DOMAIN_CAP     = _envint("RESEARCH_PER_DOMAIN", 3)       # diversity: max sources / site
FETCH_TIMEOUT      = _envint("RESEARCH_FETCH_TIMEOUT", 7)
MAX_DOC_CHARS      = _envint("RESEARCH_DOC_CHARS", 3000)     # readable text kept per source
SYNTH_MAX_TOKENS   = _envint("RESEARCH_SYNTH_TOKENS", 12000)
MAX_CONTINUATIONS  = _envint("RESEARCH_CONTINUATIONS", 2)    # auto-continue on truncation
DEADLINE_S         = _envint("RESEARCH_DEADLINE_S", 540)     # stay under gunicorn 600s
# When Pro/GLM is busy (429) it returns nothing — retry it a few times before
# dropping to the weaker Groq fallback, since GLM writes the best long report.
SYNTH_RETRIES      = _envint("RESEARCH_SYNTH_RETRIES", 2)    # extra GLM attempts on empty
SYNTH_RETRY_BACKOFF = float(os.getenv("RESEARCH_SYNTH_RETRY_BACKOFF", "2.0"))  # sec, ×attempt

# Second search pass (gap-fill round) — on by default; can be disabled via env.
SEARCH_ROUNDS_ENABLED = os.getenv("RESEARCH_SECOND_PASS", "1") not in ("0", "false", "False")

# Synthesis runs on the same model the Pro chat tier uses (Gemini 3.1 Pro
# Preview as of this writing) — strong long-form report writing, routed
# through call_vertex_gemini (Google Vertex AI). Default is pulled from
# agent_loop_service._MODEL_LABELS (the single source of truth for tier ->
# model id) instead of a hardcoded copy, so a model swap there doesn't
# silently leave research on a retired model. RESEARCH_SYNTH_MODEL env var
# still overrides if you want research on a different model than Pro chat.
from services.agent_loop_service import _MODEL_LABELS as _KAUTILYA_TIER_MODELS, FAST_MODEL as _KAUTILYA_FAST_MODEL
SYNTH_MODEL = os.getenv("RESEARCH_SYNTH_MODEL", _KAUTILYA_TIER_MODELS['pro'][1])
# When the primary Pro model is saturated, synthesis falls back to the Daily
# tier's Gemini model — still a strong long-form writer; far better than
# dropping straight to the fast/lite fallback. Default tracks the Daily
# tier's model; override/disable via env.
SYNTH_FALLBACK_MODEL = os.getenv("RESEARCH_SYNTH_FALLBACK_MODEL", _KAUTILYA_TIER_MODELS['daily'][1])
PLANNER_MODEL = os.getenv("RESEARCH_PLANNER_MODEL", _KAUTILYA_FAST_MODEL)


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

def _plan_research(question: str, mode: str = "research") -> Tuple[List[str], List[str]]:
    """Return (initial_queries, outline_sections).

    The planner thinks like a research lead: it decomposes the question into a
    report outline AND a diverse set of search queries that, together, give
    both breadth and depth.

    `mode="prd"` swaps the angle guidance from market-analyst angles (stats,
    competitors, expert opinion) to product-thinking angles (user pain
    points, competing products' actual features, technical/platform
    constraints) — the search/read/gap-fill machinery below is unchanged.
    """
    year = datetime.now().year
    if mode == "prd":
        sys = (
            "You are the lead planner for a Product Requirements Document (PRD). Decompose the "
            "user's feature/product idea into a rigorous research plan that will inform the PRD.\n"
            f"Return RAW JSON (no markdown, no prose) shaped exactly:\n"
            '{ "queries": ["...", "..."], "outline": ["Section title", "..."] }\n'
            f"- queries: {MAX_QUERIES_R1} short, DIVERSE web-search queries covering different "
            "angles a product manager actually needs — the user pain point / job-to-be-done this "
            f"addresses, how existing/competing products solve it today (name real ones, {year} "
            "state), technical or platform constraints and prior art, typical success metrics for "
            "this category, and known failure modes / user complaints with similar features.\n"
            "- outline: 5-8 section titles for a PRD covering this feature (e.g. problem, users, "
            "requirements, success metrics, risks) — these are a starting hint, not final."
        )
    else:
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
        resp = call_vertex_gemini(msgs, model=PLANNER_MODEL, temperature=0.3,
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
        resp = call_vertex_gemini([{"role": "system", "content": sys},
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


def _tavily_search(query: str, k: int = PER_QUERY_RESULTS) -> List[Dict[str, Any]]:
    """Second, independent search provider — queried IN PARALLEL with SerpAPI
    (not a fallback-on-failure like _googlesearch_fallback/_wikipedia_fallback
    below) and merged for better recall. No-ops without TAVILY_API_KEY."""
    if not TAVILY_API_KEY:
        return []
    try:
        resp = requests.post(
            "https://api.tavily.com/search",
            json={"api_key": TAVILY_API_KEY, "query": query, "max_results": k,
                  "search_depth": "basic"},
            timeout=FETCH_TIMEOUT,
        )
        if resp.status_code != 200:
            print(f"[Research] tavily HTTP {resp.status_code}: {resp.text[:200]}")
            return []
        data = resp.json()
        results = []
        for r in (data.get("results") or [])[:k]:
            url = r.get("url")
            if not url:
                continue
            results.append({
                "title": r.get("title") or url,
                "url": url,
                "snippet": r.get("content", "")[:500],
                "site": urlparse(url).netloc,
                "favicon": _favicon(url),
            })
        return results
    except Exception as e:
        print(f"[Research] tavily err: {e}")
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
    """Run all queries in parallel and flatten results (not yet deduped).

    When both SERPAPI_API_KEY and TAVILY_API_KEY are set, BOTH providers are
    queried for every query (not one-as-fallback-for-the-other) and their
    results are pooled here — _merge_sources() downstream dedupes by URL and
    caps per-domain, so this is pure recall/quality upside. With only one key
    (or neither), behavior is unchanged from before: single provider, then
    the scraper/Wikipedia last-ditch fallbacks."""
    if not queries:
        return []
    primary = _serpapi_search if SERPAPI_API_KEY else _googlesearch_fallback
    jobs = [(primary, q) for q in queries]
    if TAVILY_API_KEY:
        jobs += [(_tavily_search, q) for q in queries]
    out: List[Dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(2, len(jobs))) as ex:
        futures = [ex.submit(fn, q) for fn, q in jobs]
        for fut in futures:
            try:
                out.extend(fut.result() or [])
            except Exception as e:
                print(f"[Research] search job failed: {e}")
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


def _gather_sources(queries: List[str], cap: int = MAX_SOURCES) -> List[Dict[str, Any]]:
    """Search all queries and return a deduped, domain-diverse source list.

    Back-compat shim for callers (e.g. the chat web_search tool in
    agent_loop_service) that used the pre-multi-round API. Built on the newer
    `_search_round` + `_merge_sources` helpers."""
    return _merge_sources([], _search_round(queries), cap=cap)


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

def _build_system_prompt(outline: List[str], mode: str = "research") -> str:
    outline_hint = ""
    if outline:
        outline_hint = (
            "\nUse this outline as a backbone (adapt/rename/merge as the evidence "
            "demands, drop sections with no support):\n- " + "\n- ".join(outline) + "\n"
        )
    if mode == "prd":
        return (
            "You are KAUTILYA, acting as a senior product manager writing a Product Requirements "
            "Document (PRD). You have been given a numbered SET OF SOURCES (competitor research, "
            "user pain points, prior art). Write a PRD grounded in that research, not a generic "
            "template filled with guesses.\n\n"
            "NON-NEGOTIABLE RULES:\n"
            "- LANGUAGE: Write the ENTIRE PRD in the SAME language and script as the USER "
            "REQUEST. Keep proper nouns, brand names, and the [N] citation markers as-is.\n"
            "- Ground competitive claims and user-pain-point claims in the sources with inline "
            "citations like [3] or [3][7]. Use ONLY source numbers that exist — never invent one.\n"
            "- Requirements must be SPECIFIC and TESTABLE (\"the system SHALL...\"), not vague "
            "aspirations. Prefer concrete numbers (latency targets, error budgets) over 'fast' / "
            "'reliable'.\n"
            "- Be honest about what the research does NOT tell you — call those out as open "
            "questions rather than inventing an answer.\n"
            "- No filler, no 'Sure, here is', no apologising. Start directly with the title line.\n\n"
            "REQUIRED PRD STRUCTURE (rich markdown — use ##/### headings, **bold**, bullet lists, "
            "and markdown TABLES for requirements/comparisons):\n"
            "# <Product/Feature name> — PRD\n\n"
            "## Problem Statement\n"
            "What user pain point or job-to-be-done this addresses, grounded in the research "
            "[N]. Why now.\n\n"
            "## Goals & Non-Goals\n"
            "Bullet list of what this explicitly does and does NOT try to solve.\n\n"
            "## Target Users & Personas\n"
            "Who this is for, with the evidence [N] behind that segmentation.\n\n"
            f"{outline_hint}"
            "## User Stories\n"
            "5-10 \"As a [user], I want [goal], so that [benefit]\" stories covering the core "
            "flows.\n\n"
            "## Functional Requirements\n"
            "A numbered, testable list (or table) of what the system SHALL do. Group by feature "
            "area.\n\n"
            "## Non-Functional Requirements\n"
            "Performance, security, accessibility, compliance — concrete targets, not adjectives.\n\n"
            "## Success Metrics\n"
            "How you'll know this worked — specific, measurable, tied to the problem statement.\n\n"
            "## Risks & Mitigations\n"
            "What could go wrong (technical, market, adoption) [N] and the plan for each.\n\n"
            "## Rollout Plan\n"
            "Phasing — MVP vs. later phases, any gating/experimentation approach.\n\n"
            "## Open Questions\n"
            "What the research didn't settle and who needs to decide it.\n\n"
            "Write thoroughly and concretely — vague requirements are worse than none. Do NOT "
            "append your own 'Sources' list; that is added automatically."
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

def deep_research_stream(question: str, depth: str = "standard",
                         is_pro: bool = False, mode: str = "research") -> Iterator[Dict[str, Any]]:
    """Stream an analyst-grade, multi-round deep-research report.

    `depth` tunes breadth/effort:
      • quick      — single search pass, fewer sources, shorter report (fast)
      • standard   — full multi-round pipeline (default)
      • exhaustive — widest source net + second pass + longest report

    `mode` tunes WHAT gets written, not how much research happens:
      • research (default) — the analyst-report skeleton (Key Findings, Deep
        Analysis, Outlook, Recommendations…)
      • prd — a Product Requirements Document skeleton (Problem Statement,
        User Stories, Functional/Non-Functional Requirements, Success
        Metrics…), with the planner's search angles biased toward product
        research (competing features, user pain points) instead of market
        analysis. Search/read/gap-fill/synthesis/continuation/bibliography
        are identical in both modes — only `_plan_research` and
        `_build_system_prompt` branch on it.

    `is_pro` routes the GLM synthesis onto the reserved PRO NVIDIA lane and, on
    total failure, decides whether the user sees the PRO upsell.
    """
    mode = "prd" if str(mode or "research").lower() == "prd" else "research"
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
    queries, outline = _plan_research(question, mode=mode)
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

    system = _build_system_prompt(outline, mode=mode)
    user_prompt = (f"USER QUESTION: {question}\n\n"
                   f"Write the full report now, citing the numbered sources below.\n\n"
                   f"SOURCES:\n{context}")
    messages = [{"role": "system", "content": system},
                {"role": "user", "content": user_prompt}]

    full_report: List[str] = []
    streamed_anything = False

    def _run(call_messages, max_tokens, model=SYNTH_MODEL):
        """Generator: yields events from one Vertex Gemini synthesis call and
        RETURNS whether the model was truncated (hit its token ceiling).
        Consumed with `yield from`, which both streams the events and
        captures the return."""
        nonlocal streamed_anything
        truncated = False
        try:
            # max_thinking stays OFF: thinking tokens count against the same
            # max_tokens ceiling as the report itself for Gemini, and this
            # budget (SYNTH_MAX_TOKENS) is tuned for a long report body — a
            # 8k-token thinking pass would eat most of it and shrink the
            # visible report.
            gen = call_vertex_gemini(call_messages, model=model, temperature=0.45,
                                     stream=True, expose_thinking=True, max_tokens=max_tokens,
                                     max_thinking=False, is_pro=is_pro)
        except Exception as e:
            print(f"[Research] Vertex synth failed ({model}): {e}")
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
            print(f"[Research] Vertex stream error: {e}")
        return truncated

    def _synthesize(model, allow_empty_retry):
        """Run ONE model's synthesis with auto-continue on truncation. GLM also
        gets a couple of empty-result retries (transient 429 while Pro is busy);
        the Nemotron fallback just falls through if it yields nothing. Streams via
        `yield`; updates full_report / streamed_anything through _run."""
        continuation = 0
        synth_attempt = 0
        cur_messages = messages
        while True:
            truncated = yield from _run(cur_messages,
                                        synth_tokens if continuation == 0 else 8000,
                                        model=model)
            # Empty on the FIRST pass → model busy (429) or briefly cooling.
            # Retry a couple of times with a short backoff before moving on.
            # Skip if its circuit is hard-open (call_vertex_gemini would no-op for
            # ~45s) or we're low on deadline budget.
            if (allow_empty_retry
                    and not streamed_anything
                    and continuation == 0
                    and synth_attempt < SYNTH_RETRIES
                    and time_left() > 30
                    and not model_circuit_open(model)):
                synth_attempt += 1
                backoff = min(SYNTH_RETRY_BACKOFF * synth_attempt, max(0.0, time_left() - 20))
                print(f"[Research] {model} synth empty (busy?) — retry "
                      f"{synth_attempt}/{SYNTH_RETRIES} after {backoff:.1f}s")
                yield {"thinking": f"Pro model busy — retrying synthesis ({synth_attempt}/{SYNTH_RETRIES})…"}
                if backoff > 0:
                    time.sleep(backoff)
                continue
            # Truncated mid-report → continue from exactly where it stopped so
            # long reports aren't cut off.
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

    # Primary synthesis on Gemini Pro — the strongest long-form report writer.
    yield from _synthesize(SYNTH_MODEL, allow_empty_retry=True)

    # ---- Pro dead → fall back to the Daily-tier Gemini model --------------
    # Different model = a different rate-limit bucket, so it's usually free
    # even while the Pro model is briefly saturated — keeps the report on a
    # strong model instead of dropping straight to the fast/lite fallback.
    if not streamed_anything and time_left() > 30:
        yield {"event": "status",
               "message": "🔁 Pro model busy — switching to the Daily model to finish the report…"}
        yield from _synthesize(SYNTH_FALLBACK_MODEL, allow_empty_retry=False)

    # ---- Last-ditch fast-tier fallback if both above produced nothing -----
    # Builds a COMPACT context — fewer sources, shorter excerpts — on the
    # lightest model so a request still lands and yields a cited report
    # instead of nothing, even if both stronger models are unavailable.
    if not streamed_anything:
        gq_sources = sources[:8]
        gq_context = "\n\n".join(
            f"SOURCE [{i}] — {s['title']} ({s['site']})\nURL: {s['url']}\n"
            f"CONTENT: {(b or s.get('snippet', ''))[:1200]}"
            for i, (s, b) in enumerate(zip(gq_sources, bodies[:8]), 1)
        )
        gq_messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": (f"USER QUESTION: {question}\n\n"
                "Write the full report now, citing the numbered sources below.\n\n"
                f"SOURCES:\n{gq_context}")},
        ]
        try:
            gq_gen = call_vertex_gemini(gq_messages, stream=True, model=PLANNER_MODEL,
                                        temperature=0.4, max_tokens=3072)
            if gq_gen:
                for item in gq_gen:
                    chunk = item.get("chunk", "") if isinstance(item, dict) else item
                    if chunk:
                        full_report.append(chunk)
                        streamed_anything = True
                        yield {"event": "chunk", "chunk": chunk}
        except Exception as e:
            print(f"[Research] Fast-tier fallback failed: {e}")

    if not streamed_anything:
        # All three model attempts gave nothing → genuinely at capacity. Show
        # the PRO upsell card (free) or a soft retry (PRO).
        yield build_capacity_event(is_pro)

    # ---- 8. Bibliography (so PDF/DOCX downloads are self-contained) --------
    final = "".join(full_report)
    if streamed_anything and sources:
        biblio = _bibliography_md(sources)
        full_report.append(biblio)
        yield {"event": "chunk", "chunk": biblio}

    if len(final) > 400:
        title_prefix = "PRD" if mode == "prd" else "Deep Research"
        yield {"event": "artifact",
               "artifactType": "document",
               "artifactTitle": f"{title_prefix}: {question[:60]}"}

    elapsed = round(time.time() - t0, 1)
    yield {"event": "status",
           "message": f"✓ Done in {elapsed}s · {len(sources)} sources · {len(final):,} chars"}
    yield {"event": "done"}
