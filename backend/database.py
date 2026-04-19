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

            CREATE TABLE IF NOT EXISTS users (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                name         TEXT NOT NULL,
                email        TEXT NOT NULL UNIQUE,
                status       TEXT NOT NULL DEFAULT 'registered',
                created_at   TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS otps (
                email      TEXT PRIMARY KEY,
                code       TEXT NOT NULL,
                expires_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS pending_payments (
                iid        TEXT PRIMARY KEY,
                email      TEXT NOT NULL,
                plan_code  TEXT NOT NULL,
                region     TEXT NOT NULL DEFAULT 'eu',
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_sub_email     ON subscriptions(email);
            CREATE INDEX IF NOT EXISTS idx_sub_username  ON subscriptions(username);
            CREATE INDEX IF NOT EXISTS idx_dev_email     ON subscription_devices(email);
            CREATE INDEX IF NOT EXISTS idx_pay_reference ON payments(reference);
            CREATE INDEX IF NOT EXISTS idx_users_email   ON users(email);
        """)
        # Migrate existing DBs that lack server_region column
        try:
            conn.execute("ALTER TABLE subscriptions ADD COLUMN server_region TEXT NOT NULL DEFAULT 'us'")
        except Exception:
            pass  # column already exists
        # Migrate existing DBs that lack pending_payments table
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pending_payments (
                    iid        TEXT PRIMARY KEY,
                    email      TEXT NOT NULL,
                    plan_code  TEXT NOT NULL,
                    region     TEXT NOT NULL DEFAULT 'eu',
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """)
        except Exception:
            pass
    log.info(f"Database initialised at {DB_PATH}")


# ── OTP helpers ────────────────────────────────────────────────────────────────

def store_otp(email: str, code: str, expires_at: float):
    """Persist a one-time password for an email (upsert — one OTP per email at a time)."""
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO otps (email, code, expires_at) VALUES (?, ?, ?)",
            (email, code, expires_at),
        )


def verify_and_consume_otp(email: str, code: str) -> tuple:
    """
    Check the stored OTP for email against code.
    Returns (True, None) on success and deletes the OTP row.
    Returns (False, error_message) on failure; also deletes expired rows.
    """
    import time
    with get_conn() as conn:
        row = conn.execute(
            "SELECT code, expires_at FROM otps WHERE email = ?", (email,)
        ).fetchone()
        if not row:
            return False, "Code expired or not requested. Please try again."
        if time.time() > row["expires_at"]:
            conn.execute("DELETE FROM otps WHERE email = ?", (email,))
            return False, "Code has expired. Please request a new one."
        if code != row["code"]:
            return False, "Incorrect code. Please check your email."
        conn.execute("DELETE FROM otps WHERE email = ?", (email,))
        return True, None


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


def clear_devices_for_email(email: str) -> int:
    """Delete all per-device credential rows for a subscriber email."""
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM subscription_devices WHERE email = ?", (email.strip().lower(),))
        return cur.rowcount


def update_subscription_status(email: str, status: str, subscription_id: int | None = None):
    with get_conn() as conn:
        if subscription_id is not None:
            conn.execute("""
                UPDATE subscriptions
                SET status=?, updated_at=datetime('now')
                WHERE id=?
            """, (status, subscription_id))
        else:
            conn.execute("""
                UPDATE subscriptions
                SET status=?, updated_at=datetime('now')
                WHERE email=?
            """, (status, email))


def admin_update_subscription(email: str, status: str = None,
                              expires_at: str = None, extend_days: int = None):
    """Admin: update subscription status and/or extend expiry."""
    now = datetime.utcnow().isoformat()
    with get_conn() as conn:
        if extend_days:
            row = conn.execute(
                "SELECT expires_at FROM subscriptions WHERE email=? ORDER BY id DESC LIMIT 1",
                (email,)
            ).fetchone()
            base = datetime.utcnow()
            if row:
                try:
                    current_expiry = datetime.fromisoformat(row["expires_at"])
                    base = max(current_expiry, datetime.utcnow())
                except Exception:
                    pass
            expires_at = (base + timedelta(days=extend_days)).isoformat()

        updates = ["updated_at=?"]
        params  = [now]
        if status:
            updates.append("status=?")
            params.append(status)
        if expires_at:
            updates.append("expires_at=?")
            params.append(expires_at)
        params.append(email)
        conn.execute(
            f"UPDATE subscriptions SET {', '.join(updates)} WHERE email=?",
            params
        )


def admin_save_provisioned_credentials(
    email: str,
    plan_name: str,
    region: str,
    creds: dict,
    duration_days: int = 30,
    status: str = "active",
):
    """Persist admin-generated credentials into subscriptions and subscription_devices."""
    email = email.strip().lower()
    now = datetime.utcnow().isoformat()
    expires_at = (datetime.utcnow() + timedelta(days=max(1, int(duration_days or 30)))).isoformat()

    username = creds["username"]
    password = creds["password"]
    devices = creds.get("devices") or []

    with get_conn() as conn:
        existing = conn.execute(
            "SELECT id FROM subscriptions WHERE email = ? ORDER BY id DESC LIMIT 1",
            (email,)
        ).fetchone()

        if existing:
            conn.execute(
                """
                UPDATE subscriptions
                SET username=?, password=?, plan_name=?, status=?, server_region=?, expires_at=?, updated_at=?
                WHERE id=?
                """,
                (username, password, plan_name, status, region, expires_at, now, existing["id"])
            )
        else:
            conn.execute(
                """
                INSERT INTO subscriptions
                    (email, username, password, plan_name, status, server_region, expires_at, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (email, username, password, plan_name, status, region, expires_at, now, now)
            )

        conn.execute("DELETE FROM subscription_devices WHERE email = ?", (email,))
        for dev in devices:
            conn.execute(
                """
                INSERT INTO subscription_devices
                    (email, device_number, username, password, server_region)
                VALUES (?, ?, ?, ?, ?)
                """,
                (email, dev["device_number"], dev["username"], dev["password"], region)
            )


# ── Read operations ────────────────────────────────────────────────────────────

def payment_exists(reference: str) -> bool:
    """Return True if a payment with this reference has already been processed (dedup check)."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM payments WHERE reference = ?", (reference,)
        ).fetchone()
        return row is not None


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


# ── User registration ──────────────────────────────────────────────────────────

def register_user(name: str, email: str) -> dict:
    """Register a new user by name + email. Returns the user row or raises on duplicate."""
    now = datetime.utcnow().isoformat()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO users (name, email, status, created_at) VALUES (?, ?, 'registered', ?)",
            (name.strip(), email.strip().lower(), now)
        )
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email.strip().lower(),)).fetchone()
        return dict(row)


