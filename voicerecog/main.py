import os
# Thread env MUST be set before onnxruntime imports to take effect on CPU.
_CORES = min(4, os.cpu_count() or 2)
os.environ.setdefault("OMP_NUM_THREADS", str(_CORES))
os.environ.setdefault("OMP_WAIT_POLICY", "ACTIVE")  # keep worker threads hot → lower latency

import io
import json
import time
import shutil
import threading
import subprocess
from typing import Optional

import numpy as np
import soundfile as sf
from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

# ──────────────────────────────────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────────────────────────────────
MODEL_REPO = os.environ.get(
    "ASR_MODEL_REPO", "onnx-community/nemotron-3.5-asr-streaming-0.6b-onnx-int4"
)
MODEL_DIR = os.environ.get("ASR_MODEL_DIR", os.path.expanduser("~/asr_model"))
# Default language when the caller doesn't specify one. "" / "auto" engages the
# model's built-in language detection (lang_id 101).
DEFAULT_LANG = os.environ.get("ASR_LANG", "")

# Locale → (lang_id, name), per the onnxruntime-genai nemotron_speech example.
# lang_id is fed to the multilingual encoder via Generator.set_runtime_option.
LANG_TO_ID = {
    "en": 0, "en-US": 0, "en-GB": 1, "es-ES": 2, "es": 3, "es-US": 3,
    "zh": 4, "zh-CN": 4, "hi": 6, "hi-IN": 6, "ar": 7, "ar-AR": 7,
    "fr": 8, "fr-FR": 8, "de": 9, "de-DE": 9, "ja": 10, "ja-JP": 10,
    "ru": 11, "ru-RU": 11, "pt-BR": 12, "pt": 13, "pt-PT": 13,
    "ko": 14, "ko-KR": 14, "it": 15, "it-IT": 15, "nl": 16, "pl": 17,
    "tr": 18, "uk": 19, "ro": 20, "el": 21, "cs": 22, "hu": 23, "sv": 24,
    "da": 25, "fi": 26, "sk": 28, "hr": 29, "bg": 30, "lt": 31, "th": 32,
    "vi": 33, "he": 64, "fr-CA": 100, "auto": 101,
}

app = FastAPI(title="Kautilya RevealIQ STT (Nemotron 3.5 Streaming ASR)")

# ──────────────────────────────────────────────────────────────────────────
# Model loading (background, so /health comes up immediately)
# ──────────────────────────────────────────────────────────────────────────
og = None
_model = None
_tokenizer = None
_ready = False
_load_error = None
SAMPLE_RATE = 16000       # overwritten from genai_config.json at load
CHUNK_SAMPLES = 8960      # ~560ms @ 16k; overwritten from genai_config.json
_load_lock = threading.Lock()
# StreamingProcessor + Generator hold per-stream cache state, so each request
# gets its own; serialize on the small CPU instance for predictability.
_infer_lock = threading.Lock()


def _ensure_model_local() -> str:
    needed = os.path.join(MODEL_DIR, "genai_config.json")
    if os.path.exists(needed):
        return MODEL_DIR
    print(f"[load] model not baked in, downloading {MODEL_REPO} ...", flush=True)
    from huggingface_hub import snapshot_download
    return snapshot_download(
        repo_id=MODEL_REPO, local_dir=MODEL_DIR, ignore_patterns=["*.png", "*.md"]
    )


