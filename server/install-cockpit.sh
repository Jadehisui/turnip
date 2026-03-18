#!/bin/bash
# =============================================================================
# Turnip VPN — Cockpit + Firewall Setup
# Ubuntu 22.04 | Run as root after install.sh
# Access Cockpit at: https://YOUR_SERVER_IP:9090
# =============================================================================

set -e
RED='\033[0;31m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'
YELLOW='\033[1;33m'; BOLD='\033[1m'; NC='\033[0m'

info()    { echo -e "${CYAN}[INFO]${NC}  $1"; }
success() { echo -e "${GREEN}[OK]${NC}    $1"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $1"; }
error()   { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

[[ $EUID -ne 0 ]] && error "Run as root"

MAX_USERS="${1:-80}"

echo ""
echo -e "${BOLD}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║       Turnip VPN — Cockpit + Firewall Setup          ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""

# ── 1. Install Cockpit ────────────────────────────────────────────────────────
info "Installing Cockpit..."
apt-get update -qq
apt-get install -y -qq \
    cockpit \
    cockpit-networkmanager \
    cockpit-storaged \
    cockpit-packagekit \
    firewalld \
    python3 \
    python3-pip \
    python3-flask \
    python3-psutil

success "Cockpit installed"

# ── 2. Configure firewalld ────────────────────────────────────────────────────
info "Configuring firewalld..."

systemctl enable firewalld
systemctl start firewalld

# Core VPN ports
firewall-cmd --permanent --add-service=ssh
firewall-cmd --permanent --add-port=500/udp      # IKE
firewall-cmd --permanent --add-port=4500/udp     # IKE NAT-T
firewall-cmd --permanent --add-port=9090/tcp     # Cockpit
firewall-cmd --permanent --add-port=8765/tcp     # VPN admin API
firewall-cmd --permanent --add-service=ipsec

# Enable masquerade for VPN subnet
firewall-cmd --permanent --add-masquerade
firewall-cmd --permanent --add-rich-rule='rule family="ipv4" source address="10.10.10.0/24" masquerade'

firewall-cmd --reload
success "Firewalld configured"

# ── 3. Enable Cockpit ─────────────────────────────────────────────────────────
info "Enabling Cockpit..."
systemctl enable --now cockpit.socket
success "Cockpit running on port 9090"

# ── 4. Install VPN Admin API ──────────────────────────────────────────────────
info "Installing VPN admin API..."

mkdir -p /opt/turnip
pip3 install flask psutil --quiet --break-system-packages 2>/dev/null || \
pip3 install flask psutil --quiet

cat > /opt/turnip/admin_api.py << 'PYEOF'
#!/usr/bin/env python3
"""
Turnip VPN — Admin API
Serves real-time server stats for the dashboard.
Runs on port 8765.
"""

import subprocess, re, os, json, time, psutil
from flask import Flask, jsonify, request, abort
from datetime import datetime

app = Flask(__name__)

SECRETS_FILE  = "/etc/ipsec.secrets"
MAX_USERS     = int(os.environ.get("MAX_USERS", "80"))
API_TOKEN     = os.environ.get("ADMIN_TOKEN", "changeme-set-in-env")

def require_token():
    token = request.headers.get("X-Admin-Token", "")
    if token != API_TOKEN:
        abort(401, "Unauthorized")

def get_vpn_users():
    """Parse EAP users from ipsec.secrets."""
    users = []
    try:
        with open(SECRETS_FILE) as f:
            for line in f:
                line = line.strip()
                m = re.match(r'^(\S+)\s*:\s*EAP\s+"([^"]+)"', line)
                if m:
                    users.append({"username": m.group(1)})
    except Exception:
        pass
    return users

def get_active_tunnels():
    """Parse active IKEv2 tunnels from ipsec status."""
    tunnels = []
    try:
        result = subprocess.run(
            ["ipsec", "statusall"],
            capture_output=True, text=True, timeout=5
        )
        for line in result.stdout.splitlines():
            # Match ESTABLISHED lines: user@ip[port] ESTABLISHED X minutes ago
            m = re.search(r'(\S+)\[(\d+)\]:.*ESTABLISHED\s+(.+?)(?:,|$)', line)
            if m:
                tunnels.append({
                    "id":       m.group(2),
                    "identity": m.group(1),
                    "since":    m.group(3).strip(),
                })
    except Exception:
        pass
    return tunnels

def get_system_stats():
    cpu    = psutil.cpu_percent(interval=0.5)
    mem    = psutil.virtual_memory()
    disk   = psutil.disk_usage("/")
    net_io = psutil.net_io_counters()
    uptime = int(time.time() - psutil.boot_time())
    return {
        "cpu_pct":       round(cpu, 1),
        "mem_used_gb":   round(mem.used  / 1e9, 2),
        "mem_total_gb":  round(mem.total / 1e9, 2),
        "mem_pct":       mem.percent,
        "disk_used_gb":  round(disk.used  / 1e9, 2),
        "disk_total_gb": round(disk.total / 1e9, 2),
        "disk_pct":      round(disk.percent, 1),
        "net_rx_gb":     round(net_io.bytes_recv / 1e9, 3),
        "net_tx_gb":     round(net_io.bytes_sent / 1e9, 3),
        "uptime_sec":    uptime,
    }

def get_strongswan_status():
    try:
        result = subprocess.run(
            ["systemctl", "is-active", "strongswan-starter"],
            capture_output=True, text=True, timeout=3
        )
        return result.stdout.strip() == "active"
    except Exception:
        return False

# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/api/status")
def status():
    require_token()
    users   = get_vpn_users()
    tunnels = get_active_tunnels()
    sys     = get_system_stats()
    return jsonify({
        "timestamp":       datetime.utcnow().isoformat() + "Z",
        "vpn_running":     get_strongswan_status(),
        "max_users":       MAX_USERS,
        "total_users":     len(users),
        "active_tunnels":  len(tunnels),
        "slots_remaining": MAX_USERS - len(users),
        "capacity_pct":    round(len(users) / MAX_USERS * 100, 1),
        "system":          sys,
        "tunnels":         tunnels,
    })

@app.route("/api/users")
def list_users():
    require_token()
    users   = get_vpn_users()
    tunnels = get_active_tunnels()
    active_ids = {t["identity"] for t in tunnels}
    for u in users:
        u["online"] = u["username"] in active_ids
    return jsonify({
        "users":       users,
        "total":       len(users),
        "online":      len(active_ids),
        "max":         MAX_USERS,
        "slots_left":  MAX_USERS - len(users),
    })

@app.route("/api/users", methods=["POST"])
def add_user():
    require_token()
    if len(get_vpn_users()) >= MAX_USERS:
        return jsonify({"error": f"Server full. Maximum {MAX_USERS} users reached."}), 429
    data = request.get_json()
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    if not username or not password:
        return jsonify({"error": "username and password required"}), 400
    if re.search(r'["\s\\]', username):
        return jsonify({"error": "invalid characters in username"}), 400
    users = get_vpn_users()
    if any(u["username"] == username for u in users):
        return jsonify({"error": "user already exists"}), 409
    with open(SECRETS_FILE, "a") as f:
        f.write(f'\n{username} : EAP "{password}"\n')
    subprocess.run(["ipsec", "secrets"], timeout=5)
    return jsonify({"ok": True, "username": username}), 201

@app.route("/api/users/<username>", methods=["DELETE"])
def delete_user(username):
    require_token()
    lines_before = open(SECRETS_FILE).readlines()
    lines_after  = [l for l in lines_before if not l.strip().startswith(f"{username} :")]
    if len(lines_before) == len(lines_after):
        return jsonify({"error": "user not found"}), 404
    with open(SECRETS_FILE, "w") as f:
        f.writelines(lines_after)
    subprocess.run(["ipsec", "secrets"], timeout=5)
    return jsonify({"ok": True, "deleted": username})

@app.route("/api/vpn/restart", methods=["POST"])
def restart_vpn():
    require_token()
    subprocess.run(["systemctl", "restart", "strongswan-starter"], timeout=15)
    return jsonify({"ok": True, "message": "StrongSwan restarting..."})

@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "service": "Turnip Admin API"})

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8765, debug=False)
PYEOF

