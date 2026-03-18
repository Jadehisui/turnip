#!/usr/bin/env python3
"""
Turnip VPN — Crypto Payment Service
Monitors SUI and EVM chains for subscription payments.
Automates provisioning upon confirmation.
"""

import os, logging, time
from datetime import datetime
from dotenv import load_dotenv

# Import shared components
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from database import record_payment, get_subscription
from provisioner import provision_user, get_plan_for_amount
from emailer import send_welcome_email

load_dotenv()
log = logging.getLogger(__name__)

# Config
SUI_RPC_URL = os.environ.get("SUI_RPC_URL", "https://fullnode.mainnet.sui.io:443")
EVM_RPC_URL = os.environ.get("EVM_RPC_URL", "")
RECIPIENT_WALLET = os.environ.get("RECIPIENT_WALLET", "")

def monitor_sui_payments():
    """
    Logic: Poll SUI RPC for TransferObject or programmable transaction events
    to RECIPIENT_WALLET with a memo/metadata matching a user reference.
    """
    log.info("Monitoring SUI payments...")
    # 1. Fetch latest transactions to RECIPIENT_WALLET
    # 2. Extract 'reference' from metadata
    # 3. If reference valid and not processed:
    #    handle_successful_payment(email, amount, ref)
    pass

def monitor_evm_payments():
    """
    Logic: Monitor USDT/USDC transfers on BSC/Polygon/Ethereum.
    """
    log.info("Monitoring EVM payments...")
    pass

def handle_successful_payment(email, amount_ngn, reference):
    """Activates the VPN account after crypto confirmation."""
    log.info(f"Crypto Payment Confirmed: {email} | {amount_ngn} NGN ref={reference}")
    
    if get_subscription(reference):
        return
        
    plan = get_plan_for_amount(amount_ngn)
    creds = provision_user(email, plan)
    
    record_payment(
        email=email,
        reference=reference,
        amount=amount_ngn,
        plan_name=plan["name"],
        duration_days=plan["duration_days"],
        username=creds["username"],
        password=creds["password"]
    )
    
    send_welcome_email(email, creds, plan)
    log.info(f"Account activated via Crypto: {email}")

if __name__ == "__main__":
    log.info("Crypto Payment Service started.")
    # Implementation of the main loop would go here
