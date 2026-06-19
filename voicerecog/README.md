---
title: Kautilya RevealIQ STT
emoji: 🎧
colorFrom: purple
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# Kautilya RevealIQ STT — Nemotron 3.5 Streaming ASR

Hosts NVIDIA's **`nvidia/nemotron-3.5-asr-streaming-0.6b`** speech-to-text model on
a free CPU Space, served through a small FastAPI app for the Kautilya **STT
Studio** dashboard.

We run the official **ONNX INT4** export
(`onnx-community/nemotron-3.5-asr-streaming-0.6b-onnx-int4`) via
[`onnxruntime-genai`](https://github.com/microsoft/onnxruntime-genai). That build
is optimized for the 560 ms chunk size, fits under 1 GB, and runs faster than
real-time on CPU with sub-second latency — the realistic way to serve this model
on a free CPU instance. The ONNX package bundles the log-mel front-end, the
encoder/decoder/joint transducer graphs, and the tokenizer (`genai_config.json`),
so the app just feeds audio and runs the decode loop.

- **Languages:** 40 locales, with automatic language detection (leave `language` empty).
- **Punctuation & capitalization:** native.
- **Input:** any audio the browser/uploads produce (webm/opus, mp3, m4a, wav) — the
  app transcodes to 16 kHz mono with ffmpeg.

## API

`POST /v1/audio/transcriptions` (OpenAI-compatible, `multipart/form-data`)

| field      | required | notes                                        |
|------------|----------|----------------------------------------------|
| `file`     | yes      | audio blob                                   |
| `language` | no       | e.g. `en`; empty = auto-detect               |
| `prompt`   | no       | raw decoder prompt override                  |

```bash
curl -X POST "https://YOUR_SPACE_URL/v1/audio/transcriptions" \
     -H "Authorization: Bearer $HF_TOKEN" \
     -F "file=@sample.wav" -F "language=en"
# → {"text": "Hello, how can I help you today?", "duration": 2.1, "latency_ms": 640}
```

Other routes: `GET /health` (liveness + readiness), `GET /` (status + model id).

## Config (env)

| var              | default                                                        |
|------------------|----------------------------------------------------------------|
| `ASR_MODEL_REPO` | `onnx-community/nemotron-3.5-asr-streaming-0.6b-onnx-int4`      |
| `ASR_MODEL_DIR`  | `~/asr_model`                                                  |
| `ASR_PROMPT`     | `""` (auto language detection)                                 |
| `ASR_MAX_TOKENS` | `448`                                                          |

## Deploy

The model (~800 MB) is baked into the image at build time (`cache_model.py`) so
cold starts don't re-download it. Push these files to a Docker Space:

```
Dockerfile  requirements.txt  cache_model.py  main.py  README.md
```

Or use the helper: `python scratch/upload_voicerecog_files.py`.