chmod 600 /opt/turnip/admin_api.py

# ── 5. Generate admin token ───────────────────────────────────────────────────
ADMIN_TOKEN=$(openssl rand -hex 32)

# ── 6. Systemd service for the API ───────────────────────────────────────────
info "Creating admin API systemd service..."

cat > /etc/systemd/system/turnip-api.service << EOF
[Unit]
Description=Turnip VPN Admin API
After=network.target strongswan-starter.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/turnip
Environment=MAX_USERS=${MAX_USERS}
Environment=ADMIN_TOKEN=${ADMIN_TOKEN}
ExecStart=/usr/bin/python3 /opt/turnip/admin_api.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable turnip-api
systemctl restart turnip-api
sleep 2

if systemctl is-active --quiet turnip-api; then
    success "Admin API running on 127.0.0.1:8765"
else
    warn "Admin API may not have started — check: journalctl -u turnip-api -n 30"
fi

# ── 7. Save config ────────────────────────────────────────────────────────────
CONFIG_FILE="/opt/turnip/config.env"
cat > "${CONFIG_FILE}" << EOF
# Turnip VPN Admin Config
# Generated: $(date)
MAX_USERS=${MAX_USERS}
ADMIN_TOKEN=${ADMIN_TOKEN}
EOF
chmod 600 "${CONFIG_FILE}"
success "Config saved to ${CONFIG_FILE}"

# ── 8. Nginx reverse proxy for Cockpit (optional, if nginx installed) ─────────
if command -v nginx &> /dev/null; then
    info "Nginx detected — skipping (Cockpit runs standalone on :9090)"
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${GREEN}║              COCKPIT + FIREWALL SETUP COMPLETE ✓         ║${NC}"
echo -e "${BOLD}${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BOLD}Cockpit (server management):${NC}"
echo -e "  URL      : ${CYAN}https://$(curl -s ifconfig.me 2>/dev/null || echo YOUR_SERVER_IP):9090${NC}"
echo -e "  Login    : your Linux root / sudo user credentials"
echo ""
echo -e "${BOLD}VPN Admin API:${NC}"
echo -e "  URL      : ${CYAN}http://127.0.0.1:8765${NC} (local only)"
echo -e "  Token    : ${CYAN}${ADMIN_TOKEN}${NC}"
echo ""
echo -e "${BOLD}Max users set to:${NC} ${CYAN}${MAX_USERS}${NC}"
echo ""
echo -e "${BOLD}Firewall ports open:${NC}"
echo -e "  22/tcp   SSH"
echo -e "  500/udp  IKE"
echo -e "  4500/udp IKE NAT-T"
echo -e "  9090/tcp Cockpit"
echo -e "  8765/tcp Admin API (local only)"
echo ""
echo -e "${BOLD}Save your admin token:${NC}"
echo -e "  cat /opt/turnip/config.env"
echo ""
echo -e "${BOLD}Test the API:${NC}"
echo -e "  curl -H 'X-Admin-Token: ${ADMIN_TOKEN}' http://127.0.0.1:8765/api/status | python3 -m json.tool"
echo ""
