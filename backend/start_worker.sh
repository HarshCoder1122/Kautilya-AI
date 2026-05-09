#!/bin/bash
# Start LiveKit Agent Worker — Single process SaaS mode
# Agent resolution is dynamic per-call via Firestore (room name or SIP DID lookup)
# Optimization: Force single-threaded execution to save memory
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1

echo "Starting Kautilya LiveKit Agent (High-Capacity Self-Healing Mode)..."

# Function to run worker with auto-restart
run_worker() {
    while true; do
        echo "[Self-Healing] Starting LiveKit Worker..."
        python livekit_agent.py start
        echo "[Self-Healing] Worker crashed or stopped! Restarting in 2 seconds..."
        sleep 2
    done
}

# Start 2 workers with auto-restart
run_worker &
run_worker
