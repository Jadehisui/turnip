#!/usr/bin/env python3
"""
Turnip VPN — Crypto Payment Service (NOWPayments)
Creates hosted invoices via NOWPayments API and handles IPN webhooks.

Flow:
  1. /api/pay/crypto/initiate  → create_invoice() → returns payment_url
  2. User pays on NOWPayments hosted page
  3. NOWPayments fires POST /webhook/nowpayments with HMAC-SHA512
  4. handle_successful_payment() → provision_user() → send_welcome_email()

Docs: https://documenter.getpostman.com/view/7907941/2s93JqTRWN
"""

import os, hmac, hashlib, json, logging
import requests as http
from dotenv import load_dotenv

import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from database import record_payment, get_subscription, register_user, get_user
from provisioner import provision_user, get_plan_for_amount
from emailer import send_welcome_email

load_dotenv()
log = logging.getLogger(__name__)

NOWPAYMENTS_API_KEY    = os.environ.get("NOWPAYMENTS_API_KEY", "")
NOWPAYMENTS_IPN_SECRET = os.environ.get("NOWPAYMENTS_IPN_SECRET", "")
NOWPAYMENTS_API        = "https://api.nowpayments.io/v1"

# Approximate NGN/USD rate for converting plan prices.
# Override with NGN_TO_USD_RATE in .env (e.g. 1600).
NGN_TO_USD_RATE = float(os.environ.get("NGN_TO_USD_RATE", "1600"))


# ── Invoice creation ──────────────────────────────────────────────────────────

def create_invoice(email: str, amount_ngn: float, plan_code: str, site_url: str, region: str = "us") -> dict:
    """
    Create a NOWPayments hosted invoice.
    Returns the full API response dict which contains `invoice_url`.
    """
    if not NOWPAYMENTS_API_KEY:
        raise RuntimeError("NOWPAYMENTS_API_KEY is not configured")

    amount_usd = round(amount_ngn / NGN_TO_USD_RATE, 2)
    amount_usd = max(amount_usd, 1.0)   # NOWPayments minimum

    resp = http.post(
        f"{NOWPAYMENTS_API}/invoice",
        headers={
            "x-api-key":    NOWPAYMENTS_API_KEY,
            "Content-Type": "application/json",
        },
        json={
            "price_amount":      amount_usd,
            "price_currency":    "usd",
            "pay_currency":      "usdtbsc",          # default; user can switch on checkout
            "order_id":          f"{email}::{plan_code}::{int(amount_ngn)}::{region}",
            "order_description": f"Turnip VPN — {plan_code.title()} Plan",
            "ipn_callback_url":  f"{site_url}/webhook/nowpayments",
            "success_url":       f"{site_url}/login",
            "cancel_url":        f"{site_url}/pricing",
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


# ── Webhook signature verification ────────────────────────────────────────────

def verify_nowpayments_signature(payload: bytes, sig_header: str) -> bool:
    """Validate HMAC-SHA512 IPN signature from NOWPayments."""
    if not NOWPAYMENTS_IPN_SECRET:
        log.warning("NOWPAYMENTS_IPN_SECRET not set — skipping signature check")
        return True
    # NOWPayments signs the JSON body sorted by keys
    try:
        sorted_body = json.dumps(json.loads(payload), sort_keys=True, separators=(",", ":"))
    except Exception:
        return False
    expected = hmac.new(
        NOWPAYMENTS_IPN_SECRET.encode("utf-8"),
        sorted_body.encode("utf-8"),
        hashlib.sha512,
    ).hexdigest()
    return hmac.compare_digest(expected, sig_header or "")


# ── Payment fulfilment ────────────────────────────────────────────────────────

def handle_successful_payment(email: str, amount_ngn: float, reference: str, order_id: str = ""):
    """Provision a VPN account after a confirmed crypto payment."""
    log.info(f"Crypto payment confirmed: {email} | ₦{amount_ngn:.0f} | ref={reference}")

    if get_subscription(reference):
        log.warning(f"Duplicate crypto webhook ignored: ref={reference}")
        return

    # Parse plan_code and region from order_id (format: email::plan_code::amount::region)
    parts      = (order_id or "").split("::")
    plan_code  = parts[1] if len(parts) > 1 else ""
    region     = parts[3] if len(parts) > 3 else "eu"

    plan  = get_plan_for_amount(amount_ngn, plan_code)
    creds = provision_user(email, plan, region)

    # Ensure a users row exists so the customer can log in via OTP
    if not get_user(email=email):
        try:
            register_user(name=email.split("@")[0], email=email)
            log.info(f"Auto-registered users row for crypto-pay customer: {email}")
        except Exception as e:
            log.warning(f"Could not auto-register user {email}: {e}")

    record_payment(
        email=email,
        reference=reference,
        amount=amount_ngn,
        plan_name=plan["name"],
        duration_days=plan["duration_days"],
        username=creds["username"],
        password=creds["password"],
        region=creds["region"],
        devices=creds["devices"],
    )

    send_welcome_email(email, creds, plan)
    log.info(f"Account activated via crypto: {email} → {creds['username']}")
