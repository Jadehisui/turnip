#!/bin/bash
# Turnip VPN — Add a VPN user
# Usage: bash adduser.sh <username> [password]
# If password is omitted, a secure one is auto-generated.

set -e
RED='\033[0;31m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'; YELLOW='\033[1;33m'; NC='\033[0m'; BOLD='\033[1m'

SECRETS_FILE="/etc/ipsec.secrets"

[[ $EUID -ne 0 ]] && { echo -e "${RED}Run as root${NC}"; exit 1; }
[[ -z "$1" ]]     && { echo "Usage: bash adduser.sh <username> [password]"; exit 1; }

USERNAME="$1"
PASSWORD="${2:-$(openssl rand -base64 16 | tr -dc 'A-Za-z0-9!@#$' | head -c 20)}"

# Create secrets file if it doesn't exist yet
if [[ ! -f "${SECRETS_FILE}" ]]; then
    echo -e "# Turnip VPN — ipsec.secrets\n: RSA serverKey.pem\n" > "${SECRETS_FILE}"
    chmod 600 "${SECRETS_FILE}"
fi

# Check user doesn't already exist
if grep -q "^${USERNAME} " "${SECRETS_FILE}"; then
    echo -e "${RED}[ERROR]${NC} User '${USERNAME}' already exists in ${SECRETS_FILE}"
    exit 1
fi

# Append user
echo "${USERNAME} : EAP \"${PASSWORD}\"" >> "${SECRETS_FILE}"

# Reload secrets without restarting the daemon
# Try both ipsec and swanctl (different StrongSwan package variants)
if command -v ipsec &>/dev/null; then
    ipsec secrets
elif command -v swanctl &>/dev/null; then
    swanctl --load-creds
else
    echo -e "${YELLOW}[WARN]${NC}  Could not reload secrets: ipsec/swanctl not found. Try: systemctl restart strongswan-starter"
fi

echo ""
echo -e "${GREEN}User added successfully.${NC}"
echo ""
echo -e "${BOLD}Username :${NC} ${CYAN}${USERNAME}${NC}"
echo -e "${BOLD}Password :${NC} ${CYAN}${PASSWORD}${NC}"
echo ""
echo -e "Client VPN type : IKEv2 / EAP-MSCHAPv2"
