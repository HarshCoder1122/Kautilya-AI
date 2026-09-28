import os
# Thread env MUST be set BEFORE torch is imported to take full effect on CPU.
_CORES = min(4, os.cpu_count() or 2)
os.environ.setdefault("OMP_NUM_THREADS", str(_CORES))
os.environ.setdefault("MKL_NUM_THREADS", str(_CORES))
os.environ.setdefault("OMP_WAIT_POLICY", "ACTIVE")  # keep worker threads hot → lower latency
import io
import torch
import soundfile as sf
from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional
from kokoro import KPipeline
import numpy as np
from starlette.concurrency import run_in_threadpool
import time
import re
import asyncio
import threading

# Disable gradient calculation globally for inference
torch.set_grad_enabled(False)

# CUDA Detection for HF Spaces / GPU environments
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"DEBUG: Using device: {device}")

# Optimize for CPU performance
if device == "cpu":
    # Kokoro is a small 82M model. 2-4 intra-op threads is the sweet spot —
    # more just adds context-switching overhead on small HF CPU instances.
    torch.set_num_threads(_CORES)
    try:
        torch.set_num_interop_threads(1)  # single request → no inter-op parallelism needed
    except Exception:
        pass
    torch.backends.mkldnn.enabled = True  # oneDNN fused kernels for Intel/AMD
    try:
        torch.set_flush_denormal(True)    # denormals murder audio-DSP throughput on CPU
    except Exception:
        pass
    print(f"DEBUG: CPU threads={_CORES}, interop=1, mkldnn={torch.backends.mkldnn.enabled}")
    
# Enable optimizations for faster inference
torch.backends.cudnn.benchmark = True

app = FastAPI(title="Kautilya TTS API")

# --- Model Loading ---
print("Loading Kokoro English pipeline...")
kokoro_en = None
kokoro_hi = None
_hi_loading = False
_hi_last_error = None  # surface real reason to the API so users see WHY load failed

HI_VOICES = ("hf_alpha", "hf_beta", "hm_omega", "hm_psi")

# ── Loudness / output gain ────────────────────────────────────────────────
# Kokoro emits float32 in [-1,1] but typically peaks ~0.3-0.5, so a raw
# *32767 conversion sounds quiet. We peak-normalise each segment to TARGET_PEAK
# for consistent, full loudness (gain capped so near-silent breath frames don't
# get blown up). Override with TTS_TARGET_PEAK / TTS_MAX_GAIN.
TARGET_PEAK = float(os.environ.get("TTS_TARGET_PEAK", "0.98"))
MAX_GAIN = float(os.environ.get("TTS_MAX_GAIN", "6.0"))
FADE_MS = float(os.environ.get("TTS_FADE_MS", "2.5"))  # edge fade kills click/pop at segment joins
# Soft-clip drive: tanh saturation that raises RMS (perceived LOUDNESS) while
# keeping peaks bounded — much louder than peak-normalisation alone, no harsh
# clipping. 1.0 = off; higher = louder. Override with TTS_LOUDNESS_DRIVE.
LOUDNESS_DRIVE = float(os.environ.get("TTS_LOUDNESS_DRIVE", "2.0"))

def _maybe_quantize(pipeline, label=""):
    """INT8 dynamic quantization of the Kokoro acoustic model — a CPU speedup
    with NO external files. Any failure falls back to fp32. Disable TTS_QUANTIZE=0.

    IMPORTANT: only nn.Linear is quantized. Kokoro calls LSTM.flatten_parameters()
    during forward, which a dynamically-quantized LSTM doesn't implement
    ('LSTM has no attribute flatten_parameters'), so quantizing LSTM/GRU breaks
    inference. Leaving the LSTMs in fp32 keeps synthesis working while the
    Linear-heavy text/attention path still benefits."""
    if device != "cpu" or os.environ.get("TTS_QUANTIZE", "1") == "0":
        return
    try:
        model = getattr(pipeline, "model", None)
        if model is None:
            return
        import torch.nn as nn
        pipeline.model = torch.quantization.quantize_dynamic(
            model, {nn.Linear}, dtype=torch.qint8)
        print(f"DEBUG: INT8 dynamic quantization applied [{label}] (Linear only)")
    except Exception as e:
        print(f"WARN: quantization skipped [{label}]: {e}")

