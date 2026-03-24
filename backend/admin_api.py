#!/usr/bin/env python3
"""
Turnip VPN — Admin API Server
Flask HTTP server on :8765 backing the Admin dashboard.

All /api/* routes require the X-Admin-Token header to match
the ADMIN_TOKEN environment variable.

Talks to VPN servers via SSH using multiserver.py helpers.
"""

import os, re, logging
from flask import Flask, jsonify, request, abort
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

from multiserver import (
    load_servers,
    get_best_server,
    get_fleet_status,
    _ssh_run,
    _ssh_read_file,
    SECRETS_FILE,
    MAX_PER_SERVER,
    add_user_to_server,
    remove_user_from_server,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [admin_api] %(levelname)s %(message)s")
log = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "")


# ── Auth ──────────────────────────────────────────────────────────────────────

def _require_auth():
    if not ADMIN_TOKEN:
        abort(503, description="ADMIN_TOKEN not configured on server")
    if request.headers.get("X-Admin-Token", "") != ADMIN_TOKEN:
        abort(401, description="Invalid or missing token")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _primary_host() -> str:
    """Return the primary (first active) server host, or abort 503."""
    for srv in load_servers():
        if srv.active:
            return srv.host
    abort(503, description="No active VPN servers configured")


def _parse_tunnels(ipsec_out: str) -> list[dict]:
    """
    Parse ESTABLISHED lines from `ipsec status` output.
    Sample line:
      ikev2-vpn[12]: ESTABLISHED 3 minutes ago, 203.0.113.1[server]...10.0.0.5[vpn_user1_a1b2c3]
    Returns list of {id, identity, since}.
    """
    tunnels = []
    pattern = re.compile(
        r"\[(\d+)\]:\s+ESTABLISHED\s+([^,]+),\s+[^\[]*\[[^\]]*\]"  # ... left side
        r"\.\.\.[^\[]*\[([^\]]+)\]",                                 # ... right[identity]
        re.IGNORECASE,
    )
    for i, m in enumerate(pattern.finditer(ipsec_out)):
        tunnels.append({
            "id":       m.group(1),
            "identity": m.group(3).strip(),
            "since":    m.group(2).strip(),
        })
    return tunnels


def _parse_eap_users(secrets_content: str) -> list[str]:
    """Extract EAP usernames from ipsec.secrets content."""
    return re.findall(r"^(\S+)\s*:\s*EAP", secrets_content, re.MULTILINE)


def _parse_proc_net(dev_output: str) -> tuple[float, float]:
    """
    Sum RX/TX bytes across all non-loopback interfaces from /proc/net/dev.
    Returns (rx_gb, tx_gb).
    """
    rx = tx = 0
    for line in dev_output.splitlines():
        if ":" not in line:
            continue
        iface, _, rest = line.partition(":")
        if iface.strip() == "lo":
            continue
        parts = rest.split()
        if len(parts) >= 9:
            try:
                rx += int(parts[0])   # rx_bytes
                tx += int(parts[8])   # tx_bytes
            except (ValueError, IndexError):
                pass
    return round(rx / 1e9, 2), round(tx / 1e9, 2)


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/api/status")
def get_status():
    _require_auth()
    host = _primary_host()

    # ── System metrics in one SSH call ────────────────────────────────────────
    sys_cmd = (
        # CPU% via /proc/stat snapshot (instant, no sleep needed)
        r"echo 'CPU:'$(awk '/^cpu /{idle=$5; total=0; for(i=2;i<=NF;i++) total+=$i;"
        r" printf \"%.1f\", (1-idle/total)*100}' /proc/stat) "
        # Memory
        r"'MEM_USED:'$(free -m | awk 'NR==2{print $3}') "
        r"'MEM_TOTAL:'$(free -m | awk 'NR==2{print $2}') "
        # Disk
        r"'DISK:'$(df / | tail -1 | awk '{print $5}' | tr -d '%') "
        # Uptime seconds
        r"'UPTIME:'$(awk '{printf \"%d\", $1}' /proc/uptime) "
        # VPN running (1=yes) + active user count
        r"'VPN:'$(ipsec status 2>/dev/null | grep -c 'Security Associations' || echo 0) "
        r"'USERS:'$(grep -c 'EAP' /etc/ipsec.secrets 2>/dev/null || echo 0)"
    )
    stats_raw, _, _ = _ssh_run(host, sys_cmd)

    def _kv(key: str, default: str = "0") -> str:
        m = re.search(rf"{key}:(\S+)", stats_raw)
        return m.group(1) if m else default

    try:
        cpu_pct    = float(_kv("CPU",       "0").replace(",", "."))
    except ValueError:
        cpu_pct    = 0.0
    mem_used_mb  = int(_kv("MEM_USED",  "0") or "0")
    mem_total_mb = int(_kv("MEM_TOTAL", "1") or "1")
    disk_pct     = int(_kv("DISK",      "0") or "0")
    uptime_sec   = int(_kv("UPTIME",    "0") or "0")
    vpn_running  = int(_kv("VPN",       "0") or "0") > 0
    total_users  = int(_kv("USERS",     "0") or "0")
    mem_pct      = round(mem_used_mb / max(mem_total_mb, 1) * 100, 1)

    # ── Network I/O ───────────────────────────────────────────────────────────
    net_raw, _, _ = _ssh_run(host, "cat /proc/net/dev")
    rx_gb, tx_gb = _parse_proc_net(net_raw)

    # ── Active tunnels ────────────────────────────────────────────────────────
    ipsec_raw, _, _ = _ssh_run(host, "ipsec status 2>/dev/null")
    tunnels = _parse_tunnels(ipsec_raw)

    return jsonify({
        "vpn_running":    vpn_running,
        "total_users":    total_users,
        "max_users":      MAX_PER_SERVER,
        "active_tunnels": len(tunnels),
        "tunnels":        tunnels,
        "system": {
            "cpu_pct":     round(cpu_pct, 1),
            "mem_pct":     mem_pct,
            "mem_used_gb": round(mem_used_mb / 1024, 2),
            "mem_total_gb": round(mem_total_mb / 1024, 2),
            "net_rx_gb":   rx_gb,
            "net_tx_gb":   tx_gb,
            "uptime_sec":  uptime_sec,
            "disk_pct":    disk_pct,
        },
    })


