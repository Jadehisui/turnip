#!/bin/bash
# Turnip VPN — Remove a VPN user
# Usage: bash deluser.sh <username>

set -e
RED='\033[0;31m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'; NC='\033[0m'

SECRETS_FILE="/etc/ipsec.secrets"

[[ $EUID -ne 0 ]] && { echo -e "${RED}Run as root${NC}"; exit 1; }
[[ -z "$1" ]]     && { echo "Usage: bash deluser.sh <username>"; exit 1; }

USERNAME="$1"

if ! grep -q "^${USERNAME} " "${SECRETS_FILE}"; then
    echo -e "${RED}[ERROR]${NC} User '${USERNAME}' not found in ${SECRETS_FILE}"
    exit 1
fi

# Remove the user line safely
sed -i "/^${USERNAME} /d" "${SECRETS_FILE}"

# Reload secrets
ipsec secrets

echo -e "${GREEN}User '${USERNAME}' removed and secrets reloaded.${NC}"
