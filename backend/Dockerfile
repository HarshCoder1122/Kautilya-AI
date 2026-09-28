FROM python:3.11-slim

# Install system dependencies for audio/VAD and Node.js for MCP
RUN apt-get update && apt-get install -y \
    build-essential \
    python3-dev \
    ffmpeg \
    curl \
    fonts-dejavu-core \
    fonts-noto-core \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install global MCP servers as root to make them globally available
RUN npm install -g @modelcontextprotocol/server-github @modelcontextprotocol/server-sequential-thinking

# System libraries Chromium needs at runtime (Kautilya Computer's live
# browsing tool, services/browser_service.py). Installed as ROOT via
# Playwright's own dependency-resolver (`install-deps`) rather than a
# hand-maintained apt package list, so it stays correct for whatever Debian
# base this image is on. A throwaway pip install just to reach that CLI —
# the real `playwright` the app imports is installed later, per-user, from
# requirements.txt; only the system .so libraries from this step persist.
RUN pip install --no-cache-dir playwright \
    && playwright install-deps chromium \
    && pip uninstall -y playwright \
    && rm -rf /var/lib/apt/lists/*

# Use a non-root user for security (HF requirement)
RUN useradd -m -u 1000 user
USER user
ENV PATH="/home/user/.local/bin:$PATH"

WORKDIR /home/user/app

# Copy requirements and install. The trailing `playwright install chromium`
# downloads the BROWSER BINARY only (system .so libs were already installed
# as root above) — deliberately no --with-deps here, that would try to
# apt-get as this non-root user and fail.
COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt \
    && python -m playwright install chromium

# Copy source code
COPY --chown=user . .

# Environment variables for thread optimization
ENV OMP_NUM_THREADS=1
ENV MKL_NUM_THREADS=1
ENV PYTHONUNBUFFERED=1

# HF Space port
EXPOSE 7860

# Universal start command
CMD ["sh", "start.sh"]
