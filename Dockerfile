FROM python:3.11-slim

# Install system dependencies for audio/VAD
RUN apt-get update && apt-get install -y \
    build-essential \
    python3-dev \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Environment variables for thread optimization
ENV OMP_NUM_THREADS=1
ENV MKL_NUM_THREADS=1
ENV PYTHONUNBUFFERED=1

# Expose port 7860 for Hugging Face health check (even if we don't serve a UI)
# We use a tiny python command to listen on the port while the agent runs
CMD python -m http.server 7860 & python livekit_agent.py start
