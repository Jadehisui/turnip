#!/usr/bin/env bash
# =============================================================================
# StrongSwan demo config generator + optional apply/restart/check
# Usage examples:
#   sudo bash strongswan-demo.sh vpn.example.com
#   sudo bash strongswan-demo.sh vpn.example.com --apply
#   sudo bash strongswan-demo.sh vpn.example.com --apply --restart
# =============================================================================

set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'
YELLOW='\033[1;33m'; BOLD='\033[1m'; NC='\033[0m'

info()    { echo -e "${CYAN}[INFO]${NC}  $1"; }
success() { echo -e "${GREEN}[OK]${NC}    $1"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $1"; }
error()   { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

usage() {
    cat << 'EOF'
Usage:
  sudo bash server/strongswan-demo.sh <SERVER_ADDR> [options]

Options:
  --apply                 Backup and write files to /etc/ipsec.conf and /etc/ipsec.secrets
  --restart               Restart StrongSwan service after apply
  --conn-name <name>      Connection profile name (default: turnip-demo)
  --vpn-subnet <cidr>     Virtual IP pool CIDR (default: 10.20.30.0/24)
  --dns1 <ip>             Primary DNS pushed to clients (default: 1.1.1.1)
  --dns2 <ip>             Secondary DNS pushed to clients (default: 8.8.8.8)
  --username <name>       Demo EAP username (default: demo)
  --password <value>      Demo EAP password (default: generated random)
  --output-dir <dir>      Output folder in dry-run mode (default: /tmp)
  -h, --help              Show this help

Notes:
  - Without --apply, this script only generates demo files.
  - With --apply, existing files are backed up with a timestamp.
EOF
}

pick_service_unit() {
    if systemctl list-unit-files | grep -q '^strongswan-starter\.service'; then
        echo "strongswan-starter"
    elif systemctl list-unit-files | grep -q '^strongswan\.service'; then
        echo "strongswan"
    else
        echo ""
    fi
}

restart_and_check() {
    local unit="$1"

    [[ -z "$unit" ]] && error "Could not find StrongSwan service unit (strongswan-starter/strongswan)."

    info "Restarting ${unit}..."
    systemctl restart "$unit"

    if systemctl is-active --quiet "$unit"; then
        success "${unit} is active"
    else
        error "${unit} failed to start. Check logs with: journalctl -u ${unit} -n 100 --no-pager"
    fi

    if command -v ipsec >/dev/null 2>&1; then
        info "Reloading secrets cache..."
        ipsec secrets || warn "ipsec secrets returned non-zero; check /etc/ipsec.secrets format"

        info "Current tunnel/service summary:"
        ipsec status || true
    else
        warn "ipsec CLI not found; skipping ipsec status checks"
    fi
}

[[ $# -lt 1 ]] && { usage; exit 1; }

SERVER_ADDR="$1"
shift || true

APPLY=0
DO_RESTART=0
CONN_NAME="turnip-demo"
VPN_SUBNET="10.20.30.0/24"
DNS1="1.1.1.1"
DNS2="8.8.8.8"
USERNAME="demo"
PASSWORD=""
OUTPUT_DIR="/tmp"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --apply)
            APPLY=1
            ;;
        --restart)
            DO_RESTART=1
            ;;
        --conn-name)
            CONN_NAME="$2"
            shift
            ;;
        --vpn-subnet)
            VPN_SUBNET="$2"
            shift
            ;;
        --dns1)
            DNS1="$2"
            shift
            ;;
        --dns2)
            DNS2="$2"
            shift
            ;;
        --username)
            USERNAME="$2"
            shift
            ;;
        --password)
            PASSWORD="$2"
            shift
            ;;
        --output-dir)
            OUTPUT_DIR="$2"
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            error "Unknown option: $1"
            ;;
    esac
    shift
done

if [[ -z "$PASSWORD" ]]; then
    if command -v openssl >/dev/null 2>&1; then
        PASSWORD=$(openssl rand -base64 24 | tr -dc 'A-Za-z0-9!@#$%^&*()_+{}[]' | head -c 24)
    else
        PASSWORD="ChangeMeNow123!"
        warn "openssl not found; using fallback password. Please rotate it."
    fi
fi

TIMESTAMP=$(date +%Y%m%d-%H%M%S)

if [[ "$APPLY" -eq 1 ]]; then
    [[ $EUID -ne 0 ]] && error "Run as root when using --apply"
    IPSEC_CONF_OUT="/etc/ipsec.conf"
    SECRETS_OUT="/etc/ipsec.secrets"
else
    mkdir -p "$OUTPUT_DIR"
    IPSEC_CONF_OUT="${OUTPUT_DIR}/ipsec.conf.demo"
    SECRETS_OUT="${OUTPUT_DIR}/ipsec.secrets.demo"
fi

info "Generating demo config for server identity: ${SERVER_ADDR}"

cat > "$IPSEC_CONF_OUT" << EOF
# StrongSwan demo config
# Generated on $(date)

config setup
    charondebug="ike 1, knl 1, cfg 0"
    uniqueids=yes

conn %default
    keyexchange=ikev2
    ikelifetime=60m
    keylife=20m
    rekeymargin=3m
    keyingtries=%forever

conn ${CONN_NAME}
    auto=add

    left=%any
    leftid=${SERVER_ADDR}
    leftauth=pubkey
    leftcert=serverCert.pem
    leftsendcert=always
    leftsubnet=0.0.0.0/0

    right=%any
    rightid=%any
    rightauth=eap-mschapv2
    rightsourceip=${VPN_SUBNET}
    rightdns=${DNS1},${DNS2}
    eap_identity=%identity

    ike=aes256gcm16-prfsha384-ecp384,aes256-sha256-modp2048!
    esp=aes256gcm16,aes256-sha256!

    dpdaction=clear
    dpddelay=30s
    dpdtimeout=120s
    rekey=no
    fragmentation=yes
    leftfirewall=yes
EOF

cat > "$SECRETS_OUT" << EOF
# StrongSwan demo secrets
# Generated on $(date)

: RSA serverKey.pem
${USERNAME} : EAP "${PASSWORD}"
EOF

chmod 600 "$SECRETS_OUT"

if [[ "$APPLY" -eq 1 ]]; then
    info "Backing up existing config files..."
    cp -a /etc/ipsec.conf "/etc/ipsec.conf.bak.${TIMESTAMP}" 2>/dev/null || true
    cp -a /etc/ipsec.secrets "/etc/ipsec.secrets.bak.${TIMESTAMP}" 2>/dev/null || true
    success "Backups saved as /etc/ipsec.conf.bak.${TIMESTAMP} and /etc/ipsec.secrets.bak.${TIMESTAMP} (if originals existed)"
    success "Applied: /etc/ipsec.conf"
    success "Applied: /etc/ipsec.secrets"
else
    success "Generated: ${IPSEC_CONF_OUT}"
    success "Generated: ${SECRETS_OUT}"
fi

echo ""
echo -e "${BOLD}Demo credentials${NC}"
echo "  Username: ${USERNAME}"
echo "  Password: ${PASSWORD}"
echo ""

if [[ "$APPLY" -eq 1 && "$DO_RESTART" -eq 1 ]]; then
    UNIT=$(pick_service_unit)
    restart_and_check "$UNIT"
elif [[ "$DO_RESTART" -eq 1 ]]; then
    warn "--restart requested without --apply. Skipping restart to avoid reloading unchanged system config."
else
    info "Use --apply --restart to install and validate on this server."
fi
