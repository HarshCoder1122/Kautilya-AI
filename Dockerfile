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

# Expose the port (Koyeb/Cloud providers usually provide PORT env var)
EXPOSE 8000

# Start via start.sh which handles gunicorn and background workers
CMD ["sh", "start.sh"]
