#!/usr/bin/env python3
"""
Turnip VPN — Monitor Daemon
Checks all VPN servers every 60 seconds.
Alerts via Telegram and/or email when:
  - A server goes offline
  - A server comes back online
  - CPU > 85%
  - Server reaches 90% capacity (72/80 users)
  - StrongSwan daemon crashes

Run:  python3 monitor.py
Cron: managed by systemd service turnip-monitor
"""

import os, time, json, smtplib, logging, requests, subprocess
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("/var/log/turnip-monitor.log"),
        logging.StreamHandler(),
    ]
)
log = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
TELEGRAM_TOKEN   = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID",   "")
ALERT_EMAIL      = os.environ.get("ALERT_EMAIL",         "")
SMTP_HOST        = os.environ.get("SMTP_HOST",           "smtp.gmail.com")
SMTP_PORT        = int(os.environ.get("SMTP_PORT",       "587"))
SMTP_USER        = os.environ.get("SMTP_USER",           "")
SMTP_PASS        = os.environ.get("SMTP_PASS",           "")
FROM_EMAIL       = os.environ.get("FROM_EMAIL",          "")
MAX_USERS        = int(os.environ.get("MAX_USERS",       "80"))
CHECK_INTERVAL   = int(os.environ.get("MONITOR_INTERVAL","60"))   # seconds
CPU_ALERT_PCT    = float(os.environ.get("CPU_ALERT_PCT", "85"))
CAP_ALERT_PCT    = float(os.environ.get("CAP_ALERT_PCT", "90"))

STATE_FILE = "/opt/turnip/monitor_state.json"

# ── State tracking ────────────────────────────────────────────────────────────

def load_state() -> dict:
    try:
        return json.loads(Path(STATE_FILE).read_text())
    except Exception:
        return {}


def save_state(state: dict):
    Path(STATE_FILE).parent.mkdir(parents=True, exist_ok=True)
    Path(STATE_FILE).write_text(json.dumps(state, indent=2))


# ── Server checks ─────────────────────────────────────────────────────────────

def check_local_server() -> dict:
    """Check the local VPN server (the machine this script runs on)."""
    result = {
        "id":        "local",
        "host":      "localhost",
        "name":      "Primary",
        "reachable": True,
        "vpn_up":    False,
        "users":     0,
        "tunnels":   0,
        "cpu":       0.0,
        "mem":       0.0,
    }

    # StrongSwan status
    try:
        r = subprocess.run(
            ["systemctl", "is-active", "strongswan-starter"],
            capture_output=True, text=True, timeout=5
        )
        result["vpn_up"] = r.stdout.strip() == "active"
    except Exception:
        result["vpn_up"] = False

    # User count from ipsec.secrets
    try:
        count = 0
        for line in Path("/etc/ipsec.secrets").read_text().splitlines():
            if " : EAP " in line:
                count += 1
        result["users"] = count
    except Exception:
        pass

    # Active tunnels
    try:
        r = subprocess.run(["ipsec", "status"], capture_output=True, text=True, timeout=5)
        result["tunnels"] = r.stdout.count("ESTABLISHED")
    except Exception:
        pass

    # CPU + memory via psutil
    try:
        import psutil
        result["cpu"] = psutil.cpu_percent(interval=0.5)
        result["mem"] = psutil.virtual_memory().percent
    except Exception:
        pass

    return result


def check_remote_server(server: dict) -> dict:
    """Ping a remote server via the admin API or SSH."""
    result = {**server, "reachable": False, "vpn_up": False, "users": 0, "tunnels": 0, "cpu": 0.0}

    admin_url = f"http://{server['host']}:8765/api/status"
    admin_token = os.environ.get("ADMIN_TOKEN", "")

    try:
        resp = requests.get(
            admin_url,
            headers={"X-Admin-Token": admin_token},
            timeout=8,
        )
        if resp.status_code == 200:
            data = resp.json()
            sys  = data.get("system", {})
            result.update({
                "reachable": True,
                "vpn_up":    data.get("vpn_running", False),
                "users":     data.get("total_users", 0),
                "tunnels":   data.get("active_tunnels", 0),
                "cpu":       sys.get("cpu_pct", 0.0),
                "mem":       sys.get("mem_pct", 0.0),
            })
    except Exception as e:
        log.debug(f"Remote check failed for {server['host']}: {e}")

    return result


def check_all_servers() -> list[dict]:
    results = [check_local_server()]

    servers_path = Path("/opt/turnip/servers.json")
    if servers_path.exists():
        remote_servers = json.loads(servers_path.read_text())
        for srv in remote_servers:
            if srv.get("active") and srv.get("host") not in ("YOUR_NL_SERVER_IP", "YOUR_US_SERVER_IP", "YOUR_CA_SERVER_IP", "YOUR_SG_SERVER_IP"):
                results.append(check_remote_server(srv))

    return results


# ── Alert logic ───────────────────────────────────────────────────────────────

