#!/usr/bin/env bash
# vps_deploy.sh — Deploy APK FUD Bot v8 as a private backend service
#
# Runs ONE service on the VPS: the Python Telegram bot.
# NO web server, NO public ports, NO Node.js.
# All GitHub communication goes through the GitHub API (GITHUB_EMULATOR_PAT).
#
# USAGE (run as root on your Ubuntu/Debian VPS):
#   bash vps_deploy.sh
#
# REQUIRED (prompted if not set):
#   TELEGRAM_TOKEN        — your Telegram bot token
#   GITHUB_EMULATOR_PAT   — GitHub PAT with repo + workflow scopes
#   NP_MANAGER_EMAIL      — NP Manager account email
#   NP_MANAGER_PASS       — NP Manager account password
#
# OPTIONAL:
#   VT_API_KEY            — VirusTotal API key
#   ADMIN_USER_IDS        — comma-separated Telegram user IDs
#
# Re-run any time to upgrade (rsyncs new code, restarts service).

set -euo pipefail

DEPLOY_DIR="/opt/apk-fud-bot"
SERVICE="apk-fud-bot"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
ok()   { echo -e "${GREEN}[✓]${NC} $*"; }
info() { echo -e "${YELLOW}[→]${NC} $*"; }
err()  { echo -e "${RED}[✗]${NC} $*"; exit 1; }

echo ""
echo "═══════════════════════════════════════"
echo "  APK FUD Bot v8 — VPS Deploy"
echo "  Private backend, no public ports"
echo "═══════════════════════════════════════"
echo ""

[[ "$(id -u)" != "0" ]] && err "Run as root: sudo bash vps_deploy.sh"

# ── 1. System packages ────────────────────────────────────────────────────────
info "[1/6] Installing system packages..."
apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
    python3 python3-pip \
    openjdk-17-jre-headless \
    zipalign apksigner \
    curl wget rsync unzip 2>/dev/null || true

# apktool — try apt first, fallback to manual install
if ! command -v apktool &>/dev/null; then
    apt-get install -y -qq apktool 2>/dev/null || {
        info "Installing apktool manually..."
        mkdir -p /usr/local/lib
        wget -q "https://github.com/iBotPeaches/Apktool/releases/download/v2.9.3/apktool_2.9.3.jar" \
            -O /usr/local/lib/apktool.jar
        cat > /usr/local/bin/apktool <<'EOF'
#!/bin/bash
exec java -jar /usr/local/lib/apktool.jar "$@"
EOF
        chmod +x /usr/local/bin/apktool
    }
fi
ok "System packages ready (java: $(java -version 2>&1 | head -1 | awk '{print $3}' | tr -d '"'))"

# ── 2. Python packages ────────────────────────────────────────────────────────
info "[2/6] Installing Python packages..."
pip3 install -q --upgrade pip 2>/dev/null || true
if [[ -f "${SCRIPT_DIR}/requirements.txt" ]]; then
    pip3 install -q -r "${SCRIPT_DIR}/requirements.txt"
else
    pip3 install -q \
        "python-telegram-bot[job-queue]>=21" \
        "requests>=2.31" \
        "Pillow>=10"
fi
ok "Python packages installed"

# ── 3. Deploy code ────────────────────────────────────────────────────────────
info "[3/6] Deploying code to ${DEPLOY_DIR}..."
mkdir -p "$DEPLOY_DIR"

rsync -a --delete \
    --exclude='.git' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='node_modules' \
    --exclude='artifacts' \
    --exclude='.local' \
    --exclude='.agents' \
    --exclude='input/*' \
    --exclude='output/*' \
    --exclude='temp/*' \
    --exclude='logs/*' \
    --exclude='bot_session.json' \
    --exclude='pipeline_jobs.json' \
    "${SCRIPT_DIR}/" "${DEPLOY_DIR}/"

# Make android tool binaries executable
[[ -d "${DEPLOY_DIR}/android-tools-bin" ]] && \
    find "${DEPLOY_DIR}/android-tools-bin" -type f -exec chmod +x {} \;

ok "Code deployed"

# ── 4. Write .env ─────────────────────────────────────────────────────────────
info "[4/6] Writing secrets..."
ENV_FILE="${DEPLOY_DIR}/.env"

