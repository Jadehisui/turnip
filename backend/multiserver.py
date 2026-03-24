#!/usr/bin/env python3
"""
Turnip VPN — Multi-Server Provisioner
Manages VPN credentials across multiple regional servers via SSH.
Assigns users to the best (lowest load) server automatically.

Regions: Netherlands, United States, Canada, Singapore
"""

import os, json, re, subprocess, secrets, string, logging, paramiko
from dataclasses import dataclass, asdict
from typing import Optional
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
log = logging.getLogger(__name__)

SSH_KEY_PATH   = os.environ.get("SSH_KEY_PATH",  "/root/.ssh/turnip_deploy")
MAX_PER_SERVER = int(os.environ.get("MAX_USERS",  "80"))
SECRETS_FILE   = "/etc/ipsec.secrets"

CONTINENT_LABELS = {
    "eu": {"name": "Europe",        "flag": "🌍"},
    "na": {"name": "North America", "flag": "🌎"},
    "as": {"name": "Asia",          "flag": "🌏"},
}


# ── Server registry ───────────────────────────────────────────────────────────

@dataclass
class VPNServer:
    id:        str
    name:      str
    country:   str
    flag:      str
    host:      str          # IP or hostname
    region:    str          # nl | us | ca | sg | de | uk | jp | in
    continent: str = ""    # eu | na | as
    active:    bool = True

    def to_dict(self):
        return asdict(self)


def load_servers() -> list[VPNServer]:
    """Load server list from servers.json or environment."""
    # Check production path first, then local (dev) path
    for path in (Path("/opt/turnip/servers.json"), Path(__file__).parent / "servers.json"):
        if path.exists():
            data = json.loads(path.read_text())
            return [VPNServer(**s) for s in data]

    # Fallback: build from env vars
    servers = []
    for i in range(1, 9):
        host = os.environ.get(f"SERVER_{i}_HOST")
        if not host:
            break
        servers.append(VPNServer(
            id=f"server-{i}",
            name=os.environ.get(f"SERVER_{i}_NAME", f"Server {i}"),
            country=os.environ.get(f"SERVER_{i}_COUNTRY", "Unknown"),
            flag=os.environ.get(f"SERVER_{i}_FLAG", "🌐"),
            host=host,
            region=os.environ.get(f"SERVER_{i}_REGION", "unknown"),
        ))
    return servers


# ── SSH helpers ───────────────────────────────────────────────────────────────

def _ssh_connect(host: str) -> paramiko.SSHClient:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        hostname=host,
        username="root",
        key_filename=SSH_KEY_PATH,
        timeout=10,
    )
    return client


def _ssh_run(host: str, cmd: str, timeout: int = 15) -> tuple[str, str, int]:
    """Run command on remote host. Returns (stdout, stderr, exit_code)."""
    try:
        client = _ssh_connect(host)
        _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
        exit_code = stdout.channel.recv_exit_status()
        out = stdout.read().decode().strip()
        err = stderr.read().decode().strip()
        client.close()
        return out, err, exit_code
    except Exception as e:
        log.error(f"SSH error on {host}: {e}")
        return "", str(e), 1


def _ssh_read_file(host: str, path: str) -> Optional[str]:
    try:
        client = _ssh_connect(host)
        sftp = client.open_sftp()
        with sftp.open(path) as f:
            content = f.read().decode()
        sftp.close()
        client.close()
        return content
    except Exception as e:
        log.error(f"SFTP read {host}:{path} failed: {e}")
        return None


def _ssh_append_file(host: str, path: str, content: str) -> bool:
    try:
        client = _ssh_connect(host)
        sftp = client.open_sftp()
        with sftp.open(path, "a") as f:
            f.write(content)
        sftp.close()
        client.close()
        return True
    except Exception as e:
        log.error(f"SFTP append {host}:{path} failed: {e}")
        return False


def _ssh_write_file(host: str, path: str, content: str) -> bool:
    try:
        client = _ssh_connect(host)
        sftp = client.open_sftp()
        with sftp.open(path, "w") as f:
            f.write(content)
        sftp.close()
        client.close()
        return True
    except Exception as e:
        log.error(f"SFTP write {host}:{path} failed: {e}")
        return False


# ── Server stats ──────────────────────────────────────────────────────────────

def get_server_user_count(host: str) -> int:
    out, _, code = _ssh_run(host, f"grep -c 'EAP' {SECRETS_FILE} || echo 0")
    try:
        return int(out.strip())
    except Exception:
        return MAX_PER_SERVER  # treat as full if unreachable


def get_server_load(host: str) -> dict:
    """Get CPU load and user count from a server."""
    out, _, code = _ssh_run(
        host,
        "echo CPU:$(top -bn1 | grep 'Cpu(s)' | awk '{print $2}') "
        "USERS:$(grep -c 'EAP' /etc/ipsec.secrets 2>/dev/null || echo 0) "
        "TUNNELS:$(ipsec status 2>/dev/null | grep -c ESTABLISHED || echo 0)"
    )
    result = {"cpu": 0.0, "users": MAX_PER_SERVER, "tunnels": 0, "reachable": code == 0}
    if code == 0:
        for part in out.split():
            k, _, v = part.partition(":")
            if k == "CPU":
                try: result["cpu"] = float(v.replace(",", ".").replace("%us", ""))
                except: pass
            elif k == "USERS":
                try: result["users"] = int(v)
                except: pass
            elif k == "TUNNELS":
                try: result["tunnels"] = int(v)
                except: pass
    return result


