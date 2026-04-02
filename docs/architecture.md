# Turnip VPN — Architecture Flowchart

```mermaid
flowchart TD
    A([🌐 User visits turnipvpn.site]) --> B[Register with name & email]
    B --> C[Receives welcome email\nwith plan links]
    C --> D[Selects a plan on /pricing]

    D --> E{Payment method}
    E -->|Lemon Squeezy| F[Credit/Debit checkout\nvia Lemon Squeezy]
    E -->|Crypto| G[NOWPayments hosted\ncrypto invoice]

    F --> H[LS fires webhook\nPOST /webhook/lemonsqueezy\nport 8766]
    G --> I[NOWPayments IPN\nPOST /webhook/nowpayments\nport 8767]

    H --> J{Signature\nverified?}
    I --> J

    J -->|❌ Invalid| K([Rejected 401])
    J -->|✅ Valid| L{Duplicate\npayment?}

    L -->|Already processed| M([Ignored — idempotent])
    L -->|New payment| N[Resolve plan & region\nfrom webhook payload]

    N --> O[provision_user\nprovisioner.py]
    O --> P[Generate username\n+ password per device]
    P --> Q[Write to\n/etc/ipsec.secrets]
    Q --> R[Reload StrongSwan\nipsec secrets]
    R --> S[Generate .mobileconfig\nprofile per device]

    S --> T[record_payment\ndatabase.py]
    T --> T1[(SQLite DB\nsubscriptions\nsubscription_devices\npayments)]

    T --> U[send_welcome_email\nemailery.py via Resend]
    U --> V[📧 Email with all device\ncredentials + .mobileconfig\nattachments]

    V --> W([User connects to VPN\niOS · macOS · Windows · Android])

    subgraph Portal [Portal — port 8767]
        direction TB
        P1[Login via OTP email] --> P2[OTP stored in SQLite\nshared across workers]
        P2 --> P3[Session created]
        P3 --> P4[/dashboard — view\ncredentials and devices]
        P4 --> P5[Download .mobileconfig\nfor any device]
        P4 --> P6[Regenerate password\nupdates ipsec.secrets\n+ DB in sync]
    end

    subgraph Renewal [Subscription Renewal]
        direction TB
        R1[LS fires subscription_payment_success] --> R2[Deprovision old\nipsec.secrets entries]
        R2 --> R3[Re-provision with\nexisting server region]
        R3 --> R4[New credentials emailed]
    end

    subgraph Cancel [Cancellation / Expiry]
        direction TB
        C1[LS fires subscription_cancelled\nor subscription_expired] --> C2[Deprovision ALL devices\nfrom ipsec.secrets]
        C2 --> C3[subscription status → disabled]
    end

    W -.->|Returning user| Portal
    T1 -.->|Cron expire check| Cancel

    style A fill:#059669,color:#fff,stroke:none
    style W fill:#059669,color:#fff,stroke:none
    style K fill:#dc2626,color:#fff,stroke:none
    style M fill:#6b7280,color:#fff,stroke:none
    style T1 fill:#1e3a5f,color:#e2e8f0,stroke:#3b82f6
    style Portal fill:#0f172a,color:#e2e8f0,stroke:#6366f1
    style Renewal fill:#0f172a,color:#e2e8f0,stroke:#f59e0b
    style Cancel fill:#0f172a,color:#e2e8f0,stroke:#ef4444
```