def _post_process(audio, sample_rate=24000):
    """Per-segment loudness normalisation + edge fades. Returns float32 numpy.
    - Peak-normalise to TARGET_PEAK (consistent, loud output) with a gain cap.
    - Short linear fade in/out so concatenated segments don't click ('break')."""
    if torch.is_tensor(audio):
        a = audio.detach().to(torch.float32).cpu().numpy()
    else:
        a = np.asarray(audio, dtype=np.float32)
    if a.size == 0:
        return a
    peak = float(np.max(np.abs(a)))
    if peak > 1e-4:
        gain = min(TARGET_PEAK / peak, MAX_GAIN)
        if gain != 1.0:
            a = a * gain
    # Soft-clip saturation → louder perceived volume, peaks stay bounded.
    if LOUDNESS_DRIVE > 1.0:
        a = np.tanh(a * LOUDNESS_DRIVE) * (TARGET_PEAK / np.tanh(LOUDNESS_DRIVE))
    np.clip(a, -1.0, 1.0, out=a)
    n = int(sample_rate * FADE_MS / 1000.0)
    if n > 0 and a.size > 2 * n:
        ramp = np.linspace(0.0, 1.0, n, dtype=np.float32)
        a[:n] *= ramp
        a[-n:] *= ramp[::-1]
    return a

def _load_english():
    global kokoro_en
    try:
        pipe = KPipeline(lang_code='a', device=device)
        original_model = getattr(pipe, "model", None)
        _maybe_quantize(pipe, "en")
        # Warm-up doubles as a quantization self-test: if the int8 model can't
        # run, revert to fp32 so we never serve a broken pipeline.
        try:
            _ = list(pipe("Ready", voice="af_heart", speed=1.0))
        except Exception as qe:
            print(f"WARN: quantized EN inference failed, reverting to fp32: {qe}")
            if original_model is not None:
                pipe.model = original_model
            _ = list(pipe("Ready", voice="af_heart", speed=1.0))
        kokoro_en = pipe  # only publish after a successful warm-up
        print("Kokoro English: READY")
    except Exception as e:
        print(f"Error loading Kokoro English: {e}")

def _load_hindi():
    """Initialize the Hindi pipeline. Pre-downloads voice weights so the first
    real request doesn't hit HF Hub mid-stream. Tries multiple voices because
    the default may not always be cached on the model server."""
    global kokoro_hi, _hi_loading, _hi_last_error
    if kokoro_hi or _hi_loading:
        return
    _hi_loading = True
    try:
        pipe = KPipeline(lang_code='h', device=device)
        original_model = getattr(pipe, "model", None)
        _maybe_quantize(pipe, "hi")
        # Pre-load every Hindi voice so requests never block on a Hub fetch.
        loaded = []
        for v in HI_VOICES:
            try:
                pipe.load_voice(v)
                loaded.append(v)
            except Exception as ve:
                print(f"Hindi voice {v} not available: {ve}")
        if not loaded:
            raise RuntimeError(f"No Hindi voices could be loaded (tried {HI_VOICES})")
        # Warm-up doubles as a quantization self-test — revert to fp32 on failure.
        warm_voice = loaded[0]
        try:
            _ = list(pipe("नमस्ते, यह एक परीक्षण वाक्य है।", voice=warm_voice, speed=1.0))
        except Exception as qe:
            print(f"WARN: quantized HI inference failed, reverting to fp32: {qe}")
            if original_model is not None:
                pipe.model = original_model
            _ = list(pipe("नमस्ते, यह एक परीक्षण वाक्य है।", voice=warm_voice, speed=1.0))
        kokoro_hi = pipe  # only publish after a successful warm-up
        _hi_last_error = None
        print(f"Kokoro Hindi: READY (voices: {loaded})")
    except Exception as e:
        _hi_last_error = str(e)
        kokoro_hi = None  # reset so a retry can actually try again
        import traceback
        print(f"Error loading Kokoro Hindi: {e}")
        traceback.print_exc()
    finally:
        _hi_loading = False

