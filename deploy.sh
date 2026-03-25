#!/bin/bash
# =============================================================================
# Turnip VPN — Master Deploy Script
# Runs all install steps in the correct order on a fresh Ubuntu 22.04 VPS.
# Usage: sudo bash deploy.sh YOUR_DOMAIN_OR_IP
# =============================================================================

set -e
RED='\033[0;31m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'
YELLOW='\033[1;33m'; BOLD='\033[1m'; NC='\033[0m'

info()    { echo -e "${CYAN}[INFO]${NC}  $1"; }
success() { echo -e "${GREEN}[OK]${NC}    $1"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $1"; }
error()   { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }
step()    { echo -e "\n${BOLD}━━━ $1 ━━━${NC}"; }

[[ $EUID -ne 0 ]]  && error "Run as root: sudo bash deploy.sh YOUR_DOMAIN"
[[ -z "$1" ]]      && error "Usage: sudo bash deploy.sh YOUR_DOMAIN_OR_IP"

DOMAIN="$1"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo ""
echo -e "${BOLD}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║           Turnip VPN — Full Stack Deploy                 ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "Domain   : ${CYAN}${DOMAIN}${NC}"
echo -e "Date     : $(date)"
echo ""

# ── Pre-flight checks ─────────────────────────────────────────────────────────
step "Pre-flight"
[[ ! -f "${SCRIPT_DIR}/backend/.env" ]] && {
    cp "${SCRIPT_DIR}/backend/.env.example" "${SCRIPT_DIR}/backend/.env"
    warn ".env created from template. EDIT IT NOW before continuing."
    warn "  nano ${SCRIPT_DIR}/backend/.env"
    echo ""
    echo -e "Required values:"
    echo -e "  LEMONSQUEEZY_WEBHOOK_SECRET  — from LS dashboard → Settings → Webhooks"
    echo -e "  SMTP_USER / SMTP_PASS — your email credentials"
    echo -e "  VPN_SERVER_ADDR      — set to: ${DOMAIN}"
    echo ""
    read -p "Press ENTER after editing .env to continue..." _
}

# Inject domain into .env if not set
grep -q "^VPN_SERVER_ADDR=" "${SCRIPT_DIR}/backend/.env" || \
    echo "VPN_SERVER_ADDR=${DOMAIN}" >> "${SCRIPT_DIR}/backend/.env"
sed -i "s|^VPN_SERVER_ADDR=.*|VPN_SERVER_ADDR=${DOMAIN}|" "${SCRIPT_DIR}/backend/.env"

success "Pre-flight passed"

# ── Step 0: Build React frontend ─────────────────────────────────────────────
step "Step 0 — Build React frontend"
cd "${SCRIPT_DIR}/frontend"
if ! command -v node &>/dev/null; then
    info "Installing Node.js..."
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
    apt-get install -y nodejs
fi
npm install --silent
npm run build
mkdir -p /opt/turnip/frontend
cp -r dist /opt/turnip/frontend/dist
success "Frontend built and copied to /opt/turnip/frontend/dist"

# ── Step 1: VPN Server ────────────────────────────────────────────────────────
step "Step 1/5 — VPN Server (StrongSwan)"
cd "${SCRIPT_DIR}/server"
chmod +x *.sh
bash install.sh "${DOMAIN}"
success "VPN server ready"

# ── Step 2: Cockpit + Admin API ───────────────────────────────────────────────
step "Step 2/5 — Admin Panel + Cockpit"
bash install-cockpit.sh 80
success "Admin panel ready"

# ── Step 3: Payment Backend ───────────────────────────────────────────────────
step "Step 3/5 — Payment Backend"
cd "${SCRIPT_DIR}/backend"
cp "${SCRIPT_DIR}/backend/.env" /opt/turnip/.env
chmod +x install-payments.sh
bash install-payments.sh
success "Payment backend ready"

# ── Step 4: Customer Portal ───────────────────────────────────────────────────
step "Step 4/5 — Customer Portal"
cd "${SCRIPT_DIR}/portal"
chmod +x install-portal.sh
bash install-portal.sh
success "Customer portal ready"

# ── Step 5: Monitoring ────────────────────────────────────────────────────────
step "Step 5/5 — Monitoring + fail2ban"
cd "${SCRIPT_DIR}/monitoring"
chmod +x install-monitoring.sh
bash install-monitoring.sh
success "Monitoring ready"

# ── Copy landing page to nginx root ──────────────────────────────────────────
step "Landing page"
cp "${SCRIPT_DIR}/landing/index.html" /var/www/html/index.html 2>/dev/null || true

# ── Configure nginx to serve landing page at / ────────────────────────────────
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
    }

    location /webhook/nowpayments {
        proxy_pass       http://127.0.0.1:8766;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location ~ ^/(login|logout|dashboard|admin|download|api|health) {
        proxy_pass       http://127.0.0.1:8767;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location / {
        try_files \$uri \$uri/ /index.html;
    }
}
NGINX

ln -sf /etc/nginx/sites-available/turnip /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx
success "Landing page served at /"

# ── SSL ───────────────────────────────────────────────────────────────────────
step "SSL Certificate"
certbot --nginx -d "${DOMAIN}" --non-interactive --agree-tos \
    --email "admin@${DOMAIN}" --redirect 2>/dev/null && \
    success "SSL certificate installed" || \
    warn "Certbot failed — run manually: certbot --nginx -d ${DOMAIN}"

# ── Final summary ─────────────────────────────────────────────────────────────
ADMIN_TOKEN=$(grep ADMIN_TOKEN /opt/turnip/config.env 2>/dev/null | cut -d= -f2 || echo "see /opt/turnip/config.env")

echo ""
echo -e "${BOLD}${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${GREEN}║              SECUREFASTVPN DEPLOYED SUCCESSFULLY ✓           ║${NC}"
echo -e "${BOLD}${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BOLD}Live URLs:${NC}"
echo -e "  Landing page    : ${CYAN}https://${DOMAIN}/${NC}"
echo -e "  Customer portal : ${CYAN}https://${DOMAIN}/login${NC}"
echo -e "  Pricing         : ${CYAN}https://${DOMAIN}/pricing${NC}"
echo -e "  Cockpit         : ${CYAN}https://${DOMAIN}:9090${NC}"
echo ""
echo -e "${BOLD}Admin API token  :${NC} ${CYAN}${ADMIN_TOKEN}${NC}"
echo ""
echo -e "${BOLD}Register in Lemon Squeezy dashboard:${NC}"
echo -e "  Webhook URL: ${CYAN}https://${DOMAIN}/webhook/lemonsqueezy${NC}"
echo ""
echo -e "${BOLD}Running services:${NC}"
for svc in strongswan-starter turnip-api turnip-payments turnip-portal turnip-monitor fail2ban nginx; do
    if systemctl is-active --quiet "$svc" 2>/dev/null; then
        echo -e "  ${GREEN}●${NC} $svc"
    else
        echo -e "  ${RED}●${NC} $svc (inactive)"
    fi
done
echo ""
echo -e "${BOLD}Useful commands:${NC}"
echo -e "  ipsec status                           — VPN tunnel status"
echo -e "  bash server/adduser.sh name pass       — add VPN user"
echo -e "  fail2ban-client status ike-auth        — blocked IPs"
echo -e "  tail -f /var/log/turnip-*.log   — all logs"
echo ""
