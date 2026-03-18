#!/bin/bash
# Turnip VPN — List all VPN users
# Usage: bash listusers.sh

SECRETS_FILE="/etc/ipsec.secrets"

[[ $EUID -ne 0 ]] && { echo "Run as root"; exit 1; }

echo ""
echo "Turnip VPN — Active Users"
echo "──────────────────────────────"
COUNT=0
while IFS= read -r line; do
    if [[ "$line" =~ ^([a-zA-Z0-9_.-]+)[[:space:]]*:[[:space:]]*EAP ]]; then
        echo "  ${BASH_REMATCH[1]}"
        ((COUNT++))
    fi
done < "${SECRETS_FILE}"
echo "──────────────────────────────"
echo "Total: ${COUNT} user(s)"
echo ""

echo "Active tunnels:"
ipsec status 2>/dev/null | grep "ESTABLISHED" | awk '{print "  " $0}' || echo "  (none)"
echo ""
