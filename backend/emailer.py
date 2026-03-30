#!/usr/bin/env python3
"""
Turnip VPN — Email Delivery
Sends the welcome email with:
  - VPN credentials (username/password/server)
  - .mobileconfig attachment (iOS/macOS one-tap install)
  - Setup instructions for Windows, Android, Linux

Supports SMTP (any provider) and SendGrid.
Set EMAIL_PROVIDER=smtp or sendgrid in .env
"""

import os, base64, smtplib, logging
from email.mime.multipart  import MIMEMultipart
from email.mime.text       import MIMEText
from email.mime.base       import MIMEBase
from email import encoders

log = logging.getLogger(__name__)

EMAIL_PROVIDER  = os.environ.get("EMAIL_PROVIDER",  "smtp")      # smtp | sendgrid
SMTP_HOST       = os.environ.get("SMTP_HOST",       "smtp.gmail.com")
SMTP_PORT       = int(os.environ.get("SMTP_PORT",   "587"))
SMTP_USER       = os.environ.get("SMTP_USER",       "")
SMTP_PASS       = os.environ.get("SMTP_PASS",       "")
FROM_EMAIL      = os.environ.get("FROM_EMAIL",      "noreply@turnip.com")
FROM_NAME       = os.environ.get("FROM_NAME",       "Turnip VPN")
SENDGRID_KEY    = os.environ.get("SENDGRID_API_KEY","")


# ── Public entrypoint ─────────────────────────────────────────────────────────

def send_welcome_email(to_email: str, creds: dict, plan: dict):
    """Send welcome email with credentials and .mobileconfig attachment."""
    subject  = "Your Turnip VPN is ready — connect in 60 seconds"
    html     = _build_html(creds, plan)
    text     = _build_text(creds, plan)
    profile  = base64.b64decode(creds["mobileconfig_b64"])
    filename = f"turnip-{creds['username']}.mobileconfig"

    if EMAIL_PROVIDER == "sendgrid":
        _send_sendgrid(to_email, subject, html, text, profile, filename)
    else:
        _send_smtp(to_email, subject, html, text, profile, filename)

    log.info(f"Email delivered to {to_email}")


