"""
Kautilya AI — TTS Service
Text-to-speech utilities: text cleaning, voice detection.
"""
import re
from config import EDGE_TTS_VOICES


def clean_text_for_tts(text):
    """Remove markdown, emojis, URLs, code blocks for clean TTS output."""
    if not text:
        return ""
    # Remove code blocks
    text = re.sub(r'```[\s\S]*?```', ' [code block omitted] ', text)
    text = re.sub(r'`[^`]+`', '', text)
    # Remove markdown headers
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    # Remove markdown bold/italic
    text = re.sub(r'\*{1,3}([^*]+)\*{1,3}', r'\1', text)
    text = re.sub(r'_{1,3}([^_]+)_{1,3}', r'\1', text)
    # Remove markdown links
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    # Remove URLs
    text = re.sub(r'https?://\S+', '', text)
    # Remove emojis (common Unicode ranges)
    text = re.sub(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF'
                  r'\U0001F1E0-\U0001F1FF\U00002702-\U000027B0\U0001F900-\U0001F9FF'
                  r'\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF\U00002600-\U000026FF'
                  r'\U0000FE00-\U0000FE0F\U0000200D]+', '', text)
    # Remove special chars but keep punctuation
    text = re.sub(r'[|•·►▸▶→←↑↓★☆♦♥♣♠]', '', text)
    # Collapse whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def detect_tts_voice(text):
    """Detect language from text Unicode ranges and return appropriate Edge-TTS voice."""
    if not text:
        return EDGE_TTS_VOICES.get('en', 'en-IN-PrabhatNeural')

    # Count characters in different script ranges
    devanagari = sum(1 for c in text if '\u0900' <= c <= '\u097F')
    bengali = sum(1 for c in text if '\u0980' <= c <= '\u09FF')
    tamil = sum(1 for c in text if '\u0B80' <= c <= '\u0BFF')
    telugu = sum(1 for c in text if '\u0C00' <= c <= '\u0C7F')
    gujarati = sum(1 for c in text if '\u0A80' <= c <= '\u0AFF')
    kannada = sum(1 for c in text if '\u0C80' <= c <= '\u0CFF')
    malayalam = sum(1 for c in text if '\u0D00' <= c <= '\u0D7F')
    gurmukhi = sum(1 for c in text if '\u0A00' <= c <= '\u0A7F')

    total_indic = devanagari + bengali + tamil + telugu + gujarati + kannada + malayalam + gurmukhi
    total_len = max(len(text), 1)

    if total_indic / total_len > 0.3:
        scores = {
            'hi': devanagari, 'bn': bengali, 'ta': tamil, 'te': telugu,
            'gu': gujarati, 'kn': kannada, 'ml': malayalam, 'pa': gurmukhi
        }
        best_lang = max(scores, key=scores.get)
        if scores[best_lang] > 0:
            return EDGE_TTS_VOICES.get(best_lang, EDGE_TTS_VOICES['en'])

    return EDGE_TTS_VOICES.get('en', 'en-IN-PrabhatNeural')
