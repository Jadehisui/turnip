import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { Mail, Shield, ArrowRight, Loader2, User } from 'lucide-react';

const Login = () => {
    const [email, setEmail] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [tab, setTab] = useState('signin');

    // signup form state
    const [regName, setRegName] = useState('');
    const [regEmail, setRegEmail] = useState('');
    const [regLoading, setRegLoading] = useState(false);
    const [regMsg, setRegMsg] = useState('');

    const handleEmailLogin = async (e) => {
        e.preventDefault();
        setIsLoading(true);
        try {
            const res = await fetch('/api/auth/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email })
            });
            const data = await res.json();
            if (data.ok) {
                window.location.href = '/dashboard';
            } else {
                alert(data.error || 'No account found. Please purchase a plan first.');
            }
        } catch (err) {
            alert('Server error. Please try again later.');
        } finally {
            setIsLoading(false);
        }
    };

    const handleRegister = async (e) => {
        e.preventDefault();
        setRegLoading(true);
        setRegMsg('');
        try {
            const res = await fetch('/api/auth/register', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: regName, email: regEmail })
            });
            const data = await res.json();
            if (data.ok) {
                if (data.redirect === '/dashboard') {
                    window.location.href = '/dashboard';
                } else {
                    // registered — send to pricing to buy a plan
                    window.location.href = '/pricing';
                }
            } else {
                setRegMsg(data.error || 'Registration failed.');
            }
        } catch (err) {
            setRegMsg('Server error. Please try again.');
        } finally {
            setRegLoading(false);
        }
    };

    return (
        <div className="login-page">
            <div className="container">
                <motion.div
                    className="login-card"
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                >
                    <div className="login-header">
                        <div className="login-icon"><Shield size={24} color="var(--accent)" /></div>
                        <h2>Turnip VPN</h2>
                    </div>

                    <div className="tab-row">
                        <button className={`tab-btn ${tab === 'signin' ? 'active' : ''}`} onClick={() => setTab('signin')}>Sign In</button>
                        <button className={`tab-btn ${tab === 'create' ? 'active' : ''}`} onClick={() => setTab('create')}>Create Account</button>
                    </div>

                    {tab === 'signin' ? (
                        <>
                            <p className="tab-desc">Enter the email you used when purchasing your plan.</p>
                            <form onSubmit={handleEmailLogin}>
                                <div className="input-group">
                                    <Mail className="input-icon" size={18} />
                                    <input
                                        type="email"
                                        placeholder="you@example.com"
                                        value={email}
                                        onChange={(e) => setEmail(e.target.value)}
                                        required
                                    />
                                </div>
                                <button className="btn btn-primary btn-full" disabled={isLoading}>
                                    {isLoading ? <Loader2 className="animate-spin" size={18} /> : <>Sign In <ArrowRight size={18} /></>}
                                </button>
                            </form>
                            <div className="login-footer">
                                New here? <button className="link-btn" onClick={() => setTab('create')}>Create an account →</button>
                            </div>
                        </>
                    ) : (
                        <>
                            <p className="tab-desc">Register with your name and email. After signup you'll choose a plan to activate your VPN.</p>
                            <form onSubmit={handleRegister}>
                                <div className="input-group">
                                    <User className="input-icon" size={18} />
                                    <input
                                        type="text"
                                        placeholder="Full name"
                                        value={regName}
                                        onChange={(e) => setRegName(e.target.value)}
                                        required
                                        minLength={2}
                                    />
                                </div>
                                <div className="input-group">
                                    <Mail className="input-icon" size={18} />
                                    <input
                                        type="email"
                                        placeholder="your@email.com"
                                        value={regEmail}
                                        onChange={(e) => setRegEmail(e.target.value)}
                                        required
                                    />
                                </div>
                                {regMsg && <div className="reg-error">{regMsg}</div>}
                                <button className="btn btn-primary btn-full" disabled={regLoading}>
                                    {regLoading ? <Loader2 className="animate-spin" size={18} /> : <>Create Account <ArrowRight size={18} /></>}
                                </button>
                            </form>
                            <div className="login-footer">
                                Already have an account? <button className="link-btn" onClick={() => setTab('signin')}>Sign in →</button>
                            </div>
                        </>
                    )}
                </motion.div>
            </div>

            <style jsx>{`
        .login-page { min-height: 90vh; display: flex; align-items: center; padding: 4rem 0; }
        .login-card { background: var(--bg2); border: 1px solid var(--border); border-radius: 24px; padding: 3rem; max-width: 480px; margin: 0 auto; width: 100%; box-shadow: 0 40px 80px rgba(0,0,0,0.4); }
        .login-header { text-align: center; margin-bottom: 1.5rem; }
        .login-icon { width: 48px; height: 48px; background: var(--adim); border: 1px solid var(--border2); border-radius: 12px; display: flex; align-items: center; justify-content: center; margin: 0 auto 1rem; }
        h2 { font-size: 26px; font-weight: 800; color: var(--text); margin: 0; }
        .tab-row { display: flex; background: var(--bg3); border-radius: 10px; padding: 4px; margin-bottom: 1.5rem; gap: 4px; }
        .tab-btn { flex: 1; padding: 9px; border: none; border-radius: 7px; background: transparent; color: var(--text2); font-size: 14px; font-weight: 600; cursor: pointer; transition: all 0.2s; font-family: var(--sans); }
        .tab-btn.active { background: var(--accent); color: #050810; }
        .tab-desc { color: var(--text2); font-size: 14px; line-height: 1.6; margin-bottom: 1.5rem; }
        .input-group { position: relative; margin-bottom: 1.25rem; }
        .input-icon { position: absolute; left: 16px; top: 50%; transform: translateY(-50%); color: var(--text3); }
        input { width: 100%; background: var(--bg3); border: 1px solid var(--border); border-radius: 10px; padding: 14px 14px 14px 48px; color: var(--text); font-family: var(--sans); font-size: 15px; transition: all 0.2s; box-sizing: border-box; }
        input:focus { outline: none; border-color: var(--accent); background: var(--surf); }
        .btn-full { width: 100%; display: flex; justify-content: center; gap: 10px; padding: 14px; font-size: 15px; box-sizing: border-box; }
        .login-footer { margin-top: 1.5rem; text-align: center; font-size: 13px; color: var(--text3); }
        .link-btn { background: none; border: none; color: var(--accent); font-weight: 700; cursor: pointer; font-size: 13px; font-family: var(--sans); padding: 0; margin-left: 4px; }
        .reg-error { background: rgba(255,80,80,0.1); border: 1px solid rgba(255,80,80,0.3); border-radius: 8px; padding: 10px 14px; font-size: 13px; color: #ff6060; margin-bottom: 1rem; }
        .animate-spin { animation: spin 1s linear infinite; }
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
      `}</style>
        </div>
    );
};

