#!/usr/bin/env python3
"""
Turnip VPN — Webhook Test Script
Sends a signed test event to the local webhook server.

Usage:
    # Start webhook server in one terminal:
    cd backend && python3 webhook.py

    # Dry run (stubs provisioning — no SSH):
    cd backend && python3 test_webhook.py

    # Real run (actually provisions on VPN server):
    cd backend && DRY_RUN=0 python3 test_webhook.py

    # Custom event type:
    cd backend && EVENT=subscription_cancelled python3 test_webhook.py

Available events:
    order_created  (default)
    subscription_created
    subscription_payment_success
    subscription_cancelled
    subscription_expired
"""

import os, sys, json, hmac, hashlib, time, requests
from dotenv import load_dotenv

load_dotenv()

WEBHOOK_URL  = os.environ.get("WEBHOOK_URL",  "http://localhost:8766/webhook/lemonsqueezy")
WEBHOOK_SECRET = os.environ.get("LEMONSQUEEZY_WEBHOOK_SECRET", "")
EVENT_NAME   = os.environ.get("EVENT",        "order_created")
TEST_EMAIL   = os.environ.get("TEST_EMAIL",   "test+webhook@example.com")
TEST_PLAN    = os.environ.get("TEST_PLAN",    "pro")
TEST_REGION  = os.environ.get("TEST_REGION",  "nl")
DRY_RUN      = os.environ.get("DRY_RUN",      "1") != "0"

# ── Build realistic LS payloads ────────────────────────────────────────────────

ORDER_ID   = f"test-order-{int(time.time())}"
SUB_ID     = f"test-sub-{int(time.time())}"

BASE_ATTRS = {
    "user_email":  TEST_EMAIL,
    "user_name":   "Test User",
    "status":      "paid",
    "total":       "7000",
    "currency":    "NGN",
    "created_at":  "2026-01-01T00:00:00.000000Z",
    "updated_at":  "2026-01-01T00:00:00.000000Z",
}

CUSTOM_DATA = {
    "plan_code": TEST_PLAN,
    "region":    TEST_REGION,
}

PAYLOADS = {
    "order_created": {
        "meta": {
            "event_name": "order_created",
            "custom_data": CUSTOM_DATA,
        },
        "data": {
            "type":       "orders",
            "id":         ORDER_ID,
            "attributes": {
                **BASE_ATTRS,
                "identifier": ORDER_ID,
            },
        },
    },
    "subscription_created": {
        "meta": {
            "event_name": "subscription_created",
            "custom_data": CUSTOM_DATA,
        },
        "data": {
            "type":       "subscriptions",
            "id":         SUB_ID,
            "attributes": {
                **BASE_ATTRS,
                "identifier": f"sub_{SUB_ID}",
            },
        },
    },
    "subscription_payment_success": {
        "meta": {
            "event_name": "subscription_payment_success",
            "custom_data": CUSTOM_DATA,
        },
        "data": {
            "type":       "subscription-invoices",
            "id":         f"{SUB_ID}-renewal",
            "attributes": {
                **BASE_ATTRS,
                "identifier": f"renewal_{SUB_ID}",
            },
        },
    },
    "subscription_cancelled": {
        "meta": {"event_name": "subscription_cancelled", "custom_data": {}},
        "data": {
            "type":       "subscriptions",
            "id":         SUB_ID,
            "attributes": {
                **BASE_ATTRS,
                "status": "cancelled",
            },
        },
    },
    "subscription_expired": {
        "meta": {"event_name": "subscription_expired", "custom_data": {}},
        "data": {
            "type":       "subscriptions",
            "id":         SUB_ID,
            "attributes": {
                **BASE_ATTRS,
                "status": "expired",
            },
        },
    },
}


def sign(payload_bytes: bytes) -> str:
    if not WEBHOOK_SECRET:
        return ""
    return hmac.new(
        WEBHOOK_SECRET.encode("utf-8"),
        payload_bytes,
        hashlib.sha256,
    ).hexdigest()


def send(event_name: str):
    if event_name not in PAYLOADS:
        print(f"[ERROR] Unknown event '{event_name}'. Choose from: {', '.join(PAYLOADS)}")
        sys.exit(1)

    payload_bytes = json.dumps(PAYLOADS[event_name]).encode("utf-8")
    signature     = sign(payload_bytes)

    print(f"\n{'='*60}")
    print(f"  Event   : {event_name}")
    print(f"  Email   : {TEST_EMAIL}")
    print(f"  Plan    : {TEST_PLAN}  Region: {TEST_REGION}")
    print(f"  DryRun  : {DRY_RUN}")
    print(f"  URL     : {WEBHOOK_URL}")
    print(f"  Signing : {'yes (HMAC-SHA256)' if signature else 'no (secret not set)'}")
    print(f"{'='*60}\n")

    headers = {
        "Content-Type":  "application/json",
        "X-Signature":   signature,
        "X-Event-Name":  event_name,
    }

    try:
        resp = requests.post(WEBHOOK_URL, data=payload_bytes, headers=headers, timeout=30)
        print(f"HTTP {resp.status_code}")
        try:
            print(json.dumps(resp.json(), indent=2))
        except Exception:
            print(resp.text[:500])
    except requests.ConnectionError:
        print(f"[ERROR] Could not connect to {WEBHOOK_URL}")
        print("        Make sure the webhook server is running:  cd backend && python3 webhook.py")
        sys.exit(1)


# ── DRY RUN: patch provisioner before importing webhook ───────────────────────

if DRY_RUN:
    # Monkey-patch provision_user before the webhook module imports it
    import unittest.mock as mock
    import importlib

    fake_creds = {
        "username": "test_vpnuser",
        "password": "FakePass1234!",
        "region":   TEST_REGION,
        "devices":  1,
        "config":   "[fake IKEv2 config]",
        "profile_b64": "",
    }

    # Patch at provisioner module level
    import provisioner as _prov
    _prov.provision_user = lambda email, plan, region="eu": (
        print(f"  [DRY RUN] provision_user({email!r}, {plan['name']!r}, region={region!r}) skipped") or fake_creds
    )
    _prov.deprovision_user = lambda username: (
        print(f"  [DRY RUN] deprovision_user({username!r}) skipped")
    )

    # Also patch send_welcome_email
    import emailer as _emailer
    _emailer.send_welcome_email = lambda email, creds, plan: (
        print(f"  [DRY RUN] send_welcome_email({email!r}) skipped")
    )

send(EVENT_NAME)
