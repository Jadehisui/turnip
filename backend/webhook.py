#!/usr/bin/env python3
"""
Turnip VPN — Lemon Squeezy Webhook Server
Listens for payment events, provisions VPN accounts, emails credentials.

Run:  gunicorn -w 2 -b 0.0.0.0:8766 webhook:app
Dev:  python3 webhook.py
"""

import os, hmac, hashlib, json, logging, traceback
from flask import Flask, request, jsonify
from dotenv import load_dotenv

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../backend"))
from provisioner import provision_user, deprovision_user, PLANS
from database import db_init, record_payment, get_subscription, update_subscription_status, get_devices_for_email
from emailer import send_welcome_email

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("payments.log"),
        logging.StreamHandler(),
    ]
)
log = logging.getLogger(__name__)

app = Flask(__name__)

LS_WEBHOOK_SECRET = os.environ.get("LEMONSQUEEZY_WEBHOOK_SECRET", "")

# Plan code → plan dict lookup
PLAN_MAP = {p["name"].lower(): p for p in PLANS}


# ── Signature verification ─────────────────────────────────────────────────────

def verify_lemonsqueezy_signature(payload: bytes, sig_header: str) -> bool:
    """Validate HMAC-SHA256 signature from Lemon Squeezy."""
    if not LS_WEBHOOK_SECRET:
        log.warning("LEMONSQUEEZY_WEBHOOK_SECRET not set — skipping sig check (dev mode)")
        return True
    expected = hmac.new(
        LS_WEBHOOK_SECRET.encode("utf-8"),
        payload,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, sig_header or "")


# ── Shared provisioning helper ────────────────────────────────────────────────

def _provision_and_record(email: str, plan_code: str, reference: str, region: str = "eu"):
    """Find plan, provision VPN account(s), record payment, email credentials."""
    if get_subscription(reference):
        log.warning(f"Duplicate webhook ignored: ref={reference}")
        return

    plan  = PLAN_MAP.get(plan_code.lower(), PLAN_MAP.get("pro"))
    creds = provision_user(email, plan, region)
    log.info(f"VPN account(s) created for {email} | region={creds['region']}")

    record_payment(
        email=email,
        reference=reference,
        amount=plan["min_amount"],
        plan_name=plan["name"],
        duration_days=plan["duration_days"],
        username=creds["username"],
        password=creds["password"],
        region=creds["region"],
        devices=creds["devices"],
    )
    send_welcome_email(email, creds, plan)
    log.info(f"Welcome email sent to {email}")


# ── Event handlers ─────────────────────────────────────────────────────────────

def handle_order_created(data: dict, meta: dict):
    """One-time order confirmed — create VPN account."""
    attrs       = data.get("attributes", {})
    email       = attrs.get("user_email", "")
    reference   = attrs.get("identifier", str(data.get("id", "")))
    custom_data = meta.get("custom_data") or {}
    plan_code   = custom_data.get("plan_code", "pro")
    region      = custom_data.get("region", "eu")

    log.info(f"order_created: {email} | plan={plan_code} | region={region} | ref={reference}")
    _provision_and_record(email, plan_code, reference, region)


def handle_subscription_created(data: dict, meta: dict):
    """New subscription — same provisioning flow as one-time order."""
    attrs       = data.get("attributes", {})
    email       = attrs.get("user_email", "")
    reference   = f"sub_{data.get('id', '')}"
    custom_data = meta.get("custom_data") or {}
    plan_code   = custom_data.get("plan_code", "pro")
    region      = custom_data.get("region", "eu")

    log.info(f"subscription_created: {email} | plan={plan_code} | region={region}")
    _provision_and_record(email, plan_code, reference, region)


def handle_subscription_payment_success(data: dict, meta: dict):
    """Recurring renewal — deprovision old credentials, then re-provision with extended expiry."""
    attrs       = data.get("attributes", {})
    email       = attrs.get("user_email", "")
    reference   = f"renewal_{data.get('id', '')}_{attrs.get('updated_at', '')}"
    custom_data = meta.get("custom_data") or {}
    plan_code   = custom_data.get("plan_code", "pro")

    # BUG-2: LS does not re-send custom_data on auto-renewals — fall back to stored region
    region = custom_data.get("region") or ""
    if not region:
        existing_sub = get_subscription(email=email)
        region = (existing_sub or {}).get("server_region", "eu")

    log.info(f"subscription_payment_success: {email} | plan={plan_code} | region={region}")

    # BUG-1: Remove old ipsec.secrets entries before creating new ones
    existing_devices = get_devices_for_email(email)
    for dev in existing_devices:
        try:
            deprovision_user(dev["username"])
        except Exception as exc:
            log.warning(f"Could not deprovision {dev['username']} before renewal: {exc}")

    _provision_and_record(email, plan_code, reference, region)


