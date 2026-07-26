"""
Kautilya AI — TTS Service
Text-to-speech utilities: text cleaning, voice detection.
"""
import re
from config import EDGE_TTS_VOICES


def clean_text_for_tts(text):
    """Remove markdown, emojis, URLs, code blocks and convert special
    characters to spoken-word equivalents for natural human-like TTS output."""
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

    # ---- Mathematical / comparison operators → spoken equivalents ----
    # Multi-char operators MUST be replaced before single-char ones
    text = re.sub(r'<=', ' less than or equal to ', text)
    text = re.sub(r'>=', ' greater than or equal to ', text)
    text = re.sub(r'!=', ' not equal to ', text)
    text = re.sub(r'==', ' equals ', text)
    text = re.sub(r'=>', ' implies ', text)
    text = re.sub(r'->', ' to ', text)
    text = re.sub(r'<-', ' from ', text)
    # Single < > only when surrounded by spaces (avoid breaking words)
    text = re.sub(r'\s<\s', ' less than ', text)
    text = re.sub(r'\s>\s', ' greater than ', text)
    # Common math symbols
    text = re.sub(r'\+', ' plus ', text)
    text = re.sub(r'\s-\s', ' minus ', text)  # only spaced dash (preserve hyphens)
    text = re.sub(r'\s/\s', ' divided by ', text)
    text = re.sub(r'\s\*\s', ' times ', text)
    text = re.sub(r'%', ' percent ', text)

    # ---- Arrows and decorative symbols → remove or speak ----
    text = re.sub(r'[|•·►▸▶←↑↓★☆♦♥♣♠→⇒⇐⇔≈≠≤≥±∞√∑∏∫]', ' ', text)

    # ---- Programming / structural chars that TTS reads literally ----
    text = re.sub(r'[{}()\[\]\\<>@#$^&~`|]', ' ', text)

    # ---- Numbered / bulleted list markers → clean ----
    text = re.sub(r'^\d+[.)]\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'^[-*]\s+', '', text, flags=re.MULTILINE)

    # ---- Ellipsis → single period (pause) ----
    text = re.sub(r'\.{2,}', '.', text)

    # ---- Semicolons / colons → comma pause (more natural) ----
    text = re.sub(r'[;:]', ',', text)

    # ---- Quotes (spoken awkwardly by most TTS) → remove ----
    text = re.sub(r'["""\'\'`]', '', text)

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