def send_user_welcome_email(user_name: str, user_email: str):
    """Send a styled welcome email directing the new user to pick a plan."""
    site_url = os.environ.get("SITE_URL", "https://turnipvpn.site")
    subject  = "Your account is ready"
    text = (
        f"Hi {user_name},\n\n"
        f"Your Turnip VPN account has been created.\n\n"
        f"Next step — pick a plan to activate your connection:\n"
        f"{site_url}/pricing\n\n"
        f"Once your payment clears, your VPN credentials will be\n"
        f"sent to this address automatically.\n\n"
        f"— Turnip VPN\n"
        f"  {site_url}"
    )
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Your account is ready</title>
</head>
<body style="margin:0;padding:0;background:#020205;font-family:-apple-system,'Segoe UI',Helvetica,Arial,sans-serif">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#020205;padding:40px 16px">
    <tr><td align="center">
      <table width="540" cellpadding="0" cellspacing="0" style="background:#080812;border-radius:16px;overflow:hidden;border:1px solid rgba(168,85,247,0.18)">

        <!-- Header -->
        <tr>
          <td style="background:#0c0c1e;padding:28px 40px;border-bottom:1px solid rgba(168,85,247,0.18)">
            <span style="font-size:20px;font-weight:800;color:#f8fafc;letter-spacing:-0.5px;font-family:Arial,sans-serif">
              Turnip<span style="color:#a855f7">VPN</span>
            </span>
          </td>
        </tr>

        <!-- Body -->
        <tr>
          <td style="padding:40px">
            <p style="margin:0 0 8px;font-size:11px;font-weight:700;color:#a855f7;text-transform:uppercase;letter-spacing:.12em;font-family:'Courier New',monospace">Account created</p>
            <h1 style="margin:0 0 18px;font-size:26px;font-weight:800;color:#f8fafc;letter-spacing:-0.5px">Hi {user_name}, you're in.</h1>
            <p style="margin:0 0 28px;font-size:15px;color:#94a3b8;line-height:1.7">
              Your Turnip VPN account has been created successfully.<br>
              You're one step away from a fast, private internet connection.
            </p>

            <!-- Email info box -->
            <table width="100%" cellpadding="0" cellspacing="0" style="background:#0c0c1e;border:1px solid rgba(168,85,247,0.20);border-radius:10px;margin-bottom:28px">
              <tr>
                <td style="padding:18px 22px">
                  <p style="margin:0 0 5px;font-size:10px;font-weight:700;color:#475569;text-transform:uppercase;letter-spacing:.1em;font-family:'Courier New',monospace">Registered email</p>
                  <p style="margin:0;font-size:14px;font-weight:600;color:#f8fafc;font-family:'Courier New',monospace">{user_email}</p>
                </td>
              </tr>
            </table>

            <p style="margin:0 0 28px;font-size:14px;color:#94a3b8;line-height:1.7">
              <strong style="color:#f8fafc">Next step:</strong> choose a plan below.
              Once your payment is confirmed, your credentials will be delivered to this email automatically — no waiting.
            </p>

            <!-- CTA button -->
            <table cellpadding="0" cellspacing="0">
              <tr>
                <td style="background:#a855f7;border-radius:8px">
                  <a href="{site_url}/pricing"
                     style="display:inline-block;padding:14px 32px;font-size:15px;font-weight:800;color:#ffffff;text-decoration:none;letter-spacing:-0.2px;font-family:Arial,sans-serif">
                    View plans &amp; get started →
                  </a>
                </td>
              </tr>
            </table>
          </td>
        </tr>

        <!-- Divider -->
        <tr><td style="padding:0 40px"><div style="height:1px;background:rgba(168,85,247,0.12)"></div></td></tr>

        <!-- Feature strip -->
        <tr>
          <td style="padding:24px 40px">
            <table width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td width="33%" style="padding-right:12px;vertical-align:top">
                  <p style="margin:0 0 4px;font-size:12px;font-weight:700;color:#f8fafc;font-family:'Courier New',monospace">AES-256</p>
                  <p style="margin:0;font-size:12px;color:#475569">Military-grade encryption</p>
                </td>
                <td width="33%" style="padding-right:12px;vertical-align:top">
                  <p style="margin:0 0 4px;font-size:12px;font-weight:700;color:#f8fafc;font-family:'Courier New',monospace">Zero logs</p>
                  <p style="margin:0;font-size:12px;color:#475569">No traffic records kept</p>
                </td>
                <td width="33%" style="vertical-align:top">
                  <p style="margin:0 0 4px;font-size:12px;font-weight:700;color:#f8fafc;font-family:'Courier New',monospace">IKEv2/IPsec</p>
                  <p style="margin:0;font-size:12px;color:#475569">Native OS, no app needed</p>
                </td>
              </tr>
            </table>
          </td>
        </tr>

        <!-- Footer -->
        <tr>
          <td style="background:#0c0c1e;padding:20px 40px;border-top:1px solid rgba(168,85,247,0.12)">
            <p style="margin:0;font-size:12px;color:#475569;line-height:1.7">
              You're receiving this because you registered at
              <a href="{site_url}" style="color:#a855f7;text-decoration:none">turnipvpn.site</a>.
              Questions? Reply to this email.
            </p>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""
    try:
        if EMAIL_PROVIDER == "sendgrid":
            _send_simple_sendgrid(user_email, subject, html, text)
        else:
            _send_simple_smtp(user_email, subject, html, text)
        log.info(f"Welcome email sent to {user_email}")
    except Exception as e:
        log.error(f"Failed to send welcome email to {user_email}: {e}")


def send_otp_email(to_email: str, code: str):
    """Send a 6-digit OTP login code. Expires in 10 minutes."""
    site_url = os.environ.get("SITE_URL", "https://turnipvpn.site")
    subject  = f"{code} is your TurnipVPN login code"
    text = (
        f"Your TurnipVPN login code is: {code}\n\n"
        f"This code expires in 10 minutes.\n"
        f"If you did not request this, you can safely ignore this email.\n\n"
        f"— Turnip VPN\n  {site_url}"
    )
    html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Your login code</title></head>
