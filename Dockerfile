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

# Expose ports for HF (7860) and Koyeb (8000)
EXPOSE 7860
EXPOSE 8000

# Universal start command
CMD ["sh", "start.sh"]