def get_user(email: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE email = ?", (email.strip().lower(),)
        ).fetchone()
        return dict(row) if row else None


def ensure_user(email: str) -> None:
    """
    Ensure a users row exists for this email.
    Called by webhooks after payment so the user can always log in via OTP,
    even if they never went through the registration form.
    No-op if the row already exists.
    """
    email = email.strip().lower()
    now   = datetime.utcnow().isoformat()
    with get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO users (name, email, status, created_at) VALUES (?, ?, 'active', ?)",
            (email, email, now),
        )


def get_all_users() -> list[dict]:
    """Return all registered users joined with subscription info if available."""
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT u.id, u.name, u.email, u.status, u.created_at,
                   s.plan_name, s.status AS sub_status, s.expires_at
            FROM users u
            LEFT JOIN subscriptions s ON s.email = u.email
            ORDER BY u.created_at DESC
        """).fetchall()
        return [dict(r) for r in rows]


# ── Pending payments (NOWPayments static-invoice flow) ─────────────────────────

def store_pending_payment(iid: str, email: str, plan_code: str, region: str) -> None:
    """Record that a user is about to pay a static NOWPayments invoice."""
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO pending_payments (iid, email, plan_code, region) VALUES (?, ?, ?, ?)",
            (iid, email.strip().lower(), plan_code.lower(), region),
        )


def get_pending_payment(iid: str) -> dict | None:
    """Look up the email/plan stored for a NOWPayments invoice ID."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM pending_payments WHERE iid = ?", (iid,)
        ).fetchone()
        return dict(row) if row else None


def delete_pending_payment(iid: str) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM pending_payments WHERE iid = ?", (iid,))
