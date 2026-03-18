#!/bin/bash
# Turnip VPN — Install Payment Backend
# Run as root after install.sh and install-cockpit.sh
# Usage: bash install-payments.sh

set -e
RED='\033[0;31m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'
info()    { echo -e "${CYAN}[INFO]${NC}  $1"; }
success() { echo -e "${GREEN}[OK]${NC}    $1"; }
error()   { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

[[ $EUID -ne 0 ]] && error "Run as root"
[[ ! -f ".env" ]] && { cp .env.example .env; echo -e "${RED}[REQUIRED]${NC} Edit .env with your credentials first, then re-run."; exit 1; }

echo ""
echo -e "${BOLD}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║        Turnip VPN — Payment Backend Setup            ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""

# ── Install Python deps ───────────────────────────────────────────────────────
info "Installing Python dependencies..."
pip3 install flask gunicorn python-dotenv psutil sendgrid --break-system-packages -q
success "Dependencies installed"

# ── Deploy to /opt/turnip ─────────────────────────────────────────────
info "Deploying payment backend..."
mkdir -p /opt/turnip
cp webhook.py provisioner.py emailer.py database.py cron_expire.py /opt/turnip/
cp .env /opt/turnip/.env
chmod 600 /opt/turnip/.env
success "Files deployed to /opt/turnip/"

# ── Systemd service ───────────────────────────────────────────────────────────
info "Creating systemd service..."
cat > /etc/systemd/system/turnip-payments.service << 'EOF'
[Unit]
Description=Turnip VPN Payment Backend
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/turnip
EnvironmentFile=/opt/turnip/.env
ExecStart=/usr/bin/gunicorn -w 2 -b 0.0.0.0:8766 webhook:app
Restart=always
RestartSec=5
StandardOutput=append:/var/log/turnip-payments.log
StandardError=append:/var/log/turnip-payments.log

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable turnip-payments
systemctl restart turnip-payments
sleep 2
systemctl is-active --quiet turnip-payments && success "Payment service running on :8766" || error "Service failed — check: journalctl -u turnip-payments -n 30"

# ── Open firewall port (local only — don't expose to internet) ────────────────
# Port 8766 is Paystack-facing. Paystack sends webhooks TO your server.
# You need a public HTTPS URL. Use nginx + Let's Encrypt as reverse proxy.
info "Firewall: port 8766 kept internal (use nginx reverse proxy for Paystack)"

# ── Daily expiry cron ─────────────────────────────────────────────────────────
info "Installing daily expiry cron..."
CRON_LINE="0 2 * * * /usr/bin/python3 /opt/turnip/cron_expire.py >> /var/log/turnip-cron.log 2>&1"
(crontab -l 2>/dev/null | grep -v cron_expire.py; echo "$CRON_LINE") | crontab -
success "Cron installed (runs daily at 2:00 AM)"

# ── Initialise DB ─────────────────────────────────────────────────────────────
info "Initialising database..."
cd /opt/turnip && python3 -c "from database import db_init; db_init()"
success "Database ready at $(grep DB_PATH .env | cut -d= -f2)"

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${GREEN}║            PAYMENT BACKEND SETUP COMPLETE ✓              ║${NC}"
echo -e "${BOLD}${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BOLD}Webhook URL (register in Paystack dashboard):${NC}"
echo -e "  ${CYAN}https://YOUR_DOMAIN/webhook/paystack${NC}"
echo ""
echo -e "${BOLD}Next — set up nginx reverse proxy:${NC}"
echo -e "  apt install nginx certbot python3-certbot-nginx"
echo -e "  certbot --nginx -d YOUR_DOMAIN"
echo -e "  # Then proxy /webhook/paystack → http://127.0.0.1:8766"
echo ""
echo -e "${BOLD}Register webhook in Paystack:${NC}"
echo -e "  Dashboard → Settings → API Keys & Webhooks"
echo -e "  Webhook URL: https://YOUR_DOMAIN/webhook/paystack"
echo ""
echo -e "${BOLD}Test it:${NC}"
echo -e "  curl http://127.0.0.1:8766/health"
echo ""
echo -e "${BOLD}Logs:${NC}"
echo -e "  tail -f /var/log/turnip-payments.log"
echo -e "  tail -f /var/log/turnip-cron.log"
echo ""
