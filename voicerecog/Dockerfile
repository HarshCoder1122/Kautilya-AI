# Kautilya RevealIQ STT — Nemotron 3.5 streaming ASR (ONNX INT4) on CPU
# Python 3.12: onnxruntime-genai 0.14.x (which has Nemotron ASR support) only
# ships cp311/cp312/cp313 linux wheels — there is NO cp310 wheel, so a 3.10
# base silently downgrades to an old build that can't parse the ASR config.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV HOME=/home/user
ENV HF_HOME=$HOME/.cache/huggingface
ENV ASR_MODEL_DIR=$HOME/asr_model

# ffmpeg → transcode any browser/upload format (webm/opus, mp3, m4a) to 16k mono
# wav. libsndfile1 → soundfile reads. git → HF hub on some transports.
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Non-root user (HF Spaces requirement)
RUN useradd -m -u 1000 user
RUN mkdir -p $HF_HOME $ASR_MODEL_DIR && chown -R user:user $HOME

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN chown -R user:user /app
USER user
ENV PATH=$HOME/.local/bin:$PATH

# --- Bake the model into the image so cold starts don't fetch ~800MB ---
COPY --chown=user cache_model.py .
RUN python cache_model.py
# Model is cached locally now — skip Hub connectivity checks on every restart.
ENV HF_HUB_OFFLINE=1
ENV TRANSFORMERS_OFFLINE=1
# --- End caching ---

COPY --chown=user . .

EXPOSE 7860
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]