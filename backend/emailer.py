#!/usr/bin/env python3
"""
Turnip VPN — Email Delivery
Sends the welcome email with:
  - VPN credentials (username/password/server)
  - .mobileconfig attachment (iOS/macOS one-tap install)
  - Setup instructions for Windows, Android, Linux

Supports SMTP (any provider), SendGrid, and Resend.
Set EMAIL_PROVIDER=smtp | sendgrid | resend in .env
"""

import os, base64, smtplib, logging
from email.mime.multipart  import MIMEMultipart
from email.mime.text       import MIMEText
from email.mime.base       import MIMEBase
from email import encoders

log = logging.getLogger(__name__)

def _email_settings() -> dict:
  """Resolve email configuration at send time so live env changes take effect after restart."""
  return {
    "provider": os.environ.get("EMAIL_PROVIDER", "smtp").strip().lower(),
    "smtp_host": os.environ.get("SMTP_HOST", "smtp.gmail.com").strip(),
    "smtp_port": int(os.environ.get("SMTP_PORT", "587")),
    "smtp_user": os.environ.get("SMTP_USER", "").strip(),
    "smtp_pass": os.environ.get("SMTP_PASS", ""),
    "from_email": os.environ.get("FROM_EMAIL", "noreply@turnipvpn.site").strip(),
    "from_name": os.environ.get("FROM_NAME", "Turnip VPN").strip(),
    "sendgrid_key": os.environ.get("SENDGRID_API_KEY", "").strip(),
    "resend_key": os.environ.get("RESEND_API_KEY", "").strip(),
  }


def _validate_settings(settings: dict):
  provider = settings["provider"]
  if provider == "resend" and not settings["resend_key"]:
    raise RuntimeError("EMAIL_PROVIDER=resend but RESEND_API_KEY is missing")
  if provider == "sendgrid" and not settings["sendgrid_key"]:
    raise RuntimeError("EMAIL_PROVIDER=sendgrid but SENDGRID_API_KEY is missing")
  if provider == "smtp" and (not settings["smtp_user"] or not settings["smtp_pass"]):
    raise RuntimeError("EMAIL_PROVIDER=smtp but SMTP_USER/SMTP_PASS is missing")


# ── Public entrypoint ─────────────────────────────────────────────────────────

def send_welcome_email(to_email: str, creds: dict, plan: dict):
    """Send welcome email with credentials and .mobileconfig attachments for all devices."""
    settings = _email_settings()
    _validate_settings(settings)
    subject = "Your Turnip VPN is ready — connect in 60 seconds"
    html    = _build_html(creds, plan)
    text    = _build_text(creds, plan)

    # Build one attachment per device
    devices = creds.get("devices") or [{"device_number": 1, "username": creds["username"], "mobileconfig_b64": creds["mobileconfig_b64"]}]
    attachments = [
        (base64.b64decode(d["mobileconfig_b64"]), f"turnip-device{d['device_number']}-{d['username']}.mobileconfig")
        for d in devices
        if d.get("mobileconfig_b64")
    ]

    # Primary attachment (Device 1) for single-attachment APIs; extras appended below
    primary_bytes, primary_name = attachments[0] if attachments else (b"", "turnip.mobileconfig")

    log.info(f"Sending welcome email via {settings['provider']} to {to_email} from {settings['from_email']}")

    if settings["provider"] == "sendgrid":
        _send_sendgrid(settings, to_email, subject, html, text, primary_bytes, primary_name)
    elif settings["provider"] == "resend":
        _send_resend_multi(settings, to_email, subject, html, text, attachments)
    else:
        _send_smtp_multi(settings, to_email, subject, html, text, attachments)

    log.info(f"Email delivered to {to_email} ({len(attachments)} profile(s) attached)")


