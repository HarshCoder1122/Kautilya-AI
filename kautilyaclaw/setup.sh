#!/usr/bin/env bash
# ============================================================================
#  KautilyaClaw — one-command bare-VPS bootstrap (Ubuntu/Debian).
#  Installs Node 22+, OpenClaw, pm2, renders config from .env, and starts the
#  gateway 24/7 (auto-restart + survives reboot).
#
#  Usage:
#     cp .env.example .env && nano .env      # fill in your values
#     bash setup.sh
# ============================================================================
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

say() { printf '\033[1;34m[KautilyaClaw]\033[0m %s\n' "$*"; }
die() { printf '\033[1;31m[KautilyaClaw] ERROR:\033[0m %s\n' "$*" >&2; exit 1; }

[ -f .env ] || die "No .env found. Run: cp .env.example .env  then edit it."

# Load .env (export every var so envsubst + OpenClaw both see them).
set -a; . ./.env; set +a

[ -n "${KAUTILYA_BASE_URL:-}" ]  || die "KAUTILYA_BASE_URL is empty in .env"
[ -n "${KAUTILYA_API_KEY:-}" ]   || die "KAUTILYA_API_KEY is empty in .env"

# ---- 1. Node 22+ -----------------------------------------------------------
need_node=1
if command -v node >/dev/null 2>&1; then
  major="$(node -p 'process.versions.node.split(".")[0]')"
  [ "$major" -ge 22 ] && need_node=0
fi
if [ "$need_node" -eq 1 ]; then
  say "Installing Node.js 22 (NodeSource)…"
  curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
  sudo apt-get install -y nodejs
fi
say "Node $(node -v)"

# ---- 2. envsubst (gettext) -------------------------------------------------
command -v envsubst >/dev/null 2>&1 || { say "Installing gettext…"; sudo apt-get install -y gettext-base; }

# ---- 3. OpenClaw + pm2 -----------------------------------------------------
say "Installing openclaw + pm2 (global)…"
sudo npm install -g openclaw@latest pm2

# ---- 4. Render config to ~/.openclaw/openclaw.json -------------------------
mkdir -p "$HOME/.openclaw"
say "Rendering openclaw.json from template…"
envsubst < openclaw.json.template > "$HOME/.openclaw/openclaw.json"
say "Config written to $HOME/.openclaw/openclaw.json"

# ---- 5. Start the gateway 24/7 via pm2 -------------------------------------
# `openclaw gateway` runs the gateway in the foreground; pm2 keeps it alive.
# If your installed version names the command differently, run `openclaw --help`
# and edit the line below.
say "Starting gateway under pm2…"
pm2 delete kautilyaclaw >/dev/null 2>&1 || true
OPENCLAW_GATEWAY_TOKEN="${OPENCLAW_GATEWAY_TOKEN:-}" \
  pm2 start openclaw --name kautilyaclaw -- gateway
pm2 save
# Make pm2 (and the bot) come back after a server reboot.
pm2 startup systemd -u "$USER" --hp "$HOME" | tail -n 1 | bash || \
  say "Run the printed 'pm2 startup' command manually to enable boot-persistence."

say "✅ KautilyaClaw is live."
say "   Logs:        pm2 logs kautilyaclaw"
say "   Dashboard:   http://127.0.0.1:${OPENCLAW_PORT:-18789}/"
say "   Telegram:    message your @BotFather bot now."
say "   WhatsApp:    run 'openclaw channels login whatsapp' and scan the QR (see README)."
