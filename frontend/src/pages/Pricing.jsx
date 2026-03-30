import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Check, CreditCard, Wallet, MapPin, Globe, Mail, X, Loader2 } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';

const Pricing = () => {
    const { user } = useAuth() || {};
    const [country, setCountry] = useState(null);
    const [servers, setServers] = useState([]);
    const [region, setRegion] = useState('eu');

    // Email modal state
    const [emailPrompt, setEmailPrompt] = useState(null); // { plan, type } or null
    const [emailValue, setEmailValue] = useState('');
    const [emailError, setEmailError] = useState('');
    const [paying, setPaying] = useState(false);

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

    const openEmailPrompt = (plan, type) => {
        // Logged-in users skip the modal — use session email
        if (user?.email) {
            initiatePayment(user.email, plan, type);
            return;
        }
        setEmailValue('');
        setEmailError('');
        setEmailPrompt({ plan, type });
    };

    const initiatePayment = async (email, plan, type) => {
        setPaying(true);
        setEmailError('');
        try {
            const endpoint = type === 'crypto'
                ? '/api/pay/crypto/initiate'
                : (user?.email ? '/api/pay/initiate' : '/api/pay/public/initiate');
            const res = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    email,
                    amount_ngn: plan.amount_ngn,
                    plan_code: plan.name.toLowerCase(),
                    region
                })
            });
            const data = await res.json();
            if (data.payment_url) {
                window.location.href = data.payment_url;
            } else {
                setEmailError(data.error || 'Failed to initiate payment.');
                setPaying(false);
            }
        } catch (err) {
            console.error(err);
            setEmailError('Connection error. Please try again.');
            setPaying(false);
        }
    };

    const submitEmailPrompt = async () => {
        const email = emailValue.trim();
        if (!email || !email.includes('@')) {
            setEmailError('Please enter a valid email address.');
            return;
        }
        const { plan, type } = emailPrompt;
        await initiatePayment(email, plan, type);
    };

    const handleCardPayment = (plan) => openEmailPrompt(plan, 'card');
    const handleCryptoPayment = (plan) => openEmailPrompt(plan, 'crypto');

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

            {/* Email capture modal for guest users */}
            <AnimatePresence>
                {emailPrompt && (
                    <motion.div
                        className="modal-overlay"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        onClick={() => !paying && setEmailPrompt(null)}
                    >
                        <motion.div
                            className="modal-box"
                            initial={{ scale: 0.92, opacity: 0 }}
                            animate={{ scale: 1, opacity: 1 }}
                            exit={{ scale: 0.92, opacity: 0 }}
                            transition={{ duration: 0.18 }}
                            onClick={e => e.stopPropagation()}
                        >
                            <button className="modal-close" onClick={() => setEmailPrompt(null)} disabled={paying}>
                                <X size={18} />
                            </button>
                            <div className="modal-title">
                                {emailPrompt.type === 'crypto' ? <Wallet size={20} /> : <CreditCard size={20} />}
                                {emailPrompt.plan.name} — {emailPrompt.plan.currency}{emailPrompt.plan.price}/mo
                            </div>
                            <p className="modal-hint">Enter your email to receive VPN credentials after payment.</p>
                            <div className="modal-input-wrap">
                                <Mail size={16} className="modal-inp-icon" />
                                <input
                                    type="email"
                                    placeholder="you@example.com"
                                    value={emailValue}
                                    onChange={e => setEmailValue(e.target.value)}
                                    onKeyDown={e => e.key === 'Enter' && submitEmailPrompt()}
                                    autoFocus
                                    disabled={paying}
                                />
                            </div>
                            {emailError && <div className="modal-error">{emailError}</div>}
                            <button className="modal-btn" onClick={submitEmailPrompt} disabled={paying}>
                                {paying
                                    ? <><Loader2 className="modal-spin" size={16} /> Redirecting…</>
                                    : <>Continue to Payment →</>}
                            </button>
                        </motion.div>
                    </motion.div>
                )}
            </AnimatePresence>

            <style jsx>{`
        .modal-overlay { position: fixed; inset: 0; background: rgba(2,2,5,0.8); backdrop-filter: blur(4px); display: flex; align-items: center; justify-content: center; z-index: 200; padding: 1rem; }
        .modal-box { background: var(--bg2); border: 1px solid var(--border); border-radius: 18px; padding: 2rem; max-width: 420px; width: 100%; position: relative; }
        .modal-close { position: absolute; top: 14px; right: 14px; background: var(--bg3); border: 1px solid var(--border); border-radius: 8px; width: 32px; height: 32px; display: flex; align-items: center; justify-content: center; color: var(--text2); cursor: pointer; transition: all 0.2s; }
        .modal-close:hover { color: var(--text); border-color: var(--accent); }
        .modal-title { display: flex; align-items: center; gap: 10px; font-size: 17px; font-weight: 800; color: var(--text); margin-bottom: 0.75rem; }
        .modal-hint { font-size: 13.5px; color: var(--text2); margin-bottom: 1.5rem; line-height: 1.5; }
        .modal-input-wrap { position: relative; margin-bottom: 1rem; }
        .modal-inp-icon { position: absolute; left: 14px; top: 50%; transform: translateY(-50%); color: var(--text3); }
        .modal-input-wrap input { width: 100%; background: var(--bg3); border: 1px solid var(--border); border-radius: 10px; padding: 13px 14px 13px 42px; color: var(--text); font-family: var(--sans); font-size: 15px; box-sizing: border-box; }
        .modal-input-wrap input:focus { outline: none; border-color: var(--accent); }
        .modal-input-wrap input::placeholder { color: var(--text3); }
        .modal-error { background: rgba(239,68,68,0.08); border: 1px solid rgba(239,68,68,0.25); border-radius: 8px; padding: 9px 13px; font-size: 13px; color: #f87171; margin-bottom: 1rem; }
        .modal-btn { width: 100%; background: var(--accent); color: #fff; border: none; border-radius: 10px; padding: 13px; font-family: var(--sans); font-size: 15px; font-weight: 700; cursor: pointer; display: flex; align-items: center; justify-content: center; gap: 8px; transition: background 0.2s; }
        .modal-btn:hover:not(:disabled) { background: var(--accent2); }
        .modal-btn:disabled { opacity: 0.6; cursor: not-allowed; }
        .modal-spin { animation: mspin 0.8s linear infinite; }
        @keyframes mspin { to { transform: rotate(360deg); } }
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
