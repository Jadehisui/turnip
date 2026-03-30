import React, { useState, useEffect, useRef } from 'react';
import { motion } from 'framer-motion';
import {
    User, Mail, Calendar, Hash, Key, ExternalLink,
    Download, RefreshCw, ShieldCheck, AlertCircle, Copy, Check, Loader2
} from 'lucide-react';

const Dashboard = () => {
    const [sub, setSub] = useState(null);
    const [copied, setCopied] = useState(null);
    const [regenPass, setRegenPass] = useState(null);
    const [regenLoading, setRegenLoading] = useState(false);
    const [regenError, setRegenError] = useState('');
    const [terminateConfirm, setTerminateConfirm] = useState(false);
    const [terminateLoading, setTerminateLoading] = useState(false);
    const redirecting = useRef(false);

    const redirectToLogin = () => {
        if (redirecting.current) return;
        redirecting.current = true;
        window.location.href = '/login';
    };

    useEffect(() => {
        const fetchStatus = async () => {
            try {
                const res = await fetch('/api/user/status');
                if (res.status === 401) {
                    redirectToLogin();
                    return;
                }
                const data = await res.json();
                if (data.email) {
                    setSub(data);
                } else {
                    redirectToLogin();
                }
            } catch (err) {
                console.error('Failed to fetch user status:', err);
                redirectToLogin();
            }
        };
        fetchStatus();
    }, []); // eslint-disable-line react-hooks/exhaustive-deps

    const copyToClipboard = (text, id) => {
        navigator.clipboard.writeText(text);
        setCopied(id);
        setTimeout(() => setCopied(null), 2000);
    };

    const handleRegen = async () => {
        setRegenLoading(true);
        setRegenError('');
        setRegenPass(null);
        try {
            const res = await fetch('/api/regenerate', { method: 'POST' });
            const data = await res.json();
            if (res.ok && data.ok) {
                setRegenPass(data.password);
                setSub(prev => ({ ...prev, password: data.password }));
            } else {
                setRegenError(data.error || 'Failed to regenerate password.');
            }
        } catch {
            setRegenError('Could not reach the server.');
        } finally {
            setRegenLoading(false);
        }
    };

    const handleTerminate = async () => {
        setTerminateLoading(true);
        try {
            const res = await fetch('/api/terminate', { method: 'POST' });
            if (res.ok) {
                window.location.href = '/login';
            }
        } catch { /* ignore */ } finally {
            setTerminateLoading(false);
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

                    </section>

                    {/* Credentials */}
                    <section className="dash-card" style={{ marginTop: '20px' }}>
                        <h3>VPN Credentials</h3>
                        <p className="small-text" style={{ marginTop: '-1rem', marginBottom: '1.5rem' }}>
                            Each device gets its own unique profile. Download and install on each device separately.
                        </p>
                        {(sub.devices || [{ device_number: 1, username: sub.username, password: sub.password }]).map(dev => (
                            <div key={dev.device_number} className="device-block">
                                <div className="device-block-header">Device {dev.device_number}</div>
                                <div className="cred-item">
                                    <div className="cred-lbl">IKEv2 Username</div>
                                    <div className="cred-box">
                                        <code className="mono">{dev.username}</code>
                                        <button className="copy-btn" onClick={() => copyToClipboard(dev.username, `user_${dev.device_number}`)}>
                                            {copied === `user_${dev.device_number}` ? <Check size={14} /> : <Copy size={14} />}
                                        </button>
                                    </div>
                                </div>
                                <div className="cred-item">
                                    <div className="cred-lbl">IKEv2 Password</div>
                                    <div className="cred-box">
                                        <code className="mono">{dev.password}</code>
                                        <button className="copy-btn" onClick={() => copyToClipboard(dev.password, `pass_${dev.device_number}`)}>
                                            {copied === `pass_${dev.device_number}` ? <Check size={14} /> : <Copy size={14} />}
                                        </button>
                                    </div>
                                </div>
                                <a
                                    href={`/download/profile?device=${dev.device_number}`}
                                    className="btn btn-action"
                                    style={{ display: 'flex', alignItems: 'center', gap: 8, textDecoration: 'none', marginTop: 8 }}
                                >
                                    <Download size={14} /> Download Profile — Device {dev.device_number}
                                </a>
                            </div>
                        ))}
                    </section>
                </div>

                <div className="dash-right">
                    {/* Downloads */}
                    <section className="dash-card">
                        <h3>Downloads</h3>
                        <p className="small-text">Install CA certificate once to trust all Turnip VPN profiles.</p>
                        <div className="action-buttons">
                            <a
                                href="/download/ca"
                                className="btn btn-action"
                                style={{ display: 'flex', alignItems: 'center', gap: 8, textDecoration: 'none' }}
                            >
                                <ShieldCheck size={16} /> Download CA Certificate
                            </a>
                        </div>
                    </section>

                    <section className="dash-card" style={{ marginTop: '20px' }}>
                        <h3>Account Settings</h3>
                        <div className="action-buttons">
                            <button className="btn btn-action-outline" onClick={handleRegen} disabled={regenLoading}>
                                {regenLoading
                                    ? <><Loader2 className="spin" size={15} style={{ animation: 'spin 0.8s linear infinite' }} /> Regenerating…</>
                                    : <><RefreshCw size={16} /> Regenerate Password</>}
                            </button>
                            {regenPass && (
                                <div style={{ background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 10, padding: '10px 14px' }}>
                                    <div style={{ fontSize: 11, color: 'var(--text3)', marginBottom: 4 }}>New password (update your VPN client):</div>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                        <code className="mono" style={{ color: 'var(--accent)', flex: 1, fontSize: 13 }}>{regenPass}</code>
                                        <button className="copy-btn" onClick={() => copyToClipboard(regenPass, 'regen_pass')}>
                                            {copied === 'regen_pass' ? <Check size={14} /> : <Copy size={14} />}
                                        </button>
                                    </div>
                                </div>
                            )}
                            {regenError && <div style={{ fontSize: 12, color: 'var(--red)' }}>{regenError}</div>}
                            {!terminateConfirm ? (
                                <button className="btn btn-action-danger" onClick={() => setTerminateConfirm(true)}>
                                    Terminate Subscription
                                </button>
                            ) : (
                                <div style={{ background: 'rgba(255,71,87,0.06)', border: '1px solid rgba(255,71,87,0.25)', borderRadius: 10, padding: '14px' }}>
                                    <div style={{ fontSize: 13, color: 'var(--red)', fontWeight: 600, marginBottom: 10 }}>
                                        This will disable your account immediately. Continue?
                                    </div>
                                    <div style={{ display: 'flex', gap: 8 }}>
                                        <button
                                            className="btn btn-action-danger"
                                            style={{ flex: 1, justifyContent: 'center' }}
                                            onClick={handleTerminate}
                                            disabled={terminateLoading}
                                        >
                                            {terminateLoading ? 'Processing…' : 'Yes, terminate'}
                                        </button>
                                        <button
                                            className="btn btn-action"
                                            style={{ flex: 1, justifyContent: 'center' }}
                                            onClick={() => setTerminateConfirm(false)}
                                        >
                                            Cancel
                                        </button>
                                    </div>
                                </div>
                            )}
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
        
        .device-block { background: var(--bg3); border: 1px solid var(--border); border-radius: 14px; padding: 1.25rem; margin-bottom: 1rem; }
        .device-block:last-child { margin-bottom: 0; }
        .device-block-header { font-size: 11px; font-weight: 800; color: var(--accent); text-transform: uppercase; letter-spacing: .1em; font-family: var(--mono); margin-bottom: 1rem; }
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