def _load_model():
    global og, _model, _tokenizer, _ready, _load_error, SAMPLE_RATE, CHUNK_SAMPLES
    with _load_lock:
        if _ready or _load_error:
            return
        try:
            import onnxruntime_genai as _og
            og = _og
            path = _ensure_model_local()

            # sample_rate / chunk_samples live in genai_config.json's model block.
            try:
                with open(os.path.join(path, "genai_config.json")) as f:
                    gc = json.load(f).get("model", {})
                SAMPLE_RATE = int(gc.get("sample_rate", SAMPLE_RATE))
                CHUNK_SAMPLES = int(gc.get("chunk_samples", CHUNK_SAMPLES))
            except Exception as ce:
                print(f"[load] genai_config read note: {ce}", flush=True)

            print(f"[load] init ort-genai from {path} "
                  f"(sr={SAMPLE_RATE}, chunk={CHUNK_SAMPLES}) ...", flush=True)
            cfg = og.Config(path)
            # ort-genai validates provider at Model() and wants canonical "CPU".
            try:
                cfg.clear_providers()
                cfg.append_provider("CPU")
            except Exception as pe:
                print(f"[load] provider config note: {pe}", flush=True)
            _model = og.Model(cfg)
            _tokenizer = og.Tokenizer(_model)

            # Warm-up: push ~0.5s of silence through the streaming path so the
            # first real request doesn't pay the lazy-init penalty.
            try:
                _run_inference(np.zeros(SAMPLE_RATE // 2, dtype=np.float32), None)
                print("[load] warm-up OK", flush=True)
            except Exception as we:
                print(f"[load] warm-up note (non-fatal): {we}", flush=True)

            _ready = True
            print("[load] RevealIQ STT READY", flush=True)
        except Exception as e:
            import traceback
            _load_error = str(e)
            traceback.print_exc()
            print(f"[load] FAILED: {e}", flush=True)


# ──────────────────────────────────────────────────────────────────────────
# Audio handling
# ──────────────────────────────────────────────────────────────────────────
def _decode_to_model_sr(raw: bytes) -> np.ndarray:
    """Decode arbitrary audio bytes (webm/opus, mp3, m4a, wav, …) to a mono
    float32 array at the model's sample rate. soundfile fast-path when the
    audio is already at SAMPLE_RATE; otherwise ffmpeg (proper resampling)."""
    try:
        data, sr = sf.read(io.BytesIO(raw), dtype="float32", always_2d=False)
        if sr == SAMPLE_RATE:
            if data.ndim > 1:
                data = data.mean(axis=1)
            return np.ascontiguousarray(data, dtype=np.float32)
    except Exception:
        pass

    if not shutil.which("ffmpeg"):
        raise HTTPException(500, "ffmpeg not available to decode this audio format")
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error",
         "-i", "pipe:0", "-f", "s16le", "-ac", "1", "-ar", str(SAMPLE_RATE), "pipe:1"],
        input=raw, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if proc.returncode != 0 or not proc.stdout:
        raise HTTPException(400, f"Could not decode audio: {proc.stderr.decode()[:200]}")
    pcm = np.frombuffer(proc.stdout, dtype=np.int16).astype(np.float32) / 32768.0
    return np.ascontiguousarray(pcm, dtype=np.float32)


def _resolve_lang_id(language: Optional[str]):
    """Map a locale code to an encoder lang_id. '' / 'auto' → auto-detect (101).
    Unknown codes → None (use the model's configured default)."""
    if language is None:
        language = DEFAULT_LANG
    language = (language or "").strip()
    if language == "":
        return None  # use model default_lang_id
    if language.lower() in ("auto",):
        return LANG_TO_ID["auto"]
    return LANG_TO_ID.get(language) or LANG_TO_ID.get(language.split("-")[0])


def _decode_tokens(generator, tok_stream) -> str:
    text = ""
    while not generator.is_done():
        generator.generate_next_token()
        toks = generator.get_next_tokens()
        if len(toks) > 0:
            piece = tok_stream.decode(toks[0])
            if piece:
                text += piece
    return text


def _run_inference(samples: np.ndarray, language: Optional[str]) -> str:
    """Streaming transcription of a mono float32 array via onnxruntime-genai's
    StreamingProcessor (the nemotron_speech ASR path): feed cache-aware chunks,
    decode tokens incrementally, then flush the tail."""
    if og is None or _model is None or _tokenizer is None:
        raise RuntimeError("model not initialized")

    processor = og.StreamingProcessor(_model)
    try:
        processor.set_option("use_vad", "false")
    except Exception:
        pass
    tok_stream = _tokenizer.create_stream()
    params = og.GeneratorParams(_model)
    generator = og.Generator(_model, params)

    lang_id = _resolve_lang_id(language)
    if lang_id is not None:
        try:
            generator.set_runtime_option("lang_id", str(int(lang_id)))
        except Exception as le:
            print(f"[stt] lang_id set note: {le}", flush=True)

    text = ""
    for i in range(0, len(samples), CHUNK_SAMPLES):
        chunk = samples[i:i + CHUNK_SAMPLES].astype(np.float32)
        inputs = processor.process(chunk)
        if inputs is not None:
            generator.set_inputs(inputs)
            text += _decode_tokens(generator, tok_stream)

    inputs = processor.flush()
    if inputs is not None:
        generator.set_inputs(inputs)
        text += _decode_tokens(generator, tok_stream)

    return text.strip()


def transcribe_bytes(raw: bytes, language: Optional[str] = None) -> dict:
    samples = _decode_to_model_sr(raw)
    duration = round(len(samples) / SAMPLE_RATE, 2)
    if len(samples) < SAMPLE_RATE * 0.05:  # < 50ms → nothing to do
        return {"text": "", "duration": duration}
    t0 = time.time()
    with _infer_lock:
        text = _run_inference(samples, language)
    took = int((time.time() - t0) * 1000)
    print(f"[stt] {duration}s audio → {len(text)} chars in {took}ms (lang={language})", flush=True)
    return {"text": text, "duration": duration, "latency_ms": took}


# ──────────────────────────────────────────────────────────────────────────
# Lifecycle
# ──────────────────────────────────────────────────────────────────────────
threading.Thread(target=_load_model, daemon=True).start()


def _keepalive():
    import requests as _req
    while True:
        time.sleep(240)  # ping every 4 min so HF doesn't sleep the Space
        try:
            _req.get("http://localhost:7860/health", timeout=5)
        except Exception:
            pass


threading.Thread(target=_keepalive, daemon=True).start()


# ──────────────────────────────────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────────────────────────────────
@app.get("/")
async def root():
    return {
        "engine": "Kautilya RevealIQ STT",
        "model": MODEL_REPO,
        "ready": _ready,
        "load_error": _load_error,
        "sample_rate": SAMPLE_RATE,
        "chunk_samples": CHUNK_SAMPLES,
    }


@app.get("/health")
async def health():
    return {"status": "healthy", "ready": _ready, "load_error": _load_error}


def _require_ready():
    if not _ready:
        if _load_error:
            raise HTTPException(503, f"ASR model failed to load: {_load_error}")
        raise HTTPException(503, "ASR model still warming up, retry in 10-30s")


@app.post("/v1/audio/transcriptions")
async def transcriptions(
    file: UploadFile = File(...),
    language: Optional[str] = Form(None),
    prompt: Optional[str] = Form(None),  # accepted for OpenAI-compat; unused
):
    """OpenAI-compatible transcription. Accepts any audio the browser/uploads
    can produce; returns {"text": ...}. Used for both file upload and the
    segment-by-segment live mode."""
    _require_ready()
    raw = await file.read()
    if not raw:
        raise HTTPException(400, "empty audio")
    try:
        result = await run_in_threadpool(transcribe_bytes, raw, language)
    except HTTPException:
        raise
    except Exception as e:
        print(f"[stt] inference error: {e}", flush=True)
        raise HTTPException(500, f"transcription failed: {e}")
    return JSONResponse(result)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7860)
