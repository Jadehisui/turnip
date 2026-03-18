import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { Mail, Wallet, Shield, ArrowRight, Loader2 } from 'lucide-react';
import { ethers } from 'ethers';

const Login = () => {
    const [email, setEmail] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [isWalletLoading, setIsWalletLoading] = useState(false);

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
                alert(data.error || 'Login failed');
            }
        } catch (err) {
            console.error(err);
            alert('Server error. Please try again later.');
        } finally {
            setIsLoading(false);
        }
    };

    const handleWalletLogin = async () => {
        if (!window.ethereum) return alert('Please install MetaMask or another Web3 wallet');
        setIsWalletLoading(true);
        try {
            const provider = new ethers.BrowserProvider(window.ethereum);
            await provider.send("eth_requestAccounts", []);
            const signer = provider.getSigner();
            const address = await signer.getAddress();

            // Get nonce from backend
            const resNonce = await fetch('/api/auth/nonce');
            const { nonce } = await resNonce.json();

            const domain = window.location.host;
            const origin = window.location.origin;
            const statement = 'Sign in with Ethereum to Turnip VPN';
            const message = `${domain} wants you to sign in with your Ethereum account:\n${address}\n\n${statement}\n\nURI: ${origin}\nVersion: 1\nChain ID: 1\nNonce: ${nonce}\nIssued At: ${new Date().toISOString()}`;

            const signature = await signer.signMessage(message);

            const resAuth = await fetch('/api/auth/wallet', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message, signature })
            });

            const data = await resAuth.json();
            if (data.ok) {
                window.location.href = '/dashboard';
            } else {
                alert(data.error || 'Login failed');
            }
        } catch (err) {
            console.error(err);
            alert(err.message || 'Connection failed');
        } finally {
            setIsWalletLoading(false);
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
                        <h2>Welcome back</h2>
                        <p>Enter your email or connect your wallet to access your VPN dashboard.</p>
                    </div>

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
                            {isLoading ? <Loader2 className="animate-spin" size={18} /> : <>Continue <ArrowRight size={18} /></>}
                        </button>
                    </form>

                    <div className="divider">
                        <div className="line"></div>
                        <span>Or</span>
                        <div className="line"></div>
                    </div>

                    <button className="btn btn-wallet-login btn-full" onClick={handleWalletLogin} disabled={isWalletLoading}>
                        {isWalletLoading ? <Loader2 className="animate-spin" size={18} /> : <><Wallet size={18} /> Connect Wallet</>}
                    </button>

                    <div className="login-footer">
                        No account yet? <a href="/pricing">View plans →</a>
                    </div>
                </motion.div>
            </div>

            <style jsx>{`
        .login-page { min-height: 90vh; display: flex; align-items: center; padding: 4rem 0; }
        .login-card { background: var(--bg2); border: 1px solid var(--border); border-radius: 24px; padding: 3.5rem; max-width: 480px; margin: 0 auto; width: 100%; box-shadow: 0 40px 80px rgba(0,0,0,0.4); }
        .login-header { text-align: center; margin-bottom: 2.5rem; }
        .login-icon { width: 48px; height: 48px; background: var(--adim); border: 1px solid var(--border2); border-radius: 12px; display: flex; align-items: center; justify-content: center; margin: 0 auto 1.5rem; }
        h2 { font-size: 28px; font-weight: 800; margin-bottom: 0.75rem; color: var(--text); }
        p { color: var(--text2); font-size: 14px; line-height: 1.6; }
        
        .input-group { position: relative; margin-bottom: 1.25rem; }
        .input-icon { position: absolute; left: 16px; top: 50%; transform: translateY(-50%); color: var(--text3); }
        input { width: 100%; background: var(--bg3); border: 1px solid var(--border); border-radius: 10px; padding: 14px 14px 14px 48px; color: var(--text); font-family: var(--sans); font-size: 15px; transition: all 0.2s; }
        input:focus { outline: none; border-color: var(--accent); background: var(--surf); }
        
        .btn-full { width: 100%; display: flex; justify-content: center; gap: 10px; padding: 14px; font-size: 15px; }
        .divider { display: flex; align-items: center; gap: 15px; margin: 2rem 0; color: var(--text3); font-size: 11px; text-transform: uppercase; letter-spacing: 1px; }
        .line { flex: 1; height: 1px; background: var(--border); }
        
        .btn-wallet-login { background: rgba(79, 163, 224, 0.1); border: 1px solid rgba(79, 163, 224, 0.3); color: var(--blue); }
        .btn-wallet-login:hover { background: rgba(79, 163, 224, 0.2); border-color: var(--blue); }
        
        .login-footer { margin-top: 2rem; text-align: center; font-size: 13px; color: var(--text3); }
        .login-footer a { color: var(--accent); font-weight: 700; margin-left: 5px; }

        .animate-spin { animation: spin 1s linear infinite; }
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
      `}</style>
        </div>
    );
};

export default Login;
