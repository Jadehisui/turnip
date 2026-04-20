#!/bin/bash
# =============================================================================
# Turnip VPN — Live Server Diagnostic + Auto-Fix
# Run on an already-deployed VPN server if clients connect but have no internet.
# Usage: sudo bash diagnose-vpn.sh
# =============================================================================

RED='\033[0;31m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'
YELLOW='\033[1;33m'; BOLD='\033[1m'; NC='\033[0m'

ok()   { echo -e "${GREEN}[OK]${NC}    $1"; }
fail() { echo -e "${RED}[FAIL]${NC}  $1"; }
info() { echo -e "${CYAN}[INFO]${NC}  $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC}  $1"; }
fix()  { echo -e "${YELLOW}[FIX]${NC}   $1"; }

[[ $EUID -ne 0 ]] && { echo "Run as root: sudo bash diagnose-vpn.sh"; exit 1; }

echo ""
echo -e "${BOLD}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║        Turnip VPN — Internet Flow Diagnostic             ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""

VPN_SUBNET="10.10.10.0/24"
PRIMARY_IFACE=$(ip route show default | awk '/default/ {print $5}' | head -1)
SECRETS_FILE="/etc/ipsec.secrets"
IPSEC_CONF="/etc/ipsec.conf"
info "Primary interface : ${PRIMARY_IFACE}"
info "VPN subnet        : ${VPN_SUBNET}"
echo ""

FIXES_APPLIED=0

# ── 1. Kernel IP forwarding ───────────────────────────────────────────────────
echo -e "${BOLD}1. Kernel IP Forwarding${NC}"
IPF=$(cat /proc/sys/net/ipv4/ip_forward)
if [[ "$IPF" == "1" ]]; then
    ok "net.ipv4.ip_forward = 1"
else
    fail "net.ipv4.ip_forward = 0 (VPN traffic CANNOT be forwarded)"
    fix "Enabling ip_forward now..."
    sysctl -w net.ipv4.ip_forward=1
    echo "net.ipv4.ip_forward = 1" > /etc/sysctl.d/99-vpn.conf
    sysctl -p /etc/sysctl.d/99-vpn.conf > /dev/null
    ok "ip_forward enabled (persisted)"
    FIXES_APPLIED=$((FIXES_APPLIED+1))
fi

# ── 2. UFW forward policy ─────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}2. UFW Forward Policy${NC}"
UFW_CONF=/etc/default/ufw
if [[ -f "$UFW_CONF" ]]; then
    FWD_POLICY=$(grep '^DEFAULT_FORWARD_POLICY' "${UFW_CONF}" | cut -d= -f2 | tr -d '"')
    if [[ "$FWD_POLICY" == "ACCEPT" ]]; then
        ok "DEFAULT_FORWARD_POLICY = ACCEPT"
    else
        fail "DEFAULT_FORWARD_POLICY = ${FWD_POLICY:-?} — this BLOCKS all VPN forwarding"
        fix "Setting DEFAULT_FORWARD_POLICY=ACCEPT in ${UFW_CONF}..."
        sed -i 's/DEFAULT_FORWARD_POLICY="DROP"/DEFAULT_FORWARD_POLICY="ACCEPT"/' "${UFW_CONF}"
        sed -i 's/DEFAULT_FORWARD_POLICY="REJECT"/DEFAULT_FORWARD_POLICY="ACCEPT"/' "${UFW_CONF}"
        ok "Forward policy fixed"
        FIXES_APPLIED=$((FIXES_APPLIED+1))
    fi
else
    warn "$UFW_CONF not found — UFW not installed?"
fi

# ── 3. UFW before.rules NAT masquerade ───────────────────────────────────────
echo ""
echo -e "${BOLD}3. UFW NAT Masquerade (before.rules)${NC}"
UFW_BEFORE=/etc/ufw/before.rules
if grep -q 'MASQUERADE' "${UFW_BEFORE}" 2>/dev/null; then
    ok "MASQUERADE rule found in ${UFW_BEFORE}"
else
    warn "No MASQUERADE in UFW before.rules — injecting..."
    if ! grep -q 'TURNIP-NAT' "${UFW_BEFORE}" 2>/dev/null; then
        sed -i "1s|^|# TURNIP-NAT\n*nat\n:POSTROUTING ACCEPT [0:0]\n-A POSTROUTING -s ${VPN_SUBNET} -o ${PRIMARY_IFACE} -j MASQUERADE\nCOMMIT\n\n|" "${UFW_BEFORE}"
        ok "NAT MASQUERADE injected"
        FIXES_APPLIED=$((FIXES_APPLIED+1))
    fi
fi

# ── 4. iptables NAT check ─────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}4. iptables NAT POSTROUTING${NC}"
if iptables -t nat -L POSTROUTING -n 2>/dev/null | grep -q 'MASQUERADE'; then
    ok "MASQUERADE rule active in iptables nat"
else
    fail "No MASQUERADE rule in iptables — adding now..."
    iptables -t nat -A POSTROUTING -s "${VPN_SUBNET}" -o "${PRIMARY_IFACE}" -j MASQUERADE
    ok "MASQUERADE rule added"
    FIXES_APPLIED=$((FIXES_APPLIED+1))
fi

# ── 5. iptables FORWARD policy ────────────────────────────────────────────────
echo ""
echo -e "${BOLD}5. iptables FORWARD Chain${NC}"
FWD_POL=$(iptables -L FORWARD -n 2>/dev/null | head -1 | awk '{print $NF}')
if [[ "$FWD_POL" == "ACCEPT" ]]; then
    ok "FORWARD chain policy = ACCEPT"