# Load English synchronously (blocks startup but ensures it's ready for first request)
_load_english()
# Load Hindi lazily in background — saves ~10s off cold start
threading.Thread(target=_load_hindi, daemon=True).start()

# --- Fast ONNX engine (optional, 2-4x faster than PyTorch eager on CPU) ----
# ONNX Runtime fuses ops and uses optimized CPU kernels, so Kokoro synthesises
# MUCH faster than the PyTorch pipeline. We use it whenever the model files +
# package are present; otherwise everything transparently falls back to the
# PyTorch KPipeline above — so a missing model NEVER breaks audio. Toggle with
# TTS_ENGINE=onnx|torch.
onnx_engine = None
_GH_BASE = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/"
_ONNX_VOICES_URL = _GH_BASE + "voices-v1.0.bin"
# Models to try, FASTEST first. int8 (~80MB) is ~2x faster than fp32 on CPU;
# fp32 (~310MB) is the compatibility fallback. Whichever loads + warms up wins.
_ONNX_MODELS = [
    ("kokoro-int8.onnx", "https://huggingface.co/onnx-community/Kokoro-82M-v1.0-ONNX/resolve/main/onnx/model_quantized.onnx"),
    ("kokoro-v1.0.onnx", _GH_BASE + "kokoro-v1.0.onnx"),
]

def _download(path, url):
    """Download once if missing — lets ONNX self-heal even if the build skipped it."""
    import urllib.request
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return
    print(f"[ONNX] downloading {path} (one-time) ...", flush=True)
    urllib.request.urlretrieve(url, path)
    print(f"[ONNX] downloaded {path} ({os.path.getsize(path)//(1024*1024)} MB)", flush=True)

def _load_onnx_engine():
    global onnx_engine
    if os.environ.get("TTS_ENGINE", "onnx").lower() != "onnx":
        print("[ONNX] disabled via TTS_ENGINE → PyTorch engine")
        return
    try:
        from kokoro_onnx import Kokoro
    except Exception as e:
        print(f"[ONNX] kokoro-onnx not installed → PyTorch engine: {e}")
        return
    voices_path = os.environ.get("KOKORO_ONNX_VOICES", "voices-v1.0.bin")
    try:
        _download(voices_path, _ONNX_VOICES_URL)
    except Exception as e:
        print(f"[ONNX] voices download failed → PyTorch engine: {e}")
        return
    # Explicit override wins; otherwise try int8 → fp32.
    candidates = ([(os.environ["KOKORO_ONNX_MODEL"], None)]
                  if os.environ.get("KOKORO_ONNX_MODEL") else _ONNX_MODELS)
    for fname, url in candidates:
        try:
            if url:
                _download(fname, url)
            eng = Kokoro(fname, voices_path)
            # THOROUGH warm-up: a real sentence forces the misaki/spacy g2p +
            # onnxruntime to fully initialize NOW (in this background thread),
            # so the first user request isn't hit with a ~5s lazy-load penalty.
            eng.create(
                "This is a warm up sentence so the phonemizer and the model are fully ready.",
                voice="af_heart", speed=1.0, lang="en-us")
            onnx_engine = eng
            tag = "INT8 (quantized)" if ("int8" in fname or "quant" in fname) else "fp32"
            print(f"[ONNX] Kokoro ONNX engine READY [{fname}] {tag} — fast CPU path ACTIVE", flush=True)
            return
        except Exception as e:
            print(f"[ONNX] {fname} failed, trying next: {e}", flush=True)
    onnx_engine = None
    print("[ONNX] all ONNX models failed → PyTorch engine")

threading.Thread(target=_load_onnx_engine, daemon=True).start()

# --- Keep-alive self-ping to prevent HF Space from sleeping ---
def _keepalive():
    import requests as _req
    while True:
        time.sleep(240)  # ping every 4 minutes
        try:
            _req.get("http://localhost:7860/health", timeout=5)
        except Exception:
            pass

