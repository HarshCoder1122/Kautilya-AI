#!/bin/bash
# Kautilya AI — Backend Startup Script
# Optimized for HuggingFace Spaces & Koyeb

# 1. Performance Optimization
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1

# 2. Start Background Worker (if exists)
if [ -f "campaign_worker.py" ]; then
    echo "[START] Launching background campaign worker..."
    python3 campaign_worker.py &
fi

# 3. Detect Port (HF defaults to 7860, Koyeb uses $PORT)
TARGET_PORT=${PORT:-7860}

echo "[START] Launching Flask API on port $TARGET_PORT..."

# 4. Start Gunicorn
# Concurrency strategy: SSE streaming is I/O-bound (most time waiting on
# upstream LLM tokens), so threads matter more than processes.
#   workers=4, threads=16  →  up to 64 concurrent chat streams
# Tunables overridable via env: GUNICORN_WORKERS / GUNICORN_THREADS.
GUNICORN_WORKERS=${GUNICORN_WORKERS:-4}
GUNICORN_THREADS=${GUNICORN_THREADS:-16}

exec gunicorn app:app \
    --bind 0.0.0.0:$TARGET_PORT \
    --workers $GUNICORN_WORKERS \
    --threads $GUNICORN_THREADS \
    --timeout 600 \
    --graceful-timeout 30 \
    --keep-alive 75 \
    --worker-class gthread \
    --worker-tmp-dir /dev/shm \
    --max-requests 2000 \
    --max-requests-jitter 200 \
    --access-logfile - \
    --error-logfile -
