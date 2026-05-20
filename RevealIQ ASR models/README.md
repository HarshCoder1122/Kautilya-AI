---
title: Kautilya TTS Engine
emoji: 🎙️
colorFrom: indigo
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
---

# Kautilya TTS Engine

This space hosts a high-performance TTS API optimized for Indian languages and English, designed for integration with the Kautilya application.

## Models
- **Hindi/Indic**: `ai4bharat/indic-tts` (VITS-based)
- **English**: `hexgrad/Kokoro-82M`

## API Usage
The Space provides an OpenAI-compatible endpoint:
- `POST /v1/audio/speech`

### Example Request
```bash
curl -X POST "https://YOUR_SPACE_URL/v1/audio/speech" \
     -H "Content-Type: application/json" \
     -d '{
       "model": "kokoro",
       "input": "Hello, how can I help you today?",
       "voice": "af_heart"
     }'
```