def handle_subscription_cancelled(data: dict, meta: dict):
    """Subscription cancelled — disable all VPN devices immediately."""
    email = data.get("attributes", {}).get("user_email", "")
    log.info(f"subscription_cancelled: {email}")

    # BUG-3: Deprovision ALL devices, not just Device 1
    devices = get_devices_for_email(email)
    if devices:
        for dev in devices:
            try:
                deprovision_user(dev["username"])
            except Exception as exc:
                log.warning(f"Could not deprovision {dev['username']}: {exc}")
    else:
        # Fallback for legacy single-credential subscriptions
        sub = get_subscription(email=email)
        if sub and sub.get("username"):
            try:
                deprovision_user(sub["username"])
            except Exception as exc:
                log.warning(f"Could not deprovision {sub['username']}: {exc}")

    update_subscription_status(email, "disabled")
    log.info(f"All VPN credentials disabled for {email}")


def handle_subscription_expired(data: dict, meta: dict):
    """Subscription expired — same as cancellation."""
    handle_subscription_cancelled(data, meta)


# ── Event router ───────────────────────────────────────────────────────────────

EVENT_HANDLERS = {
    "order_created":                  handle_order_created,
    "subscription_created":           handle_subscription_created,
    "subscription_payment_success":   handle_subscription_payment_success,
    "subscription_cancelled":         handle_subscription_cancelled,
    "subscription_expired":           handle_subscription_expired,
}


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.route("/webhook/lemonsqueezy", methods=["POST"])
def lemonsqueezy_webhook():
    payload   = request.get_data()
    signature = request.headers.get("X-Signature", "")

    if not verify_lemonsqueezy_signature(payload, signature):
        log.warning("Invalid Lemon Squeezy signature — rejected")
        return jsonify({"error": "invalid signature"}), 401

    try:
        event      = json.loads(payload)
        meta       = event.get("meta", {})
        event_name = meta.get("event_name")
        data       = event.get("data", {})

        log.info(f"Received LS event: {event_name}")

        handler = EVENT_HANDLERS.get(event_name)
        if handler:
            handler(data, meta)
        else:
            log.info(f"Unhandled event type: {event_name} — ignoring")

        return jsonify({"status": "ok"}), 200

    except Exception as e:
        log.error(f"Webhook processing error: {e}\n{traceback.format_exc()}")
        # Always return 200 so Lemon Squeezy doesn't retry endlessly
        return jsonify({"status": "error", "detail": str(e)}), 200


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "Turnip Payment Backend"}), 200


# ── NOWPayments webhook ───────────────────────────────────────────────────────

@app.route("/webhook/nowpayments", methods=["POST"])
def nowpayments_webhook():
    """Handle IPN callback from NOWPayments after a confirmed crypto payment."""
    from crypto_payments import verify_nowpayments_signature, handle_successful_payment, NGN_TO_USD_RATE

    payload   = request.get_data()
    signature = request.headers.get("x-nowpayments-sig", "")

    if not verify_nowpayments_signature(payload, signature):
        log.warning("Invalid NOWPayments signature — rejected")
        return jsonify({"error": "invalid signature"}), 401

    try:
        event          = json.loads(payload)
        payment_status = event.get("payment_status")

        # Only act on terminal "finished" status
        if payment_status != "finished":
            log.info(f"NOWPayments status={payment_status} — not yet finished, skipping")
            return jsonify({"status": "ok"}), 200

        # order_id format: "email::plan_code::amount_ngn::region"
        order_id = event.get("order_id", "")
        parts    = order_id.split("::")
        if len(parts) < 2:
            log.error(f"Unexpected order_id format: {order_id!r}")
            return jsonify({"status": "error"}), 200

        email      = parts[0]
        plan_code  = parts[1]
        amount_ngn = float(parts[2]) if len(parts) >= 3 else float(event.get("price_amount", 0)) * NGN_TO_USD_RATE
        reference  = f"np_{event.get('payment_id', '')}"

        handle_successful_payment(email, amount_ngn, reference, order_id=order_id)
        return jsonify({"status": "ok"}), 200

    except Exception as e:
        log.error(f"NOWPayments webhook error: {e}\n{traceback.format_exc()}")
        return jsonify({"status": "error"}), 200


# ── Entry point ────────────────────────────────────────────────────────────────

db_init()  # ensure tables exist whether running via gunicorn or directly

if __name__ == "__main__":
    log.info("Turnip payment backend starting on :8766")
    app.run(host="0.0.0.0", port=8766, debug=False)
