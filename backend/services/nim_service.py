import os
import json
import uuid
import datetime
from openai import OpenAI
from config import KAUTILYA_API_KEY # or other config if needed
import traceback

# You can use the standard OpenAI library to interact with NVIDIA NIM
def get_nim_client():
    # Primary: NVIDIA NIM
    api_key = os.environ.get("NVIDIA_API_KEY")
    if api_key:
        print("[NIM] Using NVIDIA NIM for analytics.")
        return OpenAI(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=api_key
        ), "meta/llama-3.1-405b-instruct"
    
    # Fallback: Groq (OpenAI Compatible)
    groq_key = os.environ.get("GROQ_API_KEY")
    if groq_key:
        print("[NIM] Warning: NVIDIA_API_KEY missing. Falling back to Groq.")
        return OpenAI(
            base_url="https://api.groq.com/openai/v1",
            api_key=groq_key
        ), "llama-3.3-70b-versatile"
        
    print("[NIM] Error: Neither NVIDIA_NIM_API_KEY nor GROQ_API_KEY is set.")
    return None, None

def analyze_call_transcript(transcript: str) -> dict:
    """
    Analyzes a call transcript using Nvidia NIM (Nemotron-120B or similar).
    Returns a structured dictionary with analytics.
    """
    client, model_name = get_nim_client()
    if not client:
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

    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            top_p=0.7,
            max_tokens=1024,
            response_format={"type": "json_object"}
        )
        
        result_text = response.choices[0].message.content
        analytics = json.loads(result_text)
        return analytics
    except Exception as e:
        print(f"[NIM Error] Failed to analyze transcript: {e}")
        traceback.print_exc()
        return _fallback_analytics(reason=str(e))

def _fallback_analytics(reason="Analysis failed") -> dict:
    return {
        "sentiment": "Unknown",
        "intent": "Unknown",
        "outcome": reason,
        "summary": "Analytics could not be generated for this call.",
        "lead_status": "Unknown"
    }
