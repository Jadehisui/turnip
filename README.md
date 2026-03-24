# Turnip VPN — Complete Stack

Full-stack VPN SaaS. IKEv2/IPsec server + payment backend + customer portal + admin dashboard + monitoring.

---

## One-command deploy

```bash
# On a fresh Ubuntu 22.04 VPS, as root:
git clone / upload this folder, then:

sudo bash deploy.sh YOUR_DOMAIN_OR_IP
```

The deploy script runs all 5 steps in order and prints your live URLs at the end.

---

## Folder structure

```
turnip/
│
├── deploy.sh                  ← run this to deploy everything
│
├── server/                    ← VPN server (Step 1 + 2)
│   ├── install.sh             ← StrongSwan IKEv2 setup
│   ├── install-cockpit.sh     ← Cockpit + firewalld + Admin API
│   ├── adduser.sh             ← add a VPN user
│   ├── deluser.sh             ← remove a VPN user
│   ├── listusers.sh           ← list users + active tunnels
│   ├── gen-profile.sh         ← generate .mobileconfig for a user
│   └── admin.html             ← admin dashboard UI
│
├── backend/                   ← Payment backend (Step 3)
│   ├── webhook.py             ← Payment webhook server (Lemon Squeezy + NOWPayments, port 8766)
│   ├── provisioner.py         ← VPN user creation + .mobileconfig generator
│   ├── emailer.py             ← welcome email with credentials
│   ├── database.py            ← SQLite subscription tracker
│   ├── multiserver.py         ← multi-region server provisioning
│   ├── cron_expire.py         ← daily expiry + renewal reminder cron
│   ├── servers.json           ← server fleet config (edit IPs here)
│   ├── nginx-turnip.conf ← nginx reverse proxy config
│   ├── install-payments.sh    ← deploy payment backend
│   └── .env.example           ← copy to .env and fill in credentials
│
├── portal/                    ← Customer portal (Step 4)
│   ├── portal.py              ← Flask portal (port 8767)
│   └── install-portal.sh      ← deploy portal + nginx + SSL
│
├── monitoring/                ← Monitoring + security (Step 5)
│   ├── monitor.py             ← uptime + alert daemon
│   ├── fail2ban-config.conf   ← IKE brute-force protection
│   └── install-monitoring.sh  ← deploy monitoring + fail2ban
│
└── landing/
    └── index.html             ← public marketing page
```

---

## Manual step-by-step

If you prefer to run each step separately:

```bash
# Step 1 — VPN server
cd server && sudo bash install.sh YOUR_DOMAIN

# Step 2 — Admin panel + Cockpit + firewall
sudo bash install-cockpit.sh 80

# Step 3 — Payment backend
# Edit backend/.env first, then:
cd backend && sudo bash install-payments.sh

# Step 4 — Customer portal + nginx + SSL
cd portal && sudo bash install-portal.sh

# Step 5 — Monitoring + fail2ban
cd monitoring && sudo bash install-monitoring.sh
```

---

## Configuration: backend/.env

```env
LEMONSQUEEZY_WEBHOOK_SECRET=whsec_...  # from LS dashboard → Settings → Webhooks
NOWPAYMENTS_API_KEY=...                # from NOWPayments dashboard → API Keys
NOWPAYMENTS_IPN_SECRET=...            # from NOWPayments → Store Settings → IPN
ADMIN_TOKEN=change-me-strong-password  # for the admin API
VPN_SERVER_ADDR=vpn.yourdomain.com     # your domain
MAX_USERS=80

EMAIL_PROVIDER=smtp
FROM_EMAIL=noreply@yourdomain.com
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=you@gmail.com
SMTP_PASS=your-app-password

TELEGRAM_BOT_TOKEN=               # optional: alert bot
TELEGRAM_CHAT_ID=                 # optional: your chat ID
ALERT_EMAIL=admin@yourdomain.com  # email for server alerts
```

---

## Multi-server setup

Edit `backend/servers.json` with your server IPs:

```json
[
  { "id": "nl-01", "host": "1.2.3.4",   "region": "nl", "country": "Netherlands", ... },
  { "id": "us-01", "host": "5.6.7.8",   "region": "us", "country": "United States", ... },
  { "id": "ca-01", "host": "9.10.11.12","region": "ca", "country": "Canada", ... },
  { "id": "sg-01", "host": "13.14.15.16","region":"sg", "country": "Singapore", ... }
]
```

Run `install.sh` on each server. The provisioner will auto-select the server with the most available capacity for each new subscriber.

---

## Webhooks (register after deploy)

**Lemon Squeezy** → Settings → Webhooks → Add endpoint:
```
URL:    https://YOUR_DOMAIN/webhook/lemonsqueezy
Events: order_created, subscription_created, subscription_payment_success,
        subscription_cancelled, subscription_expired
```

**NOWPayments** → Store Settings → IPN Settings:
```
Callback URL: https://YOUR_DOMAIN/webhook/nowpayments
```

---

## Live URLs (after deploy)

| URL | Purpose |
|-----|---------|
| `https://YOUR_DOMAIN/` | Landing page |
| `https://YOUR_DOMAIN/pricing` | Pricing + checkout |
| `https://YOUR_DOMAIN/login` | Customer sign in |
| `https://YOUR_DOMAIN/dashboard` | Customer dashboard |
| `https://YOUR_DOMAIN:9090` | Cockpit (server management) |
| `http://127.0.0.1:8765` | Admin API (local only) |

---

## Useful commands

```bash
# VPN
ipsec status                            # active tunnels
ipsec statusall                         # full detail
bash server/adduser.sh alice            # add user
bash server/deluser.sh alice            # remove user
bash server/listusers.sh                # list all users

# Services
systemctl status strongswan-starter
systemctl status turnip-payments
systemctl status turnip-portal
systemctl status turnip-monitor

# Logs
tail -f /var/log/charon.log             # VPN connections
tail -f /var/log/turnip-payments.log
tail -f /var/log/turnip-portal.log
tail -f /var/log/turnip-monitor.log

# Security
fail2ban-client status ike-auth         # blocked IPs
fail2ban-client status sshd
fail2ban-client banned                  # all bans
fail2ban-client set ike-auth unbanip X  # unban an IP
```

---

## What happens when someone pays

**Card payment (Lemon Squeezy):**
1. Customer visits `/pricing` → selects continent + plan → Lemon Squeezy checkout
2. Payment confirmed → Lemon Squeezy sends `order_created` webhook
3. `webhook.py` verifies HMAC-SHA256 signature
4. `provisioner.py` creates VPN credentials for the chosen region
5. `database.py` records the subscription
6. `emailer.py` sends welcome email with credentials + `.mobileconfig` attachment
7. Customer opens `.mobileconfig` → VPN active in one tap

**Crypto payment (NOWPayments):**
1. Customer selects crypto → invoice created via NOWPayments API
2. Customer pays USDT/USDC on NOWPayments hosted page
3. NOWPayments fires IPN callback to `/webhook/nowpayments`
4. `webhook.py` verifies HMAC-SHA512 signature → same provisioning flow

Total time from payment to connected: **under 60 seconds.**

---

Built with: StrongSwan · Flask · SQLite · Lemon Squeezy · NOWPayments · Gunicorn · Nginx · fail2ban · Cockpit
