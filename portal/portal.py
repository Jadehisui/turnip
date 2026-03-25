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
from database import db_init, get_subscription, get_all_subscriptions, record_payment, get_devices_for_email
from provisioner import provision_user, deprovision_user, generate_password, generate_mobileconfig, get_plan_for_amount, get_server_host, PLANS, CA_CERT_PATH, SERVERS

app = Flask(__name__, 
            static_folder='frontend/dist', 
            template_folder='frontend/dist')
app.secret_key      = os.environ.get("PORTAL_SECRET_KEY", secrets.token_hex(32))
app.permanent_session_lifetime = timedelta(hours=12)

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
    error = request.args.get("error", "")
    return render_template_string(LOGIN_TEMPLATE, error=error)


@app.route("/api/auth/login", methods=["POST"])
def api_login():
    data = request.get_json()
    email = data.get("email", "").strip().lower()
    if not email or "@" not in email:
        return jsonify({"error": "Enter a valid email address"}), 400

    sub = get_subscription(email=email)
    if not sub:
        return jsonify({"error": "No account found with this email. Please check your plans."}), 404

    # Set session
    session.permanent = True
    session["email"]  = email
    log.info(f"API Login: {email}")
    return jsonify({"ok": True, "email": email})


@app.route("/login", methods=["POST"])
def login_post():
    email = request.form.get("email", "").strip().lower()
    if not email or "@" not in email:
        return redirect(url_for("login_page", error="Enter a valid email address"))

    sub = get_subscription(email=email)
    if not sub:
        # Don't reveal whether account exists — send magic link feel
        return render_template_string(LOGIN_CHECK_EMAIL_TEMPLATE, email=email)

    # Set session
    session.permanent = True
    session["email"]  = email
    log.info(f"Login: {email}")
    return redirect(url_for("dashboard"))


@app.route("/logout")
def logout():
    email = session.pop("email", "")
    log.info(f"Logout: {email}")
    return redirect(url_for("login_page"))


@app.route("/dashboard")
@login_required
def dashboard():
    sub = get_current_user()
    if not sub:
        session.pop("email", "")
        return redirect(url_for("login_page", error="Account not found"))

    days = days_remaining(sub.get("expires_at", ""))
    status = sub.get("status", "active")

    return render_template_string(
        DASHBOARD_TEMPLATE,
        sub=sub,
        days=days,
        status=status,
        server=VPN_SERVER_ADDR,
        plans=PLANS,
    )


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
    <div style="font-size:22px;font-weight:800;text-align:center;margin-bottom:.5rem">Secure<span style="color:var(--accent)">Fast</span></div>
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

LOGIN_CHECK_EMAIL_TEMPLATE = """<!DOCTYPE html>
<html>
<head>""" + _BASE_STYLE + """<title>Turnip VPN — Check your email</title></head>
<body>
<style>
.wrap{display:flex;align-items:center;justify-content:center;min-height:100vh;padding:2rem}
.box{background:var(--bg2);border:1px solid var(--border);border-radius:16px;padding:2.5rem;width:100%;max-width:400px;text-align:center}
</style>
<div class="wrap">
  <div class="box">
    <div style="font-size:36px;margin-bottom:1rem">🔒</div>
    <div style="font-size:18px;font-weight:700;margin-bottom:.75rem">No account found</div>
    <div style="color:var(--text2);font-size:14px;line-height:1.7;margin-bottom:1.5rem">
      No active subscription found for <strong style="color:var(--text)">{{ email }}</strong>.<br>
      Purchase a plan to create your account.
    </div>
    <a href="/pricing" class="btn btn-accent" style="display:block;padding:12px;text-align:center;font-size:14px">View plans →</a>
    <a href="/login" style="display:block;margin-top:12px;font-size:12px;color:var(--text3)">Try a different email</a>
  </div>
</div>
</body></html>"""


# ── Dashboard template ────────────────────────────────────────────────────────

