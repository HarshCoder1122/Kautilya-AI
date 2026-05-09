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
exec gunicorn app:app \
    --bind 0.0.0.0:$TARGET_PORT \
    --workers 2 \
    --threads 4 \
    --timeout 600 \
    --worker-class gthread \
    --access-logfile - \
    --error-logfile -