def get_best_server(servers: list[VPNServer]) -> Optional[VPNServer]:
    """
    Pick the active server with the most available capacity.
    Ties broken by lowest CPU load.
    """
    best = None
    best_score = -1

    for srv in servers:
        if not srv.active:
            continue
        stats = get_server_load(srv.host)
        if not stats["reachable"]:
            log.warning(f"Server {srv.name} ({srv.host}) unreachable")
            continue
        slots = MAX_PER_SERVER - stats["users"]
        if slots <= 0:
            continue
        # Score: available slots, penalised by CPU
        score = slots - (stats["cpu"] / 100 * 10)
        if score > best_score:
            best_score = score
            best = srv

    return best


def get_best_server_for_continent(continent: str) -> Optional[VPNServer]:
    """
    Pick the best active server within a given continent (eu/na/as).
    Falls back to global best if no servers exist for that continent.
    """
    servers = load_servers()
    continent_servers = [s for s in servers if s.active and s.continent == continent]
    if continent_servers:
        return get_best_server(continent_servers)
    log.warning(f"No active servers for continent '{continent}' — using global best")
    return get_best_server(servers)


def get_available_continents() -> list[dict]:
    """
    Return continents that have at least one active server, with server count.
    Used by the frontend region picker.
    """
    servers = load_servers()
    found: dict[str, dict] = {}
    for s in servers:
        if not s.active or not s.continent:
            continue
        if s.continent not in found:
            label = CONTINENT_LABELS.get(s.continent, {"name": s.continent.upper(), "flag": "🌐"})
            found[s.continent] = {
                "continent":    s.continent,
                "name":         label["name"],
                "flag":         label["flag"],
                "server_count": 0,
            }
        found[s.continent]["server_count"] += 1
    return list(found.values())


# ── Remote user management ────────────────────────────────────────────────────

def add_user_to_server(host: str, username: str, password: str) -> bool:
    """Append EAP user to remote ipsec.secrets and reload."""
    line = f'\n{username} : EAP "{password}"\n'
    ok = _ssh_append_file(host, SECRETS_FILE, line)
    if ok:
        _ssh_run(host, "ipsec secrets")
        log.info(f"User {username} added to {host}")
    return ok


def remove_user_from_server(host: str, username: str) -> bool:
    """Remove EAP user from remote ipsec.secrets and reload."""
    content = _ssh_read_file(host, SECRETS_FILE)
    if content is None:
        return False
    lines = [l for l in content.splitlines(keepends=True)
             if not l.strip().startswith(f"{username} :")]
    ok = _ssh_write_file(host, SECRETS_FILE, "".join(lines))
    if ok:
        _ssh_run(host, "ipsec secrets")
        log.info(f"User {username} removed from {host}")
    return ok


def sync_user_to_all_servers(username: str, password: str, servers: list[VPNServer]) -> list[str]:
    """
    Add a user to ALL active servers (useful for multi-hop / roaming).
    Returns list of server IDs where provisioning succeeded.
    """
    succeeded = []
    for srv in servers:
        if not srv.active:
            continue
        ok = add_user_to_server(srv.host, username, password)
        if ok:
            succeeded.append(srv.id)
        else:
            log.warning(f"Failed to sync {username} to {srv.name}")
    return succeeded


def remove_user_from_all_servers(username: str, servers: list[VPNServer]) -> list[str]:
    """Remove user from every server."""
    removed = []
    for srv in servers:
        if not srv.active:
            continue
        ok = remove_user_from_server(srv.host, username)
        if ok:
            removed.append(srv.id)
    return removed


# ── High-level provisioning API ───────────────────────────────────────────────

def provision_user_multiserver(email: str, plan: dict) -> dict:
    """
    Full multi-server provisioning flow:
    1. Pick best server by capacity
    2. Create credentials
    3. Add user (single server for Basic/Pro, all servers for Business)
    4. Return creds with assigned server info
    """
    servers = load_servers()

    if plan.get("devices", 1) == 999:
        # Business plan: sync to all servers
        target_server = servers[0] if servers else None
        server_ids = sync_user_to_all_servers(
            _gen_username(email), _gen_password(), servers
        )
        assigned_servers = [s for s in servers if s.id in server_ids]
    else:
        target_server = get_best_server(servers)
        if not target_server:
            raise RuntimeError("All servers are at capacity or unreachable")
        assigned_servers = [target_server]

    username = _gen_username(email)
    password = _gen_password()

    for srv in assigned_servers:
        add_user_to_server(srv.host, username, password)

    primary = assigned_servers[0] if assigned_servers else None

    return {
        "username":       username,
        "password":       password,
        "server":         primary.host if primary else "",
        "server_name":    primary.name if primary else "",
        "server_region":  primary.region if primary else "",
        "all_servers":    [s.to_dict() for s in assigned_servers],
        "email":          email,
    }


def _gen_username(email: str) -> str:
    local = re.sub(r"[^a-zA-Z0-9]", "", email.split("@")[0])[:12].lower()
    return f"vpn_{local}_{secrets.token_hex(3)}"


def _gen_password(length: int = 20) -> str:
    chars = string.ascii_letters + string.digits + "!@#$"
    return "".join(secrets.choice(chars) for _ in range(length))


# ── Server fleet status ───────────────────────────────────────────────────────

def get_fleet_status() -> list[dict]:
    """Get load stats for all servers. Used by admin dashboard."""
    servers = load_servers()
    results = []
    for srv in servers:
        stats = get_server_load(srv.host)
        results.append({
            **srv.to_dict(),
            **stats,
            "capacity_pct": round(stats["users"] / MAX_PER_SERVER * 100, 1),
            "slots_free":   max(0, MAX_PER_SERVER - stats["users"]),
        })
    return results
