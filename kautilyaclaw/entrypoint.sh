#!/usr/bin/env bash
# Renders the OpenClaw config from env, then runs the gateway in the foreground
# (Docker PID 1). All ${VARS} come from the container environment (.env / compose).
set -euo pipefail

CONFIG_DIR="${HOME}/.openclaw"
mkdir -p "$CONFIG_DIR"

# Render config on every start so .env changes take effect on `docker compose up`.
# Existing channel sessions (WhatsApp QR login, memory) live elsewhere under
# .openclaw and are NOT overwritten — only openclaw.json is regenerated.
envsubst < /app/openclaw.json.template > "$CONFIG_DIR/openclaw.json"
echo "[KautilyaClaw] config rendered → $CONFIG_DIR/openclaw.json"

# Run the gateway. If your openclaw version uses a different subcommand,
# override the container command (see docker-compose.yml `command:`).
exec openclaw gateway