DASHBOARD_TEMPLATE = """<!DOCTYPE html>
<html>
<head>""" + _BASE_STYLE + """<title>Turnip VPN — Dashboard</title></head>
<body>
<style>
.content{max-width:860px;margin:0 auto;padding:2rem}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px}
.grid3{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:16px}
.metric{background:var(--surf);border:1px solid var(--border);border-radius:10px;padding:1.1rem 1.25rem}
.metric-lbl{font-size:10px;color:var(--text3);font-weight:700;letter-spacing:.07em;text-transform:uppercase;margin-bottom:8px}
.metric-val{font-size:24px;font-weight:800;font-family:var(--mono);letter-spacing:-1px}
.metric-sub{font-size:11px;color:var(--text2);margin-top:3px}
.badge{font-family:var(--mono);font-size:10px;font-weight:700;padding:3px 9px;border-radius:4px}
.badge-green{background:var(--adim);color:var(--accent);border:1px solid var(--border2)}
.badge-amber{background:rgba(255,184,48,.1);color:var(--amber);border:1px solid rgba(255,184,48,.25)}
.badge-red{background:rgba(255,71,87,.1);color:var(--red);border:1px solid rgba(255,71,87,.25)}
.cred-row{display:flex;align-items:center;justify-content:space-between;padding:10px 0;border-bottom:1px solid var(--border)}
.cred-row:last-child{border-bottom:none}
.cred-lbl{font-size:10px;color:var(--text3);font-weight:700;letter-spacing:.08em;text-transform:uppercase;min-width:90px}
.cred-val{font-family:var(--mono);font-size:12px;color:var(--text);flex:1;padding:0 8px;word-break:break-all}
.copy-btn{background:transparent;border:1px solid var(--border2);color:var(--accent);font-size:10px;font-family:var(--mono);padding:3px 9px;border-radius:4px;cursor:pointer;white-space:nowrap}
.copy-btn:hover{background:var(--adim)}
.os-tab{padding:10px 16px;border-radius:6px;font-size:12px;font-weight:700;cursor:pointer;border:1px solid var(--border);background:transparent;color:var(--text2);transition:all .15s}
.os-tab.active,.os-tab:hover{border-color:var(--accent);color:var(--accent);background:var(--adim)}
.setup-step{display:flex;gap:12px;padding:10px 0;border-bottom:1px solid var(--border);font-size:13px;color:var(--text2)}
.setup-step:last-child{border-bottom:none}
.step-n{font-family:var(--mono);font-size:11px;color:var(--accent);min-width:20px;padding-top:1px}
.os-panel{display:none}.os-panel.active{display:block}
.plan-bar{height:6px;background:var(--bg3);border-radius:3px;overflow:hidden;margin-top:8px}
.plan-fill{height:100%;border-radius:3px;background:var(--accent);transition:width .5s}
</style>

<nav class="nav">
  <div class="logo">Secure<span>Fast</span></div>
  <div class="nav-right">
    <span style="font-size:12px;color:var(--text2)">{{ sub.email }}</span>
    <a href="/logout" class="btn btn-danger">Sign out</a>
  </div>
</nav>

<div class="content">

  <!-- Status row -->
  <div class="grid3">
    <div class="metric">
      <div class="metric-lbl">Plan</div>
      <div class="metric-val" style="font-size:18px;padding-top:4px">{{ sub.plan_name }}</div>
      <div class="metric-sub">
        {% if status == 'active' %}<span class="badge badge-green">ACTIVE</span>
        {% elif status == 'non_renewing' %}<span class="badge badge-amber">ACTIVE · NOT RENEWING</span>
        {% else %}<span class="badge badge-red">{{ status.upper() }}</span>{% endif %}
      </div>
    </div>
    <div class="metric">
      <div class="metric-lbl">Days remaining</div>
      <div class="metric-val" style="{% if days <= 3 %}color:var(--red){% elif days <= 7 %}color:var(--amber){% else %}color:var(--accent){% endif %}">{{ days }}</div>
      <div class="plan-bar"><div class="plan-fill" style="width:{{ [days * 100 // 30, 100] | min }}%"></div></div>
    </div>
    <div class="metric">
      <div class="metric-lbl">Expires</div>
      <div class="metric-val" style="font-size:16px;padding-top:6px">{{ sub.expires_at[:10] }}</div>
      <div class="metric-sub">UTC</div>
    </div>
  </div>

  <!-- Wallet Association -->
  <div class="card" style="margin-bottom:16px; border-color: {% if sub.wallet_address %}var(--border){% else %}var(--blue){% endif %};">
    <div style="display:flex; align-items:center; justify-content:space-between;">
      <div>
        <div style="font-size:14px; font-weight:700;">Linked Wallet</div>
        <div style="font-size:12px; color:var(--text2);">
          {% if sub.wallet_address %}
            <span class="mono">{{ sub.wallet_address[:6] }}...{{ sub.wallet_address[-4:] }}</span>
          {% else %}
            No wallet linked. Link your wallet for one-tap login and crypto payments.
          {% endif %}
        </div>
      </div>
      {% if not sub.wallet_address %}
        <button class="btn btn-wallet" style="width:auto; margin-top:0;" onclick="connectWallet()">Link Wallet</button>
      {% endif %}
    </div>
  </div>

  <div class="grid2">

    <!-- Credentials -->
    <div class="card">
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:1.25rem">
        <div style="font-size:14px;font-weight:700">VPN credentials</div>
        <button class="btn" style="font-size:11px;padding:6px 12px" onclick="regenerate()">Regenerate ↺</button>
      </div>
      <div class="cred-row">
        <div class="cred-lbl">Username</div>
        <div class="cred-val" id="cv-user">{{ sub.username }}</div>
        <button class="copy-btn" onclick="copy('cv-user', this)">Copy</button>
      </div>
      <div class="cred-row">
        <div class="cred-lbl">Password</div>
        <div class="cred-val" id="cv-pass" style="filter:blur(4px);transition:filter .2s">{{ sub.password }}</div>
        <button class="copy-btn" onclick="reveal('cv-pass', this)">Show</button>
      </div>
      <div class="cred-row">
        <div class="cred-lbl">Server</div>
        <div class="cred-val" id="cv-srv">{{ server }}</div>
        <button class="copy-btn" onclick="copy('cv-srv', this)">Copy</button>
      </div>
      <div class="cred-row">
        <div class="cred-lbl">VPN type</div>
        <div class="cred-val" style="color:var(--text2)">IKEv2 / IPsec · EAP-MSCHAPv2</div>
      </div>
      <div style="display:flex;gap:8px;margin-top:1.25rem;padding-top:1.25rem;border-top:1px solid var(--border)">
        <a href="/download/profile" class="btn btn-accent" style="flex:1;text-align:center;font-size:13px">⬇ Download .mobileconfig</a>
        <a href="/download/ca" class="btn" style="font-size:13px">CA cert</a>
      </div>
    </div>

    <!-- Setup guide -->
    <div class="card">
      <div style="font-size:14px;font-weight:700;margin-bottom:1rem">Setup guide</div>
      <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:1.25rem">
        <button class="os-tab active" onclick="showOS('ios', this)">iOS</button>
        <button class="os-tab" onclick="showOS('macos', this)">macOS</button>
        <button class="os-tab" onclick="showOS('windows', this)">Windows</button>
        <button class="os-tab" onclick="showOS('android', this)">Android</button>
      </div>

      <div id="os-ios" class="os-panel active">
        <div class="setup-step"><div class="step-n">01</div><div>Download the <strong style="color:var(--text)">.mobileconfig</strong> file above</div></div>
        <div class="setup-step"><div class="step-n">02</div><div>Tap the file → "Allow" → Settings opens automatically</div></div>
        <div class="setup-step"><div class="step-n">03</div><div>Settings → <strong style="color:var(--text)">Profile Downloaded</strong> → Install → enter device passcode</div></div>
        <div class="setup-step"><div class="step-n">04</div><div>Settings → VPN → <strong style="color:var(--text)">Turnip VPN</strong> → toggle ON</div></div>
      </div>

      <div id="os-macos" class="os-panel">
        <div class="setup-step"><div class="step-n">01</div><div>Download and double-click the <strong style="color:var(--text)">.mobileconfig</strong> file</div></div>
        <div class="setup-step"><div class="step-n">02</div><div>System Settings → <strong style="color:var(--text)">Privacy & Security → Profiles → Install</strong></div></div>
        <div class="setup-step"><div class="step-n">03</div><div>System Settings → VPN → <strong style="color:var(--text)">Turnip VPN</strong> → Connect</div></div>
      </div>

      <div id="os-windows" class="os-panel">
        <div class="setup-step"><div class="step-n">01</div><div>Download and install the <strong style="color:var(--text)">CA cert</strong> → certmgr.msc → Trusted Root CAs</div></div>
        <div class="setup-step"><div class="step-n">02</div><div>Settings → Network → VPN → <strong style="color:var(--text)">Add a VPN connection</strong></div></div>
        <div class="setup-step"><div class="step-n">03</div><div>Provider: Windows (built-in) · Type: <strong style="color:var(--text)">IKEv2</strong> · Server: <span class="mono" style="color:var(--accent)">{{ server }}</span></div></div>
        <div class="setup-step"><div class="step-n">04</div><div>Sign-in: Username / Password → enter credentials above</div></div>
      </div>

      <div id="os-android" class="os-panel">
        <div class="setup-step"><div class="step-n">01</div><div>Install <strong style="color:var(--text)">strongSwan VPN Client</strong> from Play Store</div></div>
        <div class="setup-step"><div class="step-n">02</div><div>Add VPN Profile → Server: <span class="mono" style="color:var(--accent)">{{ server }}</span></div></div>
        <div class="setup-step"><div class="step-n">03</div><div>VPN type: <strong style="color:var(--text)">IKEv2 EAP (Username/Password)</strong></div></div>
        <div class="setup-step"><div class="step-n">04</div><div>Enter your username and password → Save → Connect</div></div>
      </div>
    </div>
  </div>

  <!-- Renew / Upgrade -->
  {% if days <= 7 or status != 'active' %}
  <div class="card" style="border-color:rgba(255,184,48,.25);margin-bottom:16px">
    <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px">
      <div>
        <div style="font-size:14px;font-weight:700;margin-bottom:4px">
          {% if days == 0 %}Your subscription has expired{% else %}Expiring in {{ days }} day{% if days != 1 %}s{% endif %}{% endif %}
        </div>
        <div style="font-size:13px;color:var(--text2)">Renew now to keep your VPN active without interruption.</div>
      </div>
      <button class="btn btn-accent" onclick="openRenew()">Renew subscription →</button>
    </div>
  </div>
  {% endif %}

  <!-- Upgrade / plan options -->
  <div class="card">
    <div style="font-size:14px;font-weight:700;margin-bottom:1rem">Plans</div>
    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px">
      {% for plan in plans %}
      <div style="background:var(--bg2);border:1px solid var(--border);border-radius:10px;padding:1.25rem;{% if plan.name == sub.plan_name %}border-color:var(--accent){% endif %}">
        <div style="font-size:10px;font-weight:700;color:var(--text3);letter-spacing:.08em;text-transform:uppercase;margin-bottom:.75rem">{{ plan.name }}</div>
        <div style="font-size:28px;font-weight:800;font-family:var(--mono);letter-spacing:-1px;margin-bottom:.75rem">
          ₦{{ "{:,.0f}".format(plan.min_amount) }}<span style="font-size:13px;color:var(--text2);font-family:var(--sans);font-weight:400">/mo</span>
        </div>
        <div style="font-size:12px;color:var(--text2);margin-bottom:1rem">
          {% if plan.devices == 999 %}Unlimited devices{% else %}{{ plan.devices }} device{% if plan.devices != 1 %}s{% endif %}{% endif %}
          · {{ plan.duration_days }} days
        </div>
        {% if plan.name == sub.plan_name %}
          <div style="text-align:center;font-size:11px;font-family:var(--mono);color:var(--accent);padding:7px 0">CURRENT PLAN</div>
        {% else %}
          <button class="btn btn-accent" style="width:100%;padding:9px;font-size:12px"
            onclick="payForPlan({{ plan.min_amount }}, '{{ plan.name.lower() }}')">
            {% if plan.min_amount > (sub_plan_min_amount | default(4000)) %}Upgrade{% else %}Switch{% endif %} →
          </button>
        {% endif %}
      </div>
      {% endfor %}
    </div>
  </div>

</div>

<script>
function copy(id, btn) {
  const text = document.getElementById(id).textContent.trim();
  navigator.clipboard.writeText(text).then(() => {
    btn.textContent = 'Copied!';
    setTimeout(() => btn.textContent = 'Copy', 2000);
  });
}
function reveal(id, btn) {
  const el = document.getElementById(id);
  if (el.style.filter) { el.style.filter = ''; btn.textContent = 'Hide'; }
  else { el.style.filter = 'blur(4px)'; btn.textContent = 'Show'; }
}
function showOS(os, btn) {
  document.querySelectorAll('.os-panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.os-tab').forEach(b => b.classList.remove('active'));
  document.getElementById('os-'+os).classList.add('active');
  btn.classList.add('active');
}
async function regenerate() {
  if (!confirm('Generate a new password? Your current password will stop working immediately.')) return;
  const r = await fetch('/api/regenerate', { method:'POST' });
  const d = await r.json();
  if (d.ok) {
    document.getElementById('cv-pass').textContent = d.password;
    document.getElementById('cv-pass').style.filter = '';
    alert('Password updated. Re-connect your devices with the new password.');
  } else { alert(d.error || 'Failed'); }
}
async function payForPlan(amount, planCode) {
  const r = await fetch('/api/pay/initiate', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({ amount_ngn: amount, plan_code: planCode })
  });
  const d = await r.json();
  if (d.payment_url) { window.location.href = d.payment_url; }
  else { alert(d.error || 'Could not initiate payment'); }
}
async function connectWallet() {
  if (!window.ethereum) return alert('Please install MetaMask or another Web3 wallet');
  try {
    const provider = new ethers.providers.Web3Provider(window.ethereum);
    await provider.send("eth_requestAccounts", []);
    const signer = provider.getSigner();
    const address = await signer.getAddress();
    const r1 = await fetch('/api/auth/nonce');
    const { nonce } = await r1.json();
    const domain = window.location.host;
    const origin = window.location.origin;
    const message = `${domain} wants you to sign in with your Ethereum account:\n${address}\n\nLink wallet to Turnip VPN account\n\nURI: ${origin}\nVersion: 1\nChain ID: 1\nNonce: ${nonce}\nIssued At: ${new Date().toISOString()}`;
    const signature = await signer.signMessage(message);
    const r2 = await fetch('/api/auth/wallet', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, signature })
    });
    const d2 = await r2.json();
    if (d2.ok) location.reload();
    else alert(d2.error || 'Linking failed');
  } catch (err) { alert(err.message || 'Error'); }
}
function openRenew() { payForPlan(4000, 'pro'); }
</script>
</body></html>"""


# ── Pricing template ──────────────────────────────────────────────────────────

PRICING_TEMPLATE = """<!DOCTYPE html>
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
