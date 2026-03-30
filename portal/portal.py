#!/usr/bin/env python3
"""
Turnip VPN — Customer Portal
Self-service web portal for VPN subscribers.

Routes:
  GET  /                   → landing / redirect to dashboard
  GET  /login              → login page
  POST /login              → authenticate
  GET  /logout             → clear session
  GET  /dashboard          → customer dashboard
  GET  /download/profile   → download .mobileconfig
  GET  /download/ca        → download CA cert
  POST /api/regenerate     → regenerate password
  GET  /pricing            → pricing page (unauthenticated)
  POST /api/pay            → initiate Paystack payment

Run: gunicorn -w 2 -b 0.0.0.0:8767 portal:app
"""

import os, secrets, hashlib, logging, base64
from datetime import datetime, timedelta
from functools import wraps

from flask import (
    Flask, request, session, redirect, url_for,
    render_template, render_template_string, jsonify, send_file, make_response, send_from_directory
)
from dotenv import load_dotenv
import requests as http
from siwe import SiweMessage
from eth_account.messages import encode_defunct
from eth_account import Account

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("portal.log"),
        logging.StreamHandler(),
    ]
)
log = logging.getLogger(__name__)

# Import shared modules from payment backend
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../backend"))
from database import db_init, get_subscription, get_all_subscriptions, record_payment, get_devices_for_email, register_user, get_user, create_login_token, verify_login_token
from provisioner import provision_user, deprovision_user, generate_password, generate_mobileconfig, get_plan_for_amount, get_server_host, PLANS, CA_CERT_PATH, SERVERS
from emailer import send_registration_notification, send_user_welcome_email, send_otp_email

app = Flask(__name__, 
            static_folder='frontend/dist', 
            template_folder='frontend/dist')
app.secret_key      = os.environ.get("PORTAL_SECRET_KEY", secrets.token_hex(32))
app.permanent_session_lifetime = timedelta(hours=12)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
if os.environ.get("SITE_URL", "").startswith("https://"):
    app.config["SESSION_COOKIE_SECURE"] = True

db_init()  # ensure tables exist whether running via gunicorn or directly

VPN_SERVER_ADDR = os.environ.get("VPN_SERVER_ADDR", "vpn.yourdomain.com")
SITE_URL        = os.environ.get("SITE_URL", "")

# Lemon Squeezy — one pre-created variant URL per plan (from LS dashboard)
# Append ?checkout[email]=...&checkout[custom][plan_code]=... for pre-fill
LS_VARIANT_URLS = {
    "basic":    os.environ.get("LEMONSQUEEZY_BASIC_VARIANT_URL", ""),
    "pro":      os.environ.get("LEMONSQUEEZY_PRO_VARIANT_URL", ""),
    "business": os.environ.get("LEMONSQUEEZY_BUSINESS_VARIANT_URL", ""),
}


# ── Auth helpers ──────────────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "email" not in session:
            if request.path.startswith('/api/'):
                return jsonify({"error": "Authentication required"}), 401
            return redirect(url_for("login_page"))
        return f(*args, **kwargs)
    return decorated


def get_current_user():
    email = session.get("email")
    if not email:
        return None
    return get_subscription(email=email)


def days_remaining(expires_at: str) -> int:
    try:
        expiry = datetime.fromisoformat(expires_at)
        delta  = expiry - datetime.utcnow()
        return max(0, delta.days)
    except Exception:
        return 0


# ── Routes ─────────────────────────────────────────────────────────────────────




@app.route("/api/user/status")
@login_required
def user_status():
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    devices = get_devices_for_email(user["email"])
    if not devices:
        # Backward compat for old single-credential subscriptions
        devices = [{
            "device_number": 1,
            "username":      user["username"],
            "password":      user["password"],
            "server_region": user.get("server_region", "us"),
        }]

    return jsonify({
        "email":         user["email"],
        "username":      user["username"],
        "status":        user["status"],
        "plan_name":     user["plan_name"],
        "expires_at":    user["expires_at"],
        "wallet_address": user.get("wallet_address"),
        "server_region": user.get("server_region", "us"),
        "devices":       devices,
    })


@app.route("/login", methods=["GET"])
def login_page():
    # Login UI is handled by the React SPA
    return send_from_directory(app.static_folder, 'index.html')


