#!/usr/bin/env python3
"""
Turnip VPN — User Provisioner
Creates and removes VPN accounts. Generates .mobileconfig profiles.
Called by the webhook server after payment confirmation.
"""

import os, re, secrets, string, subprocess, base64, uuid, logging, json
from pathlib import Path
from datetime import datetime, timedelta

log = logging.getLogger(__name__)

SECRETS_FILE  = os.environ.get("IPSEC_SECRETS_FILE", "/etc/ipsec.secrets")
CA_CERT_PATH  = os.environ.get("CA_CERT_PATH",       "/etc/ipsec.d/cacerts/caCert.pem")
SERVER_ADDR   = os.environ.get("VPN_SERVER_ADDR",     "vpn.yourdomain.com")
MAX_USERS     = int(os.environ.get("MAX_USERS",       "80"))

# Load servers list from servers.json (same directory as this file)
_SERVERS_PATH = os.path.join(os.path.dirname(__file__), "servers.json")
try:
    with open(_SERVERS_PATH) as _f:
        SERVERS = json.load(_f)
except Exception:
    SERVERS = []

SERVERS_BY_REGION = {s["region"]: s for s in SERVERS if s.get("active")}

# Continent codes that trigger auto-selection of best server in that region
CONTINENT_CODES = {"eu", "na", "as"}

# ── Plans ─────────────────────────────────────────────────────────────────────

PLANS = [
    {"name": "Basic",    "min_amount": 1,     "max_amount": 6999,   "duration_days": 30, "devices": 1},
    {"name": "Pro",      "min_amount": 7000,  "max_amount": 18999,  "duration_days": 30, "devices": 5},
    {"name": "Business", "min_amount": 19000, "max_amount": 999999, "duration_days": 30, "devices": 10},
]
DEFAULT_PLAN = {"name": "Pro", "duration_days": 30, "devices": 5}


def get_plan_by_name(plan_name: str) -> dict:
    if not plan_name:
        return DEFAULT_PLAN
    for plan in PLANS:
        if plan["name"].lower() == plan_name.lower():
            return plan
    return DEFAULT_PLAN


def get_plan_for_amount(amount_ngn: float, plan_code: str = "") -> dict:
    """Match plan by code (primary) or payment amount (fallback)."""
    if plan_code:
        for plan in PLANS:
            if plan["name"].lower() == plan_code.lower():
                return plan
    for plan in PLANS:
        if plan["min_amount"] <= amount_ngn <= plan["max_amount"]:
            return plan
    log.warning(f"No plan matched for ₦{amount_ngn:.0f} / code='{plan_code}' — using default")
    return DEFAULT_PLAN


def get_server_host(region: str) -> str:
    """Resolve a specific server region code (nl/us/sg...) to a VPN server public host."""
    server = SERVERS_BY_REGION.get(region)
    if server:
        return server.get("public_host") or server["host"]
    return SERVER_ADDR  # fallback to env var


def get_server_for_continent(continent: str) -> dict:
    """
    Pick the best active server in a continent.
    Returns {"host": ..., "region": ...}.
    Falls back to any active server if the continent has none.
    """
    try:
        from multiserver import get_best_server_for_continent
        best = get_best_server_for_continent(continent)
        if best:
            return {"host": best.public_host, "region": best.region}
    except ImportError:
        log.warning("multiserver module not available — using static server fallback")
    except Exception as exc:
        log.warning(f"get_best_server_for_continent failed: {exc} — using static fallback")
    # Fallback: first active server in the requested continent
    for s in SERVERS:
        if s.get("active") and s.get("continent", "").lower() == continent.lower():
            return {"host": s.get("public_host") or s["host"], "region": s["region"]}
    # Last resort: any active server
    for s in SERVERS:
        if s.get("active"):
            return {"host": s.get("public_host") or s["host"], "region": s["region"]}
    return {"host": SERVER_ADDR, "region": continent}


# ── Capacity check ────────────────────────────────────────────────────────────

def count_vpn_users() -> int:
    try:
        count = 0
        with open(SECRETS_FILE) as f:
            for line in f:
                if re.match(r'^\S+\s*:\s*EAP\s+"', line.strip()):
                    count += 1
        return count
    except FileNotFoundError:
        return 0


def is_server_full() -> bool:
    return count_vpn_users() >= MAX_USERS


# ── Password + username generation ────────────────────────────────────────────

def generate_password(length: int = 20) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def email_to_username(email: str) -> str:
    """Convert email to a safe VPN username. e.g. john.doe@gmail.com → vpn_johndoe"""
    local = email.split("@")[0]
    safe  = re.sub(r"[^a-zA-Z0-9]", "", local)[:12].lower()
    suffix = secrets.token_hex(3)     # 6 hex chars — prevents collisions
    return f"vpn_{safe}_{suffix}"


# ── Core provisioning ─────────────────────────────────────────────────────────

def provision_user(email: str, plan: dict, region: str = "eu") -> dict:
    """
    Provision N VPN accounts (one per device slot in the plan).
    `region` can be a continent code (eu/na/as) — system picks best server —
    or a specific server region code (nl/us/sg) for direct assignment.
    Returns a dict with backward-compat top-level fields and a `devices` list.
    Raises RuntimeError if the server is at capacity.
    """
    if is_server_full():
        raise RuntimeError(
            f"Server at capacity ({MAX_USERS} users). "
            "Cannot provision new account."
        )