@app.route("/api/users")
def list_users():
    _require_auth()
    host = _primary_host()

    secrets = _ssh_read_file(host, SECRETS_FILE) or ""
    usernames = _parse_eap_users(secrets)

    # Mark each user online if they have an active tunnel
    ipsec_raw, _, _ = _ssh_run(host, "ipsec status 2>/dev/null")
    online = {t["identity"] for t in _parse_tunnels(ipsec_raw)}

    users = [{"username": u, "online": u in online} for u in sorted(usernames)]
    return jsonify({"users": users})


@app.route("/api/users", methods=["POST"])
def add_user():
    _require_auth()

    data     = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()

    # Route to the least-loaded server; fall back to primary if all unreachable
    servers = load_servers()
    best = get_best_server(servers)
    host = best.host if best else _primary_host()

    if not username:
        return jsonify({"error": "username required"}), 400
    if not re.match(r"^[a-zA-Z0-9_.@-]{2,64}$", username):
        return jsonify({"error": "username contains invalid characters"}), 400
    if not password:
        import secrets as _sec, string
        chars = string.ascii_letters + string.digits + "!@#$"
        password = "".join(_sec.choice(chars) for _ in range(20))

    ok = add_user_to_server(host, username, password)
    if ok:
        return jsonify({"ok": True, "username": username, "password": password})
    return jsonify({"error": "Failed to add user on VPN server"}), 500


@app.route("/api/users/<username>", methods=["DELETE"])
def delete_user(username):
    _require_auth()
    host = _primary_host()

    if not re.match(r"^[a-zA-Z0-9_.@-]{2,64}$", username):
        return jsonify({"error": "invalid username"}), 400

    ok = remove_user_from_server(host, username)
    if ok:
        return jsonify({"ok": True})
    return jsonify({"error": "Failed to remove user from VPN server"}), 500


@app.route("/api/servers")
def list_servers():
    _require_auth()
    try:
        fleet = get_fleet_status()
        return jsonify({"servers": fleet})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/vpn/restart", methods=["POST"])
def restart_vpn():
    _require_auth()
    host = _primary_host()

    _, _, code = _ssh_run(host, "ipsec restart 2>&1", timeout=30)
    if code == 0:
        return jsonify({"ok": True})
    return jsonify({"error": "ipsec restart returned non-zero exit code"}), 500


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if not ADMIN_TOKEN:
        log.warning("ADMIN_TOKEN is not set — all requests will get 503")
    app.run(host="127.0.0.1", port=8765, debug=False)