threading.Thread(target=_keepalive, daemon=True).start()

# --- Schemas with Validation ---

class SpeechRequest(BaseModel):
    model: str = "kokoro-en"
    input: str = Field(..., min_length=1, description="Text to synthesize")
    voice: Optional[str] = None
    speed: Optional[float] = Field(1.0, ge=0.5, le=2.0)
    response_format: Optional[str] = "mp3"

# --- Endpoints ---

@app.get("/")
async def root():
    return {
        "engine": "Kautilya Zero-Bug Stable",
        "status": "online",
        "pipelines": {"en": kokoro_en is not None, "hi": kokoro_hi is not None},
        "hi_loading": _hi_loading,
        "hi_last_error": _hi_last_error,
    }

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.post("/v1/audio/speech")
async def text_to_speech(request: SpeechRequest):
    fmt = (request.response_format or "mp3").lower()
    if fmt == "wav":
        # Stream WAV with chunked transfer encoding and a dynamic 44-byte header for zero transcoding lag
        return StreamingResponse(
            stream_wav_generator(request),
            media_type="audio/wav"
        )
    elif fmt == "pcm":
        return StreamingResponse(
            stream_audio_generator(request),
            media_type="application/octet-stream"
        )
    else:
        # Default to streaming MP3
        pcm_gen = stream_audio_generator(request)
        mp3_gen = pcm_to_mp3_stream(pcm_gen)
        return StreamingResponse(
            mp3_gen,
            media_type="audio/mpeg"
        )

@app.post("/v1/audio/stream")
async def stream_audio_endpoint(request: SpeechRequest):
    # Returns RAW PCM (No Header) - Best for LiveKit/Telephony
    return StreamingResponse(
        stream_audio_generator(request),
        media_type="application/octet-stream"
    )

# --- Core Logic ---

def get_pipeline(model_name: str):
    m = model_name.lower()
    if "hi" in m or "hindi" in m:
        if not kokoro_hi:
            # Trigger load synchronously if background thread hasn't finished
            _load_hindi()
        if not kokoro_hi:
            reason = _hi_last_error or "still warming up"
            raise HTTPException(
                status_code=503,
                detail=f"Hindi pipeline unavailable: {reason}. Retry in 10-30s."
            )
        return kokoro_hi
    else:
        if not kokoro_en:
            raise HTTPException(status_code=503, detail="English pipeline not ready")
        return kokoro_en

# ── Auto language detection ───────────────────────────────────────────────
# The caller (chat UI) always asks for the English voice, but the LLM may reply
# in Hindi (Devanagari) — which the English pipeline can't pronounce. We detect
# the script of each text segment and route it to the right pipeline + voice
# automatically, so the frontend never has to know the language. Hinglish
# (Hindi written in Roman letters) stays on English since it's Latin script.
_EN_VOICE_PREFIXES = ("af_", "am_", "bf_", "bm_")
_HI_VOICE_PREFIXES = ("hf_", "hm_")

def _detect_lang(text: str) -> str:
    """'hi' if the segment contains Devanagari, else 'en'."""
    if not text:
        return "en"
    for ch in text:
        if "ऀ" <= ch <= "ॿ":
            return "hi"
    return "en"

def _resolve_pipeline(lang: str, requested_voice: str):
    """Return (pipeline, voice) for a detected language. Lazily loads Hindi and
    falls back to English if Hindi isn't ready, so playback never hard-fails."""
    if lang == "hi":
        if not kokoro_hi:
            _load_hindi()
        if kokoro_hi:
            v = requested_voice if (requested_voice or "").startswith(_HI_VOICE_PREFIXES) else "hf_alpha"
            return kokoro_hi, v
        # Hindi not ready → fall through to English rather than erroring out.
    if not kokoro_en:
        raise HTTPException(status_code=503, detail="English pipeline not ready")
    v = requested_voice if (requested_voice or "").startswith(_EN_VOICE_PREFIXES) else "af_heart"
    return kokoro_en, v