export default Login;

const Login = () => {
    const [email, setEmail] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [tab, setTab] = useState('signin'); // 'signin' | 'create'

    const handleEmailLogin = async (e) => {
        e.preventDefault();
        setIsLoading(true);
        try {
            const res = await fetch('/api/auth/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email })
            });

            const data = await res.json();
            if (data.ok) {
                window.location.href = '/dashboard';
            } else {
                alert(data.error || 'No account found. Please purchase a plan first.');
            }
        } catch (err) {
            console.error(err);
            alert('Server error. Please try again later.');
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="login-page">
            <div className="container">
                <motion.div
                    className="login-card"
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                >
                    <div className="login-header">
                        <div className="login-icon"><Shield size={24} color="var(--accent)" /></div>
                        <h2>Turnip VPN</h2>
                    </div>

                    {/* Tab switcher */}
                    <div className="tab-row">
                        <button className={`tab-btn ${tab === 'signin' ? 'active' : ''}`} onClick={() => setTab('signin')}>Sign In</button>
                        <button className={`tab-btn ${tab === 'create' ? 'active' : ''}`} onClick={() => setTab('create')}>Create Account</button>
                    </div>

                    {tab === 'signin' ? (
                        <>
                            <p className="tab-desc">Enter the email you used when purchasing your plan.</p>
                            <form onSubmit={handleEmailLogin}>
                                <div className="input-group">
                                    <Mail className="input-icon" size={18} />
                                    <input
                                        type="email"
                                        placeholder="you@example.com"
                                        value={email}
                                        onChange={(e) => setEmail(e.target.value)}
                                        required
                                    />
                                </div>
                                <button className="btn btn-primary btn-full" disabled={isLoading}>
                                    {isLoading ? <Loader2 className="animate-spin" size={18} /> : <>Sign In <ArrowRight size={18} /></>}
                                </button>
                            </form>
                            <div className="login-footer">
                                New here? <button className="link-btn" onClick={() => setTab('create')}>Create an account →</button>
                            </div>
                        </>
                    ) : (
                        <>
                            <p className="tab-desc">No signup form needed. Your account is created instantly the moment your payment is confirmed.</p>
                            <div className="steps">
                                <div className="step"><div className="step-num">1</div><div><strong>Choose a plan</strong><br /><span>Pick Basic, Pro, or Business below</span></div></div>
                                <div className="step"><div className="step-num">2</div><div><strong>Pay with card or crypto</strong><br /><span>Lemon Squeezy or NOWPayments</span></div></div>
                                <div className="step"><div className="step-num">3</div><div><strong>Receive credentials by email</strong><br /><span>VPN username &amp; password delivered instantly</span></div></div>
                                <div className="step"><div className="step-num">4</div><div><strong>Sign in here</strong><br /><span>Use the email you paid with</span></div></div>
                            </div>
                            <a href="/pricing" className="btn btn-primary btn-full" style={{ display: 'flex', justifyContent: 'center', gap: 10, textDecoration: 'none' }}>
                                <Zap size={18} /> View Plans &amp; Get Started
                            </a>
                            <div className="trust-row">
                                <span><Lock size={12} /> AES-256</span>
                                <span><Globe size={12} /> Zero logs</span>
                                <span><Zap size={12} /> Instant activation</span>
                            </div>
                        </>
                    )}
                </motion.div>
            </div>

            <style jsx>{`
        .login-page { min-height: 90vh; display: flex; align-items: center; padding: 4rem 0; }
        .login-card { background: var(--bg2); border: 1px solid var(--border); border-radius: 24px; padding: 3rem; max-width: 480px; margin: 0 auto; width: 100%; box-shadow: 0 40px 80px rgba(0,0,0,0.4); }
        .login-header { text-align: center; margin-bottom: 1.5rem; }
        .login-icon { width: 48px; height: 48px; background: var(--adim); border: 1px solid var(--border2); border-radius: 12px; display: flex; align-items: center; justify-content: center; margin: 0 auto 1rem; }
        h2 { font-size: 26px; font-weight: 800; color: var(--text); margin: 0; }

        .tab-row { display: flex; background: var(--bg3); border-radius: 10px; padding: 4px; margin-bottom: 1.5rem; gap: 4px; }
        .tab-btn { flex: 1; padding: 9px; border: none; border-radius: 7px; background: transparent; color: var(--text2); font-size: 14px; font-weight: 600; cursor: pointer; transition: all 0.2s; font-family: var(--sans); }
        .tab-btn.active { background: var(--accent); color: #050810; }

        .tab-desc { color: var(--text2); font-size: 14px; line-height: 1.6; margin-bottom: 1.5rem; }

        .input-group { position: relative; margin-bottom: 1.25rem; }
        .input-icon { position: absolute; left: 16px; top: 50%; transform: translateY(-50%); color: var(--text3); }
        input { width: 100%; background: var(--bg3); border: 1px solid var(--border); border-radius: 10px; padding: 14px 14px 14px 48px; color: var(--text); font-family: var(--sans); font-size: 15px; transition: all 0.2s; box-sizing: border-box; }
        input:focus { outline: none; border-color: var(--accent); background: var(--surf); }

        .btn-full { width: 100%; display: flex; justify-content: center; gap: 10px; padding: 14px; font-size: 15px; box-sizing: border-box; }
        .login-footer { margin-top: 1.5rem; text-align: center; font-size: 13px; color: var(--text3); }
        .link-btn { background: none; border: none; color: var(--accent); font-weight: 700; cursor: pointer; font-size: 13px; font-family: var(--sans); padding: 0; margin-left: 4px; }

        .steps { display: flex; flex-direction: column; gap: 14px; margin-bottom: 1.75rem; }
        .step { display: flex; align-items: flex-start; gap: 14px; }
        .step-num { width: 28px; height: 28px; border-radius: 50%; background: rgba(0,200,150,0.15); border: 1px solid var(--accent); color: var(--accent); font-size: 12px; font-weight: 800; display: flex; align-items: center; justify-content: center; flex-shrink: 0; font-family: var(--mono); }
        .step strong { font-size: 14px; color: var(--text); }
        .step span { font-size: 12px; color: var(--text3); }

        .trust-row { display: flex; justify-content: center; gap: 20px; margin-top: 1.25rem; font-size: 12px; color: var(--text3); }
        .trust-row span { display: flex; align-items: center; gap: 5px; }

        .animate-spin { animation: spin 1s linear infinite; }
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
      `}</style>
        </div>
    );
};

export default Login;
