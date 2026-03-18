#!/usr/bin/env python3
"""
Turnip VPN — Expiry Manager (run as daily cron)
1. Disables VPN accounts that have passed their expiry date
2. Sends renewal reminder emails 3 days before expiry

Cron setup (runs daily at 2am):
  0 2 * * * /usr/bin/python3 /opt/turnip/cron_expire.py >> /var/log/turnip-cron.log 2>&1

Or install via the setup script:
  bash install-payments.sh
"""

import os, logging
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)

from database import db_init, get_expired_active, get_expiring_soon, update_subscription_status
from provisioner import deprovision_user
from emailer import FROM_EMAIL, FROM_NAME

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

SMTP_HOST  = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT  = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER  = os.environ.get("SMTP_USER", "")
SMTP_PASS  = os.environ.get("SMTP_PASS", "")
VPN_SERVER = os.environ.get("VPN_SERVER_ADDR", "vpn.yourdomain.com")


def disable_expired():
    """Find and disable all accounts past their expiry date."""
    expired = get_expired_active()
    if not expired:
        log.info("No expired accounts found")
        return

    for sub in expired:
        log.info(f"Disabling expired account: {sub['username']} ({sub['email']}) — expired {sub['expires_at']}")
        deprovision_user(sub["username"])
        update_subscription_status(sub["email"], "expired")
        send_expiry_notice(sub["email"], sub["expires_at"])

    log.info(f"Disabled {len(expired)} expired account(s)")


def send_renewal_reminders():
    """Send reminder emails to users expiring within 3 days."""
    expiring = get_expiring_soon(days=3)
    if not expiring:
        log.info("No accounts expiring soon")
        return

    for sub in expiring:
        log.info(f"Sending renewal reminder: {sub['email']} expires {sub['expires_at']}")
        send_reminder_email(sub["email"], sub["expires_at"], sub["plan_name"])

    log.info(f"Sent {len(expiring)} renewal reminder(s)")


def send_expiry_notice(email: str, expired_at: str):
    try:
        dt = datetime.fromisoformat(expired_at).strftime("%B %d, %Y")
    except Exception:
        dt = expired_at

    subject = "Your Turnip VPN subscription has expired"
    html = f"""<!DOCTYPE html>
<html><body style="background:#050810;font-family:-apple-system,sans-serif;padding:40px 20px;max-width:520px;margin:0 auto">
  <div style="font-size:20px;font-weight:800;color:#e8f0fe;margin-bottom:24px">Secure<span style="color:#00c896">Fast</span> VPN</div>
  <div style="background:#0a0e1a;border:1px solid rgba(255,71,87,0.2);border-radius:12px;padding:28px">
    <h1 style="font-size:18px;color:#e8f0fe;margin:0 0 12px">Your subscription has expired</h1>
    <p style="color:#8899b4;font-size:14px;line-height:1.6;margin:0 0 20px">
      Your Turnip VPN account expired on <strong style="color:#e8f0fe">{dt}</strong>
      and has been deactivated. Renew now to restore your VPN access.
    </p>
    <a href="https://{VPN_SERVER}/pricing" style="display:block;background:#00c896;color:#050810;text-align:center;padding:12px 20px;border-radius:8px;text-decoration:none;font-weight:800">Renew subscription →</a>
  </div>
  <div style="font-size:11px;color:#4a5568;text-align:center;margin-top:24px">Turnip VPN · Zero logs · AES-256</div>
</body></html>"""

    _send_plain(email, subject, html)


def send_reminder_email(email: str, expires_at: str, plan_name: str):
    try:
        dt = datetime.fromisoformat(expires_at).strftime("%B %d, %Y")
    except Exception:
        dt = expires_at

    subject = f"Turnip VPN renews in 3 days — {dt}"
    html = f"""<!DOCTYPE html>
<html><body style="background:#050810;font-family:-apple-system,sans-serif;padding:40px 20px;max-width:520px;margin:0 auto">
  <div style="font-size:20px;font-weight:800;color:#e8f0fe;margin-bottom:24px">Secure<span style="color:#00c896">Fast</span> VPN</div>
  <div style="background:#0a0e1a;border:1px solid rgba(255,184,48,0.2);border-radius:12px;padding:28px">
    <h1 style="font-size:18px;color:#e8f0fe;margin:0 0 12px">Your VPN expires in 3 days</h1>
    <p style="color:#8899b4;font-size:14px;line-height:1.6;margin:0 0 20px">
      Your <strong style="color:#e8f0fe">{plan_name}</strong> subscription expires on
      <strong style="color:#e8f0fe">{dt}</strong>. Renew now to avoid any interruption
      in your encrypted connection.
    </p>
    <a href="https://{VPN_SERVER}/pricing" style="display:block;background:#00c896;color:#050810;text-align:center;padding:12px 20px;border-radius:8px;text-decoration:none;font-weight:800">Renew now →</a>
  </div>
  <div style="font-size:11px;color:#4a5568;text-align:center;margin-top:24px">Turnip VPN · Zero logs · AES-256</div>
</body></html>"""

    _send_plain(email, subject, html)


def _send_plain(to: str, subject: str, html: str):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"{FROM_NAME} <{FROM_EMAIL}>"
    msg["To"]      = to
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(FROM_EMAIL, to, msg.as_string())
        log.info(f"Email sent to {to}: {subject}")
    except Exception as e:
        log.error(f"Failed to send email to {to}: {e}")


if __name__ == "__main__":
    log.info("=== Turnip expiry cron starting ===")
    db_init()
    disable_expired()
    send_renewal_reminders()
    log.info("=== Cron complete ===")
