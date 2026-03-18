#!/bin/bash
# Turnip VPN — Install Monitoring + fail2ban
# Run as root. Usage: bash install-monitoring.sh

set -e
RED='\033[0;31m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'; YELLOW='\033[1;33m'; BOLD='\033[1m'; NC='\033[0m'
info()    { echo -e "${CYAN}[INFO]${NC}  $1"; }
success() { echo -e "${GREEN}[OK]${NC}    $1"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $1"; }
error()   { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

[[ $EUID -ne 0 ]] && error "Run as root"

echo ""
echo -e "${BOLD}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║       Turnip VPN — Monitoring + fail2ban Setup       ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""

# ── Packages ──────────────────────────────────────────────────────────────────
info "Installing fail2ban and dependencies..."
apt-get update -qq
apt-get install -y -qq fail2ban python3-requests
pip3 install psutil paramiko requests --break-system-packages -q
success "Packages installed"

# ── fail2ban ──────────────────────────────────────────────────────────────────
info "Configuring fail2ban..."

# Parse the combined config file into separate fail2ban files
cat > /etc/fail2ban/filter.d/ike-auth.conf << 'EOF'
[INCLUDES]
before = common.conf

[Definition]
failregex = ^.*charon.*EAP method.*failed for peer \[<HOST>\].*$
            ^.*charon.*IKE_AUTH.*failed.*\[<HOST>\].*$
            ^.*charon.*authentication of '<HOST>' failed.*$

ignoreregex =

datepattern = %%b\s+%%d %%H:%%M:%%S
EOF

cat > /etc/fail2ban/jail.d/turnip.conf << 'EOF'
[ike-auth]
enabled   = true
filter    = ike-auth
logpath   = /var/log/charon.log
maxretry  = 5
findtime  = 300
bantime   = 3600
action    = iptables-allports[name=ike-auth, protocol=all]

[sshd]
enabled  = true
maxretry = 4
findtime = 300
bantime  = 7200
EOF

systemctl enable fail2ban
systemctl restart fail2ban
sleep 2
systemctl is-active --quiet fail2ban && success "fail2ban running" || warn "fail2ban may not have started"

# ── Deploy monitor ────────────────────────────────────────────────────────────
info "Deploying monitor daemon..."
cp monitor.py /opt/turnip/monitor.py
chmod 600 /opt/turnip/monitor.py

# ── Telegram setup prompt ─────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}Optional: Telegram alerts${NC}"
echo -e "To receive alerts on Telegram:"
echo -e "  1. Message @BotFather → /newbot → copy the token"
echo -e "  2. Message @userinfobot → copy your chat ID"
echo ""
echo -e "Add to /opt/turnip/.env:"
echo -e "  TELEGRAM_BOT_TOKEN=your_bot_token"
echo -e "  TELEGRAM_CHAT_ID=your_chat_id"
echo -e "  ALERT_EMAIL=you@email.com"
echo ""

# ── Systemd service ───────────────────────────────────────────────────────────
info "Creating monitor systemd service..."
cat > /etc/systemd/system/turnip-monitor.service << 'EOF'
[Unit]
Description=Turnip VPN Monitor
After=network.target strongswan-starter.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/turnip
EnvironmentFile=/opt/turnip/.env
ExecStart=/usr/bin/python3 /opt/turnip/monitor.py
Restart=always
RestartSec=10
StandardOutput=append:/var/log/turnip-monitor.log
StandardError=append:/var/log/turnip-monitor.log

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable turnip-monitor
systemctl restart turnip-monitor
sleep 2
systemctl is-active --quiet turnip-monitor && success "Monitor daemon running" || warn "Monitor may not have started — check .env"

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${GREEN}║         MONITORING + FAIL2BAN SETUP COMPLETE ✓           ║${NC}"
echo -e "${BOLD}${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BOLD}fail2ban status:${NC}"
echo -e "  fail2ban-client status ike-auth"
echo -e "  fail2ban-client status sshd"
echo ""
echo -e "${BOLD}Monitor logs:${NC}"
echo -e "  tail -f /var/log/turnip-monitor.log"
echo ""
echo -e "${BOLD}View banned IPs:${NC}"
echo -e "  fail2ban-client banned"
echo ""
echo -e "${BOLD}Unban an IP:${NC}"
echo -e "  fail2ban-client set ike-auth unbanip <IP>"
echo ""
