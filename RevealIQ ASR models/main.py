import os
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

app = FastAPI(title="Kautilya TTS API")

# --- Model Loading ---
print("Loading Kokoro English pipeline...")
kokoro_en = None
kokoro_hi = None
_hi_loading = False
_hi_last_error = None  # surface real reason to the API so users see WHY load failed

HI_VOICES = ("hf_alpha", "hf_beta", "hm_omega", "hm_psi")

def _load_english():
    global kokoro_en
    try:
        kokoro_en = KPipeline(lang_code='a', device=device)
        # Single warm-up pass
        _ = list(kokoro_en("Ready", voice="af_heart", speed=1.0))
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
        kokoro_hi = KPipeline(lang_code='h', device=device)
        # Pre-load every Hindi voice so requests never block on a Hub fetch.
        loaded = []
        for v in HI_VOICES:
            try:
                kokoro_hi.load_voice(v)
                loaded.append(v)
            except Exception as ve:
                print(f"Hindi voice {v} not available: {ve}")
        if not loaded:
            raise RuntimeError(f"No Hindi voices could be loaded (tried {HI_VOICES})")
        # Warm-up with a real Hindi sentence using whichever voice loaded.
        warm_voice = loaded[0]
        _ = list(kokoro_hi("नमस्ते, यह एक परीक्षण वाक्य है।", voice=warm_voice, speed=1.0))
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
        try:
            audio_data, sample_rate = await run_in_threadpool(generate_full_audio_sync, request)
            buffer = io.BytesIO()
            sf.write(buffer, audio_data, sample_rate, format="WAV")
            buffer.seek(0)
            return Response(content=buffer.read(), media_type="audio/wav")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
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

def generate_full_audio_sync(request: SpeechRequest):
    pipeline = get_pipeline(request.model)
    # Smart Default Voice
    voice = request.voice if request.voice else ("hf_alpha" if "hi" in request.model.lower() else "af_heart")
    
    generator = pipeline(request.input, voice=voice, speed=request.speed)
    audio_chunks = [audio for _, _, audio in generator if audio is not None]
    
    if not audio_chunks:
        raise ValueError("Audio generation failed")
        
    return np.concatenate(audio_chunks), 24000

def split_text(text: str):
    """
    Advanced splitting logic to minimize TTFB. 
    Splits by sentences and major pauses to start streaming audio ASAP.
    """
    # Split by [.!?] followed by space, or by newlines, or by semicolons
    segments = re.split(r'(?<=[.!?])\s+|\n+|(?<=;)\s+', text)
    return [s.strip() for s in segments if s.strip()]

# --- Optimized Streaming Implementation ---

def generate_voice_thread(loop, queue, text, model_name, voice, speed):
    try:
        pipeline = get_pipeline(model_name)
        sentences = split_text(text)
        for sentence in sentences:
            generator = pipeline(sentence, voice=voice, speed=speed)
            for _, _, audio in generator:
                if audio is not None:
                    # Faster conversion: Vectorized scale and cast
                    if torch.is_tensor(audio):
                        audio_int16 = (audio * 32767).to(torch.int16).cpu().numpy()
                    else:
                        audio_int16 = (audio * 32767).astype(np.int16)
                    loop.call_soon_threadsafe(queue.put_nowait, audio_int16.tobytes())
    except Exception as e:
        print(f"Error in background generation thread: {e}")
    finally:
        loop.call_soon_threadsafe(queue.put_nowait, None)

async def stream_audio_generator(request: SpeechRequest):
    loop = asyncio.get_running_loop()
    queue = asyncio.Queue()
    voice = request.voice if request.voice else ("hf_alpha" if "hi" in request.model.lower() else "af_heart")
    
    # Start generation thread
    thread = threading.Thread(
        target=generate_voice_thread,
        args=(loop, queue, request.input, request.model, voice, request.speed or 1.0),
        daemon=True
    )
    thread.start()
    
    while True:
        chunk = await queue.get()
        if chunk is None:
            break
        yield chunk

async def pcm_to_mp3_stream(pcm_generator):
    """
    Transcode raw PCM (s16le, 24000Hz, mono) to MP3 on-the-fly using an async ffmpeg subprocess.
    """
    cmd = [
        'ffmpeg',
        '-y',
        '-f', 's16le',
        '-ar', '24000',
        '-ac', '1',
        '-i', 'pipe:0',
        '-f', 'mp3',
        '-acodec', 'libmp3lame',
        '-ab', '64k',
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
                await process.stdin.wait_closed()
            except Exception:
                pass

    writer_task = asyncio.create_task(write_to_stdin())

    try:
        while True:
            chunk = await process.stdout.read(4096)
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