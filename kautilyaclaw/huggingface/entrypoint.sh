#!/usr/bin/env bash
# KautilyaClaw on Hugging Face — render config, pick a writable state dir, run gateway.
set -euo pipefail

# Prefer HF persistent storage (/data, owned by uid 1000 when the Space has it
# enabled) so WhatsApp login + memory survive restarts. If persistent storage
# is OFF, /data isn't writable → fall back to ephemeral $HOME (sessions reset
# on every restart; Telegram still works fine since it needs no saved login).
if mkdir -p /data/.openclaw 2>/dev/null; then
  ln -sfn /data/.openclaw "$HOME/.openclaw"
  echo "[KautilyaClaw] state dir: /data/.openclaw (persistent)"
else
  mkdir -p "$HOME/.openclaw"
  echo "[KautilyaClaw] state dir: $HOME/.openclaw (EPHEMERAL — enable HF persistent storage to keep WhatsApp login)"
fi

# Secrets come from HF Space Settings → Secrets (injected as env vars).
envsubst < "$HOME/app/openclaw.json.template" > "$HOME/.openclaw/openclaw.json"
echo "[KautilyaClaw] config rendered → $HOME/.openclaw/openclaw.json"

# Gateway auth token (protects the dashboard). Auto-generate if not provided.
TOKEN="${OPENCLAW_GATEWAY_TOKEN:-$(cat /proc/sys/kernel/random/uuid)}"
PORT="${OPENCLAW_PORT:-18789}"

# Headless launch (verified flags): --allow-unconfigured skips interactive
# onboarding, --bind lan binds 0.0.0.0 so HF can route to it. The config we
# rendered above (Kautilya provider + channels) is still loaded from
# ~/.openclaw/openclaw.json.
echo "[KautilyaClaw] starting gateway on 0.0.0.0:$PORT"
exec openclaw gateway --allow-unconfigured --bind lan --auth token --token "$TOKEN" --port "$PORT"