def _synth_segment(sentence, lang, requested_voice, speed):
    """Synthesize ONE segment → float32 numpy audio. Prefers the fast ONNX
    engine; falls back to the PyTorch pipeline per-segment on any failure, so a
    single ONNX hiccup (e.g. an unsupported lang) never drops audio."""
    # Fast path: ONNX Runtime
    if onnx_engine is not None:
        try:
            if lang == "hi":
                v = requested_voice if (requested_voice or "").startswith(_HI_VOICE_PREFIXES) else "hf_alpha"
                lc = "hi"
            else:
                v = requested_voice if (requested_voice or "").startswith(_EN_VOICE_PREFIXES) else "af_heart"
                lc = "en-us"
            samples, _sr = onnx_engine.create(sentence, voice=v, speed=float(speed), lang=lc)
            return np.asarray(samples, dtype=np.float32)
        except Exception as e:
            print(f"[ONNX] segment failed → PyTorch fallback: {e}")
    # Fallback path: PyTorch KPipeline
    pipeline, seg_voice = _resolve_pipeline(lang, requested_voice)
    out = []
    with torch.inference_mode():
        for _, _, audio in pipeline(sentence, voice=seg_voice, speed=speed):
            if audio is None:
                continue
            out.append(audio.detach().cpu().numpy() if torch.is_tensor(audio) else np.asarray(audio, dtype=np.float32))
    if not out:
        return np.zeros(0, dtype=np.float32)
    return np.concatenate(out).astype(np.float32)

# ── Repeated-phrase audio cache ───────────────────────────────────────────
# Greetings, UI sounds and common replies repeat constantly. Caching the final
# PCM for short inputs makes those instant (zero synthesis). Keyed by
# (lang, voice, speed, text); LRU-evicted.
from collections import OrderedDict
_AUDIO_CACHE = OrderedDict()
_AUDIO_CACHE_MAX = 256
_AUDIO_CACHE_MAX_CHARS = 600
_cache_lock = threading.Lock()

def _cache_key(text, model_name, voice, speed):
    lang = "hi" if ("hi" in model_name.lower() or "hindi" in model_name.lower()) else "en"
    return (lang, voice, round(float(speed), 2), text.strip())

def _cache_get(key):
    with _cache_lock:
        v = _AUDIO_CACHE.get(key)
        if v is not None:
            _AUDIO_CACHE.move_to_end(key)
        return v

def _cache_put(key, data):
    with _cache_lock:
        _AUDIO_CACHE[key] = data
        _AUDIO_CACHE.move_to_end(key)
        while len(_AUDIO_CACHE) > _AUDIO_CACHE_MAX:
            _AUDIO_CACHE.popitem(last=False)


# Tight join cushions — when a sentence is split into segments, big trailing/
# leading silences made an audible PAUSE at every join. Keeping only ~8ms each
# side butts the segments together so split sentences flow continuously. The
# 2.5ms edge-fade in _post_process keeps the tight joins click-free.
_TRIM_START_MS = int(os.environ.get("TTS_TRIM_START_MS", "8"))
_TRIM_END_MS = int(os.environ.get("TTS_TRIM_END_MS", "8"))

def trim_silence(audio, sample_rate=24000, threshold=0.005, keep_start_ms=_TRIM_START_MS, keep_end_ms=_TRIM_END_MS):
    """
    Trim leading and trailing silence from float32 audio, keeping only a tiny
    cushion each side so segments of a split sentence join with no audible gap.
    """
    is_tensor = False
    if torch.is_tensor(audio):
        is_tensor = True
        audio_np = audio.cpu().numpy()
    else:
        audio_np = audio

    # Find indices where amplitude exceeds threshold
    non_silent = np.where(np.abs(audio_np) > threshold)[0]
    
    if len(non_silent) == 0:
        return audio

    start_idx = non_silent[0]
    end_idx = non_silent[-1]

    # Calculate cushions in samples
    start_cushion = int((keep_start_ms / 1000.0) * sample_rate)
    end_cushion = int((keep_end_ms / 1000.0) * sample_rate)

    new_start = max(0, start_idx - start_cushion)
    new_end = min(len(audio_np), end_idx + end_cushion)

    trimmed_audio = audio_np[new_start:new_end]

    if is_tensor:
        return torch.from_numpy(trimmed_audio).to(audio.device)
    return trimmed_audio

