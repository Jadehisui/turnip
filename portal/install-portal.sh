#!/bin/bash
# Turnip VPN — Install Customer Portal
# Run as root after install-payments.sh
# Usage: bash install-portal.sh

set -e
RED='\033[0;31m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'
info()    { echo -e "${CYAN}[INFO]${NC}  $1"; }
success() { echo -e "${GREEN}[OK]${NC}    $1"; }
error()   { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

[[ $EUID -ne 0 ]] && error "Run as root"
[[ ! -f "/opt/turnip/.env" ]] && error "Run install-payments.sh first — .env not found"

echo ""
echo -e "${BOLD}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║         Turnip VPN — Customer Portal Setup           ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""

# ── Remove old Paystack public key prompt (now using Lemon Squeezy) ─────────
# Add portal secret key to .env if not present
if ! grep -q "PORTAL_SECRET_KEY" /opt/turnip/.env; then
    PORTAL_KEY=$(openssl rand -hex 32)
    echo "PORTAL_SECRET_KEY=${PORTAL_KEY}" >> /opt/turnip/.env
    info "Portal secret key generated"
fi

# ── Deploy portal ─────────────────────────────────────────────────────────────
info "Deploying portal..."
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cp portal.py /opt/turnip/portal.py
cp -r "${SCRIPT_DIR}/../backend/crypto_payments.py" /opt/turnip/
success "portal.py deployed"

# ── Systemd service ───────────────────────────────────────────────────────────
info "Creating systemd service..."
cat > /etc/systemd/system/turnip-portal.service << 'EOF'
[Unit]
Description=Turnip VPN Customer Portal
After=network.target turnip-payments.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/turnip
EnvironmentFile=/opt/turnip/.env
ExecStart=/usr/bin/gunicorn -w 2 -b 0.0.0.0:8767 portal:app
Restart=always
RestartSec=5
StandardOutput=append:/var/log/turnip-portal.log
StandardError=append:/var/log/turnip-portal.log

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable turnip-portal
systemctl restart turnip-portal
sleep 2
systemctl is-active --quiet turnip-portal && success "Portal running on :8767" || error "Portal failed — check: journalctl -u turnip-portal -n 30"

# ── Nginx config ──────────────────────────────────────────────────────────────
info "Writing nginx config..."
DOMAIN=$(grep VPN_SERVER_ADDR /opt/turnip/.env | cut -d= -f2)

cat > /etc/nginx/sites-available/turnip << NGINX
server {
    listen 80;
    server_name ${DOMAIN};

    root /opt/turnip/frontend/dist;
    index index.html;

    location /webhook/lemonsqueezy {
        proxy_pass       http://127.0.0.1:8766;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 30s;
    }

    location /webhook/nowpayments {
        proxy_pass       http://127.0.0.1:8766;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 30s;
    }

    location ~ ^/(login|logout|dashboard|admin|download|api|pricing|health) {
        proxy_pass       http://127.0.0.1:8767;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 30s;
    }

    location / {
        try_files \$uri \$uri/ /index.html;
    }
}
NGINX

ln -sf /etc/nginx/sites-available/turnip /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx
success "Nginx configured for ${DOMAIN}"

# ── SSL ───────────────────────────────────────────────────────────────────────
info "Installing SSL certificate..."
apt-get install -y -qq certbot python3-certbot-nginx
certbot --nginx -d "${DOMAIN}" --non-interactive --agree-tos --email "admin@${DOMAIN}" --redirect || \
  warn "Certbot failed — run manually: certbot --nginx -d ${DOMAIN}"

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${GREEN}║           CUSTOMER PORTAL SETUP COMPLETE ✓               ║${NC}"
echo -e "${BOLD}${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BOLD}Customer portal:${NC}    ${CYAN}https://${DOMAIN}/${NC}"
echo -e "${BOLD}Pricing page:${NC}       ${CYAN}https://${DOMAIN}/pricing${NC}"
echo -e "${BOLD}Paystack webhook:${NC}   ${CYAN}https://${DOMAIN}/webhook/paystack${NC}"
echo ""
echo -e "${BOLD}Logs:${NC}"
echo -e "  tail -f /var/log/turnip-portal.log"
echo -e "  tail -f /var/log/turnip-payments.log"
echo ""