load() { [[ -f "$ENV_FILE" ]] && grep "^${1}=" "$ENV_FILE" 2>/dev/null | cut -d= -f2- || echo ""; }

TELEGRAM_TOKEN="${TELEGRAM_TOKEN:-$(load TELEGRAM_TOKEN)}"
GITHUB_EMULATOR_PAT="${GITHUB_EMULATOR_PAT:-$(load GITHUB_EMULATOR_PAT)}"
NP_MANAGER_EMAIL="${NP_MANAGER_EMAIL:-$(load NP_MANAGER_EMAIL)}"
NP_MANAGER_PASS="${NP_MANAGER_PASS:-$(load NP_MANAGER_PASS)}"
VT_API_KEY="${VT_API_KEY:-$(load VT_API_KEY)}"
ADMIN_USER_IDS="${ADMIN_USER_IDS:-$(load ADMIN_USER_IDS)}"

echo ""
[[ -z "$TELEGRAM_TOKEN"      ]] && { read -rsp "  TELEGRAM_TOKEN: "      TELEGRAM_TOKEN;      echo; }
[[ -z "$GITHUB_EMULATOR_PAT" ]] && { read -rsp "  GITHUB_EMULATOR_PAT: " GITHUB_EMULATOR_PAT; echo; }
[[ -z "$NP_MANAGER_EMAIL"    ]] && { read -rp  "  NP_MANAGER_EMAIL: "    NP_MANAGER_EMAIL; }
[[ -z "$NP_MANAGER_PASS"     ]] && { read -rsp "  NP_MANAGER_PASS: "     NP_MANAGER_PASS;     echo; }

cat > "$ENV_FILE" <<EOF
TELEGRAM_TOKEN=${TELEGRAM_TOKEN}
GITHUB_EMULATOR_PAT=${GITHUB_EMULATOR_PAT}
NP_MANAGER_EMAIL=${NP_MANAGER_EMAIL}
NP_MANAGER_PASS=${NP_MANAGER_PASS}
VT_API_KEY=${VT_API_KEY}
ADMIN_USER_IDS=${ADMIN_USER_IDS}
BOT_BASE_DIR=${DEPLOY_DIR}
EOF
chmod 600 "$ENV_FILE"
ok ".env written (chmod 600 — secrets protected)"

# ── 5. Create data directories ────────────────────────────────────────────────
info "[5/6] Creating data directories..."
for d in input output temp logs dropper clone tool_apks; do
    mkdir -p "${DEPLOY_DIR}/${d}"
done
ok "Directories ready"

# ── 6. Install & start systemd service ───────────────────────────────────────
info "[6/6] Installing systemd service..."

cat > "/etc/systemd/system/${SERVICE}.service" <<EOF
[Unit]
Description=APK FUD Bot v8 — Telegram backend
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=${DEPLOY_DIR}
EnvironmentFile=${DEPLOY_DIR}/.env
Environment="PATH=${DEPLOY_DIR}/android-tools-bin:/usr/local/bin:/usr/bin:/bin"
Environment="BOT_BASE_DIR=${DEPLOY_DIR}"
ExecStart=/usr/bin/python3 ${DEPLOY_DIR}/bot.py
Restart=always
RestartSec=10
StartLimitIntervalSec=0
TimeoutStopSec=30
StandardOutput=journal
StandardError=journal
SyslogIdentifier=${SERVICE}

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable "$SERVICE"
systemctl restart "$SERVICE"
sleep 3

if systemctl is-active --quiet "$SERVICE"; then
    ok "Service is RUNNING"
else
    err "Service failed to start. Check logs: journalctl -u ${SERVICE} -n 50"
fi

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════"
echo "  Deployed! Bot is live 24/7"
echo "═══════════════════════════════════════"
echo ""
echo "  No web server, no public ports."
echo "  Bot ↔ Telegram ↔ GitHub Actions only."
echo ""
echo "  journalctl -u ${SERVICE} -f    # live logs"
echo "  systemctl restart ${SERVICE}   # restart"
echo "  systemctl stop ${SERVICE}      # stop"
echo ""
echo "  To upgrade: rsync new code here and re-run this script."
echo ""