def generate_full_audio_sync(request: SpeechRequest):
    # Auto-detect language from the actual text; ONNX fast path via _synth_segment.
    lang = _detect_lang(request.input)
    audio = _synth_segment(request.input, lang, request.voice, request.speed)
    if audio is None or len(audio) == 0:
        raise ValueError("Audio generation failed")
    return _post_process(trim_silence(audio)), 24000

def split_text(text: str):
    """
    Advanced progressive splitting logic to minimize TTFB.
    Splits the first segment aggressively (2-5 words or first punctuation) to achieve instant TTFT,
    and subsequent segments into natural phrases (8-15 words) for optimal prosody and smooth streaming.
    """
    # Clean text from multiple spaces
    text = re.sub(r'\s+', ' ', text).strip()
    if not text:
        return []

    # 1. First split by major sentence boundaries, Hindi full stops, and newlines
    sentences = re.split(r'(?<=[.!?।])\s+|\n+|(?<=;)\s+', text)
    if not sentences:
        return []

    first_sentence = sentences[0].strip()
    rest_text = " ".join(sentences[1:]).strip()

    # Determine if we should split the first sentence further for instant start
    words = first_sentence.split()
    first_chunk = ""
    remaining_first_sentence = ""

    # If first sentence is longer than 5 words, let's split it progressively
    if len(words) > 5:
        # Try to find a comma or conjunction near the beginning (words 2 to 5)
        split_pos = -1
        # Comma search
        comma_idx = first_sentence.find(',')
        if 0 < comma_idx < len(first_sentence):
            left_words = first_sentence[:comma_idx].split()
            if 2 <= len(left_words) <= 6:
                split_pos = comma_idx + 1
        
        # If no comma split found, look for English/Hindi conjunctions in the first 5 words
        if split_pos == -1:
            conjunctions = [" and ", " but ", " or ", " because ", " so ", " or ", " और ", " लेकिन ", " कि "]
            for conj in conjunctions:
                idx = first_sentence.lower().find(conj)
                if idx != -1:
                    left_words = first_sentence[:idx].split()
                    if 2 <= len(left_words) <= 6:
                        split_pos = idx + len(conj)
                        break
        
        # Fallback: split exactly at 3-4 words
        if split_pos == -1:
            split_pos = len(" ".join(words[:4]))
            
        first_chunk = first_sentence[:split_pos].strip()
        remaining_first_sentence = first_sentence[split_pos:].strip()
    else:
        first_chunk = first_sentence
        remaining_first_sentence = ""

    # Reconstruct the list of segments
    segments = []
    if first_chunk:
        segments.append(first_chunk)
    if remaining_first_sentence:
        segments.append(remaining_first_sentence)
        
    # Process the remaining text with standard splitting
    if rest_text:
        # Standard splitting for the rest
        rest_sentences = re.split(r'(?<=[.!?।])\s+|\n+|(?<=;)\s+', rest_text)
        conjunctions = [
            " and ", " but ", " or ", " because ", " so ", " then ", 
            " with ", " that ", " to ", " for ", " how ", " who ", 
            " what ", " why ", " when ", " if ", " as ", " about ",
            " और ", " या ", " लेकिन ", " कि ", " क्योंकि ", " इसलिए ", " अगर "
        ]
        for s in rest_sentences:
            s = s.strip()
            if not s:
                continue
            words_s = s.split()
            # Keep whole sentences intact up to a generous size — fewer, larger
            # synthesis calls = far less per-call g2p/setup overhead (faster
            # overall) AND smoother prosody (no mid-sentence chopping). Only
            # genuinely long sentences get split.
            if len(words_s) <= 35:
                segments.append(s)
            else:
                sub_segments = []
                split_subsegment(s, sub_segments, conjunctions)
                segments.extend(sub_segments)
    else:
        pass
                
    return [s for s in segments if s.strip()]