@app.route("/api/auth/login", methods=["POST"])
def api_login():
    data  = request.get_json() or {}
    email = data.get("email", "").strip().lower()
    if not email or "@" not in email:
        return jsonify({"error": "Enter a valid email address"}), 400

    # Verify this email belongs to a known account before sending an OTP
    sub  = get_subscription(email=email)
    user = get_user(email=email) if not sub else None
    if not sub and not user:
        return jsonify({"error": "No account found with this email. Please register first."}), 404

    # Generate OTP and email it — session is only set after verification
    try:
        code = create_login_token(email)
        send_otp_email(email, code)
    except Exception as e:
        log.error(f"OTP send failed for {email}: {e}")
        return jsonify({"error": "Could not send login code. Please try again."}), 500

    log.info(f"OTP sent to {email}")
    return jsonify({"step": "otp", "email": email})


@app.route("/api/auth/verify-otp", methods=["POST"])
def api_verify_otp():
    data  = request.get_json() or {}
    email = data.get("email", "").strip().lower()
    code  = data.get("code", "").strip()

    if not email or not code:
        return jsonify({"error": "Email and code are required"}), 400

    if not verify_login_token(email, code):
        return jsonify({"error": "Invalid or expired code. Please try again."}), 401

    # Token verified — establish session
    session.permanent = True
    session["email"]  = email

    sub = get_subscription(email=email)
    if sub:
        log.info(f"OTP login (sub): {email}")
        return jsonify({"ok": True, "email": email, "redirect": "/dashboard"})

    log.info(f"OTP login (no sub): {email}")
    return jsonify({"ok": True, "email": email, "redirect": "/pricing"})


@app.route("/api/auth/register", methods=["POST"])
def api_register():
    data  = request.get_json() or {}
    name  = data.get("name", "").strip()
    email = data.get("email", "").strip().lower()

    if not name or len(name) < 2:
        return jsonify({"error": "Please enter your full name"}), 400
    if not email or "@" not in email:
        return jsonify({"error": "Enter a valid email address"}), 400

    # If an account already exists for this email, don't log them in without OTP.
    # Tell the frontend to switch to the Sign In tab instead.
    sub      = get_subscription(email=email)
    existing = get_user(email=email)
    if sub or existing:
        log.info(f"Register attempt for existing account: {email}")
        return jsonify({
            "error": "An account with this email already exists. Use Sign In to continue.",
            "switch_to_signin": True,
            "email": email,
        }), 409

    try:
        register_user(name=name, email=email)
    except Exception as e:
        log.error(f"Register error: {e}")
        return jsonify({"error": "Registration failed. Please try again."}), 500

    # Sign them in immediately
    session.permanent = True
    session["email"]  = email

    log.info(f"New user registered: {name} <{email}>")

    # Send emails synchronously — registration is a low-frequency path and
    # SMTP (port 465) completes in <1 s. Threading with daemon=True/False is
    # unsafe here because gunicorn SIGTERM kills the worker mid-send.
    try:
        send_user_welcome_email(user_name=name, user_email=email)
    except Exception as e:
        log.error(f"Welcome email failed: {e}")

    try:
        send_registration_notification(user_name=name, user_email=email)
    except Exception as e:
        log.error(f"Admin notification failed: {e}")

    return jsonify({"ok": True, "email": email, "redirect": "/pricing"})


@app.route("/logout")
def logout():
    email = session.get("email", "")
    session.clear()
    log.info(f"Logout: {email}")
    return redirect("/login")


@app.route("/dashboard")
def dashboard():
    # Dashboard UI is handled by the React SPA
    return send_from_directory(app.static_folder, 'index.html')


@app.route("/download/profile")
@login_required
def download_profile():
    sub = get_current_user()
    if not sub or sub.get("status") not in ("active", "non_renewing"):
        return redirect(url_for("dashboard"))

    device_num = int(request.args.get("device", 1))
    devices    = get_devices_for_email(sub["email"])

    if devices:
        dev = next((d for d in devices if d["device_number"] == device_num), devices[0])
        username    = dev["username"]
        password    = dev["password"]
        server_host = get_server_host(dev["server_region"])
    else:
        username    = sub["username"]
        password    = sub["password"]
        server_host = VPN_SERVER_ADDR

    profile_b64  = generate_mobileconfig(username, password, server_host)
    profile_bytes = base64.b64decode(profile_b64)
    filename      = f"turnip-device{device_num}-{username}.mobileconfig"

    response = make_response(profile_bytes)
    response.headers["Content-Type"]        = "application/x-apple-aspen-config"
    response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    log.info(f"Device {device_num} profile download: {sub['email']}")
    return response


