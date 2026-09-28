import os
import json
import traceback

# Post-call analytics model: Gemini Flash-Lite via Vertex AI. Called with
# thinking OFF so it returns the final JSON fast instead of spending seconds
# on a reasoning trace. A stable GA model is the fallback. Both overridable
# via env.
NIM_ANALYTICS_MODEL = os.environ.get("NIM_ANALYTICS_MODEL", "gemini-3.5-flash-lite")
NIM_ANALYTICS_FALLBACK_MODEL = os.environ.get("NIM_ANALYTICS_FALLBACK_MODEL", "gemini-2.5-flash")


def analyze_call_transcript(transcript: str) -> dict:
    """
    Analyzes a call transcript using Gemini (via Vertex AI).
    Returns a structured dictionary with analytics.
    """
    from services.llm_service import call_vertex_gemini

    if not transcript or len(transcript.strip()) < 10:
        return _fallback_analytics(reason="Transcript too short or empty")

    prompt = f"""
    You are an expert AI call analyst. Analyze the following telephony conversation transcript and extract key structured information.

    TRANSCRIPT:
    {transcript}

    Extract the following information and return ONLY a valid JSON object:
    - "sentiment": the CUSTOMER's attitude, one of exactly "positive", "neutral", or "negative" (lowercase).
        * positive = clearly interested/happy/agreed/thanked/booked.
        * negative = clearly angry/complained/frustrated/firmly refused or abused.
        * neutral = everything else: short calls, polite info-gathering, no clear emotion,
          wrong number, voicemail, or the customer barely spoke.
        When unsure, ALWAYS choose "neutral" — never default to "negative".
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
    for model_name in (NIM_ANALYTICS_MODEL, NIM_ANALYTICS_FALLBACK_MODEL):
        try:
            print(f"[NIM] Analyzing transcript via Vertex ({model_name})")
            result_text = call_vertex_gemini(
                [{"role": "user", "content": prompt}],
                model=model_name, stream=False,
                temperature=0.2, top_p=0.7, max_tokens=1024,
                max_thinking=False, expose_thinking=False,
                json_mode=True,
            )
            if not result_text:
                raise RuntimeError("empty response")
            return _normalize(json.loads(result_text))
        except Exception as e:
            last_err = e
            print(f"[NIM Error] {model_name} analytics failed: {e} — trying next model")
    print("[NIM Error] All analytics attempts failed.")
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
