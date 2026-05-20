FROM python:3.11-slim

# Install system dependencies for audio/VAD
RUN apt-get update && apt-get install -y \
    build-essential \
    python3-dev \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Use a non-root user for security (HF requirement)
RUN useradd -m -u 1000 user
USER user
ENV PATH="/home/user/.local/bin:$PATH"

WORKDIR /home/user/app

# Copy requirements and install
COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Copy source code
COPY --chown=user . .

# Environment variables for thread optimization
ENV OMP_NUM_THREADS=1
ENV MKL_NUM_THREADS=1
ENV PYTHONUNBUFFERED=1

# Run the LiveKit Agent in PRODUCTION mode.
# 'dev' watches files and self-restarts on signal 15, which kills sessions
# mid-call. 'start' is the stable production worker — handles reconnects.
CMD ["python3", "main.py", "start"]
