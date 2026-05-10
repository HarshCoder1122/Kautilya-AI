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

from services.llm_service import call_groq
from services.agent_loop_service import agent_loop
from system_prompts import (
    PRO_SYSTEM_PROMPT, CODER_SYSTEM_PROMPT_PRO, RESEARCH_SYSTEM_PROMPT,
    AGENT_PERSONALITIES,
)


AGENT_REGISTRY: Dict[str, Dict] = {
    "researcher": {
        "label": "Researcher",
        "emoji": "🔎",
        "model": "pro",
        "prompt": RESEARCH_SYSTEM_PROMPT,
        "description": "Multi-source research with citations.",
    },
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
        "model": "pro",
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
    """Return an agent id. Small fast LLM classifier with regex fallback."""
    # Cheap regex fast-path (keeps latency low for obvious cases)
    q = question.lower()
    if re.search(r'\b(write|fix|debug|refactor|error|exception|stack ?trace|typescript|python|javascript|java|golang|rust|sql|react|vue|django|flask|fastapi|api)\b', q):
        return "coder"
    if re.search(r'\b(research|competitor|market (size|share|trend)|industry|latest|news|report|cite|sources?)\b', q):
        return "researcher"
    if re.search(r'\b(pitch|cold ?email|objection|lead|prospect|sdr|pipeline|crm|follow[- ]?up|discount|negotiate)\b', q):
        return "sales"
    if re.search(r'\b(not working|broken|won\'?t|error message|crash|refund|complain|frustrated|angry|issue|problem)\b', q):
        return "support"
    if re.search(r'\b(analyze deep|philosophy|strategy|complex|logic|reasoning|step by step)\b', q):
        # Allow pro model only for very complex reasoning requests
        return "general" # In registry, general is now daily, but we can add a 'pro' agent

    # LLM classifier fallback
    try:
        msgs = [
            {"role": "system", "content":
             "Classify the user request into exactly ONE of: researcher, coder, sales, support, general. "
             "Output only the label. No explanation."},
            {"role": "user", "content": question[:600]},
        ]
        out = call_groq(msgs, model="llama-3.3-70b-versatile",
                        temperature=0, max_tokens=10, stream=False)
        if isinstance(out, str):
            label = out.strip().lower().split()[0] if out.strip() else ""
            label = re.sub(r'[^a-z]', '', label)
            if label in AGENT_REGISTRY:
                return label
    except Exception as e:
        print(f"[Orchestrator] classify err: {e}")
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