def split_subsegment(s: str, result_list: list, conjunctions: list):
    words = s.split()
    if len(words) <= 35:
        result_list.append(s)
        return
        
    best_pos = -1
    best_len = 999
    
    mid_word_idx = len(words) // 2
    
    for conj in conjunctions:
        # Search for conjunction in the string (case insensitive)
        pattern = re.compile(re.escape(conj), re.IGNORECASE)
        for match in pattern.finditer(s):
            start_char = match.start()
            word_idx = len(s[:start_char].split())
            distance = abs(word_idx - mid_word_idx)
            if distance < best_len:
                best_len = distance
                best_pos = start_char
                
    # If a good conjunction is found (not too far from middle), split there
    if best_pos != -1 and best_len < (len(words) // 3 + 2):
        left = s[:best_pos].strip()
        right = s[best_pos:].strip()
        if left and right:
            split_subsegment(left, result_list, conjunctions)
            split_subsegment(right, result_list, conjunctions)
            return
            
    # Fallback: split exactly at the space closest to the middle
    mid_idx = len(words) // 2
    left = " ".join(words[:mid_idx])
    right = " ".join(words[mid_idx:])
    if left and right:
        split_subsegment(left, result_list, conjunctions)
        split_subsegment(right, result_list, conjunctions)
    else:
        result_list.append(s)


# --- Ultra-Fast Streaming Implementation ---

def generate_voice_thread(loop, queue, text, model_name, voice, speed):
    # Audio frame chunking: 4096 bytes (2048 samples of 16-bit PCM = ~85ms of
    # 24kHz mono audio) keeps the streaming flow steady.
    CHUNK_SIZE = 4096

    def _emit(audio_bytes):
        for i in range(0, len(audio_bytes), CHUNK_SIZE):
            loop.call_soon_threadsafe(queue.put_nowait, audio_bytes[i:i + CHUNK_SIZE])

    try:
        # ── Cache fast-path: instant replay for repeated short phrases ──
        cacheable = len(text) <= _AUDIO_CACHE_MAX_CHARS
        ckey = _cache_key(text, model_name, voice, speed) if cacheable else None
        if ckey is not None:
            cached = _cache_get(ckey)
            if cached is not None:
                _emit(cached)
                loop.call_soon_threadsafe(queue.put_nowait, None)
                return

        # Pre-split text for faster streaming using progressive splitting
        sentences = split_text(text)
        full_pcm = bytearray() if ckey is not None else None
        _t0 = time.time()
        _first = True

        for sentence in sentences:
            if not sentence.strip():
                continue

            # AUTO LANGUAGE: pick engine/voice from the segment's own script, so
            # a Hindi reply renders on the Hindi voice even though the request
            # asked for English. _synth_segment uses the fast ONNX engine when
            # available, else the PyTorch pipeline.
            lang = _detect_lang(sentence)
            try:
                audio = _synth_segment(sentence, lang, voice, speed)
            except Exception as e:
                print(f"[TTS] segment synth failed: {e}")
                continue
            if audio is None or len(audio) == 0:
                continue
            # Gentle trim → loudness-normalise → edge-fade. The fade removes the
            # clicks/pops at segment joins; normalisation makes it loud.
            audio = trim_silence(audio)
            a = _post_process(audio)
            audio_int16 = (a * 32767.0).astype(np.int16)
            audio_bytes = audio_int16.tobytes()
            if full_pcm is not None:
                full_pcm.extend(audio_bytes)
            if _first:
                print(f"[TTS] TTFB {int((time.time()-_t0)*1000)}ms "
                      f"engine={'onnx' if onnx_engine is not None else 'torch'} "
                      f"lang={lang} chars={len(text)}", flush=True)
                _first = False
            _emit(audio_bytes)

        # Store the finished utterance for instant future replays.
        if ckey is not None and full_pcm:
            _cache_put(ckey, bytes(full_pcm))

        # Signal end of stream
        loop.call_soon_threadsafe(queue.put_nowait, None)
    except Exception as e:
        print(f"Error in background generation thread: {e}")
        loop.call_soon_threadsafe(queue.put_nowait, None)

async def stream_audio_generator(request: SpeechRequest):
    loop = asyncio.get_running_loop()
    queue = asyncio.Queue()  # Unbounded queue to handle rapid frame-based chunk streaming without QueueFull exceptions
    voice = request.voice if request.voice else ("hf_alpha" if "hi" in request.model.lower() else "af_heart")
    
    # Start ultra-fast generation thread with pre-compiled text
    thread = threading.Thread(
        target=generate_voice_thread,
        args=(loop, queue, request.input, request.model, voice, request.speed or 1.0),
        daemon=True
    )
    thread.start()
    
    # Ultra-fast streaming loop with zero polling latency
    while True:
        chunk = await queue.get()
        if chunk is None:
            break
        yield chunk

def get_wav_header(sample_rate=24000, num_channels=1, bits_per_sample=16):
    """
    Generate a 44-byte WAV header with maximum length fields (0xFFFFFFFF)
    to signify an infinite/streaming length. This allows browsers and media players
    to play the WAV stream in real-time as it is received, with zero transcoding latency.
    """
    import struct
    # We use 0xFFFFFFFF for chunk sizes to represent unknown/streaming length
    header = struct.pack('<4sI4s4sIHHIIHH4sI',
        b'RIFF',
        0xFFFFFFFF, # ChunkSize (unknown/infinite)
        b'WAVE',
        b'fmt ',
        16,          # Subchunk1Size (PCM has 16)
        1,           # AudioFormat (PCM = 1)
        num_channels,
        sample_rate,
        sample_rate * num_channels * (bits_per_sample // 8), # ByteRate
        num_channels * (bits_per_sample // 8),               # BlockAlign
        bits_per_sample,
        b'data',
        0xFFFFFFFF  # Subchunk2Size (unknown/infinite)
    )
    return header

async def stream_wav_generator(request: SpeechRequest):
    # Yield WAV header instantly
    yield get_wav_header(sample_rate=24000, num_channels=1, bits_per_sample=16)
    # Stream PCM chunks
    async for chunk in stream_audio_generator(request):
        yield chunk

async def pcm_to_mp3_stream(pcm_generator):
    """
    Transcode raw PCM (s16le, 24000Hz, mono) to MP3 on-the-fly using an async ffmpeg subprocess.
    Optimized for zero latency and real-time streaming.
    """
    cmd = [
        'ffmpeg',
        '-y',
        '-fflags', 'nobuffer',
        '-analyzeduration', '0',
        '-probesize', '32',
        '-f', 's16le',
        '-ar', '24000',
        '-ac', '1',
        '-i', 'pipe:0',
        '-f', 'mp3',
        '-acodec', 'libmp3lame',
        '-ab', '64k',
        '-compression_level', '9',  # Enable fastest encoding speed (lowest CPU usage)
        '-reservoir', '0',          # Disable bit reservoir for instant frame output
        '-flush_packets', '1',      # Flush each packet immediately
        'pipe:1'
    ]
    
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL
        )
    except Exception as e:
        print(f"ERROR starting ffmpeg: {e}. Fallback to raw PCM bytes.")
        async for chunk in pcm_generator:
            yield chunk
        return

    async def write_to_stdin():
        try:
            async for chunk in pcm_generator:
                if process.returncode is not None:
                    break
                process.stdin.write(chunk)
                await process.stdin.drain()
        except Exception as e:
            print(f"Error writing PCM to ffmpeg: {e}")
        finally:
            try:
                process.stdin.close()
                await process.wait_closed()
            except Exception:
                pass

    writer_task = asyncio.create_task(write_to_stdin())

    try:
        while True:
            # Read smaller buffers to feed client immediately (1024 bytes)
            chunk = await process.stdout.read(1024)
            if not chunk:
                break
            yield chunk
    except Exception as e:
        print(f"Error reading MP3 from ffmpeg: {e}")
    finally:
        await writer_task
        try:
            await process.wait()
        except Exception:
            pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7860)