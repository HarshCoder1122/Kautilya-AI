# ============================================================================
#  KautilyaClaw — OpenClaw on Kautilya models, containerized for 24/7 hosting.
# ============================================================================
FROM node:24-bookworm-slim

# gettext-base → envsubst; tini → clean PID 1 signal handling for the daemon.
RUN apt-get update \
 && apt-get install -y --no-install-recommends gettext-base tini ca-certificates \
 && rm -rf /var/lib/apt/lists/*

RUN npm install -g openclaw@latest

# OpenClaw stores config + state under $HOME/.openclaw — mount this as a volume
# so memory, skills, and channel sessions (WhatsApp login) survive restarts.
ENV HOME=/data
WORKDIR /app

COPY openclaw.json.template /app/openclaw.json.template
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Gateway / dashboard port.
EXPOSE 18789

VOLUME ["/data/.openclaw"]

ENTRYPOINT ["/usr/bin/tini", "--", "/app/entrypoint.sh"]
