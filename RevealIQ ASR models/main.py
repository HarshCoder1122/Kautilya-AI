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

# Optimize for CPU performance
if device == "cpu":
    # Set CPU threads to use up to 4 cores for optimal performance on HF free/pro tiers
    import os
    cores = min(4, os.cpu_count() or 2)
    torch.set_num_threads(cores)
    print(f"DEBUG: Set PyTorch CPU threads to {cores}")
    
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

def trim_silence(audio, sample_rate=24000, threshold=0.005, keep_start_ms=20, keep_end_ms=40):
    """
    Trim leading and trailing silence from float32 audio.
    Keeps a small cushion of silence (keep_start_ms at start, keep_end_ms at end)
    so it doesn't sound completely cut off, preventing long breaks after punctuation.
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
    pipeline = get_pipeline(request.model)
    # Smart Default Voice
    voice = request.voice if request.voice else ("hf_alpha" if "hi" in request.model.lower() else "af_heart")
    
    generator = pipeline(request.input, voice=voice, speed=request.speed)
    audio_chunks = []
    for _, _, audio in generator:
        if audio is not None:
            trimmed = trim_silence(audio)
            audio_chunks.append(trimmed)
    
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


# --- Ultra-Fast Streaming Implementation ---

# Pre-compiled regex for text splitting (faster than re.split)
TEXT_SPLIT_PATTERN = re.compile(r'(?<=[.!?,;:])\s+|\n+')

def generate_voice_thread(loop, queue, text, model_name, voice, speed):
    try:
        pipeline = get_pipeline(model_name)
        # Pre-split text for faster streaming using pre-compiled regex
        sentences = [s.strip() for s in TEXT_SPLIT_PATTERN.split(text) if s.strip()]
        
        with torch.inference_mode():
            # Pre-allocate audio buffer for better performance
            for sentence in sentences:
                # Process in smaller chunks for real-time streaming
                generator = pipeline(sentence, voice=voice, speed=speed)
                for _, _, audio in generator:
                    if audio is not None:
                        # Trim silence from the audio chunk to keep the flow continuous
                        audio = trim_silence(audio)
                        # Ultra-fast conversion: Direct memory copy
                        if torch.is_tensor(audio):
                            # Use faster tensor operations with pre-determined device
                            audio_int16 = (audio * 32767).to(torch.int16).cpu().numpy()
                        else:
                            audio_int16 = (audio * 32767).astype(np.int16)
                        
                        # Stream immediately without queue overhead
                        loop.call_soon_threadsafe(queue.put_nowait, audio_int16.tobytes())
                    
        # Signal end of stream
        loop.call_soon_threadsafe(queue.put_nowait, None)
    except Exception as e:
        print(f"Error in background generation thread: {e}")
        loop.call_soon_threadsafe(queue.put_nowait, None)

async def stream_audio_generator(request: SpeechRequest):
    loop = asyncio.get_running_loop()
    queue = asyncio.Queue(maxsize=20)  # Larger queue allows pre-generation of subsequent sentences to prevent playback gaps
    voice = request.voice if request.voice else ("hf_alpha" if "hi" in request.model.lower() else "af_heart")
    
    # Start ultra-fast generation thread with pre-compiled text
    thread = threading.Thread(
        target=generate_voice_thread,
        args=(loop, queue, request.input, request.model, voice, request.speed or 1.0),
        daemon=True
    )
    thread.start()
    
    # Ultra-fast streaming loop with minimal latency
    while True:
        try:
            # Non-blocking get with minimal timeout for maximum responsiveness
            chunk = await asyncio.wait_for(queue.get(), timeout=0.01)
            if chunk is None:
                break
            yield chunk
        except asyncio.TimeoutError:
            # Continue loop on timeout
            continue

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