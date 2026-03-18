#!/bin/bash
# Turnip VPN — Add a VPN user
# Usage: bash adduser.sh <username> [password]
# If password is omitted, a secure one is auto-generated.

set -e
RED='\033[0;31m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'; NC='\033[0m'; BOLD='\033[1m'

SECRETS_FILE="/etc/ipsec.secrets"

[[ $EUID -ne 0 ]] && { echo -e "${RED}Run as root${NC}"; exit 1; }
[[ -z "$1" ]]     && { echo "Usage: bash adduser.sh <username> [password]"; exit 1; }

USERNAME="$1"
PASSWORD="${2:-$(openssl rand -base64 16 | tr -dc 'A-Za-z0-9!@#$' | head -c 20)}"

# Check user doesn't already exist
if grep -q "^${USERNAME} " "${SECRETS_FILE}"; then
    echo -e "${RED}[ERROR]${NC} User '${USERNAME}' already exists in ${SECRETS_FILE}"
    exit 1
fi

# Append user
echo "${USERNAME} : EAP \"${PASSWORD}\"" >> "${SECRETS_FILE}"

# Reload secrets without restarting the daemon
ipsec secrets

echo ""
echo -e "${GREEN}User added successfully.${NC}"
echo ""
echo -e "${BOLD}Username :${NC} ${CYAN}${USERNAME}${NC}"
echo -e "${BOLD}Password :${NC} ${CYAN}${PASSWORD}${NC}"
echo ""
echo -e "Client VPN type : IKEv2 / EAP-MSCHAPv2"