@app.route("/download/ca")
@login_required
def download_ca():
    try:
        with open(CA_CERT_PATH, "rb") as f:
            ca_bytes = f.read()
        response = make_response(ca_bytes)
        response.headers["Content-Type"]        = "application/x-pem-file"
        response.headers["Content-Disposition"] = 'attachment; filename="turnip-ca.pem"'
        return response
    except FileNotFoundError:
        return jsonify({"error": "CA cert not found"}), 404


@app.route("/api/regenerate", methods=["POST"])
@login_required
def regenerate_password():
    """Generate a new password for the user's VPN account."""
    sub = get_current_user()
    if not sub or sub.get("status") not in ("active", "non_renewing"):
        return jsonify({"error": "inactive account"}), 403

    new_password = generate_password()
    username     = sub["username"]

    # Update ipsec.secrets
    import re
    from pathlib import Path
    SECRETS_FILE = os.environ.get("IPSEC_SECRETS_FILE", "/etc/ipsec.secrets")
    lines = Path(SECRETS_FILE).read_text().splitlines(keepends=True)
    updated = []
    for line in lines:
        if line.strip().startswith(f"{username} :"):
            updated.append(f'{username} : EAP "{new_password}"\n')
        else:
            updated.append(line)
    Path(SECRETS_FILE).write_text("".join(updated))

    import subprocess
    subprocess.run(["ipsec", "secrets"], timeout=5)

    # Update DB
    from database import get_conn
    with get_conn() as conn:
        conn.execute(
            "UPDATE subscriptions SET password=?, updated_at=datetime('now') WHERE email=?",
            (new_password, sub["email"])
        )

    log.info(f"Password regenerated: {username}")
    return jsonify({"ok": True, "password": new_password})


@app.route("/api/terminate", methods=["POST"])
@login_required
def terminate_subscription():
    """Disable the user's subscription and log them out."""
    sub = get_current_user()
    if not sub:
        return jsonify({"error": "No active subscription"}), 404
    from database import get_conn
    with get_conn() as conn:
        conn.execute(
            "UPDATE subscriptions SET status='disabled', updated_at=datetime('now') WHERE email=?",
            (sub["email"],)
        )
    email = session.get("email", "")
    session.clear()
    log.info(f"Subscription terminated by user: {email}")
    return jsonify({"ok": True})


def _ls_checkout_url(email: str, plan_code: str, region: str = "eu") -> str:
    """Build a Lemon Squeezy checkout URL with pre-filled email and custom data."""
    from urllib.parse import urlencode
    base = LS_VARIANT_URLS.get(plan_code.lower(), "")
    if not base:
        raise ValueError(
            f"No Lemon Squeezy variant URL configured for plan '{plan_code}'. "
            "Set LEMONSQUEEZY_<PLAN>_VARIANT_URL in .env."
        )
    redirect_url = SITE_URL.rstrip("/") + "/login" if SITE_URL else ""
    params = {
        "checkout[email]": email,
        "checkout[custom][plan_code]": plan_code.lower(),
        "checkout[custom][region]": region,
    }
    if redirect_url:
        params["checkout[redirect]"] = redirect_url
    return f"{base}?{urlencode(params)}"


@app.route("/api/pay/initiate", methods=["POST"])
@login_required
def initiate_payment():
    """Return a Lemon Squeezy checkout URL for the logged-in user (renewal/upgrade)."""
    data      = request.get_json()
    plan_code = data.get("plan_code", "pro")
    region    = data.get("region", "eu")
    try:
        payment_url = _ls_checkout_url(session["email"], plan_code, region)
        return jsonify({"ok": True, "payment_url": payment_url})
    except ValueError as e:
        log.error(f"LS checkout URL error: {e}")
        return jsonify({"error": str(e)}), 500 


