# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV HOME=/home/user
ENV HF_HOME=$HOME/.cache/huggingface

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    espeak-ng \
    libsndfile1 \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Create a non-root user
RUN useradd -m -u 1000 user
RUN mkdir -p $HF_HOME && chown -R user:user $HOME

# Copy the requirements file and install dependencies as ROOT
# (kokoro-onnx + onnxruntime included → fast ONNX engine; runtime still falls
#  back to the PyTorch pipeline if the ONNX model files are missing.)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Fix permissions for /app
RUN chown -R user:user /app

# Switch to non-root user
USER user
ENV PATH=$HOME/.local/bin:$PATH

# --- Model Caching ---
COPY cache_models.py .
RUN python cache_models.py && rm cache_models.py
# Prevent Hub connectivity checks on every restart — models are already cached
ENV HF_HUB_OFFLINE=1
ENV TRANSFORMERS_OFFLINE=1
# --- End Caching ---

# Copy the application code
COPY --chown=user . .

# Expose the port
EXPOSE 7860

# Command to run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
