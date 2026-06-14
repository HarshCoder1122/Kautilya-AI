import os
import json
import uuid
import datetime
from openai import OpenAI
from config import KAUTILYA_API_KEY, NVIDIA_API_KEY, NVIDIA_API_KEYS
import traceback

# Post-call analytics model. The old default (meta/llama-3.1-405b-instruct)
# was retired from NVIDIA's catalog and started returning "404 page not found",
# silently killing every call's sentiment/summary. Default to the same Mistral
# model the live chat path uses (known-good on NVIDIA NIM); override via env.
NIM_ANALYTICS_MODEL = os.environ.get("NIM_ANALYTICS_MODEL", "mistralai/mistral-medium-3.5-128b")
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
    - "sentiment": A string representing the overall sentiment of the user (e.g., "Positive", "Neutral", "Negative", "Frustrated").
    - "intent": The primary reason the user was calling or what they wanted to achieve.
    - "outcome": The final resolution of the call (e.g., "Resolved", "Follow-up required", "Hung up early").
    - "summary": A brief 1-2 sentence summary of the conversation.
    - "lead_status": Based on the call, is this a "Hot Lead", "Warm Lead", or "Not a Lead"?

    Return EXACTLY valid JSON and nothing else.
    """

    last_err = None
    for label, client, model_name in providers:
        try:
            print(f"[NIM] Analyzing transcript via {label} ({model_name})")
            response = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                top_p=0.7,
                max_tokens=1024,
                response_format={"type": "json_object"}
            )
            result_text = response.choices[0].message.content
            return json.loads(result_text)
        except Exception as e:
            last_err = e
            print(f"[NIM Error] {label} analytics failed: {e} — trying next provider")
    print("[NIM Error] All analytics providers failed.")
    traceback.print_exc()
    return _fallback_analytics(reason=str(last_err) if last_err else "Analysis failed")

def _fallback_analytics(reason="Analysis failed") -> dict:
    return {
        "sentiment": "Unknown",
        "intent": "Unknown",
        "outcome": reason,
        "summary": "Analytics could not be generated for this call.",
        "lead_status": "Unknown"
    }