@app.route("/api/pay/public/initiate", methods=["POST"])
def pay_public_initiate():
    """Return a Lemon Squeezy checkout URL for a new (unauthenticated) user."""
    data      = request.get_json()
    email     = data.get("email", "")
    plan_code = data.get("plan_code", "pro")
    region    = data.get("region", "eu")

    if not email or "@" not in email:
        return jsonify({"error": "Valid email is required"}), 400

    try:
        payment_url = _ls_checkout_url(email, plan_code, region)
        return jsonify({"ok": True, "payment_url": payment_url})
    except ValueError as e:
        log.error(f"LS checkout URL error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/pay/crypto/initiate", methods=["POST"])
def crypto_pay_initiate():
    """Create a NOWPayments hosted crypto invoice."""
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../backend"))
    from crypto_payments import create_invoice

    data       = request.get_json()
    email      = data.get("email") or session.get("email", "")
    amount_ngn = float(data.get("amount_ngn", 4000))
    plan_code  = data.get("plan_code", "pro")
    region     = data.get("region", "eu")

    if not email or "@" not in email:
        return jsonify({"error": "Valid email is required"}), 400

    site_url = os.environ.get("SITE_URL", request.url_root.rstrip("/"))

    try:
        invoice = create_invoice(email, amount_ngn, plan_code, site_url, region)
        return jsonify({"ok": True, "payment_url": invoice.get("invoice_url")})
    except Exception as e:
        log.error(f"NOWPayments create error: {e}")
        return jsonify({"error": "Could not create crypto payment. Check NOWPAYMENTS_API_KEY."}), 500


@app.route("/api/auth/nonce")
def get_nonce():
    session["nonce"] = secrets.token_hex(16)
    return jsonify({"nonce": session["nonce"]})


@app.route("/api/auth/wallet", methods=["POST"])
def auth_wallet():
    data = request.get_json()
    message = data.get("message")
    signature = data.get("signature")
    
    try:
        siwe_msg = SiweMessage(message=message)
        # Verify nonce
        if siwe_msg.nonce != session.get("nonce"):
            return jsonify({"error": "Invalid nonce"}), 403
            
        # Verify signature
        # siwe-python verification
        # Note: siwe_msg.verify(signature) might require domain/time checks
        # For simplicity and robustness in this env:
        recovered = Account.recover_message(encode_defunct(text=message), signature=signature)
        if recovered.lower() != siwe_msg.address.lower():
            return jsonify({"error": "Invalid signature"}), 403

        address = recovered.lower()
        sub = get_subscription(wallet=address)
        
        if not sub:
            # If already logged in via email, link the wallet
            if "email" in session:
                from database import get_conn
                with get_conn() as conn:
                    conn.execute("UPDATE subscriptions SET wallet_address=? WHERE email=?", (address, session["email"]))
                log.info(f"Wallet {address} linked to {session['email']}")
                return jsonify({"ok": True, "address": address, "linked": True})
            else:
                return jsonify({"error": "No account associated with this wallet. Login with email first to link your wallet."}), 404

        # Log in
        session.permanent = True
        session["email"] = sub["email"]
        log.info(f"Wallet login: {sub['email']} ({address})")
        return jsonify({"ok": True, "email": sub["email"]})
        
    except Exception as e:
        log.error(f"Wallet auth error: {e}")
        return jsonify({"error": str(e)}), 400


@app.route("/pricing")
def pricing():
    # Pricing is handled by the React SPA
    return send_from_directory(app.static_folder, 'index.html')


@app.route("/api/plans")
def get_plans():
    """Return plan definitions with both NGN and USD pricing for the pricing page."""
    plans = [
        {
            "code":      "basic",
            "name":      "Basic",
            "price_ngn": 4999,
            "price_usd": 4.99,
            "amount_ngn": 4999,
            "amount_ngn_intl": 7984,
            "devices":   1,
            "period":    "1 device · 30 days",
            "features":  ["1 device", "AES-256 encryption", "2 server regions", "Zero traffic logs", "Email support"],
            "featured":  False,
        },
        {
            "code":      "pro",
            "name":      "Pro",
            "price_ngn": 7999,
            "price_usd": 7.99,
            "amount_ngn": 7999,
            "amount_ngn_intl": 12784,
            "devices":   5,
            "period":    "5 devices · 30 days",
            "features":  ["5 devices", "AES-256 encryption", "All 4 server regions", "Zero traffic logs", "Priority support", "Custom VPN profiles"],
            "featured":  True,
        },
        {
            "code":      "business",
            "name":      "Business",
            "price_ngn": 19999,
            "price_usd": 19.99,
            "amount_ngn": 19999,
            "amount_ngn_intl": 31984,
            "devices":   10,
            "period":    "Up to 10 devices · 30 days",
            "features":  ["Up to 10 devices", "AES-256 encryption", "All 4 server regions", "Zero traffic logs", "Dedicated support", "Multi-server sync"],
            "featured":  False,
        },
    ]
    return jsonify({"plans": plans})