<body style="margin:0;padding:0;background:#f0f0f5;font-family:-apple-system,'Segoe UI',Helvetica,Arial,sans-serif">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f0f0f5;padding:40px 16px">
    <tr><td align="center">
      <table width="480" cellpadding="0" cellspacing="0" style="background:#080812;border-radius:16px;overflow:hidden;border:1px solid rgba(168,85,247,0.18)">
        <tr>
          <td style="background:#0c0c1e;padding:24px 36px;border-bottom:1px solid rgba(168,85,247,0.18)">
            <span style="font-size:18px;font-weight:800;color:#f8fafc;letter-spacing:-0.5px;font-family:Arial,sans-serif">
              Turnip<span style="color:#a855f7">VPN</span>
            </span>
          </td>
        </tr>
        <tr>
          <td style="padding:36px">
            <p style="margin:0 0 6px;font-size:11px;font-weight:700;color:#a855f7;text-transform:uppercase;letter-spacing:.12em;font-family:'Courier New',monospace">Login code</p>
            <h1 style="margin:0 0 20px;font-size:22px;font-weight:800;color:#f8fafc">Verify your identity</h1>
            <p style="margin:0 0 28px;font-size:14px;color:#94a3b8;line-height:1.7">
              Use the code below to sign in to your TurnipVPN account.<br>
              It expires in <strong style="color:#f8fafc">10 minutes</strong>.
            </p>
            <table cellpadding="0" cellspacing="0" style="margin:0 auto 28px">
              <tr>
                <td style="background:#0c0c1e;border:2px solid rgba(168,85,247,0.4);border-radius:12px;padding:18px 40px;text-align:center">
                  <span style="font-size:36px;font-weight:900;letter-spacing:10px;color:#a855f7;font-family:'Courier New',monospace">{code}</span>
                </td>
              </tr>
            </table>
            <p style="margin:0;font-size:12px;color:#475569;line-height:1.7;text-align:center">
              If you did not request this code, ignore this email — your account is safe.
            </p>
          </td>
        </tr>
        <tr>
          <td style="background:#0c0c1e;padding:16px 36px;border-top:1px solid rgba(168,85,247,0.12)">
            <p style="margin:0;font-size:11px;color:#475569">
              <a href="{site_url}" style="color:#a855f7;text-decoration:none">turnipvpn.site</a>
            </p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""
    try:
        if EMAIL_PROVIDER == "sendgrid":
            _send_simple_sendgrid(to_email, subject, html, text)
        else:
            _send_simple_smtp(to_email, subject, html, text)
        log.info(f"OTP email sent to {to_email}")
    except Exception as e:
        log.error(f"Failed to send OTP email to {to_email}: {e}")
        raise


def send_registration_notification(user_name: str, user_email: str):
    """Send a plain admin notification to dev@turnipvpn.site when a new user registers."""
    admin_to = os.environ.get("ADMIN_NOTIFY_EMAIL", "dev@turnipvpn.site")
    subject  = f"New registration: {user_name} <{user_email}>"
    text     = (
        f"A new user just registered on Turnip VPN.\n\n"
        f"Name:  {user_name}\n"
        f"Email: {user_email}\n\n"
        f"They have been directed to the pricing page to pick a plan."
    )
    html = f"""<!DOCTYPE html>
<html><body style="font-family:sans-serif;color:#111;background:#fff;padding:24px">
<h2 style="color:#059669">New Turnip VPN Registration</h2>
<table>
  <tr><td style="padding:4px 12px 4px 0;font-weight:700">Name</td><td>{user_name}</td></tr>
  <tr><td style="padding:4px 12px 4px 0;font-weight:700">Email</td><td>{user_email}</td></tr>
</table>
<p style="color:#555;margin-top:16px">They have been directed to the pricing page to choose a plan.</p>
</body></html>"""

    try:
        if EMAIL_PROVIDER == "sendgrid":
            _send_simple_sendgrid(admin_to, subject, html, text)
        else:
            _send_simple_smtp(admin_to, subject, html, text)
        log.info(f"Admin registration notification sent for {user_email}")
    except Exception as e:
        log.error(f"Failed to send admin notification: {e}")


def _send_simple_smtp(to: str, subject: str, html: str, text: str):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"{FROM_NAME} <{FROM_EMAIL}>"
    msg["To"]      = to
    msg.attach(MIMEText(text, "plain"))
    msg.attach(MIMEText(html, "html"))
    if SMTP_PORT == 465:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as s:
            s.login(SMTP_USER, SMTP_PASS)
            s.sendmail(FROM_EMAIL, to, msg.as_string())
    else:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
            s.starttls()
            s.login(SMTP_USER, SMTP_PASS)
            s.sendmail(FROM_EMAIL, to, msg.as_string())


