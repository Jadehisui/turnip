import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Check, CreditCard, Wallet, MapPin, Globe } from 'lucide-react';

const Pricing = () => {
    const [country, setCountry] = useState(null);
    const [servers, setServers] = useState([]);
    const [region, setRegion] = useState('eu');

    useEffect(() => {
        fetch('/api/geo')
            .then(r => r.json())
            .then(d => setCountry(d.country))
            .catch(() => setCountry('NG'));

        fetch('/api/servers')
            .then(r => r.json())
            .then(d => setServers(d.servers || []))
            .catch(() => {});
    }, []);

    const isNG = !country || country === 'NG';

    // Continent metadata for display
    const CONTINENT_META = {
        eu: { name: 'Europe',        flag: '🌍' },
        na: { name: 'North America', flag: '🌎' },
        as: { name: 'Asia',          flag: '🌏' },
    };

    // Derive available continents from active servers (deduplicated)
    const availableContinents = [
        ...new Map(
            servers
                .filter(s => s.continent && CONTINENT_META[s.continent])
                .map(s => [s.continent, { continent: s.continent, ...CONTINENT_META[s.continent] }])
        ).values()
    ];

    // Auto-select first available continent if current choice isn't available
    useEffect(() => {
        if (availableContinents.length > 0 && !availableContinents.find(c => c.continent === region)) {
            setRegion(availableContinents[0].continent);
        }
    }, [servers]); // eslint-disable-line react-hooks/exhaustive-deps

    const plans = [
        {
            name: 'Basic',
            price: isNG ? '4,999' : '4.99',
            amount_ngn: isNG ? 4999 : 7984,
            currency: isNG ? '₦' : '$',
            devices: 1,
            period: '1 device · 30 days',
            features: ['1 device', 'AES-256 encryption', '2 server regions', 'Zero traffic logs', 'Email support'],
            featured: false
        },
        {
            name: 'Pro',
            price: isNG ? '7,999' : '7.99',
            amount_ngn: isNG ? 7999 : 12784,
            currency: isNG ? '₦' : '$',
            devices: 5,
            period: '5 devices · 30 days',
            features: ['5 devices', 'AES-256 encryption', 'All 4 server regions', 'Zero traffic logs', 'Priority support', 'Custom VPN profiles'],
            featured: true
        },
        {
            name: 'Business',
            price: isNG ? '19,999' : '19.99',
            amount_ngn: isNG ? 19999 : 31984,
            currency: isNG ? '₦' : '$',
            devices: 10,
            period: 'Up to 10 devices · 30 days',
            features: ['Up to 10 devices', 'AES-256 encryption', 'All 4 server regions', 'Zero traffic logs', 'Dedicated support', 'Multi-server sync'],
            featured: false
        }
    ];

    const handleCardPayment = async (plan) => {
        const email = prompt('Enter your email for your VPN account credentials:');
        if (!email || !email.includes('@')) return alert('Please enter a valid email.');

        try {
            const res = await fetch('/api/pay/public/initiate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    email: email,
                    amount_ngn: plan.amount_ngn,
                    plan_code: plan.name.toLowerCase(),
                    region: region
                })
            });
            const data = await res.json();
            if (data.payment_url) {
                window.location.href = data.payment_url;
            } else {
                alert(data.error || 'Failed to initiate payment.');
            }
        } catch (err) {
            console.error(err);
            alert('Connection error. Please try again.');
        }
    };

    const handleCryptoPayment = async (plan) => {
        const email = prompt('Enter your email to receive VPN credentials after payment:');
        if (!email || !email.includes('@')) return alert('Please enter a valid email.');

        try {
            const res = await fetch('/api/pay/crypto/initiate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    email: email,
                    amount_ngn: plan.amount_ngn,
                    plan_code: plan.name.toLowerCase(),
                    region: region
                })
            });
            const data = await res.json();
            if (data.payment_url) {
                window.location.href = data.payment_url;
            } else {
                alert(data.error || 'Failed to create crypto invoice.');
            }
        } catch (err) {
            console.error(err);
            alert('Connection error. Please try again.');
        }
    };

    return (
        <section className="section pricing-page">
            <div className="container" style={{ textAlign: 'center' }}>
                <div className="section-tag" style={{ display: 'inline-block' }}>// pricing</div>
                <h2 className="section-title">Simple, transparent plans.</h2>
                <p className="section-sub" style={{ margin: '0 auto 1.5rem' }}>Pay for access. No data harvesting, no upsells, no nonsense.</p>

                {country && (
                    <div className="geo-badge">
                        <MapPin size={13} />
                        {isNG ? '🇳🇬 Nigerian pricing (₦)' : '🌍 International pricing ($)'}
                    </div>
                )}

                {availableContinents.length > 0 && (
                    <div className="region-picker">
                        <div className="region-label"><Globe size={14} /> Choose server region</div>
                        <div className="region-options">
                            {availableContinents.map(c => (
                                <button
                                    key={c.continent}
                                    className={`region-btn ${region === c.continent ? 'active' : ''}`}
                                    onClick={() => setRegion(c.continent)}
                                >
                                    {c.flag} {c.name}
                                </button>
                            ))}
                        </div>
                    </div>
                )}

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
                            <div className="price-amount">{plan.currency}{plan.price}<span>/mo</span></div>
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
                    <p>Card payments via Lemon Squeezy · Crypto via NOWPayments · Instant activation</p>
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
        
        .geo-badge { display: inline-flex; align-items: center; gap: 6px; background: var(--bg2); border: 1px solid var(--border); border-radius: 100px; padding: 5px 14px; font-size: 12px; color: var(--text2); margin-bottom: 1rem; font-family: var(--mono); }
        .region-picker { margin: 0 auto 2.5rem; max-width: 700px; }
        .region-label { display: flex; align-items: center; justify-content: center; gap: 6px; font-size: 12px; color: var(--text3); text-transform: uppercase; letter-spacing: .08em; font-weight: 700; margin-bottom: 0.75rem; }
        .region-options { display: flex; flex-wrap: wrap; justify-content: center; gap: 10px; }
        .region-btn { background: var(--bg2); border: 1px solid var(--border); border-radius: 100px; padding: 7px 18px; font-size: 13px; color: var(--text2); cursor: pointer; transition: all 0.2s; font-family: var(--sans); }
        .region-btn:hover { border-color: var(--accent); color: var(--text); }
        .region-btn.active { background: rgba(0,200,150,0.1); border-color: var(--accent); color: var(--accent); font-weight: 700; }
        @media (max-width: 900px) { .pricing-grid { grid-template-columns: 1fr; max-width: 400px; } }
      `}</style>
        </section>
    );
};

export default Pricing;