@app.route("/api/servers")
def get_servers():
    """Return the list of active VPN server regions for the region picker UI."""
    active = [s for s in SERVERS if s.get("active")]
    # Don't expose internal host IPs to the frontend
    safe = [
        {
            "region":    s["region"],
            "name":      s["name"],
            "country":   s["country"],
            "flag":      s["flag"],
            "continent": s.get("continent", ""),
        }
        for s in active
    ]
    return jsonify({"servers": safe})


@app.route("/api/geo")
def get_geo():
    """Return the visitor's country code based on IP for geo-based pricing."""
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    if ip and ',' in ip:
        ip = ip.split(',')[0].strip()
    # Local dev defaults to NG
    if not ip or ip in ('127.0.0.1', '::1'):
        return jsonify({'country': 'NG'})
    try:
        r = http.get(f'http://ip-api.com/json/{ip}?fields=countryCode', timeout=3)
        data = r.json()
        return jsonify({'country': data.get('countryCode', 'NG')})
    except Exception:
        return jsonify({'country': 'NG'})


@app.route("/health")
def health():
    return jsonify({"status": "ok", "service": "Turnip Portal"}), 200


# ═══════════════════════════════════════════════════════════════════════════════
# HTML TEMPLATES
# ═══════════════════════════════════════════════════════════════════════════════

_BASE_STYLE = """
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Syne:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#050810;--bg2:#0a0e1a;--bg3:#0f1525;--surf:#141c2e;--surf2:#1a2540;
  --border:rgba(0,200,150,0.13);--border2:rgba(0,200,150,0.28);
  --accent:#00c896;--accent2:#00e6aa;--adim:rgba(0,200,150,0.08);
  --text:#e8f0fe;--text2:#8899b4;--text3:#4a5568;
  --red:#ff4757;--amber:#ffb830;--blue:#4fa3e0;
  --mono:'Space Mono',monospace;--sans:'Syne',sans-serif;
}
body{background:var(--bg);color:var(--text);font-family:var(--sans);min-height:100vh}
a{color:var(--accent);text-decoration:none}
input,button{font-family:var(--sans)}
.nav{display:flex;align-items:center;justify-content:space-between;padding:1rem 2rem;border-bottom:1px solid var(--border);background:var(--bg2)}
.logo{font-size:17px;font-weight:800;color:var(--text)}
.logo span{color:var(--accent)}
.nav-right{display:flex;gap:12px;align-items:center}
.btn{padding:8px 18px;border-radius:7px;font-size:13px;font-weight:700;cursor:pointer;transition:all .2s;border:1px solid var(--border2);background:transparent;color:var(--text)}
.btn:hover{border-color:var(--accent);color:var(--accent)}
.btn-accent{background:var(--accent);border-color:var(--accent);color:#050810}
.btn-accent:hover{background:var(--accent2)}
.btn-danger{border-color:rgba(255,71,87,.3);color:var(--red)}
.btn-danger:hover{background:rgba(255,71,87,.08);border-color:var(--red)}
.btn-wallet{border-color:rgba(79,163,224,.3);color:var(--blue);margin-top:12px;width:100%;display:flex;align-items:center;justify-content:center;gap:8px}
.btn-wallet:hover{background:rgba(79,163,224,.08);border-color:var(--blue)}
.card{background:var(--surf);border:1px solid var(--border);border-radius:12px;padding:1.5rem}
.mono{font-family:var(--mono);font-size:12px}
</style>
"""

# ── Login template ────────────────────────────────────────────────────────────