def _send_simple_sendgrid(to: str, subject: str, html: str, text: str):
    try:
        import sendgrid
        from sendgrid.helpers.mail import Mail, To, From
    except ImportError:
        log.error("sendgrid package not installed")
        raise
    sg = sendgrid.SendGridAPIClient(api_key=SENDGRID_KEY)
    message = Mail(
        from_email=From(FROM_EMAIL, FROM_NAME),
        to_emails=To(to),
        subject=subject,
        plain_text_content=text,
        html_content=html,
    )
    sg.send(message)


# ── SMTP sender ───────────────────────────────────────────────────────────────

def _send_smtp(to: str, subject: str, html: str, text: str,
               attachment: bytes, filename: str):
    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"]    = f"{FROM_NAME} <{FROM_EMAIL}>"
    msg["To"]      = to

    # Body (HTML + plain fallback)
    body = MIMEMultipart("alternative")
    body.attach(MIMEText(text, "plain"))
    body.attach(MIMEText(html, "html"))
    msg.attach(body)

    # .mobileconfig attachment
    part = MIMEBase("application", "x-apple-aspen-config")
    part.set_payload(attachment)
    encoders.encode_base64(part)
    part.add_header("Content-Disposition", f'attachment; filename="{filename}"')
    msg.attach(part)

    if SMTP_PORT == 465:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(FROM_EMAIL, to, msg.as_string())
    else:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(FROM_EMAIL, to, msg.as_string())


# ── SendGrid sender ───────────────────────────────────────────────────────────

def _send_sendgrid(to: str, subject: str, html: str, text: str,
                   attachment: bytes, filename: str):
    try:
        import sendgrid
        from sendgrid.helpers.mail import (
            Mail, Attachment, FileContent, FileName,
            FileType, Disposition, To, From,
        )
    except ImportError:
        log.error("sendgrid package not installed. Run: pip install sendgrid")
        raise

    sg = sendgrid.SendGridAPIClient(api_key=SENDGRID_KEY)

    message = Mail(
        from_email=From(FROM_EMAIL, FROM_NAME),
        to_emails=To(to),
        subject=subject,
        plain_text_content=text,
        html_content=html,
    )

    att = Attachment(
        FileContent(base64.b64encode(attachment).decode()),
        FileName(filename),
        FileType("application/x-apple-aspen-config"),
        Disposition("attachment"),
    )
    message.attachment = att
    sg.send(message)


# ── Email templates ───────────────────────────────────────────────────────────

