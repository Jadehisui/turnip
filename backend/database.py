#!/usr/bin/env python3
"""
Turnip VPN — Database Layer
SQLite for single-server deployments. Swap to PostgreSQL easily — 
just change the connection string and install psycopg2.

Tables:
  subscriptions — one row per active/past customer
  payments      — payment event log
"""

import os, sqlite3, logging
from datetime import datetime, timedelta
from contextlib import contextmanager
from pathlib import Path

log = logging.getLogger(__name__)

DB_PATH = os.environ.get("DB_PATH", "/opt/turnip/payments.db")


# ── Connection ─────────────────────────────────────────────────────────────────

@contextmanager
def get_conn():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Schema ─────────────────────────────────────────────────────────────────────

def db_init():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                email        TEXT NOT NULL,
                username     TEXT NOT NULL,
                password     TEXT NOT NULL,
                plan_name    TEXT NOT NULL,
                status       TEXT NOT NULL DEFAULT 'active',
                                            -- active | expired | disabled | non_renewing
                wallet_address TEXT,
                server_region  TEXT NOT NULL DEFAULT 'us',
                expires_at   TEXT NOT NULL,
                created_at   TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS subscription_devices (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                email         TEXT NOT NULL,
                device_number INTEGER NOT NULL,
                username      TEXT NOT NULL,
                password      TEXT NOT NULL,
                server_region TEXT NOT NULL DEFAULT 'us',
                created_at    TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE(email, device_number)
            );

            CREATE TABLE IF NOT EXISTS payments (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                email        TEXT NOT NULL,
                reference    TEXT UNIQUE NOT NULL,
                amount       REAL NOT NULL,
                plan_name    TEXT NOT NULL,
                duration_days INTEGER NOT NULL,
                username     TEXT NOT NULL,
                created_at   TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_sub_email     ON subscriptions(email);
            CREATE INDEX IF NOT EXISTS idx_sub_username  ON subscriptions(username);
            CREATE INDEX IF NOT EXISTS idx_dev_email     ON subscription_devices(email);
            CREATE INDEX IF NOT EXISTS idx_pay_reference ON payments(reference);
        """)
        # Migrate existing DBs that lack server_region column
        try:
            conn.execute("ALTER TABLE subscriptions ADD COLUMN server_region TEXT NOT NULL DEFAULT 'us'")
        except Exception:
            pass  # column already exists
    log.info(f"Database initialised at {DB_PATH}")


# ── Write operations ───────────────────────────────────────────────────────────

def record_payment(
    email: str,
    reference: str,
    amount: float,
    plan_name: str,
    duration_days: int,
    username: str,
    password: str,
    region: str = "us",
    devices: list = None,
):
    """Record a confirmed payment and create/extend a subscription."""
    expires_at = (datetime.utcnow() + timedelta(days=duration_days)).isoformat()
    now        = datetime.utcnow().isoformat()

    with get_conn() as conn:
        # Log the payment
        conn.execute("""
            INSERT OR IGNORE INTO payments
                (email, reference, amount, plan_name, duration_days, username)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (email, reference, amount, plan_name, duration_days, username))

        # Create or extend subscription
        existing = conn.execute(
            "SELECT id FROM subscriptions WHERE email = ?", (email,)
        ).fetchone()

        if existing:
            conn.execute("""
                UPDATE subscriptions
                SET username=?, password=?, plan_name=?, status='active',
                    server_region=?, expires_at=?, updated_at=?
                WHERE email=?
            """, (username, password, plan_name, region, expires_at, now, email))
            log.info(f"Subscription renewed: {email}")
        else:
            conn.execute("""
                INSERT INTO subscriptions
                    (email, username, password, plan_name, status, server_region, expires_at, created_at, updated_at)
                VALUES (?, ?, ?, ?, 'active', ?, ?, ?, ?)
            """, (email, username, password, plan_name, region, expires_at, now, now))
            log.info(f"New subscription: {email} → {username}")

        # Store per-device credentials
        if devices:
            conn.execute("DELETE FROM subscription_devices WHERE email = ?", (email,))
            for dev in devices:
                conn.execute("""
                    INSERT INTO subscription_devices
                        (email, device_number, username, password, server_region)
                    VALUES (?, ?, ?, ?, ?)
                """, (email, dev["device_number"], dev["username"], dev["password"], region))


def get_devices_for_email(email: str) -> list[dict]:
    """Return all per-device credentials for a subscriber."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM subscription_devices WHERE email = ? ORDER BY device_number ASC",
            (email,)
        ).fetchall()
        return [dict(r) for r in rows]


def update_subscription_status(email: str, status: str):
    with get_conn() as conn:
        conn.execute("""
            UPDATE subscriptions
            SET status=?, updated_at=datetime('now')
            WHERE email=?
        """, (status, email))


# ── Read operations ────────────────────────────────────────────────────────────

def get_subscription(reference: str = None, email: str = None, wallet: str = None) -> dict | None:
    with get_conn() as conn:
        if reference:
            row = conn.execute(
                "SELECT * FROM payments WHERE reference = ?", (reference,)
            ).fetchone()
        elif email:
            row = conn.execute(
                "SELECT * FROM subscriptions WHERE email = ? ORDER BY id DESC LIMIT 1",
                (email,)
            ).fetchone()
        elif wallet:
            row = conn.execute(
                "SELECT * FROM subscriptions WHERE wallet_address = ? ORDER BY id DESC LIMIT 1",
                (wallet,)
            ).fetchone()
        else:
            return None
        return dict(row) if row else None


def get_all_subscriptions() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT s.*, p.amount, p.reference
            FROM subscriptions s
            LEFT JOIN payments p ON p.username = s.username
            ORDER BY s.created_at DESC
        """).fetchall()
        return [dict(r) for r in rows]


def get_expiring_soon(days: int = 3) -> list[dict]:
    """Return subscriptions expiring within `days` days."""
    cutoff = (datetime.utcnow() + timedelta(days=days)).isoformat()
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT * FROM subscriptions
            WHERE status = 'active'
            AND expires_at <= ?
            ORDER BY expires_at ASC
        """, (cutoff,)).fetchall()
        return [dict(r) for r in rows]


def get_expired_active() -> list[dict]:
    """Return subscriptions that have passed expiry but are still marked active."""
    now = datetime.utcnow().isoformat()
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT * FROM subscriptions
            WHERE status = 'active'
            AND expires_at < ?
        """, (now,)).fetchall()
        return [dict(r) for r in rows]