def provision_user_with_device_count(
    email: str,
    plan_name: str,
    duration_days: int,
    device_count: int,
    region: str = "eu",
) -> dict:
    """Provision VPN credentials with an explicit device count for admin/demo flows."""
    safe_devices = max(1, min(int(device_count), 10))
    plan = {
        "name": plan_name or "Demo",
        "duration_days": max(1, int(duration_days or 30)),
        "devices": safe_devices,
    }
    return provision_user(email=email, plan=plan, region=region)

    # Resolve continent → best specific server
    if region in CONTINENT_CODES:
        srv = get_server_for_continent(region)
        server_host     = srv["host"]
        resolved_region = srv["region"]
    else:
        server_host     = get_server_host(region)
        resolved_region = region

    n_devices = min(plan.get("devices", 1), 10)  # cap Business at 10
    expiry    = datetime.utcnow() + timedelta(days=plan["duration_days"])

    devices = []
    for i in range(n_devices):
        username = email_to_username(email)
        password = generate_password()
        _add_ipsec_user(username, password)
        profile_b64 = generate_mobileconfig(username, password, server_host)
        devices.append({
            "device_number": i + 1,
            "username":      username,
            "password":      password,
            "server":        server_host,
            "mobileconfig_b64": profile_b64,
        })

    # Single secrets reload after all users are written
    _reload_ipsec_secrets()

    log.info(
        f"Provisioned {n_devices} device(s) for {email} "
        f"| plan={plan['name']} | region={resolved_region} | expiry={expiry.date()}"
    )

    return {
        # Backward-compat top-level fields (Device 1)
        "username":         devices[0]["username"],
        "password":         devices[0]["password"],
        "server":           server_host,
        "plan":             plan["name"],
        "region":           resolved_region,   # actual server region, not continent code
        "expiry":           expiry.isoformat(),
        "expiry_display":   expiry.strftime("%B %d, %Y"),
        "mobileconfig_b64": devices[0]["mobileconfig_b64"],
        "email":            email,
        # Full device list
        "devices":          devices,
    }


def deprovision_user(username: str):
    """Remove a VPN user from ipsec.secrets and reload."""
    if not username:
        return
    try:
        lines = Path(SECRETS_FILE).read_text().splitlines(keepends=True)
        filtered = [l for l in lines if not l.strip().startswith(f"{username} :")]
        Path(SECRETS_FILE).write_text("".join(filtered))
        _reload_ipsec_secrets()
        log.info(f"Deprovisioned: {username}")
    except Exception as e:
        log.error(f"Failed to deprovision {username}: {e}")


def _add_ipsec_user(username: str, password: str):
    with open(SECRETS_FILE, "a") as f:
        f.write(f'\n{username} : EAP "{password}"\n')


def _reload_ipsec_secrets():
    try:
        subprocess.run(["ipsec", "secrets"], timeout=5, check=True)
    except Exception as e:
        log.warning(f"ipsec secrets reload failed (non-fatal): {e}")


# ── .mobileconfig generator ───────────────────────────────────────────────────

def generate_mobileconfig(username: str, password: str, server: str) -> str:
    """
    Generate an Apple .mobileconfig profile with embedded CA cert.
    Returns base64-encoded profile bytes for email attachment.
    """
    # Load CA cert — fail loudly rather than generating a silently broken profile
    try:
        ca_b64 = base64.b64encode(Path(CA_CERT_PATH).read_bytes()).decode()
    except FileNotFoundError:
        raise RuntimeError(
            f"CA certificate not found at {CA_CERT_PATH}. "
            "Set CA_CERT_PATH in .env or copy caCert.pem to the expected location."
        )

    profile_uuid = str(uuid.uuid4()).upper()
    vpn_uuid     = str(uuid.uuid4()).upper()
    cert_uuid    = str(uuid.uuid4()).upper()

    profile_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>PayloadDisplayName</key>
  <string>Turnip VPN</string>
  <key>PayloadDescription</key>
  <string>Installs the Turnip VPN IKEv2 configuration and CA certificate.</string>
  <key>PayloadIdentifier</key>
  <string>com.turnip.profile.{profile_uuid}</string>
  <key>PayloadType</key>
  <string>Configuration</string>
  <key>PayloadUUID</key>
  <string>{profile_uuid}</string>
  <key>PayloadVersion</key>
  <integer>1</integer>
  <key>PayloadContent</key>
  <array>

    <dict>
      <key>PayloadType</key>
      <string>com.apple.security.root</string>
      <key>PayloadIdentifier</key>
      <string>com.turnip.ca.{cert_uuid}</string>
      <key>PayloadUUID</key>
      <string>{cert_uuid}</string>
      <key>PayloadVersion</key>
      <integer>1</integer>
      <key>PayloadDisplayName</key>
      <string>Turnip VPN CA</string>
      <key>PayloadContent</key>
      <data>{ca_b64}</data>
    </dict>

    <dict>
      <key>PayloadType</key>
      <string>com.apple.vpn.managed</string>
      <key>PayloadIdentifier</key>
      <string>com.turnip.vpn.{vpn_uuid}</string>
      <key>PayloadUUID</key>
      <string>{vpn_uuid}</string>
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
        <string>{server}</string>
        <key>RemoteIdentifier</key>
        <string>{server}</string>
        <key>LocalIdentifier</key>
        <string>{username}</string>
        <key>AuthenticationMethod</key>
        <string>None</string>
        <key>ExtendedAuthEnabled</key>
        <true/>
        <key>AuthName</key>
        <string>{username}</string>
        <key>AuthPassword</key>
        <string>{password}</string>
        <key>DeadPeerDetectionRate</key>
        <string>Medium</string>
        <key>EnablePFS</key>
        <true/>
        <key>DisableRedirect</key>
        <true/>
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
      </dict>
      <key>IPv4</key>
      <dict>
        <key>OverridePrimary</key>
        <integer>1</integer>
      </dict>
    </dict>

  </array>
</dict>
</plist>"""

    return base64.b64encode(profile_xml.encode("utf-8")).decode()
