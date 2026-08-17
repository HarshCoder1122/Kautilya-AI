"""
Kautilya AI — Truth Lens: cross-model answer verification.

After the main model finishes a pure-knowledge answer (no tool grounding),
a DIFFERENT model family (Groq Llama — independent of the NVIDIA-served
Mistral/GLM/Kimi that wrote the answer) adversarially cross-examines it.
The verdict streams to the UI as a `truth_lens` event and renders as a
verification badge on the message — per-answer cross-model consensus as a
first-class UI element.

Design constraints:
  • Zero impact on answer latency: runs AFTER the full answer has streamed.
  • Fail-silent: any error/timeout → no event, the chat works exactly as
    before. Truth Lens can only add information, never break a reply.
  • Cheap: one non-stream Groq call, temperature 0, ~220 max tokens.

Toggle with TRUTH_LENS=0.
"""
import os
import json
import re

TRUTH_LENS_ENABLED = os.environ.get("TRUTH_LENS", "1").strip().lower() in ("1", "true", "yes", "on")

# Answers shorter than this are greetings/acks — nothing to verify.
_MIN_ANSWER_CHARS = 250
# Cap what we send to the verifier so the check stays fast and cheap.
_MAX_QUESTION_CHARS = 800
_MAX_ANSWER_CHARS = 3500

_VERIFIER_PROMPT = """You are an adversarial fact-checker. Another AI answered a user's question. \
Your ONLY job is to catch factual errors — wrong dates, wrong names, wrong numbers, \
fabricated entities, impossible claims, outdated facts stated as current.

Rules:
- Judge ONLY objective factual claims. Opinions, advice, style and code design are NOT errors.
- Be conservative: flag a claim only when you are confident it is wrong or unverifiable.
- 0-3 flags maximum, each under 15 words.
- Output ONLY this JSON, nothing else:
{"verdict":"verified"|"caution","confidence":<0-100 integer>,"flags":["...", "..."]}

verdict=verified → no confident factual errors found (flags must be []).
verdict=caution  → at least one claim is likely wrong or unverifiable (list them in flags)."""


def should_verify(model_choice, answer_text, turn):
    """Gate: verify only substantive, first-turn, pure-knowledge answers.
    Tool-grounded turns (turn > 0) are already backed by observations, and
    coder/research have their own grounding (files / citations)."""
    if not TRUTH_LENS_ENABLED:
        return False
    if model_choice in ("coder", "research"):
        return False
    if turn != 0:
        return False
    if not answer_text or len(answer_text) < _MIN_ANSWER_CHARS:
        return False
    # Tool tags mean this turn isn't final prose — the loop handles it.
    if "[INTEGRATION:" in answer_text or re.search(r"\[(SEARCH|CALCULATE|RUN_PYTHON|MAP_SEARCH|ROUTE_PLAN|CALENDAR_|GMAIL_|WHATSAPP_|SLACK_|HUBSPOT_|GST_INVOICE|FILE_WRITE|FILE_READ|FILE_LIST)", answer_text):
        return False
    return True


def verify(question, answer):
    """Cross-examine `answer` with an independent model.
    Returns a `truth_lens` event dict, or None (fail-silent)."""
    try:
        from services.llm_service import call_groq
        result = call_groq(
            [
                {"role": "system", "content": _VERIFIER_PROMPT},
                {"role": "user", "content": (
                    f"QUESTION:\n{(question or '')[:_MAX_QUESTION_CHARS]}\n\n"
                    f"AI ANSWER TO CHECK:\n{(answer or '')[:_MAX_ANSWER_CHARS]}"
                )},
            ],
            temperature=0.0,
            max_tokens=220,
            stream=False,
        )
        if not result or not isinstance(result, str):
            return None
        m = re.search(r"\{[\s\S]*\}", result)
        if not m:
            return None
        data = json.loads(m.group(0))
        verdict = str(data.get("verdict", "")).strip().lower()
        if verdict not in ("verified", "caution"):
            return None
        flags = [str(f)[:120] for f in (data.get("flags") or []) if f][:3]
        if verdict == "verified":
            flags = []
        try:
            confidence = max(0, min(100, int(data.get("confidence", 0))))
        except (TypeError, ValueError):
            confidence = 0
        return {
            "event": "truth_lens",
            "verdict": verdict,
            "confidence": confidence,
            "flags": flags,
        }
    except Exception as e:
        print(f"[TruthLens] verification failed (silent): {e}")
        return None
