"""
Kautilya AI — Multi-Agent Orchestrator.

Routes user queries to a specialized sub-agent based on intent.
Sub-agents share context but use different system prompts and, optionally,
different underlying models.

Agents:
  - researcher  : web-search-heavy, citation discipline
  - coder       : frontier code generation (DeepSeek V4)
  - sales       : SDR / pitch / objection handling
  - support     : empathetic technical support
  - general     : fallback — normal Kautilya voice

Public API:
  classify_intent(question) → agent_id
  agent_system_prompt(agent_id) → str
  run(messages, uid, …) → generator (same contract as agent_loop)

Emits an extra event at the start so the UI can show which agent was picked:
  {"event": "agent", "agent": "researcher", "reason": "…"}
"""
from __future__ import annotations

import json
import re
from typing import Dict, Iterator

from services.agent_loop_service import agent_loop
from system_prompts import (
    PRO_SYSTEM_PROMPT, CODER_SYSTEM_PROMPT_PRO, RESEARCH_SYSTEM_PROMPT,
    AGENT_PERSONALITIES,
)


# Routing rule: Daily handles everything. Only code is delegated to Coder.
# Deep Search has its own path (chat_routes when model == 'research') and is
# not invoked from auto-routing — that's an explicit user toggle.
AGENT_REGISTRY: Dict[str, Dict] = {
    "coder": {
        "label": "Coder",
        "emoji": "💻",
        "model": "coder",
        "prompt": CODER_SYSTEM_PROMPT_PRO,
        "description": "Frontier code generation, debugging, architecture.",
    },
    "sales": {
        "label": "Sales",
        "emoji": "📈",
        "model": "daily",
        "prompt": AGENT_PERSONALITIES.get("sdr", PRO_SYSTEM_PROMPT),
        "description": "Pitch creation, objection handling, lead qualification.",
    },
    "support": {
        "label": "Support",
        "emoji": "🛟",
        "model": "daily",
        "prompt": AGENT_PERSONALITIES.get("support", PRO_SYSTEM_PROMPT),
        "description": "Empathetic technical troubleshooting.",
    },
    "general": {
        "label": "General",
        "emoji": "💬",
        "model": "daily",
        "prompt": PRO_SYSTEM_PROMPT,
        "description": "Default Kautilya voice.",
    },
}


def classify_intent(question: str) -> str:
    """Return an agent id. REGEX-ONLY — zero network latency.

    This used to fall back to a synchronous Groq classifier (stream=False, no
    timeout cap) for every query that missed the regex — i.e. almost every
    normal conversational message routed to 'general' AFTER paying a full LLM
    round-trip (~300-800ms, worse on a slow day) BEFORE the real model even
    started. That single blocking call was the biggest avoidable chunk of
    time-to-first-token in auto mode.

    Now routing is a pure regex decision: instant. The pattern is broadened so
    obvious code intent still reaches Coder; anything ambiguous defaults to
    'general' (Daily/Mistral), which is both the faster model AND handles most
    code-adjacent questions fine. Users who want guaranteed Coder can pick the
    Code mode explicitly.
    """
    q = (question or "").lower()
    # Coder: code verbs, languages, frameworks, "build me a …", error/stacktrace.
    if re.search(
        r'\b(write|generate|create|build|make|fix|debug|refactor|optimi[sz]e|implement|'
        r'rewrite|convert|migrate|review)\b[^.?!]*\b(code|app|api|script|function|class|'
        r'component|page|website|program|bug|error|endpoint|query|regex|algorithm|'
        r'snippet|module|backend|frontend|database|schema)\b'
        r'|\b(typescript|javascript|python|golang|rust|kotlin|swift|java|c\+\+|c#|php|ruby|'
        r'react|vue|svelte|angular|next\.?js|node\.?js|django|flask|fastapi|spring|laravel|'
        r'sql|html|css|tailwind|docker|kubernetes|terraform)\b'
        r'|\b(stack ?trace|traceback|compile|syntax error|null ?pointer|segfault|'
        r'undefined is not|cannot read propert)\b',
        q,
    ):
        return "coder"
    if re.search(r'\b(pitch|cold ?email|objection|lead|prospect|sdr|pipeline|crm|follow[- ]?up|discount|negotiate)\b', q):
        return "sales"
    if re.search(r'\b(not working|broken|won\'?t|error message|crash|refund|complain|frustrated|angry)\b', q):
        return "support"
    return "general"


def run(messages, uid=None, user_ip=None, max_thinking: bool = False,
        forced_agent: str | None = None) -> Iterator:
    """
    Drop-in replacement for get_llm_response when model='auto'.
    Yields the same envelope agent_loop does, PLUS an initial
    {"event":"agent", "agent":..., "label":..., "emoji":..., "reason":...} event.
    """
    # Find the last user message
    last_user = ""
    if messages and messages[-1]["role"] == "user":
        c = messages[-1]["content"]
        last_user = c if isinstance(c, str) else " ".join(
            p.get("text", "") for p in c if isinstance(p, dict) and p.get("type") == "text"
        )

    agent_id = forced_agent if (forced_agent in AGENT_REGISTRY) else classify_intent(last_user)
    agent = AGENT_REGISTRY[agent_id]

    # Announce routing decision to the UI
    yield json.dumps({
        "event": "agent",
        "agent": agent_id,
        "label": agent["label"],
        "emoji": agent["emoji"],
        "description": agent["description"],
    })

    # Swap system prompt for this turn only (do not mutate caller's list).
    rewritten = [dict(m) for m in messages]
    if rewritten and rewritten[0].get("role") == "system":
        rewritten[0] = {"role": "system", "content": agent["prompt"]}
    else:
        rewritten = [{"role": "system", "content": agent["prompt"]}, *rewritten]

    yield from agent_loop(
        rewritten, uid=uid, model_choice=agent["model"],
        user_ip=user_ip, max_thinking=max_thinking,
    )
