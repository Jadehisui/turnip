#!/bin/bash
# Turnip VPN — Generate .mobileconfig for iOS / macOS
# Usage: bash gen-profile.sh <username> <password> <server_addr>
# Output: /root/<username>-turnip.mobileconfig

set -e
RED='\033[0;31m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'; NC='\033[0m'; BOLD='\033[1m'

[[ $EUID -ne 0 ]]  && { echo -e "${RED}Run as root${NC}"; exit 1; }
[[ -z "$3" ]]      && { echo "Usage: bash gen-profile.sh <username> <password> <server_addr>"; exit 1; }

USERNAME="$1"
PASSWORD="$2"
SERVER="$3"
CA_PATH="/etc/ipsec.d/cacerts/caCert.pem"
PROFILE_UUID=$(cat /proc/sys/kernel/random/uuid)
VPN_UUID=$(cat /proc/sys/kernel/random/uuid)
CERT_UUID=$(cat /proc/sys/kernel/random/uuid)
OUTFILE="/root/${USERNAME}-turnip.mobileconfig"

# Base64-encode the CA cert for embedding
CA_B64=$(base64 -w 0 "${CA_PATH}")

cat > "${OUTFILE}" << PROFILE
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>PayloadDisplayName</key>
  <string>Turnip VPN</string>
  <key>PayloadIdentifier</key>
  <string>com.turnip.profile.${PROFILE_UUID}</string>
  <key>PayloadType</key>
  <string>Configuration</string>
  <key>PayloadUUID</key>
  <string>${PROFILE_UUID}</string>
  <key>PayloadVersion</key>
  <integer>1</integer>
  <key>PayloadContent</key>
  <array>

    <!-- CA Certificate -->
    <dict>
      <key>PayloadType</key>
      <string>com.apple.security.root</string>
      <key>PayloadIdentifier</key>
      <string>com.turnip.ca.${CERT_UUID}</string>
      <key>PayloadUUID</key>
      <string>${CERT_UUID}</string>
      <key>PayloadVersion</key>
      <integer>1</integer>
      <key>PayloadDisplayName</key>
      <string>Turnip VPN CA</string>
      <key>PayloadContent</key>
      <data>${CA_B64}</data>
    </dict>

    <!-- IKEv2 VPN Configuration -->
    <dict>
      <key>PayloadType</key>
      <string>com.apple.vpn.managed</string>
      <key>PayloadIdentifier</key>
      <string>com.turnip.vpn.${VPN_UUID}</string>
      <key>PayloadUUID</key>
      <string>${VPN_UUID}</string>
      <key>PayloadVersion</key>
      <integer>1</integer>
      <key>PayloadDisplayName</key>
      <string>Turnip VPN</string>
      <key>UserDefinedName</key>
      <string>Turnip VPN</string>
      <key>VPNType</key>
      <string>IKEv2</string>
      <key>IKEv2</key>
      <dict>
        <key>RemoteAddress</key>
        <string>${SERVER}</string>
        <key>RemoteIdentifier</key>
        <string>${SERVER}</string>
        <key>LocalIdentifier</key>
        <string>${USERNAME}</string>
        <key>AuthenticationMethod</key>
        <string>None</string>
        <key>ExtendedAuthEnabled</key>
        <true/>
        <key>AuthName</key>
        <string>${USERNAME}</string>
        <key>AuthPassword</key>
        <string>${PASSWORD}</string>
        <key>ChildSecurityAssociationParameters</key>
        <dict>
          <key>EncryptionAlgorithm</key>
          <string>AES-256-GCM</string>
          <key>IntegrityAlgorithm</key>
          <string>SHA2-256</string>
          <key>DiffieHellmanGroup</key>
          <integer>14</integer>
        </dict>
        <key>IKESecurityAssociationParameters</key>
        <dict>
          <key>EncryptionAlgorithm</key>
          <string>AES-256-GCM</string>
          <key>IntegrityAlgorithm</key>
          <string>SHA2-256</string>
          <key>DiffieHellmanGroup</key>
          <integer>14</integer>
        </dict>
        <key>DeadPeerDetectionRate</key>
        <string>Medium</string>
        <key>DisableRedirect</key>
        <true/>
        <key>EnablePFS</key>
        <true/>
        <key>UseConfigurationAttributeInternalIPSubnet</key>
        <integer>0</integer>
      </dict>
      <key>IPv4</key>
      <dict>
        <key>OverridePrimary</key>
        <integer>1</integer>
      </dict>
    </dict>

  </array>
</dict>
</plist>
PROFILE

chmod 600 "${OUTFILE}"

echo ""
echo -e "${GREEN}Profile generated:${NC} ${OUTFILE}"
echo ""
echo -e "${BOLD}Next steps:${NC}"
echo "  1. SCP this file to the user's device:"
echo "     scp ${OUTFILE} user@device:/path/"
echo "  2. On iOS: AirDrop or email the .mobileconfig, then open it"
echo "  3. On macOS: Double-click and install via System Preferences"
echo "  4. The CA cert and VPN credentials are embedded automatically"
echo ""
