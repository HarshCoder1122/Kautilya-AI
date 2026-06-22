import os
import json
import uuid
import datetime
from openai import OpenAI
from config import KAUTILYA_API_KEY, NVIDIA_API_KEY, NVIDIA_API_KEYS
import traceback

# Post-call analytics model: NVIDIA NIM GLM 5.1 (Kautilya Pro). We call it with
# thinking OFF (see extra_body below) so it returns the final JSON fast instead
# of spending seconds on a reasoning trace. Groq llama-3.3-70b is the fast
# fallback. Both overridable via env.
NIM_ANALYTICS_MODEL = os.environ.get("NIM_ANALYTICS_MODEL", "z-ai/glm-5.1")
GROQ_ANALYTICS_MODEL = os.environ.get("GROQ_ANALYTICS_MODEL", "llama-3.3-70b-versatile")


def _nvidia_client():
    api_key = NVIDIA_API_KEYS[0] if NVIDIA_API_KEYS else NVIDIA_API_KEY
    if not api_key:
        return None
    return OpenAI(base_url="https://integrate.api.nvidia.com/v1", api_key=api_key)


def _groq_client():
    groq_key = os.environ.get("GROQ_API_KEY")
    if not groq_key:
        return None
    return OpenAI(base_url="https://api.groq.com/openai/v1", api_key=groq_key)


def _analytics_providers():
    """Ordered (label, client, model) list to try. NVIDIA first, Groq as a
    real fallback — not just when the NVIDIA key is missing, but whenever the
    NVIDIA call itself fails (404 on a retired model, 5xx, timeout, etc.)."""
    providers = []
    nv = _nvidia_client()
    if nv:
        providers.append(("NVIDIA", nv, NIM_ANALYTICS_MODEL))
    gq = _groq_client()
    if gq:
        providers.append(("Groq", gq, GROQ_ANALYTICS_MODEL))
    return providers

def analyze_call_transcript(transcript: str) -> dict:
    """
    Analyzes a call transcript using Nvidia NIM (Nemotron-120B or similar).
    Returns a structured dictionary with analytics.
    """
    providers = _analytics_providers()
    if not providers:
        return _fallback_analytics(reason="No API keys (NIM/Groq) configured")

    if not transcript or len(transcript.strip()) < 10:
        return _fallback_analytics(reason="Transcript too short or empty")

    prompt = f"""
    You are an expert AI call analyst. Analyze the following telephony conversation transcript and extract key structured information.

    TRANSCRIPT:
    {transcript}

    Extract the following information and return ONLY a valid JSON object:
    - "sentiment": one of exactly "positive", "neutral", or "negative" (lowercase).
    - "intent": The primary reason the user was calling or what they wanted to achieve.
    - "outcome": The final resolution of the call (e.g., "Resolved", "Follow-up required", "Hung up early").
    - "summary": A brief 1-2 sentence summary of the conversation.
    - "lead_status": Based on the call, one of "hot", "warm", "cold", or "not_a_lead".
    - "topics": array of up to 5 short topic strings discussed.
    - "lead": an object with the contact details the caller revealed:
        {{"name": "...", "email": "...", "company": "...", "phone": "...", "score": 0-10}}
      Use "" for anything not mentioned. Never invent values. Phone/email must be
      taken verbatim from what the caller said (do not guess digits).

    Return EXACTLY valid JSON and nothing else.
    """

    last_err = None
    for label, client, model_name in providers:
        try:
            print(f"[NIM] Analyzing transcript via {label} ({model_name})")
            create_kwargs = dict(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                top_p=0.7,
                max_tokens=1024,
                response_format={"type": "json_object"},
            )
            # GLM (z-ai/glm-*) on NVIDIA NIM: turn thinking OFF so we get the
            # final JSON immediately instead of a slow reasoning trace.
            if model_name.startswith("z-ai/glm"):
                create_kwargs["extra_body"] = {
                    "chat_template_kwargs": {"enable_thinking": False, "clear_thinking": False}
                }
            response = client.chat.completions.create(**create_kwargs)
            result_text = response.choices[0].message.content
            return _normalize(json.loads(result_text))
        except Exception as e:
            last_err = e
            print(f"[NIM Error] {label} analytics failed: {e} — trying next provider")
    print("[NIM Error] All analytics providers failed.")
    traceback.print_exc()
    return _fallback_analytics(reason=str(last_err) if last_err else "Analysis failed")


def _normalize(data: dict) -> dict:
    """Coerce the model's output into the shape the dashboard + lead pipeline
    expect: lowercase 3-class sentiment, a guaranteed `lead` object, and a
    list `topics`."""
    if not isinstance(data, dict):
        return _fallback_analytics()
    s = str(data.get("sentiment") or "neutral").strip().lower()
    if s in ("frustrated", "angry", "negative"):
        s = "negative"
    elif s in ("positive", "happy", "satisfied"):
        s = "positive"
    elif s not in ("positive", "neutral", "negative"):
        s = "neutral"
    data["sentiment"] = s
    lead = data.get("lead")
    if not isinstance(lead, dict):
        lead = {}
    data["lead"] = {
        "name": str(lead.get("name") or "")[:120],
        "email": str(lead.get("email") or "")[:200],
        "company": str(lead.get("company") or "")[:160],
        "phone": str(lead.get("phone") or "")[:40],
        "score": int(lead.get("score") or 0) if str(lead.get("score") or "0").isdigit() else 0,
    }
    if not isinstance(data.get("topics"), list):
        data["topics"] = []
    data["topics"] = [str(t)[:60] for t in data["topics"][:5]]
    return data


def _fallback_analytics(reason="Analysis failed") -> dict:
    return {
        "sentiment": "neutral",
        "intent": "Unknown",
        "outcome": reason,
        "summary": "Analytics could not be generated for this call.",
        "lead_status": "Unknown",
        "topics": [],
        "lead": {"name": "", "email": "", "company": "", "phone": "", "score": 0},
    }