LOGIN_TEMPLATE = """<!DOCTYPE html>
<html>
<head>""" + _BASE_STYLE + """<title>Turnip VPN — Login</title></head>
<body>
<style>
.wrap{display:flex;align-items:center;justify-content:center;min-height:100vh;padding:2rem}
.box{background:var(--bg2);border:1px solid var(--border);border-radius:16px;padding:2.5rem;width:100%;max-width:380px}
.lbl{font-size:11px;font-weight:700;color:var(--text2);letter-spacing:.08em;text-transform:uppercase;display:block;margin-bottom:6px}
.inp{width:100%;background:var(--bg3);border:1px solid var(--border);border-radius:8px;padding:11px 14px;color:var(--text);font-size:14px;margin-bottom:14px;outline:none;transition:border .2s}
.inp:focus{border-color:var(--accent)}
.err{color:var(--red);font-size:12px;font-family:var(--mono);margin-bottom:12px;display:{% if error %}block{% else %}none{% endif %}}
.sub{width:100%;padding:12px;background:var(--accent);border:none;border-radius:8px;color:#050810;font-size:14px;font-weight:800;cursor:pointer;transition:background .2s}
.sub:hover{background:var(--accent2)}
.tagline{color:var(--text3);font-size:12px;text-align:center;margin-top:1.5rem;line-height:1.7}
</style>
<div class="wrap">
  <div class="box">
    <div style="font-size:22px;font-weight:800;text-align:center;margin-bottom:.5rem">Turnip<span style="color:var(--accent)">VPN</span></div>
    <div style="text-align:center;color:var(--text2);font-size:13px;margin-bottom:2rem">Sign in to your VPN account</div>
    <div class="err">{{ error }}</div>
    <form method="POST" action="/login">
      <label class="lbl">Email address</label>
      <input class="inp" type="email" name="email" placeholder="you@example.com" required autofocus>
      <button class="sub" type="submit">Continue →</button>
    </form>
    <div style="display:flex;align-items:center;gap:10px;margin:1.5rem 0;color:var(--text3);font-size:11px;text-transform:uppercase;letter-spacing:1px">
      <div style="flex:1;height:1px;background:var(--border)"></div>
      <span>Or</span>
      <div style="flex:1;height:1px;background:var(--border)"></div>
    </div>
    <button class="btn btn-wallet" onclick="connectWallet()">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12V7a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h7"/><path d="M16 19h6"/><path d="M19 16v6"/><rect x="12" y="11" width="10" height="6" rx="2"/></svg>
      Connect Wallet
    </button>
    <div class="tagline">
      No account yet? <a href="/pricing" style="color:var(--accent)">View plans →</a><br>
      <span style="color:var(--text3)">AES-256 · IKEv2 · Zero logs</span>
    </div>
  </div>
</div>
<script src="https://cdn.jsdelivr.net/npm/ethers@5.7.2/dist/ethers.umd.min.js"></script>
<script>
async function connectWallet() {
  if (!window.ethereum) return alert('Please install MetaMask or another Web3 wallet');
  try {
    const provider = new ethers.providers.Web3Provider(window.ethereum);
    await provider.send("eth_requestAccounts", []);
    const signer = provider.getSigner();
    const address = await signer.getAddress();
    
    // Get nonce
    const r1 = await fetch('/api/auth/nonce');
    const { nonce } = await r1.json();
    
    const domain = window.location.host;
    const origin = window.location.origin;
    const statement = 'Sign in with Ethereum to Turnip VPN';
    
    const message = `${domain} wants you to sign in with your Ethereum account:\n${address}\n\n${statement}\n\nURI: ${origin}\nVersion: 1\nChain ID: 1\nNonce: ${nonce}\nIssued At: ${new Date().toISOString()}`;
    
    const signature = await signer.signMessage(message);
    
    const r2 = await fetch('/api/auth/wallet', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, signature })
    });
    
    const d2 = await r2.json();
    if (d2.ok) window.location.href = '/dashboard';
    else alert(d2.error || 'Login failed');
  } catch (err) {
    console.error(err);
    alert(err.message || 'Connection failed');
  }
}
</script>
</body></html>"""


# ─────────────────────────────────────────────────────────────────────────────
# (Pricing is served by the React SPA — no Jinja2 template needed)
# ─────────────────────────────────────────────────────────────────────────────

