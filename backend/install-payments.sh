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
pip3 install flask gunicorn python-dotenv psutil sendgrid requests siwe eth-account --break-system-packages --ignore-installed -q
success "Dependencies installed"

# ── Deploy to /opt/turnip ─────────────────────────────────────────────
info "Deploying payment backend..."
mkdir -p /opt/turnip
cp webhook.py provisioner.py emailer.py database.py cron_expire.py crypto_payments.py multiserver.py servers.json /opt/turnip/
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
ExecStart=/usr/bin/python3 -m gunicorn -w 2 -b 0.0.0.0:8766 webhook:app
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
# Port 8766 receives webhooks from Lemon Squeezy and NOWPayments.
# You need a public HTTPS URL. Use nginx + Let's Encrypt as reverse proxy.
info "Firewall: port 8766 kept internal (proxied via nginx)"

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
echo -e "${BOLD}Webhook URLs (register in dashboards):${NC}"
echo -e "  Lemon Squeezy : ${CYAN}https://YOUR_DOMAIN/webhook/lemonsqueezy${NC}"
echo -e "  NOWPayments   : ${CYAN}https://YOUR_DOMAIN/webhook/nowpayments${NC}"
echo ""
echo -e "${BOLD}Next — set up nginx reverse proxy:${NC}"
echo -e "  apt install nginx certbot python3-certbot-nginx"
echo -e "  certbot --nginx -d YOUR_DOMAIN"
echo ""
echo -e "${BOLD}Register Lemon Squeezy webhook:${NC}"
echo -e "  Dashboard → Settings → Webhooks → Add endpoint"
echo -e "  URL: https://YOUR_DOMAIN/webhook/lemonsqueezy"
echo -e "  Events: order_created, subscription_created, subscription_payment_success,"
echo -e "          subscription_cancelled, subscription_expired"
echo ""
echo -e "${BOLD}Register NOWPayments IPN:${NC}"
echo -e "  Dashboard → Store Settings → IPN Settings"
echo -e "  Callback URL: https://YOUR_DOMAIN/webhook/nowpayments"
echo ""
echo -e "${BOLD}Test it:${NC}"
echo -e "  curl http://127.0.0.1:8766/health"
echo ""
echo -e "${BOLD}Logs:${NC}"
echo -e "  tail -f /var/log/turnip-payments.log"
echo -e "  tail -f /var/log/turnip-cron.log"
echo ""
