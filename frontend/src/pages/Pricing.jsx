import React from 'react';
import { motion } from 'framer-motion';
import { Check, CreditCard, Wallet } from 'lucide-react';

const Pricing = () => {
    const plans = [
        {
            name: 'Basic',
            price: '1,500',
            period: '1 device · 30 days',
            features: ['1 device', 'AES-256 encryption', '2 server regions', 'Zero traffic logs', 'Email support'],
            cta: 'Pay with Card',
            featured: false
        },
        {
            name: 'Pro',
            price: '4,000',
            period: '5 devices · 30 days',
            features: ['5 devices', 'AES-256 encryption', 'All 4 server regions', 'Zero traffic logs', 'Priority support', 'Custom VPN profiles'],
            cta: 'Pay with Card',
            featured: true
        },
        {
            name: 'Business',
            price: '10,000',
            period: 'Unlimited devices · 30 days',
            features: ['Unlimited devices', 'AES-256 encryption', 'All 4 server regions', 'Zero traffic logs', 'Dedicated support', 'Multi-server sync'],
            cta: 'Pay with Card',
            featured: false
        }
    ];

    const handleCardPayment = (plan) => {
        alert(`Initiating Paystack payment for ${plan.name} plan...`);
        // Logic for Paystack inline
    };

    const handleCryptoPayment = (plan) => {
        alert(`Crypto payment selected for ${plan.name} plan. SUI and EVM payment addresses will be generated in the next step.`);
    };

    return (
        <section className="section pricing-page">
            <div className="container" style={{ textAlign: 'center' }}>
                <div className="section-tag" style={{ display: 'inline-block' }}>// pricing</div>
                <h2 className="section-title">Simple, transparent plans.</h2>
                <p className="section-sub" style={{ margin: '0 auto 4rem' }}>Pay for access. No data harvesting, no upsells, no nonsense.</p>

                <div className="pricing-grid">
                    {plans.map((plan, i) => (
                        <motion.div
                            key={i}
                            className={`price-card ${plan.featured ? 'featured' : ''}`}
                            initial={{ opacity: 0, y: 20 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ delay: i * 0.1 }}
                            whileHover={{ y: -5 }}
                        >
                            {plan.featured && <div className="price-badge">Most Popular</div>}
                            <div className="price-name">{plan.name}</div>
                            <div className="price-amount">₦{plan.price}<span>/mo</span></div>
                            <div className="price-period">{plan.period}</div>

                            <div className="price-features">
                                {plan.features.map((f, j) => (
                                    <div className="pf" key={j}>
                                        <Check size={14} color="var(--accent)" /> {f}
                                    </div>
                                ))}
                            </div>

                            <div className="price-actions">
                                <button
                                    className={`btn price-cta ${plan.featured ? 'btn-primary' : 'btn-outline'}`}
                                    onClick={() => handleCardPayment(plan)}
                                >
                                    <CreditCard size={16} /> Pay with Card
                                </button>
                                <button
                                    className="btn btn-wallet-pricing"
                                    onClick={() => handleCryptoPayment(plan)}
                                >
                                    <Wallet size={16} /> Pay with Crypto
                                </button>
                            </div>
                        </motion.div>
                    ))}
                </div>

                <div className="pricing-info">
                    <p>Payments secured by Paystack · Instant activation · Cancel anytime</p>
                    <div className="accepted-crypto">
                        <span>Accepted Crypto: </span>
                        <span className="crypto-tag">SUI</span>
                        <span className="crypto-tag">USDT (EVM)</span>
                        <span className="crypto-tag">USDC (EVM)</span>
                    </div>
                </div>
            </div>

            <style jsx>{`
        .pricing-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; max-width: 1000px; margin: 0 auto; }
        .price-card { background: var(--bg2); border: 1px solid var(--border); border-radius: 18px; padding: 2.5rem; position: relative; transition: all 0.2s; display: flex; flex-direction: column; }
        .price-card.featured { border-color: var(--accent); background: var(--surf); box-shadow: 0 20px 40px rgba(0,200,150,0.1); }
        .price-badge { position: absolute; top: -12px; left: 50%; transform: translateX(-50%); background: var(--accent); color: #050810; font-size: 11px; font-weight: 800; padding: 5px 16px; border-radius: 100px; white-space: nowrap; font-family: var(--mono); text-transform: uppercase; }
        .price-name { font-size: 13px; font-weight: 700; color: var(--text2); letter-spacing: .08em; text-transform: uppercase; margin-bottom: 1rem; }
        .price-amount { font-size: 48px; font-weight: 800; letter-spacing: -2px; font-family: var(--mono); line-height: 1; color: var(--text); }
        .price-amount span { font-size: 16px; color: var(--text2); font-family: var(--sans); font-weight: 400; letter-spacing: 0; }
        .price-period { font-size: 13px; color: var(--text3); margin: 8px 0 2rem; font-family: var(--mono); }
        .price-features { display: flex; flex-direction: column; gap: 12px; margin-bottom: 2.5rem; flex: 1; text-align: left; }
        .pf { display: flex; align-items: center; gap: 10px; font-size: 14px; color: var(--text2); }
        .price-actions { display: flex; flex-direction: column; gap: 10px; }
        .price-cta { width: 100%; display: flex; justify-content: center; gap: 10px; }
        .btn-wallet-pricing { 
          width: 100%; display: flex; justify-content: center; gap: 10px; 
          background: rgba(79, 163, 224, 0.1); border: 1px solid rgba(79, 163, 224, 0.3); 
          color: var(--blue); padding: 12px; border-radius: 8px; font-weight: 700;
          font-size: 14px; transition: all 0.2s;
        }
        .btn-wallet-pricing:hover { background: rgba(79, 163, 224, 0.2); border-color: var(--blue); }
        .pricing-info { margin-top: 3rem; color: var(--text3); font-size: 13px; }
        .accepted-crypto { margin-top: 1rem; display: flex; align-items: center; justify-content: center; gap: 10px; }
        .crypto-tag { background: var(--bg3); border: 1px solid var(--border); padding: 4px 10px; border-radius: 6px; font-family: var(--mono); font-size: 11px; color: var(--text2); }
        
        @media (max-width: 900px) { .pricing-grid { grid-template-columns: 1fr; max-width: 400px; } }
      `}</style>
        </section>
    );
};

export default Pricing;