def _build_html(creds: dict, plan: dict) -> str:
    username = creds["username"]
    password = creds["password"]
    server   = creds["server"]
    expiry   = creds["expiry_display"]
    plan_name= plan["name"]

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  body {{ margin:0; padding:0; background:#050810; font-family: -apple-system, 'Segoe UI', sans-serif; }}
  .wrap {{ max-width:560px; margin:0 auto; padding:40px 20px; }}
  .logo {{ font-size:22px; font-weight:800; color:#e8f0fe; margin-bottom:32px; }}
  .logo span {{ color:#00c896; }}
  .hero {{ background:#0a0e1a; border:1px solid rgba(0,200,150,0.15); border-radius:12px; padding:32px; margin-bottom:24px; }}
  .hero h1 {{ font-size:22px; font-weight:700; color:#e8f0fe; margin:0 0 8px; letter-spacing:-0.5px; }}
  .hero p  {{ color:#8899b4; font-size:14px; line-height:1.6; margin:0 0 24px; }}
  .cred-block {{ background:#050810; border:1px solid rgba(0,200,150,0.2); border-radius:8px; padding:20px; margin-bottom:16px; }}
  .cred-row {{ display:flex; justify-content:space-between; align-items:center; padding:8px 0; border-bottom:1px solid rgba(255,255,255,0.04); }}
  .cred-row:last-child {{ border-bottom:none; }}
  .cred-label {{ font-size:11px; color:#556070; text-transform:uppercase; letter-spacing:0.08em; font-weight:600; }}
  .cred-value {{ font-family:'Courier New',monospace; font-size:13px; color:#00c896; font-weight:700; }}
  .install-btn {{ display:block; background:#00c896; color:#050810; text-align:center; padding:14px 24px; border-radius:8px; text-decoration:none; font-weight:800; font-size:15px; margin-bottom:24px; }}
  .section {{ margin-bottom:24px; }}
  .section h2 {{ font-size:13px; font-weight:700; color:#e8f0fe; letter-spacing:0.05em; text-transform:uppercase; margin:0 0 12px; }}
  .os-card {{ background:#0a0e1a; border:1px solid rgba(255,255,255,0.06); border-radius:8px; padding:16px; margin-bottom:8px; }}
  .os-name {{ font-size:13px; font-weight:700; color:#e8f0fe; margin-bottom:6px; }}
  .os-steps {{ font-size:12px; color:#8899b4; line-height:1.8; margin:0; padding-left:16px; }}
  .footer {{ font-size:11px; color:#4a5568; text-align:center; line-height:1.8; margin-top:32px; }}
  .plan-badge {{ display:inline-block; background:rgba(0,200,150,0.1); border:1px solid rgba(0,200,150,0.3); color:#00c896; font-size:11px; font-weight:700; padding:3px 10px; border-radius:4px; font-family:'Courier New',monospace; margin-bottom:16px; }}
</style>
</head>
<body>
<div class="wrap">
  <div class="logo">Secure<span>Fast</span> VPN</div>

  <div class="hero">
    <div class="plan-badge">{plan_name.upper()} PLAN · ACTIVE</div>
    <h1>Your VPN is ready.</h1>
    <p>Your account is live. Open the attached <strong style="color:#e8f0fe">.mobileconfig</strong> file on iOS or macOS to connect in one tap — no manual setup needed.</p>

    <div class="cred-block">
      <div class="cred-row">
        <span class="cred-label">Username</span>
        <span class="cred-value">{username}</span>
      </div>
      <div class="cred-row">
        <span class="cred-label">Password</span>
        <span class="cred-value">{password}</span>
      </div>
      <div class="cred-row">
        <span class="cred-label">Server</span>
        <span class="cred-value">{server}</span>
      </div>
      <div class="cred-row">
        <span class="cred-label">VPN Type</span>
        <span class="cred-value">IKEv2 / IPsec</span>
      </div>
      <div class="cred-row">
        <span class="cred-label">Expires</span>
        <span class="cred-value">{expiry}</span>
      </div>
    </div>

    <p style="font-size:12px;color:#556070;margin:0">
      Keep these credentials private. Do not share them — each account is single-use per plan.
    </p>
  </div>

  <div class="section">
    <h2>Setup guides</h2>

    <div class="os-card">
      <div class="os-name">iOS / macOS — one tap (recommended)</div>
      <ol class="os-steps">
        <li>Open the <strong style="color:#e8f0fe">turnip-{username}.mobileconfig</strong> attachment</li>
        <li>Tap "Allow" → then open Settings → Profile Downloaded → Install</li>
        <li>Go to Settings → VPN → Turnip VPN → toggle ON</li>
      </ol>
    </div>

    <div class="os-card">
      <div class="os-name">Windows</div>
      <ol class="os-steps">
        <li>Settings → Network &amp; Internet → VPN → Add a VPN</li>
        <li>Provider: Windows (built-in) · Type: IKEv2</li>
        <li>Server: <span style="color:#00c896;font-family:monospace">{server}</span> · Username + password above</li>
      </ol>
    </div>

    <div class="os-card">
      <div class="os-name">Android</div>
      <ol class="os-steps">
        <li>Install the <strong style="color:#e8f0fe">strongSwan</strong> app from Play Store</li>
        <li>Add profile: server <span style="color:#00c896;font-family:monospace">{server}</span> · type IKEv2 EAP</li>
        <li>Enter username and password above</li>
      </ol>
    </div>
  </div>

  <div class="footer">
    Turnip VPN · Encrypted. Private. Zero logs.<br>
    Questions? Reply to this email.<br><br>
    Your subscription expires {expiry}. You'll receive a renewal reminder before then.
  </div>
</div>
</body>
</html>"""


def _build_text(creds: dict, plan: dict) -> str:
    return f"""Turnip VPN — Your account is ready

Plan: {plan['name']}

VPN CREDENTIALS
───────────────
Username : {creds['username']}
Password : {creds['password']}
Server   : {creds['server']}
VPN Type : IKEv2 / IPsec
Expires  : {creds['expiry_display']}

SETUP
─────
iOS/macOS : Open the attached .mobileconfig file and tap Install
Windows   : Settings → VPN → Add → IKEv2 → enter server + credentials
Android   : Install strongSwan app → add profile with credentials above

Keep these credentials private.

Turnip VPN · Zero logs · AES-256
"""
