import React, { useState, useEffect, useRef } from 'react';
import { Shield, Activity, Users, Globe, Cpu, Tablet, Server, Trash2, RotateCcw, Search, ChevronRight, Check, AlertCircle } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

const Admin = () => {
    const [isLoggedIn, setIsLoggedIn] = useState(() => !!sessionStorage.getItem('admin_token'));
    const [token, setToken] = useState(() => sessionStorage.getItem('admin_token') || '');
    const [apiUrl, setApiUrl] = useState(() => {
        const { hostname, protocol } = window.location;
        if (hostname === 'localhost' || hostname === '127.0.0.1') {
            return 'http://127.0.0.1:8765';
        }
        return `${protocol}//${hostname}/admin-api`;
    });
    const [loginError, setLoginError] = useState('');
    const [status, setStatus] = useState(null);
    const [users, setUsers] = useState([]);
    const [servers, setServers] = useState([]);
    const [searchQuery, setSearchQuery] = useState('');
    const [addUserForm, setAddUserForm] = useState({ username: '', password: '' });
    const [addMsg, setAddMsg] = useState({ text: '', type: '' });
    const [toast, setToast] = useState({ show: false, text: '', type: 'ok' });
    const [subscribers, setSubscribers] = useState([]);
    const pollTimer = useRef(null);

    const showToast = (text, type = 'ok') => {
        setToast({ show: true, text, type });
        setTimeout(() => setToast({ show: false, text: '', type: 'ok' }), 3500);
    };

    const isAdminStatusPayload = (data) => {
        return data && typeof data === 'object' &&
            Object.prototype.hasOwnProperty.call(data, 'max_users') &&
            Object.prototype.hasOwnProperty.call(data, 'total_users') &&
            Object.prototype.hasOwnProperty.call(data, 'system');
    };

    const apiFetch = async (path, opts = {}) => {
        const url = `${apiUrl.replace(/\/$/, '')}${path}`;
        try {
            const response = await fetch(url, {
                ...opts,
                headers: {
                    'X-Admin-Token': token,
                    'Content-Type': 'application/json',
                    ...(opts.headers || {}),
                },
            });
            return response;
        } catch (error) {
            console.error('API Fetch Error:', error);
            throw error;
        }
    };

    const refresh = async () => {
        if (!token) return;
        try {
            const [statusRes, usersRes, serversRes, subsRes] = await Promise.all([
                apiFetch('/api/status'),
                apiFetch('/api/users'),
                apiFetch('/api/servers'),
                apiFetch('/api/subscribers'),
            ]);

            if (!statusRes.ok || !usersRes.ok) {
                throw new Error('Authentication failed');
            }

            const statusData = await statusRes.json();
            const usersData = await usersRes.json();

            if (!isAdminStatusPayload(statusData)) {
                throw new Error('Wrong API base URL. Use /admin-api (admin backend), not the customer portal API.');
            }

            // Normalise tunnels to always be an array so .map() never throws
            if (statusData && !Array.isArray(statusData.tunnels)) {
                statusData.tunnels = [];
            }

            setStatus(statusData);
            setUsers(usersData.users || []);

            if (serversRes.ok) {
                try {
                    const serversData = await serversRes.json();
                    setServers(serversData.servers || []);
                } catch (_) {}
            }

            if (subsRes.ok) {
                try {
                    const subsData = await subsRes.json();
                    setSubscribers(subsData.subscribers || []);
                } catch (_) {}
            }
        } catch (error) {
            console.error('Refresh Error:', error);
            if (isLoggedIn) {
                showToast('Polling failed: ' + error.message, 'err');
            }
        }
    };

    const startPolling = () => {
        refresh();
        pollTimer.current = setInterval(refresh, 8000);
    };

    const handleLogin = async (e) => {
        e.preventDefault();
        if (!token.trim()) {
            setLoginError('Token is required');
            return;
        }
        try {
            const res = await apiFetch('/api/status');
            if (res.ok) {
                const statusData = await res.json();
                if (!isAdminStatusPayload(statusData)) {
                    setLoginError('Connected to wrong API. Use https://<domain>/admin-api');
                    return;
                }
                sessionStorage.setItem('admin_token', token);
                setIsLoggedIn(true);
                setLoginError('');
                startPolling();
            } else {
                setLoginError('Invalid token or API unreachable');
            }
        } catch (error) {
            setLoginError('Could not connect to API');
        }
    };

    const handleLogout = () => {
        clearInterval(pollTimer.current);
        sessionStorage.removeItem('admin_token');
        setIsLoggedIn(false);
        setToken('');
        setStatus(null);
        setUsers([]);
    };

    const handleAddUser = async (e) => {
        e.preventDefault();
        if (!addUserForm.username.trim()) {
            setAddMsg({ text: 'Username required', type: 'err' });
            return;
        }

        const password = addUserForm.password.trim() || generatePass();
        try {
            const res = await apiFetch('/api/users', {
                method: 'POST',
                body: JSON.stringify({ username: addUserForm.username, password }),
            });
            const data = await res.json();
            if (res.ok) {
                setAddMsg({ text: `✓ Added: ${addUserForm.username}`, type: 'ok' });
                setAddUserForm({ username: '', password: '' });
                showToast(`User added: ${addUserForm.username}`);
                refresh();
            } else {
                setAddMsg({ text: `✗ ${data.error || 'Failed'}`, type: 'err' });
            }
        } catch (error) {
            setAddMsg({ text: '✗ API error', type: 'err' });
        }
    };

    const handleDeleteUser = async (username) => {
        if (!window.confirm(`Remove VPN user: ${username}?`)) return;
        try {
            const res = await apiFetch(`/api/users/${encodeURIComponent(username)}`, {
                method: 'DELETE',
            });
            if (res.ok) {
                showToast(`Removed: ${username}`);
                refresh();
            } else {
                showToast('Delete failed', 'err');
            }
        } catch (error) {
            showToast('API error', 'err');
        }
    };

    const handleRestartVpn = async () => {
        if (!window.confirm('Restart StrongSwan? Active connections will drop briefly.')) return;
        try {
            await apiFetch('/api/vpn/restart', { method: 'POST' });
            showToast('StrongSwan restarting...');
            setTimeout(refresh, 4000);
        } catch (error) {
            showToast('Restart failed', 'err');
        }
    };

    const handleSubAction = async (email, action, days = 30) => {
        const labels = { extend: `Extend ${days}d`, activate: 'Activate', suspend: 'Suspend', expire: 'Expire' };
        if (!window.confirm(`${labels[action] || action} for ${email}?`)) return;
        try {
            const res = await apiFetch(`/api/subscribers/${encodeURIComponent(email)}`, {
                method: 'PUT',
                body: JSON.stringify({ action, days }),
            });
            const data = await res.json();
            if (res.ok) {
                showToast(`${labels[action]} applied to ${email}`);
                refresh();
            } else {
                showToast(data.error || 'Action failed', 'err');
            }
        } catch {
            showToast('API error', 'err');
        }
    };

    const generatePass = () => {
        const chars = 'ABCDEFGHJKMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789!@#$';
        return Array.from({ length: 18 }, () => chars[Math.floor(Math.random() * chars.length)]).join('');
    };

    const fmtBytes = (gb) => {
        if (!gb || gb === 0) return '0 MB';
        if (gb < 0.001) return `${(gb * 1024 * 1024).toFixed(0)} KB`;
        if (gb < 1) return `${(gb * 1024).toFixed(1)} MB`;
        return `${gb.toFixed(2)} GB`;
    };

    useEffect(() => {
        if (token && isLoggedIn) {
            startPolling();
        }
        return () => clearInterval(pollTimer.current);
    }, []); // eslint-disable-line react-hooks/exhaustive-deps

    const filteredUsers = users.filter((u) => u.username.toLowerCase().includes(searchQuery.toLowerCase()));

    if (!isLoggedIn) {
        return (
            <div className="admin-login-overlay">
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="login-card"
                >
                    <div className="login-logo">
                        Turnip<span>VPN</span>
                    </div>
                    <div className="login-sub">
                        Admin Panel — Enter your API token
                    </div>

                    <form onSubmit={handleLogin} className="login-form">
                        <div className="form-group">
                            <label>API Token</label>
                            <input
                                type="password"
                                placeholder="Your ADMIN_TOKEN"
                                value={token}
                                onChange={(e) => setToken(e.target.value)}
                            />
                        </div>

                        <div className="form-group">
                            <label>API Base URL</label>
                            <input
                                type="text"
                                value={apiUrl}
                                onChange={(e) => setApiUrl(e.target.value)}
                            />
                        </div>

                        <button type="submit" className="login-btn">
                            Connect →
                        </button>

                        {loginError && (
                            <div className="error-msg">
                                {loginError}
                            </div>
                        )}
                    </form>
                </motion.div>

                <style jsx>{`
          .admin-login-overlay {
            position: fixed; top: 0; left: 0; width: 100%; height: 100%;
            background: var(--bg); display: flex; align-items: center; justify-content: center; z-index: 1000;
          }
          .login-card {
            background: var(--bg2); border: 1px solid var(--border);
            border-radius: 20px; padding: 3rem; width: 100%; max-width: 420px;
            box-shadow: 0 40px 100px rgba(0,0,0,0.5);
          }
          .login-logo { font-size: 24px; font-weight: 800; color: var(--text); text-align: center; margin-bottom: 0.5rem; }
          .login-logo span { color: var(--accent); }
          .login-sub { text-align: center; color: var(--text2); font-size: 13px; margin-bottom: 2.5rem; }
          .login-form { display: flex; flex-direction: column; gap: 1.5rem; }
          .form-group label { display: block; font-family: var(--mono); font-size: 10px; color: var(--text3); text-transform: uppercase; letter-spacing: .1em; margin-bottom: 0.5rem; }
          .form-group input {
            width: 100%; background: var(--bg3); border: 1px solid var(--border);
            border-radius: 10px; padding: 12px 16px; color: var(--text);
            font-family: var(--mono); font-size: 13px; outline: none; transition: border 0.2s;
          }
          .form-group input:focus { border-color: var(--accent); }
          .login-btn {
            background: var(--accent); color: var(--bg); border: none;
            border-radius: 10px; padding: 14px; font-weight: 800; font-size: 15px;
            cursor: pointer; transition: background 0.2s;
          }
          .login-btn:hover { background: var(--accent2); }
          .error-msg { font-family: var(--mono); font-size: 11px; color: var(--red); text-align: center; margin-top: 1rem; }
        `}</style>
            </div>
        );
    }

    const sys = status?.system || {};
    const capacityPct = status ? Math.round((status.total_users / status.max_users) * 100) : 0;

    return (
        <div className="admin-container">
            {/* Toast */}
            <AnimatePresence>
                {toast.show && (
                    <motion.div
                        initial={{ y: 50, opacity: 0 }}
                        animate={{ y: 0, opacity: 1 }}
                        exit={{ y: 50, opacity: 0 }}
                        className={`toast ${toast.type}`}
                    >
                        {toast.text}
                    </motion.div>
                )}
            </AnimatePresence>

            {/* Nav */}
            <nav className="admin-nav">
                <div className="nav-left">
                    <div className="logo">Turnip<span>VPN</span> <small>Admin</small></div>
                    {status && (
                        <div className={`status-indicator ${status.vpn_running ? 'running' : 'offline'}`}>
                            <div className="dot" />
                            <span>{status.vpn_running ? 'StrongSwan online' : 'VPN offline'}</span>
                        </div>
                    )}
                </div>
                <div className="nav-right">
                    <button onClick={handleRestartVpn} className="btn-restart">Restart VPN</button>
                    <button onClick={handleLogout} className="btn-signout">Sign out</button>
                </div>
            </nav>

            <div className="dashboard-content">
                {/* Capacity */}
                <div className="capacity-card">
                    <div className="capacity-info">
                        <div className="metric-tag">// server capacity</div>
                        <div className="progress-bg">
                            <motion.div className="progress-fill" initial={{ width: 0 }} animate={{ width: `${capacityPct}%` }} style={{ background: capacityPct >= 90 ? 'var(--red)' : capacityPct >= 70 ? 'var(--amber)' : 'var(--accent)' }} />
                        </div>
                        <div className="capacity-stats">
                            <span>{status ? status.max_users - status.total_users : '0'} slots available</span>
                            <span>{capacityPct}% target load</span>
                            <span className="srv-count">{status?.servers_active ?? 1}/{status?.servers_total ?? 1} server{(status?.servers_total ?? 1) > 1 ? 's' : ''} active</span>
                        </div>
                    </div>
                    <div className="capacity-value">
                        <div className="val">{status?.total_users || '0'}<span>/{status?.max_users || '80'}</span></div>
                        <div className="status-label">{capacityPct >= 90 ? 'ALMOST FULL' : capacityPct >= 70 ? 'HEAVY LOAD' : 'STABLE'}</div>
                    </div>
                </div>

                {/* Metrics Grid */}
                <div className="metrics-grid">
                    <div className="metric-box">
                        <div className="metric-tag">Conns</div>
                        <div className="metric-val accent">{status?.active_tunnels || '0'}</div>
                        <div className="metric-sub">Active tunnels</div>
                    </div>
                    <div className="metric-box">
                        <div className="metric-tag">CPU</div>
                        <div className="metric-val">{sys.cpu_pct || '0'}%</div>
                        <div className="metric-sub">System load</div>
                    </div>
                    <div className="metric-box">
                        <div className="metric-tag">Memory</div>
                        <div className="metric-val">{sys.mem_pct || '0'}%</div>
                        <div className="metric-sub">{sys.mem_used_gb || '0'} / {sys.mem_total_gb || '0'}GB</div>
                    </div>
                    <div className="metric-box">
                        <div className="metric-tag">Bandwidth</div>
                        <div className="metric-val-small">
                            <span className="tx">↑{sys.net_tx_rate_mbps > 0 ? `${sys.net_tx_rate_mbps} Mbps` : fmtBytes(sys.net_tx_gb)}</span>
                            <span className="rx">↓{sys.net_rx_rate_mbps > 0 ? `${sys.net_rx_rate_mbps} Mbps` : fmtBytes(sys.net_rx_gb)}</span>
                        </div>
                        <div className="metric-sub">Total ↑{fmtBytes(sys.net_tx_gb)} ↓{fmtBytes(sys.net_rx_gb)}</div>
                    </div>
                </div>

                {/* Server Fleet */}
                {servers.length > 0 && (
                    <div className="fleet-card">
                        <div className="card-header">
                            <h3>Server Fleet</h3>
                            <div className="badge">{servers.filter(s => s.reachable).length}/{servers.length} online</div>
                        </div>
                        <div className="fleet-grid">
                            {servers.map((srv) => {
                                const cap = Math.round((srv.users / (srv.slots_free + srv.users || 1)) * 100);
                                const color = !srv.reachable ? 'var(--red)' : cap >= 90 ? 'var(--red)' : cap >= 70 ? 'var(--amber)' : 'var(--accent)';
                                return (
                                    <div key={srv.id} className={`fleet-item ${!srv.reachable ? 'offline' : ''}`}>
                                        <div className="fleet-top">
                                            <span className="fleet-flag">{srv.flag}</span>
                                            <span className="fleet-name">{srv.name}</span>
                                            <span className="fleet-status" style={{ color }}>
                                                {!srv.reachable ? 'OFFLINE' : srv.slots_free === 0 ? 'FULL' : 'OK'}
                                            </span>
                                        </div>
                                        <div className="fleet-bars">
                                            <div className="fleet-bar-row">
                                                <span>Load</span>
                                                <div className="res-bg"><motion.div className="res-fill" initial={{ width: 0 }} animate={{ width: `${cap}%` }} style={{ background: color }} /></div>
                                                <span className="fleet-pct">{cap}%</span>
                                            </div>
                                            <div className="fleet-bar-row">
                                                <span>CPU</span>
                                                <div className="res-bg"><motion.div className="res-fill" initial={{ width: 0 }} animate={{ width: `${srv.cpu || 0}%` }} style={{ background: 'var(--blue)' }} /></div>
                                                <span className="fleet-pct">{srv.cpu || 0}%</span>
                                            </div>
                                        </div>
                                        <div className="fleet-meta">
                                            <span>{srv.users} users</span>
                                            <span>{srv.slots_free} free</span>
                                            <span>{srv.tunnels} tunnels</span>
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    </div>
                )}

                {/* Registered Users */}
                <div className="subs-card">
                    <div className="card-header">
                        <h3>Registered Users</h3>
                        <div className="badge">{subscribers.length} total</div>
                    </div>
                    <div className="subs-table-wrap custom-scrollbar">
                        {subscribers.length === 0 ? (
                            <div className="empty">No registered users yet</div>
                        ) : (
                            <table className="subs-table">
                                <thead>
                                    <tr>
                                        <th>Name</th>
                                        <th>Email</th>
                                        <th>Registered</th>
                                        <th>Plan</th>
                                        <th>Status</th>
                                        <th>Expires</th>
                                        <th>Actions</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {subscribers.map((s) => (
                                        <tr key={s.email}>
                                            <td>{s.name}</td>
                                            <td className="mono">{s.email}</td>
                                            <td className="mono muted">{s.created_at ? s.created_at.slice(0, 10) : '—'}</td>
                                        <td>{s.plan_name || '—'}</td>
                                        <td>
                                                <span className={`sub-badge ${s.sub_status === 'active' ? 'active' : s.sub_status === 'expired' ? 'expired' : 'none'}`}>
                                                    {s.sub_status || 'none'}
                                                </span>
                                            </td>
                                            <td className="mono muted">{s.expires_at ? s.expires_at.slice(0, 10) : '—'}</td>
                                            <td>
                                                <div className="sub-actions">
                                                    <button className="sub-btn ext" onClick={() => handleSubAction(s.email, 'extend', 30)} title="Extend 30 days">+30d</button>
                                                    {s.sub_status !== 'active' && <button className="sub-btn act" onClick={() => handleSubAction(s.email, 'activate')} title="Activate">Activate</button>}
                                                    {s.sub_status === 'active' && <button className="sub-btn sus" onClick={() => handleSubAction(s.email, 'suspend')} title="Suspend">Suspend</button>}
                                                </div>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        )}
                    </div>
                </div>

                <div className="main-grid">
                    {/* User Management */}
                    <div className="users-card">
                        <div className="card-header">
                            <h3>VPN Users</h3>
                            <div className="count">{users.length} enrolled</div>
                        </div>

                        <div className="search-bar">
                            <Search size={14} className="search-icon" />
                            <input
                                type="text"
                                placeholder="Find users..."
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                            />
                        </div>

                        <div className="users-list custom-scrollbar">
                            {filteredUsers.length === 0 ? (
                                <div className="empty">No matches found</div>
                            ) : (
                                filteredUsers.map((u) => (
                                    <div key={u.username} className="user-item">
                                        <div className={`online-dot ${u.online ? 'active' : ''}`} />
                                        <div className="user-name">{u.username}</div>
                                        <div className={`user-status ${u.online ? 'active' : ''}`}>{u.online ? 'ONLINE' : 'OFFLINE'}</div>
                                        <button onClick={() => handleDeleteUser(u.username)} className="btn-delete"><Trash2 size={13} /></button>
                                    </div>
                                ))
                            )}
                        </div>

                        <form onSubmit={handleAddUser} className="add-user-field">
                            <input type="text" placeholder="User" value={addUserForm.username} onChange={(e) => setAddUserForm({ ...addUserForm, username: e.target.value })} />
                            <input type="password" placeholder="Pass" value={addUserForm.password} onChange={(e) => setAddUserForm({ ...addUserForm, password: e.target.value })} />
                            <button type="submit">Add User</button>
                        </form>
                        {addMsg.text && <div className={`form-msg ${addMsg.type}`}>{addMsg.text}</div>}
                    </div>

                    <div className="sidebar-grid">
                        {/* Tunnels */}
                        <div className="card tunnels-card">
                            <div className="card-header">
                                <h3>Live Handshakes</h3>
                                <div className="badge">{status?.tunnels?.length || 0} active</div>
                            </div>
                            <div className="tunnel-list">
                                {status?.tunnels?.length > 0 ? (
                                    status.tunnels.map((t) => (
                                        <div key={t.id} className="tunnel-item">
                                            <span className="tid">#{t.id}</span>
                                            <span className="tname">{t.identity}</span>
                                            <span className="tsince">{t.since}</span>
                                        </div>
                                    ))
                                ) : <div className="empty">No handshakes</div>}
                            </div>
                        </div>

                        {/* SysInfo */}
                        <div className="card resources-card">
                            <div className="card-header">
                                <h3>System</h3>
                                <div className="uptime">up {status ? `${Math.floor(sys.uptime_sec / 3600)}h ${Math.floor((sys.uptime_sec % 3600) / 60)}m` : '--'}</div>
                            </div>
                            <div className="resource-bars">
                                {[
                                    { label: 'CPU', val: sys.cpu_pct, color: 'var(--accent)' },
                                    { label: 'MEM', val: sys.mem_pct, color: 'var(--blue)' },
                                    { label: 'DSK', val: sys.disk_pct, color: 'var(--amber)' }
                                ].map(r => (
                                    <div className="res-row" key={r.label}>
                                        <div className="res-lbl"><span>{r.label}</span> <span>{r.val || 0}%</span></div>
                                        <div className="res-bg"><motion.div className="res-fill" initial={{ width: 0 }} animate={{ width: `${r.val || 0}%` }} style={{ background: r.color }} /></div>
                                    </div>
                                ))}
                            </div>
                        </div>

                        {/* Firewall */}
                        <div className="card firewall-card">
                            <div className="card-header">
                                <h3>Firewall</h3>
                                <div className={`badge ${status?.firewall?.enabled ? '' : 'badge-err'}`}>
                                    {status?.firewall?.enabled ? 'Active' : 'Disabled'}
                                </div>
                            </div>
                            <div className="fw-rows">
                                <div className="fw-row">
                                    <span className="fw-label">UFW</span>
                                    <span className={status?.firewall?.enabled ? 'fw-ok' : 'fw-err'}>
                                        {status?.firewall?.enabled ? '● Active' : '○ Inactive'}
                                    </span>
                                </div>
                                <div className="fw-row">
                                    <span className="fw-label">Rules</span>
                                    <span className="fw-val">{status?.firewall?.rules ?? 0} configured</span>
                                </div>
                                <div className="fw-row">
                                    <span className="fw-label">VPN NAT</span>
                                    <span className={status?.firewall?.vpn_nat ? 'fw-ok' : 'fw-err'}>
                                        {status?.firewall?.vpn_nat ? '● Masquerade OK' : '○ Not found'}
                                    </span>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <style jsx>{`
        .admin-container { background: var(--bg); min-height: 100vh; color: var(--text); padding-bottom: 4rem; }
        .admin-nav {
          background: var(--bg2); border-bottom: 1px solid var(--border);
          padding: 1.25rem 2rem; display: flex; align-items: center; justify-content: space-between;
          position: sticky; top: 0; z-index: 100;
        }
        .nav-left { display: flex; align-items: center; gap: 2rem; }
        .logo { font-size: 18px; font-weight: 800; }
        .logo span { color: var(--accent); }
        .logo small { font-size: 11px; font-weight: 400; color: var(--text3); margin-left: 6px; }
        .status-indicator { display: flex; align-items: center; gap: 10px; font-family: var(--mono); font-size: 10px; }
        .status-indicator .dot { width: 6px; height: 6px; border-radius: 50%; }
        .status-indicator.running .dot { background: var(--accent); box-shadow: 0 0 10px var(--accent); }
        .status-indicator.offline .dot { background: var(--red); }
        .status-indicator.running span { color: var(--accent); }
        .status-indicator.offline span { color: var(--red); }

        .nav-right { display: flex; gap: 12px; }
        .btn-restart { 
          background: rgba(244, 63, 94, 0.08); border: 1px solid rgba(244, 63, 94, 0.2); 
          color: var(--red); padding: 8px 16px; border-radius: 6px; font-size: 11px; font-weight: 700; cursor: pointer;
        }
        .btn-signout {
          background: var(--adim); border: 1px solid var(--border);
          color: var(--text); padding: 8px 16px; border-radius: 6px; font-size: 11px; font-weight: 700; cursor: pointer;
        }

        .dashboard-content { max-width: 1100px; margin: 0 auto; padding: 2rem; }
        .capacity-card {
          background: var(--bg2); border: 1px solid var(--border); border-radius: 16px;
          padding: 2.5rem; display: flex; align-items: center; gap: 4rem; margin-bottom: 1.5rem;
        }
        .capacity-info { flex: 1; }
        .metric-tag { font-family: var(--mono); font-size: 10px; color: var(--text3); text-transform: uppercase; letter-spacing: .1em; margin-bottom: 1rem; }
        .progress-bg { height: 6px; background: var(--bg3); border-radius: 100px; overflow: hidden; margin-bottom: 0.75rem; }
        .progress-fill { height: 100%; border-radius: 100px; }
        .capacity-stats { display: flex; justify-content: space-between; font-family: var(--mono); font-size: 11px; color: var(--text2); flex-wrap: wrap; gap: 0.25rem; }
        .srv-count { color: var(--accent); font-weight: 700; }
        .badge-err { background: rgba(239,68,68,.15); color: var(--red); }
        .firewall-card { }
        .fw-rows { display: flex; flex-direction: column; gap: 0.6rem; margin-top: 0.5rem; }
        .fw-row { display: flex; justify-content: space-between; align-items: center; font-size: 12px; }
        .fw-label { font-family: var(--mono); color: var(--text3); font-size: 11px; text-transform: uppercase; letter-spacing: .05em; }
        .fw-val { font-family: var(--mono); color: var(--text2); font-size: 12px; }
        .fw-ok { color: var(--accent); font-family: var(--mono); font-size: 12px; }
        .fw-err { color: var(--red); font-family: var(--mono); font-size: 12px; }
        .capacity-value { text-align: right; }
        .capacity-value .val { font-size: 42px; font-weight: 800; font-family: var(--mono); line-height: 1; }
        .capacity-value .val span { font-size: 18px; color: var(--text3); font-weight: 400; }
        .status-label { font-family: var(--mono); font-size: 10px; margin-top: 8px; font-weight: 700; }

        .metrics-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; margin-bottom: 1.5rem; }
        .metric-box { background: var(--bg2); border: 1px solid var(--border); border-radius: 12px; padding: 1.25rem; }
        .metric-val { font-size: 24px; font-weight: 800; font-family: var(--mono); margin: 0.5rem 0; }
        .metric-val.accent { color: var(--accent); }
        .metric-val-small { display: flex; flex-direction: column; gap: 4px; font-family: var(--mono); font-size: 14px; font-weight: 700; margin: 0.5rem 0; }
        .tx { color: var(--accent); } .rx { color: var(--blue); }
        .metric-sub { font-size: 11px; color: var(--text3); font-weight: 600; }

        .main-grid { display: grid; grid-template-columns: 2fr 1fr; gap: 1.5rem; }
        .card { background: var(--bg2); border: 1px solid var(--border); border-radius: 16px; padding: 1.5rem; }
        .users-card { background: var(--bg2); border: 1px solid var(--border); border-radius: 16px; padding: 1.5rem; }
        .card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem; }
        .card-header h3 { font-size: 16px; font-weight: 700; }
        .card-header .count, .card-header .uptime, .card-header .badge { font-family: var(--mono); font-size: 10px; color: var(--text2); padding: 4px 8px; background: var(--bg3); border-radius: 4px; }

        .search-bar { position: relative; margin-bottom: 1rem; }
        .search-icon { position: absolute; left: 12px; top: 12px; color: var(--text3); }
        .search-bar input {
          width: 100%; background: var(--bg3); border: 1px solid var(--border); border-radius: 8px;
          padding: 10px 14px 10px 36px; color: var(--text); font-family: var(--mono); font-size: 12px; outline: none;
        }
        .users-list { height: 320px; overflow-y: auto; display: flex; flex-direction: column; gap: 4px; }
        .user-item { 
          display: flex; align-items: center; gap: 12px; padding: 10px 12px;
          border-radius: 8px; transition: background 0.2s;
        }
        .user-item:hover { background: var(--bg3); }
        .online-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--text3); }
        .online-dot.active { background: var(--accent); box-shadow: 0 0 6px var(--accent); }
        .user-name { flex: 1; font-family: var(--mono); font-size: 13px; }
        .user-status { font-family: var(--mono); font-size: 9px; font-weight: 700; color: var(--text3); padding: 2px 6px; border: 1px solid var(--border); border-radius: 4px; }
        .user-status.active { color: var(--accent); border-color: var(--adim); background: var(--adim); }
        .btn-delete { color: var(--text3); cursor: pointer; background: none; border: none; opacity: 0; transition: opacity 0.2s; }
        .user-item:hover .btn-delete { opacity: 1; }
        .user-item:hover .btn-delete:hover { color: var(--red); }

        .add-user-field { display: flex; gap: 8px; margin-top: 1.5rem; padding-top: 1.5rem; border-top: 1px solid var(--border); }
        .add-user-field input { 
          flex: 1; background: var(--bg3); border: 1px solid var(--border); border-radius: 6px;
          padding: 8px 12px; color: var(--text); font-family: var(--mono); font-size: 11px; outline: none;
        }
        .add-user-field button {
          background: var(--accent); color: var(--bg); border: none; border-radius: 6px;
          padding: 0 16px; font-weight: 800; font-size: 11px; cursor: pointer;
        }
        .form-msg { font-family: var(--mono); font-size: 10px; margin-top: 8px; }
        .form-msg.ok { color: var(--accent); } .form-msg.err { color: var(--red); }

        .sidebar-grid { display: flex; flex-direction: column; gap: 1.5rem; }
        .tunnel-list { display: flex; flex-direction: column; gap: 8px; }
        .tunnel-item { display: flex; justify-content: space-between; font-family: var(--mono); font-size: 11px; padding-bottom: 8px; border-bottom: 1px solid var(--adim); }
        .tid { color: var(--accent); opacity: 0.6; }
        .tname { font-weight: 700; }
        .tsince { color: var(--text3); font-size: 10px; }

        .resource-bars { display: flex; flex-direction: column; gap: 1.25rem; }
        .res-lbl { display: flex; justify-content: space-between; font-family: var(--mono); font-size: 10px; font-weight: 700; color: var(--text2); margin-bottom: 6px; }
        .res-bg { height: 4px; background: var(--bg3); border-radius: 10px; overflow: hidden; }
        .res-fill { height: 100%; border-radius: 10px; }

        .toast {
          position: fixed; bottom: 2rem; right: 2rem; z-index: 1000;
          background: var(--bg2); border: 1px solid var(--border); border-radius: 10px;
          padding: 12px 24px; font-family: var(--mono); font-size: 12px; font-weight: 700;
          box-shadow: 0 20px 40px rgba(0,0,0,0.3);
        }
        .toast.ok { color: var(--accent); border-color: var(--adim); }
        .toast.err { color: var(--red); border-color: rgba(244, 63, 94, 0.2); }

        .empty { text-align: center; color: var(--text3); font-family: var(--mono); font-size: 11px; padding: 2rem 0; }
        .custom-scrollbar::-webkit-scrollbar { width: 3px; }
        .custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
        .custom-scrollbar::-webkit-scrollbar-thumb { background: var(--surf); border-radius: 10px; }

        .fleet-card { background: var(--bg2); border: 1px solid var(--border); border-radius: 16px; padding: 1.5rem; margin-bottom: 1.5rem; }
        .fleet-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 1rem; }
        .fleet-item { background: var(--bg3); border: 1px solid var(--border); border-radius: 12px; padding: 1rem; }
        .fleet-item.offline { opacity: 0.5; }
        .fleet-top { display: flex; align-items: center; gap: 8px; margin-bottom: 1rem; }
        .fleet-flag { font-size: 18px; }
        .fleet-name { flex: 1; font-size: 13px; font-weight: 700; }
        .fleet-status { font-family: var(--mono); font-size: 9px; font-weight: 800; letter-spacing: .05em; }
        .fleet-bars { display: flex; flex-direction: column; gap: 8px; margin-bottom: 1rem; }
        .fleet-bar-row { display: grid; grid-template-columns: 28px 1fr 32px; align-items: center; gap: 8px; font-family: var(--mono); font-size: 9px; color: var(--text3); }
        .fleet-pct { text-align: right; font-weight: 700; }
        .fleet-meta { display: flex; justify-content: space-between; font-family: var(--mono); font-size: 9px; color: var(--text3); padding-top: 0.75rem; border-top: 1px solid var(--border); }

        .subs-card { background: var(--bg2); border: 1px solid var(--border); border-radius: 16px; padding: 1.5rem; margin-bottom: 1.5rem; }
        .subs-table-wrap { overflow-x: auto; max-height: 320px; overflow-y: auto; }
        .subs-table { width: 100%; border-collapse: collapse; font-size: 13px; }
        .subs-table th { font-family: var(--mono); font-size: 9px; text-transform: uppercase; letter-spacing: .08em; color: var(--text3); padding: 0 12px 10px; text-align: left; border-bottom: 1px solid var(--border); white-space: nowrap; }
        .subs-table td { padding: 10px 12px; border-bottom: 1px solid var(--adim); vertical-align: middle; }
        .subs-table tr:last-child td { border-bottom: none; }
        .subs-table tr:hover td { background: var(--bg3); }
        .subs-table .mono { font-family: var(--mono); font-size: 12px; }
        .subs-table .muted { color: var(--text2); }
        .sub-badge { font-family: var(--mono); font-size: 9px; font-weight: 800; letter-spacing: .05em; padding: 3px 8px; border-radius: 4px; text-transform: uppercase; }
        .sub-badge.active { color: var(--accent); background: var(--adim); border: 1px solid rgba(74,222,128,0.2); }
        .sub-badge.expired { color: var(--red); background: rgba(244,63,94,0.08); border: 1px solid rgba(244,63,94,0.2); }
        .sub-badge.none { color: var(--text3); background: var(--bg3); border: 1px solid var(--border); }
        .sub-actions { display: flex; gap: 5px; }
        .sub-btn { padding: 3px 8px; border-radius: 5px; border: 1px solid; font-size: 10px; font-weight: 700; cursor: pointer; font-family: var(--mono); transition: opacity 0.15s; }
        .sub-btn:hover { opacity: 0.75; }
        .sub-btn.ext { background: rgba(168,85,247,0.1); border-color: rgba(168,85,247,0.3); color: var(--accent); }
        .sub-btn.act { background: rgba(74,222,128,0.08); border-color: rgba(74,222,128,0.25); color: var(--green, #4ade80); }
        .sub-btn.sus { background: rgba(251,146,60,0.08); border-color: rgba(251,146,60,0.25); color: var(--amber, #fb923c); }
      `}</style>
        </div>
    );
};

export default Admin;
