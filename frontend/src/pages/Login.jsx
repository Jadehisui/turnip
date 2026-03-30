import React, { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Mail, Shield, ArrowRight, Loader2, User, CheckCircle, Lock, Zap, Globe, KeyRound } from 'lucide-react';

const Login = () => {
    const [tab, setTab] = useState('signin');

    // sign-in state
    const [loginStep, setLoginStep] = useState('email'); // 'email' | 'otp'
    const [email, setEmail] = useState('');
    const [pendingEmail, setPendingEmail] = useState('');
    const [otpCode, setOtpCode] = useState('');
    const [otpError, setOtpError] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [loginError, setLoginError] = useState('');
    const otpInputRef = useRef(null);

    // sign-up state
    const [regName, setRegName] = useState('');
    const [regEmail, setRegEmail] = useState('');
    const [regLoading, setRegLoading] = useState(false);
    const [regError, setRegError] = useState('');
    const [regSuccess, setRegSuccess] = useState(false);

    const handleSignIn = async (e) => {
        e.preventDefault();
        setLoginError('');
        setIsLoading(true);
        try {
            const res = await fetch('/api/auth/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email }),
            });
            let data = {};
            try { data = await res.json(); } catch (_) {}
            if (res.ok && data.step === 'otp') {
                setPendingEmail(data.email || email);
                setOtpCode('');
                setOtpError('');
                setLoginStep('otp');
                setTimeout(() => otpInputRef.current?.focus(), 80);
            } else {
                setLoginError(data.error || 'Could not send login code. Please try again.');
            }
        } catch {
            setLoginError('Could not reach the server. Please try again.');
        } finally {
            setIsLoading(false);
        }
    };

    const handleVerifyOtp = async (e) => {
        e.preventDefault();
        setOtpError('');
        if (otpCode.length !== 6) {
            setOtpError('Enter the 6-digit code from your email.');
            return;
        }
        setIsLoading(true);
        try {
            const res = await fetch('/api/auth/verify-otp', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email: pendingEmail, code: otpCode }),
            });
            let data = {};
            try { data = await res.json(); } catch (_) {}
            if (res.ok && data.ok) {
                window.location.href = data.redirect || '/dashboard';
            } else {
                setOtpError(data.error || 'Invalid code. Please try again.');
            }
        } catch {
            setOtpError('Could not reach the server. Please try again.');
        } finally {
            setIsLoading(false);
        }
    };

    const handleRegister = async (e) => {
        e.preventDefault();
        setRegError('');
        setRegLoading(true);
        try {
            const res = await fetch('/api/auth/register', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: regName, email: regEmail }),
            });
            let data = {};
            try { data = await res.json(); } catch (_) {}

            // Existing account — switch to Sign In tab and pre-fill the email
            if (res.status === 409 && data.switch_to_signin) {
                setEmail(data.email || regEmail);
                setLoginStep('email');
                setLoginError('We found your account — enter your email below to get a sign-in code.');
                setTab('signin');
                return;
            }

            if (res.ok && data.ok) {
                setRegSuccess(true);
                setTimeout(() => {
                    window.location.href = data.redirect || '/pricing';
                }, 1800);
            } else {
                setRegError(data.error || 'Registration failed. Please try again.');
            }
        } catch {
            setRegError('Could not reach the server. Please try again.');
        } finally {
            setRegLoading(false);
        }
    };

    return (
        <div className="lp-wrap">
            {/* Left panel — branding */}
            <div className="lp-brand">
                <div className="brand-inner">
                    <div className="brand-logo">Turnip<span>VPN</span></div>
                    <p className="brand-tagline">Fast. Private. Unbreakable.</p>
                    <div className="feature-list">
                        {[
                            { icon: <Lock size={15} />, text: 'AES-256 encryption' },
                            { icon: <Globe size={15} />, text: 'Zero-log policy' },
                            { icon: <Zap size={15} />, text: 'Instant activation after payment' },
                            { icon: <Shield size={15} />, text: 'IKEv2/IPSec protocol' },
                        ].map((f, i) => (
                            <div key={i} className="feature-item">
                                <span className="feat-icon">{f.icon}</span>
                                <span>{f.text}</span>
                            </div>
                        ))}
                    </div>
                </div>
            </div>

            {/* Right panel — form */}
            <div className="lp-form-side">
                <motion.div
                    className="lp-card"
                    initial={{ opacity: 0, y: 24 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.4 }}
                >
                    {/* Tabs */}
                    <div className="tab-row">
                        <button className={`tab-btn ${tab === 'signin' ? 'active' : ''}`} onClick={() => { setTab('signin'); setLoginError(''); }}>Sign In</button>
                        <button className={`tab-btn ${tab === 'create' ? 'active' : ''}`} onClick={() => { setTab('create'); setRegError(''); setRegSuccess(false); }}>Create Account</button>
                    </div>

                    <AnimatePresence mode="wait">
                        {tab === 'signin' ? (
                            <motion.div key="signin" initial={{ opacity: 0, x: -12 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 12 }} transition={{ duration: 0.2 }}>
                                <AnimatePresence mode="wait">
                                {loginStep === 'email' ? (
                                    <motion.div key="email-step" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.18 }}>
                                        <p className="form-hint">Enter the email address linked to your plan.</p>
                                        <form onSubmit={handleSignIn}>
                                            <label className="field-label">Email address</label>
                                            <div className="input-wrap">
                                                <Mail className="inp-icon" size={16} />
                                                <input
                                                    type="email"
                                                    placeholder="you@example.com"
                                                    value={email}
                                                    onChange={e => setEmail(e.target.value)}
                                                    required
                                                    autoComplete="email"
                                                />
                                            </div>
                                            {loginError && <div className="msg-error">{loginError}</div>}
                                            <button className="btn-submit" disabled={isLoading}>
                                                {isLoading
                                                    ? <><Loader2 className="spin" size={16} /> Sending code…</>
                                                    : <>Continue <ArrowRight size={16} /></>}
                                            </button>
                                        </form>
                                        <div className="form-footer">
                                            Don&apos;t have an account?{' '}
                                            <button className="link-btn" onClick={() => setTab('create')}>Create one →</button>
                                        </div>
                                    </motion.div>
                                ) : (
                                    <motion.div key="otp-step" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.18 }}>
                                        <p className="form-hint">
                                            We sent a 6-digit code to <strong style={{color:'var(--text)'}}>{pendingEmail}</strong>. Enter it below.
                                        </p>
                                        <form onSubmit={handleVerifyOtp}>
                                            <label className="field-label">Login code</label>
                                            <div className="input-wrap">
                                                <KeyRound className="inp-icon" size={16} />
                                                <input
                                                    ref={otpInputRef}
                                                    type="text"
                                                    inputMode="numeric"
                                                    placeholder="000000"
                                                    maxLength={6}
                                                    value={otpCode}
                                                    onChange={e => setOtpCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                                                    required
                                                    autoComplete="one-time-code"
                                                    style={{letterSpacing:'6px', fontSize:'22px', textAlign:'center', paddingLeft:'14px'}}
                                                />
                                            </div>
                                            {otpError && <div className="msg-error">{otpError}</div>}
                                            <button className="btn-submit" disabled={isLoading || otpCode.length !== 6}>
                                                {isLoading
                                                    ? <><Loader2 className="spin" size={16} /> Verifying…</>
                                                    : <>Verify &amp; Sign In <ArrowRight size={16} /></>}
                                            </button>
                                        </form>
                                        <div className="form-footer">
                                            Wrong email?{' '}
                                            <button className="link-btn" onClick={() => { setLoginStep('email'); setOtpCode(''); setOtpError(''); setLoginError(''); }}>Go back ←</button>
                                        </div>
                                        <div className="form-footer" style={{marginTop:'0.5rem'}}>
                                            Didn&apos;t receive it?{' '}
                                            <button className="link-btn" onClick={async () => {
                                                setOtpError('');
                                                setIsLoading(true);
                                                try {
                                                    const res = await fetch('/api/auth/login', {
                                                        method: 'POST',
                                                        headers: { 'Content-Type': 'application/json' },
                                                        body: JSON.stringify({ email: pendingEmail }),
                                                    });
                                                    if (!res.ok) {
                                                        const d = await res.json().catch(() => ({}));
                                                        setOtpError(d.error || 'Could not resend.');
                                                    }
                                                } catch { setOtpError('Could not reach the server.'); }
                                                finally { setIsLoading(false); }
                                            }}>Resend code</button>
                                        </div>
                                    </motion.div>
                                )}
                                </AnimatePresence>
                            </motion.div>
                        ) : (
                            <motion.div key="register" initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -12 }} transition={{ duration: 0.2 }}>
                                {regSuccess ? (
                                    <motion.div className="success-state" initial={{ scale: 0.9, opacity: 0 }} animate={{ scale: 1, opacity: 1 }}>
                                        <CheckCircle size={44} className="success-icon" />
                                        <h3>Account created!</h3>
                                        <p>Taking you to pricing to choose your plan…</p>
                                    </motion.div>
                                ) : (
                                    <>
                                        <p className="form-hint">Create a free account, then pick a plan to activate your VPN.</p>
                                        <form onSubmit={handleRegister}>
                                            <label className="field-label">Full name</label>
                                            <div className="input-wrap">
                                                <User className="inp-icon" size={16} />
                                                <input
                                                    type="text"
                                                    placeholder="Jane Doe"
                                                    value={regName}
                                                    onChange={e => setRegName(e.target.value)}
                                                    required
                                                    minLength={2}
                                                    autoComplete="name"
                                                />
                                            </div>
                                            <label className="field-label">Email address</label>
                                            <div className="input-wrap">
                                                <Mail className="inp-icon" size={16} />
                                                <input
                                                    type="email"
                                                    placeholder="you@example.com"
                                                    value={regEmail}
                                                    onChange={e => setRegEmail(e.target.value)}
                                                    required
                                                    autoComplete="email"
                                                />
                                            </div>
                                            {regError && <div className="msg-error">{regError}</div>}
                                            <button className="btn-submit" disabled={regLoading}>
                                                {regLoading
                                                    ? <><Loader2 className="spin" size={16} /> Creating account…</>
                                                    : <>Create Account <ArrowRight size={16} /></>}
                                            </button>
                                        </form>
                                        <div className="form-footer">
                                            Already have an account?{' '}
                                            <button className="link-btn" onClick={() => setTab('signin')}>Sign in →</button>
                                        </div>
                                    </>
                                )}
                            </motion.div>
                        )}
                    </AnimatePresence>
                </motion.div>
            </div>

            <style jsx>{`
        /* Layout */
        .lp-wrap {
          display: flex; min-height: 100vh;
        }

        /* Left brand panel */
        .lp-brand {
          flex: 0 0 420px;
          background: linear-gradient(160deg, #031a10 0%, #042e1c 60%, #051f12 100%);
          border-right: 1px solid rgba(5,150,105,0.2);
          display: flex; align-items: center; justify-content: center;
          padding: 3rem;
        }
        .brand-inner { max-width: 300px; }
        .brand-logo {
          font-size: 32px; font-weight: 900; color: #f9fafb;
          letter-spacing: -1px; margin-bottom: 0.5rem;
        }
        .brand-logo span { color: #34d399; }
        .brand-tagline {
          color: #6b7280; font-size: 15px; margin-bottom: 2.5rem;
          font-style: italic;
        }
        .feature-list { display: flex; flex-direction: column; gap: 14px; }
        .feature-item {
          display: flex; align-items: center; gap: 12px;
          color: #d1d5db; font-size: 14px;
        }
        .feat-icon {
          width: 30px; height: 30px; border-radius: 8px;
          background: rgba(52,211,153,0.1); border: 1px solid rgba(52,211,153,0.2);
          display: flex; align-items: center; justify-content: center;
          color: #34d399; flex-shrink: 0;
        }

        /* Right form panel */
        .lp-form-side {
          flex: 1; display: flex; align-items: center;
          justify-content: center; padding: 2rem;
          background: var(--bg);
        }
        .lp-card {
          width: 100%; max-width: 420px;
          background: var(--bg2);
          border: 1px solid var(--border);
          border-radius: 20px;
          padding: 2.5rem;
          box-shadow: 0 32px 64px rgba(0,0,0,0.35);
        }

        /* Tabs */
        .tab-row {
          display: flex; background: var(--bg3);
          border-radius: 10px; padding: 4px;
          margin-bottom: 2rem; gap: 4px;
        }
        .tab-btn {
          flex: 1; padding: 10px 0; border: none; border-radius: 7px;
          background: transparent; color: var(--text2);
          font-size: 14px; font-weight: 600; cursor: pointer;
          transition: all 0.2s; font-family: var(--sans);
        }
        .tab-btn.active { background: #059669; color: #fff; }
        .tab-btn:not(.active):hover { background: var(--border); color: var(--text); }

        /* Form elements */
        .form-hint { color: var(--text2); font-size: 13.5px; line-height: 1.6; margin: 0 0 1.5rem; }
        .field-label {
          display: block; font-size: 11px; font-weight: 700;
          color: var(--text3); text-transform: uppercase;
          letter-spacing: .08em; margin-bottom: 6px; font-family: var(--mono);
        }
        .input-wrap { position: relative; margin-bottom: 1.25rem; }
        .inp-icon {
          position: absolute; left: 14px; top: 50%;
          transform: translateY(-50%); color: var(--text3);
        }
        input {
          width: 100%; background: var(--bg3);
          border: 1px solid var(--border); border-radius: 10px;
          padding: 13px 14px 13px 42px; color: var(--text);
          font-family: var(--sans); font-size: 15px;
          transition: border 0.2s, background 0.2s; box-sizing: border-box;
        }
        input:focus { outline: none; border-color: #059669; background: var(--surf, #0d1524); }
        input::placeholder { color: var(--text3); }

        /* Button */
        .btn-submit {
          width: 100%; background: #059669; color: #fff;
          border: none; border-radius: 10px;
          padding: 14px; font-family: var(--sans);
          font-size: 15px; font-weight: 700;
          cursor: pointer; display: flex;
          align-items: center; justify-content: center; gap: 8px;
          transition: background 0.2s, transform 0.1s;
          margin-top: 0.5rem;
        }
        .btn-submit:hover:not(:disabled) { background: #047857; transform: translateY(-1px); }
        .btn-submit:disabled { opacity: 0.6; cursor: not-allowed; }

        /* Messages */
        .msg-error {
          background: rgba(239,68,68,0.08);
          border: 1px solid rgba(239,68,68,0.25);
          border-radius: 8px; padding: 10px 14px;
          font-size: 13px; color: #f87171; margin-bottom: 1rem;
          line-height: 1.5;
        }

        /* Footer */
        .form-footer {
          margin-top: 1.5rem; text-align: center;
          font-size: 13px; color: var(--text3);
        }
        .link-btn {
          background: none; border: none; color: #34d399;
          font-weight: 700; cursor: pointer; font-size: 13px;
          font-family: var(--sans); padding: 0; margin-left: 3px;
          text-decoration: underline; text-decoration-color: transparent;
          transition: text-decoration-color 0.2s;
        }
        .link-btn:hover { text-decoration-color: #34d399; }

        /* Success state */
        .success-state {
          text-align: center; padding: 2rem 0;
        }
        .success-icon { color: #34d399; margin: 0 auto 1rem; display: block; }
        .success-state h3 { color: var(--text); font-size: 20px; margin: 0 0 0.5rem; }
        .success-state p { color: var(--text2); font-size: 14px; margin: 0; }

        /* Spinner */
        .spin { animation: spin 0.8s linear infinite; }
        @keyframes spin { to { transform: rotate(360deg); } }

        /* Mobile */
        @media (max-width: 768px) {
          .lp-wrap { flex-direction: column; }
          .lp-brand { flex: none; padding: 2rem; border-right: none; border-bottom: 1px solid rgba(5,150,105,0.2); }
          .brand-logo { font-size: 26px; }
          .brand-tagline { margin-bottom: 1.25rem; }
          .feature-list { flex-direction: row; flex-wrap: wrap; gap: 10px; }
          .lp-form-side { padding: 1.5rem 1rem; }
          .lp-card { padding: 1.75rem; }
        }
      `}</style>
        </div>
    );
};

export default Login;
