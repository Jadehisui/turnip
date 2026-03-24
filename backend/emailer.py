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