else
    warn "FORWARD chain policy = ${FWD_POL:-?}"
    # Check if there's an explicit ACCEPT rule for VPN subnet
    if iptables -L FORWARD -n 2>/dev/null | grep -q "${VPN_SUBNET%%/*}"; then
        ok "Explicit FORWARD ACCEPT rule found for VPN subnet"
    else
        fix "Adding explicit FORWARD ACCEPT rule for ${VPN_SUBNET}..."
        iptables -I FORWARD -s "${VPN_SUBNET}" -j ACCEPT
        iptables -I FORWARD -d "${VPN_SUBNET}" -j ACCEPT
        ok "FORWARD rules added"
        FIXES_APPLIED=$((FIXES_APPLIED+1))
    fi
fi

# ── 6. StrongSwan running ─────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}6. StrongSwan Service${NC}"
SS_UNIT=""
if systemctl is-active --quiet strongswan-starter 2>/dev/null; then
    SS_UNIT="strongswan-starter"
    ok "strongswan-starter is running"
elif systemctl is-active --quiet strongswan 2>/dev/null; then
    SS_UNIT="strongswan"
    ok "strongswan is running"
else
    fail "StrongSwan is NOT running"
    fix "Attempting to start StrongSwan..."
    systemctl start strongswan-starter 2>/dev/null || systemctl start strongswan 2>/dev/null || true
    sleep 2
    if systemctl is-active --quiet strongswan-starter 2>/dev/null; then
        SS_UNIT="strongswan-starter"
        ok "StrongSwan started"
    elif systemctl is-active --quiet strongswan 2>/dev/null; then
        SS_UNIT="strongswan"
        ok "StrongSwan started"
    else
        fail "StrongSwan still not running — check: journalctl -u strongswan-starter -n 50"
    fi
fi

# ── 7. Config and secrets sanity ──────────────────────────────────────────────
echo ""
echo -e "${BOLD}7. Config + Secrets Sanity${NC}"
if [[ -f "$IPSEC_CONF" ]]; then
    ok "Found ${IPSEC_CONF}"
else
    fail "Missing ${IPSEC_CONF}"
fi

if [[ -f "$SECRETS_FILE" ]]; then
    ok "Found ${SECRETS_FILE}"
else
    fail "Missing ${SECRETS_FILE}"
fi

if [[ -f "$SECRETS_FILE" ]]; then
    PERM=$(stat -c "%a" "$SECRETS_FILE" 2>/dev/null || echo "")
    if [[ "$PERM" == "600" ]]; then
        ok "${SECRETS_FILE} permissions are 600"
    else
        warn "${SECRETS_FILE} permissions are ${PERM:-unknown} (recommended: 600)"
    fi

    USER_LINES=$(grep -Ec '^\S+\s*:\s*EAP\s+"' "$SECRETS_FILE" 2>/dev/null || true)
    if [[ "$USER_LINES" -gt 0 ]]; then
        ok "Found ${USER_LINES} EAP user entry/entries in ${SECRETS_FILE}"
    else
        fail "No EAP users found in ${SECRETS_FILE}"
    fi
fi

# ── 8. Handshake/auth visibility checks ──────────────────────────────────────
echo ""
echo -e "${BOLD}8. Handshake/Auth Visibility${NC}"
if command -v ipsec >/dev/null 2>&1; then
    if ipsec statusall >/tmp/turnip-ipsec-statusall.txt 2>/tmp/turnip-ipsec-statusall.err; then
        ok "ipsec statusall ran successfully"
    else
        warn "ipsec statusall failed — see /tmp/turnip-ipsec-statusall.err"
    fi

    if ipsec secrets >/tmp/turnip-ipsec-secrets.txt 2>/tmp/turnip-ipsec-secrets.err; then
        ok "ipsec secrets reload command succeeded"
    else
        fail "ipsec secrets command failed — credentials may not be loaded"
    fi
else
    warn "ipsec CLI not found — cannot run statusall/secrets checks"
fi

if [[ -n "$SS_UNIT" ]]; then
    AUTH_FAILS=$(journalctl -u "$SS_UNIT" --since "-30 min" --no-pager 2>/dev/null | grep -Eic 'AUTHENTICATION_FAILED|EAP|NO_PROPOSAL_CHOSEN|invalid ID')
    if [[ "$AUTH_FAILS" -gt 0 ]]; then
        warn "Detected ${AUTH_FAILS} auth/proposal warning(s) in ${SS_UNIT} logs in last 30m"
        warn "Run: journalctl -u ${SS_UNIT} --since '-30 min' | grep -Ei 'AUTHENTICATION_FAILED|EAP|NO_PROPOSAL_CHOSEN|invalid ID'"
    else
        ok "No recent auth/proposal failures detected in ${SS_UNIT} logs"
    fi
fi

# ── 9. Reload UFW if fixes were applied ──────────────────────────────────────
if [[ $FIXES_APPLIED -gt 0 ]]; then
    echo ""
    info "Reloading UFW to apply changes..."
    ufw reload > /dev/null 2>&1
    ok "UFW reloaded"
fi

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}═══════════════════════════════════════════════${NC}"
if [[ $FIXES_APPLIED -gt 0 ]]; then
    echo -e "${YELLOW}${FIXES_APPLIED} issue(s) found and fixed.${NC}"
    echo -e "Reconnect your VPN client and test internet access."
else
    echo -e "${GREEN}All checks passed. VPN routing looks correct.${NC}"
    echo -e "If clients still have no internet, check:"
    echo -e "  • ipsec statusall — confirm tunnel is established"
    echo -e "  • Client's split-tunnel settings (should send ALL traffic via VPN)"
    echo -e "  • DNS: client should use 1.1.1.1 from pushed rightdns"
fi
echo -e "${BOLD}═══════════════════════════════════════════════${NC}"
echo ""