def evaluate_alerts(current: list[dict], state: dict) -> list[dict]:
    """Compare current stats to previous state and generate alerts."""
    alerts = []
    now    = datetime.utcnow().isoformat()

    for srv in current:
        sid = srv["id"]
        prev = state.get(sid, {})

        # Server went offline
        if not srv["reachable"] and prev.get("reachable", True):
            alerts.append({
                "level":   "critical",
                "server":  srv["name"],
                "message": f"🔴 {srv['name']} is OFFLINE",
                "detail":  f"Server {srv['host']} is not responding.",
            })

        # Server came back online
        if srv["reachable"] and not prev.get("reachable", True):
            alerts.append({
                "level":   "info",
                "server":  srv["name"],
                "message": f"🟢 {srv['name']} is back ONLINE",
                "detail":  f"Server {srv['host']} recovered.",
            })

        if not srv["reachable"]:
            continue

        # VPN daemon down
        if not srv["vpn_up"] and prev.get("vpn_up", True):
            alerts.append({
                "level":   "critical",
                "server":  srv["name"],
                "message": f"🔴 StrongSwan DOWN on {srv['name']}",
                "detail":  "The VPN daemon is not running. New connections are blocked.",
            })

        # VPN daemon recovered
        if srv["vpn_up"] and not prev.get("vpn_up", True):
            alerts.append({
                "level":   "info",
                "server":  srv["name"],
                "message": f"🟢 StrongSwan recovered on {srv['name']}",
                "detail":  "VPN daemon is running again.",
            })

        # Capacity warning (only alert once per threshold crossing)
        cap_pct = srv["users"] / MAX_USERS * 100
        prev_cap = prev.get("users", 0) / MAX_USERS * 100
        if cap_pct >= CAP_ALERT_PCT and prev_cap < CAP_ALERT_PCT:
            alerts.append({
                "level":   "warning",
                "server":  srv["name"],
                "message": f"⚠️ {srv['name']} at {cap_pct:.0f}% capacity",
                "detail":  f"{srv['users']}/{MAX_USERS} users. Consider adding a server.",
            })

        # CPU warning
        if srv["cpu"] >= CPU_ALERT_PCT and prev.get("cpu", 0) < CPU_ALERT_PCT:
            alerts.append({
                "level":   "warning",
                "server":  srv["name"],
                "message": f"⚠️ High CPU on {srv['name']}: {srv['cpu']:.0f}%",
                "detail":  f"CPU has been above {CPU_ALERT_PCT:.0f}% threshold.",
            })

        # Update state
        state[sid] = {
            "reachable": srv["reachable"],
            "vpn_up":    srv["vpn_up"],
            "users":     srv["users"],
            "cpu":       srv["cpu"],
            "last_seen": now,
        }

    return alerts


# ── Alert delivery ────────────────────────────────────────────────────────────

def send_telegram(message: str):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"},
            timeout=8,
        )
    except Exception as e:
        log.error(f"Telegram alert failed: {e}")


def send_alert_email(subject: str, body: str):
    if not ALERT_EMAIL or not SMTP_USER:
        return
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = f"Turnip Monitor <{FROM_EMAIL}>"
        msg["To"]      = ALERT_EMAIL
        msg.attach(MIMEText(body, "plain"))
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
            s.starttls()
            s.login(SMTP_USER, SMTP_PASS)
            s.sendmail(FROM_EMAIL, ALERT_EMAIL, msg.as_string())
    except Exception as e:
        log.error(f"Alert email failed: {e}")


def dispatch_alert(alert: dict):
    msg   = alert["message"]
    detail = alert["detail"]
    full  = f"Turnip VPN Alert\n{msg}\n{detail}\n{datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"

    log.warning(f"ALERT [{alert['level']}]: {msg}")
    send_telegram(f"<b>Turnip VPN</b>\n{msg}\n<i>{detail}</i>")
    send_alert_email(f"[Turnip VPN] {msg}", full)


# ── Main loop ─────────────────────────────────────────────────────────────────

def run():
    log.info("Turnip monitor starting")
    log.info(f"Check interval: {CHECK_INTERVAL}s | CPU threshold: {CPU_ALERT_PCT}% | Capacity threshold: {CAP_ALERT_PCT}%")

    if TELEGRAM_TOKEN:
        log.info("Telegram alerts: enabled")
        send_telegram("🟢 <b>Turnip VPN Monitor started</b>\nAll systems nominal.")
    if ALERT_EMAIL:
        log.info(f"Email alerts: enabled → {ALERT_EMAIL}")

    state = load_state()

    while True:
        try:
            current = check_all_servers()
            alerts  = evaluate_alerts(current, state)
            save_state(state)

            for alert in alerts:
                dispatch_alert(alert)

            # Log summary every cycle
            for srv in current:
                status = "UP" if srv.get("vpn_up") else ("OFFLINE" if not srv.get("reachable") else "DEGRADED")
                log.info(
                    f"{srv['name']:12} | {status:8} | "
                    f"users={srv.get('users',0):3}/{MAX_USERS} | "
                    f"tunnels={srv.get('tunnels',0):3} | "
                    f"cpu={srv.get('cpu',0):.1f}%"
                )

        except Exception as e:
            log.error(f"Monitor cycle error: {e}")

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    run()
