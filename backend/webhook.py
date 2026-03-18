#!/usr/bin/env python3
"""
Turnip VPN — Paystack Webhook Server
Listens for payment events, provisions VPN accounts, emails credentials.

Run:  gunicorn -w 2 -b 0.0.0.0:8766 webhook:app
Dev:  python3 webhook.py
"""

import os, hmac, hashlib, json, logging, traceback
from flask import Flask, request, jsonify
from dotenv import load_dotenv

from provisioner import provision_user, deprovision_user, get_plan_for_amount
from database import db_init, record_payment, get_subscription, update_subscription_status
from emailer import send_welcome_email

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("/var/log/turnip-payments.log"),
        logging.StreamHandler(),
    ]
)
log = logging.getLogger(__name__)

app = Flask(__name__)

PAYSTACK_SECRET = os.environ["PAYSTACK_SECRET_KEY"]


# ── Signature verification ─────────────────────────────────────────────────────

def verify_paystack_signature(payload: bytes, sig_header: str) -> bool:
    """Validate HMAC-SHA512 signature from Paystack."""
    expected = hmac.new(
        PAYSTACK_SECRET.encode("utf-8"),
        payload,
        hashlib.sha512
    ).hexdigest()
    return hmac.compare_digest(expected, sig_header or "")


# ── Event handlers ─────────────────────────────────────────────────────────────

def handle_charge_success(data: dict):
    """
    Triggered when a payment is confirmed.
    Creates VPN credentials and emails the customer.
    """
    email       = data["customer"]["email"]
    amount_kobo = data["amount"]                    # Paystack sends in kobo (₦1 = 100 kobo)
    amount_ngn  = amount_kobo / 100
    reference   = data["reference"]
    metadata    = data.get("metadata", {})
    plan_code   = metadata.get("plan_code", "")

    log.info(f"Payment confirmed: {email} | ₦{amount_ngn:.0f} | ref={reference}")

    # Prevent duplicate processing
    if get_subscription(reference):
        log.warning(f"Duplicate webhook ignored: ref={reference}")
        return

    # Determine plan from amount
    plan = get_plan_for_amount(amount_ngn, plan_code)
    log.info(f"Assigning plan: {plan['name']} ({plan['duration_days']} days)")

    # Create VPN account
    creds = provision_user(email, plan)
    log.info(f"VPN account created: {creds['username']}")

    # Persist to database
    record_payment(
        email=email,
        reference=reference,
        amount=amount_ngn,
        plan_name=plan["name"],
        duration_days=plan["duration_days"],
        username=creds["username"],
        password=creds["password"],
    )

    # Email credentials + .mobileconfig to customer
    send_welcome_email(email, creds, plan)
    log.info(f"Welcome email sent to {email}")


def handle_subscription_disable(data: dict):
    """Triggered when a recurring subscription is cancelled or payment fails."""
    email    = data["customer"]["email"]
    sub_code = data.get("subscription_code", "")
    log.info(f"Subscription disabled: {email} | sub={sub_code}")

    sub = get_subscription(email=email)
    if sub and sub.get("username"):
        deprovision_user(sub["username"])
        update_subscription_status(email, "disabled")
        log.info(f"VPN account disabled: {sub['username']}")


def handle_subscription_not_renew(data: dict):
    """Triggered when customer disables auto-renew."""
    email = data["customer"]["email"]
    log.info(f"Auto-renew disabled: {email} — account stays active until expiry")
    update_subscription_status(email, "non_renewing")


# ── Event router ───────────────────────────────────────────────────────────────

EVENT_HANDLERS = {
    "charge.success":             handle_charge_success,
    "subscription.disable":       handle_subscription_disable,
    "subscription.not_renew":     handle_subscription_not_renew,
}


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.route("/webhook/paystack", methods=["POST"])
def paystack_webhook():
    payload   = request.get_data()
    signature = request.headers.get("x-paystack-signature", "")

    if not verify_paystack_signature(payload, signature):
        log.warning("Invalid Paystack signature — rejected")
        return jsonify({"error": "invalid signature"}), 401

    try:
        event = json.loads(payload)
        event_type = event.get("event")
        data       = event.get("data", {})

        log.info(f"Received event: {event_type}")

        handler = EVENT_HANDLERS.get(event_type)
        if handler:
            handler(data)
        else:
            log.info(f"Unhandled event type: {event_type} — ignoring")

        return jsonify({"status": "ok"}), 200

    except Exception as e:
        log.error(f"Webhook processing error: {e}\n{traceback.format_exc()}")
        # Always return 200 so Paystack doesn't retry endlessly
        return jsonify({"status": "error", "detail": str(e)}), 200


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "Turnip Payment Backend"}), 200


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    db_init()
    log.info("Turnip payment backend starting on :8766")
    app.run(host="0.0.0.0", port=8766, debug=False)
