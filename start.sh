# Force single-threaded execution for AI models to save memory
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1

# Start Automated Campaign Dialer in background (only if file exists)
if [ -f "campaign_worker.py" ]; then
    python campaign_worker.py &
fi

# Detect Environment and Start Correct Service
if [ -n "$HF_SPACE_ID" ]; then
    echo "[DEPLOY] Detected Hugging Face Space. Starting LiveKit Agent Worker..."
    # HF Health Check on 7860
    python -m http.server 7860 &
    # Start Agent
    python livekit_agent.py start
else
    echo "[DEPLOY] Detected Standard Cloud (Koyeb). Starting Web Server on port ${PORT:-8000}..."
    exec gunicorn app:app --bind 0.0.0.0:${PORT:-8000} --workers 2 --threads 4 --timeout 600 --worker-class gthread
fi

