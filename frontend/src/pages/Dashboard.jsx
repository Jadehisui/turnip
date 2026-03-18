import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
    User, Mail, Calendar, Hash, Key, ExternalLink,
    Download, RefreshCw, Wallet, ShieldCheck, AlertCircle, Copy, Check
} from 'lucide-react';
import { ethers } from 'ethers';

const Dashboard = () => {
    const [sub, setSub] = useState(null);
    const [copied, setCopied] = useState(null);
    const [isLinking, setIsLinking] = useState(false);

    // Mock data for initial design
    useEffect(() => {
        setSub({
            email: 'user@example.com',
            username: 'vpn_user_9921',
            password: '••••••••••••',
            status: 'active',
            plan_name: 'Pro',
            expires_at: '2025-04-14 10:00:00',
            wallet_address: null
        });
    }, []);

    const copyToClipboard = (text, id) => {
        navigator.clipboard.writeText(text);
        setCopied(id);
        setTimeout(() => setCopied(null), 2000);
    };

    const handleLinkWallet = async () => {
        if (!window.ethereum) return alert('Please install MetaMask');
        setIsLinking(true);
        try {
            const provider = new ethers.BrowserProvider(window.ethereum);
            await provider.send("eth_requestAccounts", []);
            const signer = provider.getSigner();
            const address = await signer.getAddress();

            const r1 = await fetch('/api/auth/nonce');
            const { nonce } = await r1.json();

            const domain = window.location.host;
            const origin = window.location.origin;
            const message = `${domain} wants you to sign in with your Ethereum account:\n${address}\n\nLink wallet to Turnip VPN account\n\nURI: ${origin}\nVersion: 1\nChain ID: 1\nNonce: ${nonce}\nIssued At: ${new Date().toISOString()}`;

            const signature = await signer.signMessage(message);

            const r2 = await fetch('/api/auth/wallet', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message, signature })
            });

            const d2 = await r2.json();
            if (d2.ok) {
                setSub({ ...sub, wallet_address: address });
            } else {
                alert(d2.error || 'Linking failed');
            }
        } catch (err) {
            console.error(err);
        } finally {
            setIsLinking(false);
        }
    };

    if (!sub) return <div className="loading">Loading...</div>;

    return (
        <div className="dashboard container">
            <motion.div
                className="dashboard-header"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
            >
                <div>
                    <h1>Your Dashboard</h1>
                    <p>Manage your VPN subscription and credentials.</p>
                </div>
                <div className={`status-badge ${sub.status}`}>
                    <div className="dot"></div> {sub.status.toUpperCase()}
                </div>
            </motion.div>

            <div className="dash-grid">
                <div className="dash-left">
                    {/* Subscription Info */}
                    <section className="dash-card">
                        <h3>Subscription Details</h3>
                        <div className="metrics-grid">
                            <div className="metric">
                                <span className="m-label"><Calendar size={14} /> Plan</span>
                                <span className="m-val">{sub.plan_name}</span>
                            </div>
                            <div className="metric">
                                <span className="m-label"><User size={14} /> Email</span>
                                <span className="m-val">{sub.email}</span>
                            </div>
                            <div className="metric">
                                <span className="m-label"><AlertCircle size={14} /> Expires</span>
                                <span className="m-val mono">{sub.expires_at.split(' ')[0]}</span>
                            </div>
                        </div>
                        {!sub.wallet_address && (
                            <div className="wallet-promo">
                                <div className="promo-text">
                                    <strong>Link your wallet</strong>
                                    <span>Enable one-tap login and crypto payments.</span>
                                </div>
                                <button className="btn btn-wallet-dash" onClick={handleLinkWallet} disabled={isLinking}>
                                    {isLinking ? 'Linking...' : <><Wallet size={16} /> Link Wallet</>}
                                </button>
                            </div>
                        )}
                        {sub.wallet_address && (
                            <div className="wallet-linked">
                                <ShieldCheck size={18} color="var(--accent)" />
                                <span>Linked: <span className="mono">{sub.wallet_address.substring(0, 6)}...{sub.wallet_address.substring(38)}</span></span>
                            </div>
                        )}
                    </section>

                    {/* Credentials */}
                    <section className="dash-card" style={{ marginTop: '20px' }}>
                        <h3>VPN Credentials</h3>
                        <div className="cred-item">
                            <div className="cred-lbl">IKEv2 Username</div>
                            <div className="cred-box">
                                <code className="mono">{sub.username}</code>
                                <button className="copy-btn" onClick={() => copyToClipboard(sub.username, 'user')}>
                                    {copied === 'user' ? <Check size={14} /> : <Copy size={14} />}
                                </button>
                            </div>
                        </div>
                        <div className="cred-item">
                            <div className="cred-lbl">IKEv2 Password</div>
                            <div className="cred-box">
                                <code className="mono">{sub.password}</code>
                                <button className="copy-btn" onClick={() => copyToClipboard('ACTUAL_PASSWORD_HERE', 'pass')}>
                                    {copied === 'pass' ? <Check size={14} /> : <Copy size={14} />}
                                </button>
                            </div>
                        </div>
                        <div className="cred-item">
                            <div className="cred-lbl">Server Address</div>
                            <div className="cred-box">
                                <code className="mono">vpn.securefast.net</code>
                                <button className="copy-btn" onClick={() => copyToClipboard('vpn.securefast.net', 'host')}>
                                    {copied === 'host' ? <Check size={14} /> : <Copy size={14} />}
                                </button>
                            </div>
                        </div>
                    </section>
                </div>

                <div className="dash-right">
                    {/* Quick Actions */}
                    <section className="dash-card">
                        <h3>Downloads</h3>
                        <p className="small-text">One-tap profiles for instant configuration.</p>
                        <div className="action-buttons">
                            <button className="btn btn-action">
                                <Download size={16} /> iOS Profile (.mobileconfig)
                            </button>
                            <button className="btn btn-action">
                                <Download size={16} /> macOS Profile (.mobileconfig)
                            </button>
                            <button className="btn btn-action">
                                <ShieldCheck size={16} /> Download CA Certificate
                            </button>
                        </div>
                    </section>

                    <section className="dash-card" style={{ marginTop: '20px' }}>
                        <h3>Account Settings</h3>
                        <div className="action-buttons">
                            <button className="btn btn-action-outline">
                                <RefreshCw size={16} /> Regenerate Password
                            </button>
                            <button className="btn btn-action-danger">
                                Terminate Subscription
                            </button>
                        </div>
                    </section>
                </div>
            </div>

            <style jsx>{`
        .dashboard { padding-top: 8rem; padding-bottom: 5rem; }
        .dashboard-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 3rem; }
        h1 { font-size: 32px; font-weight: 800; letter-spacing: -1px; }
        .dashboard-header p { color: var(--text2); }
        
        .status-badge { display: flex; align-items: center; gap: 8px; font-family: var(--mono); font-size: 11px; font-weight: 700; background: var(--bg2); border: 1px solid var(--border); padding: 6px 14px; border-radius: 100px; }
        .status-badge.active { color: var(--accent); border-color: var(--border2); }
        .status-badge .dot { width: 6px; height: 6px; border-radius: 50%; background: currentColor; }
        
        .dash-grid { display: grid; grid-template-columns: 1.5fr 1fr; gap: 24px; }
        .dash-card { background: var(--bg2); border: 1px solid var(--border); border-radius: 20px; padding: 2rem; box-shadow: 0 10px 30px rgba(0,0,0,0.2); }
        .dash-card h3 { font-size: 16px; font-weight: 700; margin-bottom: 1.5rem; color: var(--text); }
        
        .metrics-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin-bottom: 2rem; }
        .metric { display: flex; flex-direction: column; gap: 4px; }
        .m-label { font-size: 11px; color: var(--text3); display: flex; align-items: center; gap: 5px; text-transform: uppercase; font-weight: 700; }
        .m-val { font-size: 15px; font-weight: 600; color: var(--text); }
        
        .wallet-promo { background: var(--adim); border: 1px solid var(--border2); border-radius: 12px; padding: 1.25rem; display: flex; align-items: center; justify-content: space-between; gap: 15px; }
        .promo-text { display: flex; flex-direction: column; }
        .promo-text strong { font-size: 14px; color: var(--text); }
        .promo-text span { font-size: 12px; color: var(--text2); }
        .btn-wallet-dash { background: var(--blue); color: white; padding: 10px 18px; font-size: 13px; font-weight: 700; border-radius: 8px; border: none; cursor: pointer; display: flex; align-items: center; gap: 8px; transition: all 0.2s; }
        .btn-wallet-dash:hover { opacity: 0.9; transform: translateY(-1px); }
        .btn-wallet-dash:disabled { opacity: 0.5; cursor: not-allowed; }
        
        .wallet-linked { display: flex; align-items: center; gap: 10px; font-size: 13px; color: var(--accent); background: rgba(0,200,150,0.05); padding: 10px 14px; border-radius: 8px; border: 1px solid var(--border2); }

        .cred-item { margin-bottom: 1.25rem; }
        .cred-lbl { font-size: 12px; color: var(--text3); margin-bottom: 6px; font-weight: 600; }
        .cred-box { background: var(--bg3); border: 1px solid var(--border); border-radius: 10px; padding: 10px 14px; display: flex; align-items: center; justify-content: space-between; }
        code { color: var(--text2); font-size: 14px; }
        .copy-btn { background: none; border: none; color: var(--text3); cursor: pointer; transition: color 0.2s; }
        .copy-btn:hover { color: var(--accent); }

        .small-text { font-size: 13px; color: var(--text2); margin-top: -1rem; margin-bottom: 1.5rem; }
        .action-buttons { display: flex; flex-direction: column; gap: 10px; }
        .btn-action { background: var(--bg3); border: 1px solid var(--border); color: var(--text2); padding: 12px; font-size: 13px; font-weight: 600; text-align: left; display: flex; align-items: center; gap: 10px; border-radius: 10px; transition: all 0.2s; }
        .btn-action:hover { border-color: var(--accent); color: var(--text); background: var(--surf); }
        .btn-action-outline { background: transparent; border: 1px solid var(--border); color: var(--text2); padding: 12px; font-size: 13px; font-weight: 600; border-radius: 10px; display: flex; align-items: center; justify-content: center; gap: 8px; cursor: pointer; }
        .btn-action-outline:hover { border-color: var(--blue); color: var(--blue); }
        .btn-action-danger { background: rgba(255, 71, 87, 0.05); border: 1px solid rgba(255, 71, 87, 0.2); color: var(--red); padding: 12px; font-size: 13px; font-weight: 700; border-radius: 10px; cursor: pointer; }
        .btn-action-danger:hover { background: rgba(255, 71, 87, 0.1); border-color: var(--red); }

        @media (max-width: 900px) { .dash-grid { grid-template-columns: 1fr; } .metrics-grid { grid-template-columns: 1fr; } }
      `}</style>
        </div>
    );
};

export default Dashboard;