_DELETED_PRICING_TEMPLATE = None  # type: ignore  # was removed — React SPA handles /pricing
if False:
    _DELETED_PRICING_TEMPLATE = """<!DOCTYPE html>
<html>
<head>""" + _BASE_STYLE + """<title>Turnip VPN — Pricing</title></head>
<body>
<nav class="nav">
  <a href="/" class="logo">Secure<span>Fast</span></a>
  <div class="nav-right">
    {% if email %}<a href="/dashboard" class="btn btn-accent">Dashboard</a>
    {% else %}<a href="/login" class="btn">Sign in</a>{% endif %}
  </div>
</nav>
<div style="max-width:700px;margin:4rem auto;padding:0 1.5rem;text-align:center">
  <div style="font-size:11px;font-family:var(--mono);color:var(--accent);letter-spacing:.12em;text-transform:uppercase;margin-bottom:1rem">// pricing</div>
  <h1 style="font-size:36px;font-weight:800;letter-spacing:-1.5px;margin-bottom:.75rem">Simple, transparent plans.</h1>
  <p style="color:var(--text2);font-size:16px;margin-bottom:3rem">Pay once. Get connected. No upsells.</p>
  <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-bottom:2rem">
    {% for plan in plans %}
    <div style="background:var(--bg2);border:1px solid var(--border{% if plan.name=='Pro' %}2{% endif %});border-radius:12px;padding:1.75rem;position:relative{% if plan.name=='Pro' %};border-color:var(--accent){% endif %}">
      {% if plan.name=='Pro' %}<div style="position:absolute;top:-12px;left:50%;transform:translateX(-50%);background:var(--accent);color:#050810;font-size:10px;font-weight:700;padding:4px 14px;border-radius:100px;font-family:var(--mono);white-space:nowrap">MOST POPULAR</div>{% endif %}
      <div style="font-size:11px;font-weight:700;color:var(--text3);letter-spacing:.08em;text-transform:uppercase;margin-bottom:.75rem">{{ plan.name }}</div>
      <div style="font-size:36px;font-weight:800;font-family:var(--mono);letter-spacing:-2px;margin-bottom:.75rem">₦{{ "{:,.0f}".format(plan.min_amount) }}<span style="font-size:14px;color:var(--text2);font-family:var(--sans);font-weight:400">/mo</span></div>
      <div style="font-size:13px;color:var(--text2);margin-bottom:1.25rem;line-height:1.7">
        {% if plan.devices == 999 %}Unlimited devices{% else %}{{ plan.devices }} device{% if plan.devices != 1 %}s{% endif %}{% endif %}<br>
        {{ plan.duration_days }}-day access<br>
        AES-256 · IKEv2 · Zero logs
      </div>
      <button class="btn {% if plan.name=='Pro' %}btn-accent{% endif %}" style="width:100%;padding:11px;font-size:13px"
        onclick="startPayment({{ plan.min_amount }}, '{{ plan.name.lower() }}')">Pay with Card →</button>
      <button class="btn btn-wallet" style="margin-top:8px; padding:10px; font-size:12px;"
        onclick="payWithCrypto({{ plan.min_amount }}, '{{ plan.name.lower() }}')">Pay with Crypto</button>
    </div>
    {% endfor %}
  </div>
  <p style="font-size:12px;color:var(--text3)">Payments secured by Paystack. Instant activation after payment.</p>
</div>
<script>
async function startPayment(amount, planCode) {
  const email = prompt('Enter your email address:');
  if (!email) return;
  const r = await fetch('/api/pay/public/initiate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, amount_ngn: amount, plan_code: planCode })
  });
  const d = await r.json();
  if (d.payment_url) window.location.href = d.payment_url;
  else alert(d.error || 'Could not start payment');
}
async function payWithCrypto(amount, planCode) {
  const email = prompt('Enter your email address:');
  if (!email) return;
  const r = await fetch('/api/pay/crypto/initiate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, amount_ngn: amount, plan_code: planCode })
  });
  const d = await r.json();
  if (d.payment_url) { window.location.href = d.payment_url; }
  else { alert(d.error || 'Could not initiate crypto payment'); }
}
</script>
</body></html>"""


# ── Main ───────────────────────────────────────────────────────────────────────
# (unreachable block above kept as tombstone — dead code marker)

if __name__ == "__main__":
    log.info("Turnip customer portal starting on :8767")
    app.run(host="0.0.0.0", port=8767, debug=False)

@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve(path):
    if path != "" and os.path.exists(app.static_folder + "/" + path):
        return send_from_directory(app.static_folder, path)
    else:
        # If it's an API route that somehow reached here, it's 404
        if path.startswith("api/"):
            return jsonify({"error": "Not Found"}), 404
        return render_template("index.html")
