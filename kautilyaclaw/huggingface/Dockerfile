# ============================================================================
#  KautilyaClaw — Hugging Face Docker Space variant.
#  Differences vs the VPS Dockerfile:
#    • Runs as non-root UID 1000 (HF requirement).
#    • Gateway binds 0.0.0.0 so HF's router can reach it.
#    • Sandbox is OFF (HF has no docker-in-docker) — safety via allowlists.
#    • State goes to /data (HF persistent storage) when available.
#  Deploy: create a *Docker* Space, copy this huggingface/ folder into it,
#  set secrets in Space Settings. See README.md (the Space card).
# ============================================================================
FROM node:24-bookworm-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends gettext-base tini ca-certificates \
 && rm -rf /var/lib/apt/lists/*

RUN npm install -g openclaw@latest

# HF Spaces execute the container as UID 1000.
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user
WORKDIR /home/user/app

COPY --chown=user:user openclaw.json.template ./openclaw.json.template
COPY --chown=user:user entrypoint.sh ./entrypoint.sh
RUN chmod +x ./entrypoint.sh

# Bind to all interfaces so HF can route to the gateway. Port 18789 must match
# `app_port` in the Space README front-matter.
ENV OPENCLAW_GATEWAY_BIND=custom:0.0.0.0
EXPOSE 18789

ENTRYPOINT ["/usr/bin/tini", "--", "/home/user/app/entrypoint.sh"]