def send_user_welcome_email(user_name: str, user_email: str):
    """Send a welcome email to the newly registered user directing them to pick a plan."""
    settings = _email_settings()
    _validate_settings(settings)
    site_url = os.environ.get("SITE_URL", "https://turnipvpn.site")
    subject  = "Welcome to Turnip VPN — pick your plan to get started"
    text = (
        f"Hi {user_name},\n\n"
        f"Your Turnip VPN account has been created successfully.\n\n"
        f"Next step: choose a plan to activate your VPN connection.\n"
        f"{site_url}/pricing\n\n"
        f"Once payment is confirmed your VPN credentials will be delivered\n"
        f"to this email address automatically.\n\n"
        f"— The Turnip VPN Team"
    )
    html = f"""<!DOCTYPE html>
<html>
<head><meta charset=\"UTF-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"></head>
<body style=\"margin:0;padding:0;background:#0a0f1e;font-family:sans-serif\">
  <table width=\"100%\" cellpadding=\"0\" cellspacing=\"0\">
    <tr><td align=\"center\" style=\"padding:40px 16px\">
      <table width=\"560\" cellpadding=\"0\" cellspacing=\"0\" style=\"background:#111827;border-radius:16px;overflow:hidden;border:1px solid #1f2937\">
        <!-- Header -->
        <tr><td style=\"background:#059669;padding:28px 36px\">
          <h1 style=\"margin:0;color:#fff;font-size:22px;font-weight:800\">Turnip<span style=\"color:#d1fae5\">VPN</span></h1>
        </td></tr>
        <!-- Body -->
        <tr><td style=\"padding:36px\">
          <p style=\"margin:0 0 8px;color:#9ca3af;font-size:13px;text-transform:uppercase;letter-spacing:.08em\">Welcome aboard</p>
          <h2 style=\"margin:0 0 20px;color:#f9fafb;font-size:24px\">Hi {user_name} 👋</h2>
          <p style=\"color:#d1d5db;font-size:15px;line-height:1.6;margin:0 0 24px\">
            Your Turnip VPN account has been created. You're one step away from a fast, private internet connection.
          </p>
          <table cellpadding=\"0\" cellspacing=\"0\" style=\"margin-bottom:28px\">
            <tr>
              <td style=\"background:#0a0f1e;border:1px solid #1f2937;border-radius:10px;padding:18px 20px\">
                <p style=\"margin:0 0 6px;color:#6b7280;font-size:12px;font-weight:700;text-transform:uppercase\">Registered email</p>
                <p style=\"margin:0;color:#f9fafb;font-family:monospace;font-size:15px\">{user_email}</p>
              </td>
            </tr>
          </table>
          <p style=\"color:#d1d5db;font-size:14px;line-height:1.6;margin:0 0 28px\">
            <strong style=\"color:#f9fafb\">Next step:</strong> choose a plan below. Once your payment is confirmed,
            your VPN credentials will be sent to this email automatically.
          </p>
          <a href=\"{site_url}/pricing\" style=\"
            display:inline-block;background:#059669;color:#fff;
            text-decoration:none;padding:14px 32px;border-radius:8px;
            font-weight:800;font-size:15px\">View Plans &amp; Get Started →</a>
        </td></tr>
        <!-- Footer -->
        <tr><td style=\"padding:20px 36px;border-top:1px solid #1f2937\">
          <p style=\"margin:0;color:#4b5563;font-size:12px\">Turnip VPN · You're receiving this because you just registered.</p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body></html>"""
    try:
        log.info(f"Sending user welcome email via {settings['provider']} to {user_email} from {settings['from_email']}")
        if settings["provider"] == "sendgrid":
            _send_simple_sendgrid(settings, user_email, subject, html, text)
        elif settings["provider"] == "resend":
            _send_simple_resend(settings, user_email, subject, html, text)
        else:
            _send_simple_smtp(settings, user_email, subject, html, text)
        log.info(f"Welcome email sent to {user_email}")
    except Exception as e:
        log.error(f"Failed to send welcome email to {user_email}: {e}")


def send_registration_notification(user_name: str, user_email: str):
    """Send a plain admin notification to dev@turnipvpn.site when a new user registers."""
    settings = _email_settings()
    _validate_settings(settings)
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
        log.info(f"Sending admin notification via {settings['provider']} to {admin_to} from {settings['from_email']}")
        if settings["provider"] == "sendgrid":
            _send_simple_sendgrid(settings, admin_to, subject, html, text)
        elif settings["provider"] == "resend":
            _send_simple_resend(settings, admin_to, subject, html, text)
        else:
            _send_simple_smtp(settings, admin_to, subject, html, text)
        log.info(f"Admin registration notification sent for {user_email}")
    except Exception as e:
        log.error(f"Failed to send admin notification: {e}")


