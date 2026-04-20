#!/usr/bin/env python3
"""
Turnip VPN — Admin API Server
Flask HTTP server on :8765 backing the Admin dashboard.

All /api/* routes require the X-Admin-Token header to match
the ADMIN_TOKEN environment variable.

Talks to VPN servers via SSH using multiserver.py helpers.
"""

import os, re, time, subprocess, logging, html
from pathlib import Path
from flask import Flask, jsonify, request, abort
from flask_cors import CORS
from dotenv import load_dotenv
import psutil

load_dotenv()

import sys
sys.path.insert(0, os.path.dirname(__file__))
from database import (
    db_init,
    get_all_users,
    get_all_subscriptions,
    admin_update_subscription,
    get_subscription,
    get_devices_for_email,
    ensure_user,
    admin_save_provisioned_credentials,
    clear_devices_for_email,
)
from provisioner import (
    get_plan_by_name,
    provision_user,
    provision_user_with_device_count,
    deprovision_user,
    generate_mobileconfig,
    get_server_host,
)
from emailer import send_welcome_email, send_transactional_email

from multiserver import (
    load_servers,
    get_best_server,
    get_fleet_status,
    _ssh_run,
    _ssh_read_file,
    _is_local,
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
db_init()


# ── Auth ──────────────────────────────────────────────────────────────────────

def _require_auth():
    if not ADMIN_TOKEN:
        abort(503, description="ADMIN_TOKEN not configured on server")
    if request.headers.get("X-Admin-Token", "") != ADMIN_TOKEN:
        abort(401, description="Invalid or missing token")


# ── Helpers ───────────────────────────────────────────────────────────────────

_net_prev: dict = {}  # for live bandwidth rate calculation


def _collect_local_stats() -> dict:
    """Collect server status for the local machine using psutil."""
    global _net_prev

    cpu_pct    = psutil.cpu_percent(interval=0.3)
    mem        = psutil.virtual_memory()
    disk       = psutil.disk_usage("/")
    net_io     = psutil.net_io_counters()
    uptime_sec = int(time.time() - psutil.boot_time())

    # Live bandwidth rate (Mbps)
    now = time.time()
    rx_rate_mbps = tx_rate_mbps = 0.0
    if _net_prev:
        dt = now - _net_prev["ts"]
        if dt > 0.5:
            rx_rate_mbps = round((net_io.bytes_recv - _net_prev["rx"]) / dt / 1e6, 2)
            tx_rate_mbps = round((net_io.bytes_sent - _net_prev["tx"]) / dt / 1e6, 2)
    _net_prev = {"ts": now, "rx": net_io.bytes_recv, "tx": net_io.bytes_sent}

    # VPN users from ipsec.secrets
    try:
        secrets     = Path(SECRETS_FILE).read_text()
        total_users = len(re.findall(r"^\S+\s*:\s*EAP", secrets, re.MULTILINE))
    except Exception:
        total_users = 0

    # StrongSwan running?
    try:
        r = subprocess.run(
            ["systemctl", "is-active", "strongswan-starter"],
            capture_output=True, text=True, timeout=3,
        )
        vpn_running = r.stdout.strip() == "active"
    except Exception:
        vpn_running = False

    # Active tunnels
    try:
        ipsec_out = subprocess.run(
            ["ipsec", "status"], capture_output=True, text=True, timeout=5
        ).stdout
        tunnels = _parse_tunnels(ipsec_out)
    except Exception:
        tunnels = []

    # Firewall status
    firewall = {"enabled": False, "rules": 0, "vpn_nat": False}
    try:
        ufw_out = subprocess.run(
            ["ufw", "status", "numbered"], capture_output=True, text=True, timeout=5
        ).stdout
        firewall["enabled"] = "Status: active" in ufw_out
        if firewall["enabled"]:
            firewall["rules"] = len(re.findall(r"^\s*\[\s*\d+\]", ufw_out, re.MULTILINE))
    except Exception:
        pass
    try:
        ipt_out = subprocess.run(
            ["iptables", "-t", "nat", "-L", "POSTROUTING", "-n"],
            capture_output=True, text=True, timeout=5
        ).stdout
        firewall["vpn_nat"] = "MASQUERADE" in ipt_out
    except Exception:
        pass

    # Server registry counts
    try:
        all_srvs = load_servers()
        servers_total  = len(all_srvs)
        servers_active = sum(1 for s in all_srvs if s.active)
    except Exception:
        servers_total = servers_active = 1

    return {
        "vpn_running":    vpn_running,
        "total_users":    total_users,
        "max_users":      MAX_PER_SERVER,
        "active_tunnels": len(tunnels),
        "tunnels":        tunnels,
        "servers_total":  servers_total,
        "servers_active": servers_active,
        "firewall":       firewall,
        "system": {
            "cpu_pct":          round(cpu_pct, 1),
            "mem_pct":          mem.percent,
            "mem_used_gb":      round(mem.used  / 1e9, 2),
            "mem_total_gb":     round(mem.total / 1e9, 2),
            "net_rx_gb":        round(net_io.bytes_recv / 1e9, 3),
            "net_tx_gb":        round(net_io.bytes_sent / 1e9, 3),
            "net_rx_rate_mbps": rx_rate_mbps,
            "net_tx_rate_mbps": tx_rate_mbps,
            "disk_pct":         round(disk.percent, 1),
            "uptime_sec":       uptime_sec,
        },
    }


def _primary_host() -> str:
    """Return the primary (first active) server host, or abort 503."""
    for srv in load_servers():
        if srv.active:
            return srv.host
    abort(503, description="No active VPN servers configured")


def _deprovision_existing_devices(email: str):
    """Remove all known VPN identities for an email before re-provisioning."""
    sub = get_subscription(email=email)
    if sub and sub.get("username"):
        deprovision_user(sub["username"])
    for dev in get_devices_for_email(email):
        if dev.get("username"):
            deprovision_user(dev["username"])


def _collect_usernames_for_email(email: str) -> list[str]:
    usernames = []
    sub = get_subscription(email=email)
    if sub and sub.get("username"):
        usernames.append(sub["username"])
    for dev in get_devices_for_email(email):
        u = dev.get("username")
        if u:
            usernames.append(u)
    # Keep insertion order, drop duplicates
    return list(dict.fromkeys(usernames))


def _send_admin_copy_if_configured(creds: dict, plan: dict):
    admin_email = os.environ.get("ADMIN_NOTIFY_EMAIL", "").strip().lower()
    if not admin_email:
        return False
    try:
        send_welcome_email(admin_email, creds, plan)
        return True
    except Exception as exc:
        log.warning(f"Admin copy email failed to {admin_email}: {exc}")
        return False


def _build_broadcast_html(subject: str, body_text: str) -> str:
    """Render safe HTML from plain text body for transactional/broadcast sends."""
    escaped = html.escape(body_text).replace("\n", "<br>")
    escaped_subject = html.escape(subject)
    return (
        "<!DOCTYPE html><html><body "
        "style=\"font-family:-apple-system,Segoe UI,Arial,sans-serif;background:#f7f8fb;" 
        "margin:0;padding:24px;color:#111\">"
        "<div style=\"max-width:640px;margin:0 auto;background:#fff;border:1px solid #e5e7eb;"
        "border-radius:10px;padding:24px\">"
        f"<h2 style=\"margin:0 0 14px;font-size:20px\">{escaped_subject}</h2>"
        f"<div style=\"font-size:14px;line-height:1.7\">{escaped}</div>"
        "</div></body></html>"
    )


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

    if _is_local(host):
        return jsonify(_collect_local_stats())

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


@app.route("/api/subscribers")
def list_subscribers():
    _require_auth()
    try:
        users = get_all_users()
        return jsonify({"subscribers": users, "total": len(users)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/subscribers/broadcast-email", methods=["POST"])
def broadcast_email_to_subscribers():
    _require_auth()
    try:
        data = request.get_json(silent=True) or {}
        subject = (data.get("subject") or "").strip()
        body = (data.get("body") or "").strip()
        audience = (data.get("audience") or "all").strip().lower()
        dry_run = bool(data.get("dry_run", False))

        if not subject:
            return jsonify({"error": "subject required"}), 400
        if not body:
            return jsonify({"error": "body required"}), 400
        if audience not in {"all", "active", "registered"}:
            return jsonify({"error": "audience must be one of: all, active, registered"}), 400

        users = get_all_users()
        recipients = []
        for u in users:
            email = (u.get("email") or "").strip().lower()
            if not email:
                continue
            if audience == "active" and u.get("sub_status") not in {"active", "non_renewing"}:
                continue
            if audience == "registered" and u.get("sub_status") in {"active", "non_renewing", "expired", "disabled"}:
                continue
            recipients.append(email)

        # Preserve order while deduplicating
        recipients = list(dict.fromkeys(recipients))

        if dry_run:
            return jsonify({
                "ok": True,
                "dry_run": True,
                "audience": audience,
                "recipient_count": len(recipients),
                "sample": recipients[:10],
            })

        html_body = _build_broadcast_html(subject, body)
        sent = 0
        failures = []
        for recipient in recipients:
            try:
                send_transactional_email(recipient, subject, html_body, body)
                sent += 1
            except Exception as exc:
                failures.append({"email": recipient, "error": str(exc)})

        log.info(
            f"Admin broadcast completed | audience={audience} | recipients={len(recipients)} "
            f"| sent={sent} | failed={len(failures)}"
        )
        return jsonify({
            "ok": True,
            "dry_run": False,
            "audience": audience,
            "recipient_count": len(recipients),
            "sent": sent,
            "failed": len(failures),
            "failures": failures[:50],
        })
    except Exception as exc:
        log.exception(f"Broadcast email failed: {exc}")
        return jsonify({"error": "Broadcast failed on server. Check turnip-api logs."}), 500


@app.route("/api/vpn/restart", methods=["POST"])
def restart_vpn():
    _require_auth()
    host = _primary_host()

    _, _, code = _ssh_run(host, "ipsec restart 2>&1", timeout=30)
    if code == 0:
        return jsonify({"ok": True})
    return jsonify({"error": "ipsec restart returned non-zero exit code"}), 500


@app.route("/api/subscribers/<path:email>", methods=["PUT"])
def update_subscriber(email):
    _require_auth()
    try:
        data   = request.get_json(silent=True) or {}
        action = data.get("action", "")
        days   = max(1, min(int(data.get("days", 30)), 3650))

        if action == "extend":
            admin_update_subscription(email, status="active", extend_days=days)
        elif action == "activate":
            provision = bool(data.get("provision", True))
            send_email = bool(data.get("send_email", True))
            sub = get_subscription(email=email)

            if provision:
                plan = get_plan_by_name((sub or {}).get("plan_name", "Pro"))
                region = data.get("region") or (sub or {}).get("server_region", "eu")

                _deprovision_existing_devices(email)
                creds = provision_user(email=email, plan=plan, region=region)
                ensure_user(email)
                admin_save_provisioned_credentials(
                    email=email,
                    plan_name=plan["name"],
                    region=creds.get("region", region),
                    creds=creds,
                    duration_days=plan.get("duration_days", 30),
                    status="active",
                )

                emailed_user = False
                emailed_admin = False
                if send_email:
                    try:
                        send_welcome_email(email, creds, plan)
                        emailed_user = True
                    except Exception as exc:
                        log.warning(f"Activation email failed for {email}: {exc}")
                    emailed_admin = _send_admin_copy_if_configured(creds, plan)

                log.info(f"Admin activate on {email} | provisioned={provision} | emailed_user={emailed_user} | emailed_admin={emailed_admin}")
                return jsonify({
                    "ok": True,
                    "email": email,
                    "action": action,
                    "provisioned": True,
                    "emailed_user": emailed_user,
                    "emailed_admin": emailed_admin,
                    "devices": len(creds.get("devices", [])),
                })

            admin_update_subscription(email, status="active")
        elif action == "suspend":
            admin_update_subscription(email, status="disabled")
        elif action == "expire":
            admin_update_subscription(email, status="expired")
        else:
            return jsonify({"error": f"Unknown action: {action}"}), 400

        log.info(f"Admin {action} on {email}")
        return jsonify({"ok": True, "email": email, "action": action})
    except RuntimeError as exc:
        log.warning(f"Admin action failed on {email}: {exc}")
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        log.exception(f"Admin action failed on {email}: {exc}")
        return jsonify({"error": "Activation failed on server. Check turnip-api logs."}), 500


@app.route("/api/subscribers/<path:email>/generate-config", methods=["POST"])
def generate_demo_config(email):
    _require_auth()
    try:
        data = request.get_json(silent=True) or {}
        sub = get_subscription(email=email)
        region = (data.get("region") or "eu").strip().lower()
        plan_name = (data.get("plan_name") or (sub or {}).get("plan_name") or "Demo").strip()
        duration_days = max(1, min(int(data.get("duration_days", 30)), 3650))
        num_devices = max(1, min(int(data.get("num_devices", 1)), 10))
        if plan_name.lower() == "demo":
            num_devices = 1
        send_email = bool(data.get("send_email", True))
        replace_existing = bool(data.get("replace_existing", True))

        if replace_existing:
            _deprovision_existing_devices(email)

        creds = provision_user_with_device_count(
            email=email,
            plan_name=plan_name,
            duration_days=duration_days,
            device_count=num_devices,
            region=region,
        )
        ensure_user(email)
        admin_save_provisioned_credentials(
            email=email,
            plan_name=plan_name,
            region=creds.get("region", region),
            creds=creds,
            duration_days=duration_days,
            status="active",
        )

        plan_payload = {"name": plan_name, "duration_days": duration_days, "devices": num_devices}
        emailed_user = False
        emailed_admin = False
        if send_email:
            try:
                send_welcome_email(email, creds, plan_payload)
                emailed_user = True
            except Exception as exc:
                log.warning(f"Demo config email failed for {email}: {exc}")
            emailed_admin = _send_admin_copy_if_configured(creds, plan_payload)

        log.info(
            f"Admin generated config for {email} | devices={num_devices} | region={region} | "
            f"emailed_user={emailed_user} | emailed_admin={emailed_admin}"
        )
        return jsonify({
            "ok": True,
            "email": email,
            "region": creds.get("region", region),
            "plan_name": plan_name,
            "devices": creds.get("devices", []),
            "emailed_user": emailed_user,
            "emailed_admin": emailed_admin,
        })
    except RuntimeError as exc:
        log.warning(f"Config generation failed for {email}: {exc}")
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        log.exception(f"Config generation failed for {email}: {exc}")
        return jsonify({"error": "Config generation failed on server. Check turnip-api logs."}), 500


@app.route("/api/subscribers/<path:email>/terminate-configs", methods=["POST"])
def terminate_subscriber_configs(email):
    _require_auth()

    try:
        usernames = _collect_usernames_for_email(email)
        if not usernames:
            return jsonify({"error": "No configs found for this subscriber"}), 404

        removed = 0
        failures = []
        for username in usernames:
            try:
                deprovision_user(username)
                removed += 1
            except Exception as exc:
                failures.append({"username": username, "error": str(exc)})

        admin_update_subscription(email, status="disabled")
        deleted_rows = clear_devices_for_email(email)

        log.info(
            f"Admin terminated configs for {email} | removed={removed}/{len(usernames)} "
            f"| deleted_device_rows={deleted_rows}"
        )
        return jsonify({
            "ok": True,
            "email": email,
            "terminated": removed,
            "attempted": len(usernames),
            "deleted_device_rows": deleted_rows,
            "status": "disabled",
            "failures": failures,
        })
    except Exception as exc:
        log.exception(f"Terminate configs failed for {email}: {exc}")
        return jsonify({"error": "Terminate configs failed on server. Check turnip-api logs."}), 500


@app.route("/api/subscribers/<path:email>/resend-configs", methods=["POST"])
def resend_subscriber_configs(email):
    _require_auth()

    try:
        sub = get_subscription(email=email)
        if not sub:
            return jsonify({"error": "Subscriber not found"}), 404

        devices = get_devices_for_email(email)
        if not devices and sub.get("username") and sub.get("password"):
            devices = [{
                "device_number": 1,
                "username": sub["username"],
                "password": sub["password"],
                "server_region": sub.get("server_region", "eu"),
            }]

        if not devices:
            return jsonify({"error": "No stored configs found for this subscriber"}), 404

        enriched_devices = []
        for dev in devices:
            server_host = get_server_host(dev.get("server_region", sub.get("server_region", "eu")))
            profile_b64 = generate_mobileconfig(dev["username"], dev["password"], server_host)
            enriched_devices.append({
                "device_number": dev["device_number"],
                "username": dev["username"],
                "password": dev["password"],
                "server": server_host,
                "mobileconfig_b64": profile_b64,
            })

        creds = {
            "username": enriched_devices[0]["username"],
            "password": enriched_devices[0]["password"],
            "server": enriched_devices[0]["server"],
            "mobileconfig_b64": enriched_devices[0]["mobileconfig_b64"],
            "devices": enriched_devices,
            "region": sub.get("server_region", "eu"),
            "email": email,
        }
        plan = get_plan_by_name(sub.get("plan_name", "Pro"))

        send_welcome_email(email, creds, plan)
        emailed_admin = _send_admin_copy_if_configured(creds, plan)

        log.info(
            f"Admin resent configs for {email} | devices={len(enriched_devices)} | emailed_admin={emailed_admin}"
        )
        return jsonify({
            "ok": True,
            "email": email,
            "devices": len(enriched_devices),
            "emailed_user": True,
            "emailed_admin": emailed_admin,
        })
    except Exception as exc:
        log.exception(f"Resend configs failed for {email}: {exc}")
        return jsonify({"error": "Resend configs failed on server. Check turnip-api logs."}), 500


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if not ADMIN_TOKEN:
        log.warning("ADMIN_TOKEN is not set — all requests will get 503")
    app.run(host="127.0.0.1", port=8765, debug=False)