def send_otp_email(to_email: str, code: str):
    """Send a one-time 6-digit login code email."""
    settings = _email_settings()
    _validate_settings(settings)
    subject = f"{code} — Your Turnip VPN login code"
    text = (
        f"Your one-time login code is: {code}\n\n"
        f"Enter this on the Turnip VPN sign-in page. It expires in 10 minutes.\n\n"
        f"If you didn't request this, you can safely ignore this email.\n\n"
        f"— The Turnip VPN Team"
    )
    html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#020205;font-family:sans-serif">
  <table width="100%" cellpadding="0" cellspacing="0">
    <tr><td align="center" style="padding:40px 16px">
      <table width="480" cellpadding="0" cellspacing="0" style="background:#080812;border-radius:16px;overflow:hidden;border:1px solid rgba(168,85,247,0.2)">
        <tr><td style="background:linear-gradient(135deg,#a855f7 0%,#7c3aed 100%);padding:28px 36px">
          <h1 style="margin:0;color:#fff;font-size:20px;font-weight:800">Turnip<span style="color:#f3e8ff">VPN</span></h1>
        </td></tr>
        <tr><td style="padding:36px;text-align:center">
          <p style="margin:0 0 8px;color:#6b7280;font-size:13px;text-transform:uppercase;letter-spacing:.08em">Sign-in code</p>
          <div style="font-size:44px;font-weight:900;letter-spacing:14px;color:#a855f7;font-family:monospace;margin:16px 0 24px">{code}</div>
          <p style="color:#9ca3af;font-size:14px;line-height:1.6;margin:0 0 8px">
            Enter this code on the Turnip VPN login page. It expires in <strong style="color:#f9fafb">10 minutes</strong>.
          </p>
          <p style="color:#6b7280;font-size:12px;margin:0">If you didn't request this, you can safely ignore this email.</p>
        </td></tr>
        <tr><td style="padding:16px 36px;border-top:1px solid rgba(255,255,255,0.05)">
          <p style="margin:0;color:#374151;font-size:11px;text-align:center">Turnip VPN &middot; One-time login code</p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body></html>"""
    log.info(f"Sending OTP email via {settings['provider']} to {to_email} from {settings['from_email']}")
    if settings["provider"] == "sendgrid":
        _send_simple_sendgrid(settings, to_email, subject, html, text)
    elif settings["provider"] == "resend":
        _send_simple_resend(settings, to_email, subject, html, text)
    else:
        _send_simple_smtp(settings, to_email, subject, html, text)
    log.info(f"OTP email sent to {to_email}")


def _send_simple_resend(settings: dict, to: str, subject: str, html: str, text: str):
    try:
        import resend
    except ImportError:
        log.error("resend package not installed. Run: pip install resend")
        raise
    resend.api_key = settings["resend_key"]
    resend.Emails.send({
        "from": f"{settings['from_name']} <{settings['from_email']}>",
        "to": [to],
        "subject": subject,
        "html": html,
        "text": text,
    })


def _send_simple_smtp(settings: dict, to: str, subject: str, html: str, text: str):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"{settings['from_name']} <{settings['from_email']}>"
    msg["To"]      = to
    msg.attach(MIMEText(text, "plain"))
    msg.attach(MIMEText(html, "html"))
    if settings["smtp_port"] == 465:
        with smtplib.SMTP_SSL(settings["smtp_host"], settings["smtp_port"]) as s:
            s.login(settings["smtp_user"], settings["smtp_pass"])
            s.sendmail(settings["from_email"], to, msg.as_string())
    else:
        with smtplib.SMTP(settings["smtp_host"], settings["smtp_port"]) as s:
            s.starttls()
            s.login(settings["smtp_user"], settings["smtp_pass"])
            s.sendmail(settings["from_email"], to, msg.as_string())


def _send_simple_sendgrid(settings: dict, to: str, subject: str, html: str, text: str):
    try:
        import sendgrid
        from sendgrid.helpers.mail import Mail, To, From
    except ImportError:
        log.error("sendgrid package not installed")
        raise
    sg = sendgrid.SendGridAPIClient(api_key=settings["sendgrid_key"])
    message = Mail(
        from_email=From(settings["from_email"], settings["from_name"]),
        to_emails=To(to),
        subject=subject,
        plain_text_content=text,
        html_content=html,
    )
    sg.send(message)


# ── SMTP sender ───────────────────────────────────────────────────────────────

def _send_smtp_multi(settings: dict, to: str, subject: str, html: str, text: str,
                     attachments: list):
    """Send email with one or more .mobileconfig attachments via SMTP."""
    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"]    = f"{settings['from_name']} <{settings['from_email']}>"
    msg["To"]      = to

    body = MIMEMultipart("alternative")
    body.attach(MIMEText(text, "plain"))
    body.attach(MIMEText(html, "html"))
    msg.attach(body)

    for att_bytes, att_name in attachments:
        part = MIMEBase("application", "x-apple-aspen-config")
        part.set_payload(att_bytes)
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f'attachment; filename="{att_name}"')
        msg.attach(part)

    if settings["smtp_port"] == 465:
      with smtplib.SMTP_SSL(settings["smtp_host"], settings["smtp_port"]) as server:
        server.login(settings["smtp_user"], settings["smtp_pass"])
        server.sendmail(settings["from_email"], to, msg.as_string())
    else:
      with smtplib.SMTP(settings["smtp_host"], settings["smtp_port"]) as server:
        server.starttls()
        server.login(settings["smtp_user"], settings["smtp_pass"])
        server.sendmail(settings["from_email"], to, msg.as_string())


  def _send_smtp(settings: dict, to: str, subject: str, html: str, text: str,
           attachment: bytes, filename: str):
    _send_smtp_multi(settings, to, subject, html, text, [(attachment, filename)])


# ── SendGrid sender ───────────────────────────────────────────────────────────

def _send_sendgrid(settings: dict, to: str, subject: str, html: str, text: str,
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

    sg = sendgrid.SendGridAPIClient(api_key=settings["sendgrid_key"])

    message = Mail(
      from_email=From(settings["from_email"], settings["from_name"]),
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


# ── Resend sender ─────────────────────────────────────────────────────────────

def _send_resend_multi(settings: dict, to: str, subject: str, html: str, text: str,
                       attachments: list):
    """Send email with one or more .mobileconfig attachments via Resend."""
    try:
        import resend
    except ImportError:
        log.error("resend package not installed. Run: pip install resend")
        raise
    resend.api_key = settings["resend_key"]
    resend.Emails.send({
      "from": f"{settings['from_name']} <{settings['from_email']}>",
        "to": [to],
        "subject": subject,
        "html": html,
        "text": text,
        "attachments": [
            {"filename": att_name, "content": list(att_bytes)}
            for att_bytes, att_name in attachments
        ],
    })


def _send_resend(settings: dict, to: str, subject: str, html: str, text: str,
                 attachment: bytes, filename: str):
    _send_resend_multi(settings, to, subject, html, text, [(attachment, filename)])


# ── Email templates ───────────────────────────────────────────────────────────

def _device_cred_block_html(devices: list) -> str:
    """Render credential rows for all devices."""
    if len(devices) == 1:
        d = devices[0]
        return f"""
      <div class="cred-row">
        <span class="cred-label">Username</span>
        <span class="cred-value">{d['username']}</span>
      </div>
      <div class="cred-row">
        <span class="cred-label">Password</span>
        <span class="cred-value">{d['password']}</span>
      </div>
      <div class="cred-row">
        <span class="cred-label">Server</span>
        <span class="cred-value">{d['server']}</span>
      </div>"""
    blocks = []
    for d in devices:
        n = d['device_number']
        blocks.append(f"""
      <tr><td colspan="2" style="padding:10px 0 4px;color:#00c896;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.08em">Device {n}</td></tr>
      <tr><td class="cred-label">Username</td><td class="cred-value" style="font-family:'Courier New',monospace;font-size:13px;color:#00c896;font-weight:700">{d['username']}</td></tr>
      <tr><td class="cred-label">Password</td><td class="cred-value" style="font-family:'Courier New',monospace;font-size:13px;color:#00c896;font-weight:700">{d['password']}</td></tr>
      <tr><td class="cred-label">Server</td><td class="cred-value" style="font-family:'Courier New',monospace;font-size:13px;color:#00c896;font-weight:700">{d['server']}</td></tr>""")
    return "<table style='width:100%;border-collapse:collapse'>" + "".join(blocks) + "</table>"


def _device_cred_block_text(devices: list) -> str:
    if len(devices) == 1:
        d = devices[0]
        return f"Username : {d['username']}\nPassword : {d['password']}\nServer   : {d['server']}"
    lines = []
    for d in devices:
        lines.append(f"Device {d['device_number']}\n  Username : {d['username']}\n  Password : {d['password']}\n  Server   : {d['server']}")
    return "\n".join(lines)


def _build_html(creds: dict, plan: dict) -> str:
    devices  = creds.get("devices") or [{"device_number": 1, "username": creds["username"], "password": creds["password"], "server": creds["server"]}]
    username = creds["username"]
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
  <div class="logo">Turnip<span>VPN</span></div>

  <div class="hero">
    <div class="plan-badge">{plan_name.upper()} PLAN · ACTIVE</div>
    <h1>Your VPN is ready.</h1>
    <p>Your account is live. Open the attached <strong style="color:#e8f0fe">.mobileconfig</strong> file on iOS or macOS to connect in one tap — no manual setup needed.</p>

    <div class="cred-block">
      {_device_cred_block_html(devices)}
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
    devices = creds.get("devices") or [{"device_number": 1, "username": creds["username"], "password": creds["password"], "server": creds["server"]}]
    cred_lines = _device_cred_block_text(devices)
    return f"""Turnip VPN — Your account is ready

Plan: {plan['name']}

VPN CREDENTIALS
───────────────
{cred_lines}
VPN Type : IKEv2 / IPsec
Expires  : {creds['expiry_display']}

SETUP
─────
iOS/macOS : Open an attached .mobileconfig file and tap Install (one per device)
Windows   : Settings → VPN → Add → IKEv2 → enter server + credentials
Android   : Install strongSwan app → add profile with credentials above

Keep these credentials private.

Turnip VPN · Zero logs · AES-256
"""
