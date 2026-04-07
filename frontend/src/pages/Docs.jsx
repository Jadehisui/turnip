import React, { useState } from 'react';
import { ChevronDown, Smartphone, Monitor, Globe, Shield, Wifi, HelpCircle } from 'lucide-react';

const articles = [
    {
        id: 'ios-setup',
        icon: <Smartphone size={18} />,
        title: 'How to Connect on iOS / macOS',
        tag: 'Setup',
        content: (
            <>
                <p>After payment, a <strong>.mobileconfig</strong> profile is sent to your email. It configures everything in your device settings automatically — no apps to download or install.</p>
                <h4>iOS (iPhone / iPad)</h4>
                <ol>
                    <li>Open the email with subject <em>"Your Turnip VPN is ready"</em> on your device.</li>
                    <li>Tap the <code>turnip-device1-*.mobileconfig</code> attachment.</li>
                    <li>Tap <strong>Allow</strong>, then open <strong>Settings → Profile Downloaded → Install</strong>. Enter your passcode when prompted.</li>
                    <li>Once installed, go to <strong>Settings → VPN</strong> → select <em>Turnip VPN</em> → toggle <strong>ON</strong>.</li>
                </ol>
                <h4>macOS</h4>
                <ol>
                    <li>Open the email on your Mac and double-click the <code>.mobileconfig</code> attachment.</li>
                    <li>Open <strong>System Settings → Privacy &amp; Security → Profiles</strong> → click <strong>Install</strong>.</li>
                    <li>Go to <strong>System Settings → VPN</strong> → toggle <em>Turnip VPN</em> <strong>ON</strong>.</li>
                </ol>
                <p className="tip">💡 Your credentials email contains one profile per device slot on your plan. Use a different profile for each iPhone, iPad, or Mac.</p>
            </>
        ),
    },
    {
        id: 'android-setup',
        icon: <Smartphone size={18} />,
        title: 'How to Connect on Android',
        tag: 'Setup',
        content: (
            <>
                <p>Android has a built-in IKEv2 VPN client. No apps to install — everything is configured directly in your phone settings using the credentials from your email.</p>
                <h4>Steps</h4>
                <ol>
                    <li>Open <strong>Settings → Network &amp; Internet → VPN</strong> (on Samsung: <strong>Settings → Connections → More connection settings → VPN</strong>).</li>
                    <li>Tap the <strong>＋</strong> or <strong>Add VPN</strong> button.</li>
                    <li>Fill in:
                        <ul>
                            <li><strong>Name</strong>: Turnip VPN (or any label)</li>
                            <li><strong>Type</strong>: IKEv2/IPSec MSCHAPv2</li>
                            <li><strong>Server address</strong>: from your credentials email</li>
                            <li><strong>IPSec identifier</strong>: same as server address</li>
                            <li><strong>Username</strong> and <strong>Password</strong>: from your credentials email</li>
                        </ul>
                    </li>
                    <li>Tap <strong>Save</strong>, then tap the VPN name to connect.</li>
                    <li>Accept the connection request when prompted.</li>
                </ol>
                <h4>Install the CA certificate (if the connection is rejected)</h4>
                <ol>
                    <li>Download <code>turnip-ca.pem</code> from your <a href="/dashboard">Dashboard</a>.</li>
                    <li>Go to <strong>Settings → Security → Encryption &amp; credentials → Install a certificate → CA certificate</strong> and select the file.</li>
                    <li>Return to the VPN settings and connect again.</li>
                </ol>
                <p className="tip">💡 The menu location varies slightly by Android version and manufacturer, but search "VPN" in your Settings search bar and it will take you straight there.</p>
            </>
        ),
    },
    {
        id: 'windows-setup',
        icon: <Monitor size={18} />,
        title: 'How to Connect on Windows',
        tag: 'Setup',
        content: (
            <>
                <p>Windows 10 and 11 have a built-in IKEv2 VPN client — no third-party apps needed.</p>
                <h4>Steps</h4>
                <ol>
                    <li>Open <strong>Settings → Network &amp; Internet → VPN → Add a VPN connection</strong>.</li>
                    <li>Set the fields:
                        <ul>
                            <li><strong>VPN provider</strong>: Windows (built-in)</li>
                            <li><strong>Connection name</strong>: Turnip VPN (or any name)</li>
                            <li><strong>Server name or address</strong>: from your credentials email</li>
                            <li><strong>VPN type</strong>: IKEv2</li>
                            <li><strong>Type of sign-in info</strong>: Username and password</li>
                            <li><strong>Username / Password</strong>: from your credentials email</li>
                        </ul>
                    </li>
                    <li>Click <strong>Save</strong>.</li>
                    <li>Click on the VPN connection and press <strong>Connect</strong>.</li>
                </ol>
                <h4>Install the CA certificate (required on most systems)</h4>
                <ol>
                    <li>Download <code>turnip-ca.pem</code> from your <a href="/dashboard">Dashboard</a>.</li>
                    <li>Double-click the file → <strong>Install Certificate</strong> → <strong>Local Machine</strong> → <strong>Trusted Root Certification Authorities</strong> → <strong>Finish</strong>.</li>
                    <li>Try connecting again — the certificate warning should be gone.</li>
                </ol>
                <h4>Verify all traffic routes through the VPN</h4>
                <p>After connecting, open a browser and visit <a href="https://whatismyip.com" target="_blank" rel="noopener noreferrer">whatismyip.com</a>. Your IP should show the VPN server's location, not your real location.</p>
                <p className="tip">💡 If Windows shows "The connection was terminated" immediately, the CA cert is likely not installed correctly. Repeat the certificate install as <strong>Local Machine</strong> (not Current User).</p>
            </>
        ),
    },
    {
        id: 'linux-setup',
        icon: <Monitor size={18} />,
        title: 'How to Connect on Linux',
        tag: 'Setup',
        content: (
            <>
                <p>Linux has a built-in IKEv2 VPN client via NetworkManager. No third-party apps needed — configure it directly in your system network settings.</p>
                <h4>GNOME (Ubuntu, Fedora, Pop!_OS)</h4>
                <ol>
                    <li>Open <strong>Settings → Network → VPN → ＋</strong>.</li>
                    <li>Select <strong>IKEv2</strong> from the list.</li>
                    <li>Fill in:
                        <ul>
                            <li><strong>Gateway (Server)</strong>: from your credentials email</li>
                            <li><strong>Authentication</strong>: EAP / Username</li>
                            <li><strong>Username</strong> and <strong>Password</strong>: from your credentials email</li>
                            <li><strong>CA certificate</strong>: download <code>turnip-ca.pem</code> from your <a href="/dashboard">Dashboard</a> and select it here</li>
                        </ul>
                    </li>
                    <li>Click <strong>Add</strong>, then toggle the VPN on from the Network panel.</li>
                </ol>
                <h4>KDE Plasma</h4>
                <ol>
                    <li>Open <strong>System Settings → Connections → ＋ → VPN → IKEv2</strong>.</li>
                    <li>Enter the same server, username, password, and CA certificate as above.</li>
                    <li>Click <strong>OK</strong> and activate the connection from the system tray.</li>
                </ol>
                <p className="tip">💡 If IKEv2 is not listed in NetworkManager, it may need the IPsec backend: <code>sudo apt install network-manager-l2tp</code> or check your distro's VPN plugin package. No extra apps beyond the system plugin are required.</p>
            </>
        ),
    },
    {
        id: 'ikev2-explained',
        icon: <Shield size={18} />,
        title: 'What is IKEv2/IPsec?',
        tag: 'Security',
        content: (
            <>
                <p>Turnip VPN uses <strong>IKEv2/IPsec</strong> — the same protocol used by corporate security teams and government agencies worldwide. Here's what that means for you.</p>
                <h4>IKEv2 (Internet Key Exchange v2)</h4>
                <p>IKEv2 is the handshake protocol that establishes and manages the encrypted tunnel between your device and the VPN server. It authenticates both ends of the connection and negotiates the encryption keys. IKEv2 is fast to connect/reconnect (ideal for mobile devices switching between WiFi and cellular) and is resilient against packet loss.</p>
                <h4>IPsec (Internet Protocol Security)</h4>
                <p>IPsec is the encryption layer that wraps all your internet traffic inside an authenticated, encrypted capsule. Every packet is:</p>
                <ul>
                    <li><strong>Encrypted</strong> with AES-256-GCM — the same cipher used for top-secret data.</li>
                    <li><strong>Authenticated</strong> with SHA-384 — nobody can tamper with packets in transit.</li>
                    <li><strong>Signed</strong> with our server's certificate — you're always connecting to the real Turnip server, not an impersonator.</li>
                </ul>
                <h4>Why IKEv2/IPsec?</h4>
                <p>IKEv2/IPsec is <strong>natively built into iOS, macOS, Windows, and Android</strong> — no third-party apps needed, ever. Your VPN is configured directly in your device's own network settings, just like a Wi-Fi password. This means it works system-wide, covers every app automatically, and reconnects instantly when you switch from Wi-Fi to mobile data.</p>
                <h4>Zero logs</h4>
                <p>The Turnip VPN server never writes your source IP, DNS queries, or any traffic content to disk. The only data stored is your username (for credential verification) and your subscription expiry date.</p>
            </>
        ),
    },
    {
        id: 'no-internet',
        icon: <Wifi size={18} />,
        title: 'Troubleshooting: Connected but No Internet',
        tag: 'Troubleshooting',
        content: (
            <>
                <p>If you can connect to the VPN but websites don't load, work through these checks in order:</p>
                <h4>1. Verify the tunnel is active</h4>
                <ul>
                    <li>Your VPN client should show a green "Connected" state.</li>
                    <li>On iOS, the VPN icon (🔒) should appear in the status bar.</li>
                    <li>If not fully connected, disconnect and reconnect.</li>
                </ul>
                <h4>2. Check DNS</h4>
                <p>The VPN server pushes <code>1.1.1.1</code> and <code>8.8.8.8</code> as DNS. You can verify:</p>
                <ul>
                    <li><strong>iOS/macOS</strong>: Settings → Wi-Fi → tap your network → DNS should show <code>1.1.1.1</code> while connected.</li>
                    <li><strong>Windows</strong>: open Command Prompt → <code>nslookup google.com</code> — should use <code>1.1.1.1</code>.</li>
                    <li><strong>Linux</strong>: <code>cat /etc/resolv.conf</code> — should list <code>1.1.1.1</code>.</li>
                </ul>
                <h4>3. Force all traffic through the VPN</h4>
                <p>Some clients use "split tunneling" by default — only sending some traffic through the VPN. Make sure your setup routes <strong>all traffic</strong> (<code>0.0.0.0/0</code>) through the tunnel. On iOS this is automatic with the .mobileconfig profile.</p>
                <h4>4. Check your subscription</h4>
                <p>If your subscription has expired, the VPN server will reject traffic even after the handshake completes. Log in to your <a href="/dashboard">Dashboard</a> to verify your expiry date.</p>
                <h4>5. Try a different device or region</h4>
                <p>Switch to a different server region in your account dashboard and download a new profile. If one region works and another doesn't, the specific server may have a temporary issue — contact support.</p>
                <h4>6. Contact support</h4>
                <p>Reply to any email you've received from <code>turnipvpn0x@gmail.com</code> with your username, device type, and a brief description. We typically respond within a few hours.</p>
            </>
        ),
    },
];

const tagColors = {
    Setup: { bg: 'rgba(0,200,150,0.08)', border: 'rgba(0,200,150,0.25)', color: 'var(--accent)' },
    Security: { bg: 'rgba(168,85,247,0.08)', border: 'rgba(168,85,247,0.25)', color: '#a855f7' },
    Troubleshooting: { bg: 'rgba(251,146,60,0.08)', border: 'rgba(251,146,60,0.25)', color: '#fb923c' },
};

const Docs = () => {
    const [openId, setOpenId] = useState(null);
    const toggle = (id) => setOpenId(prev => prev === id ? null : id);

    return (
        <section className="docs-page">
            <div className="container">
                <div className="docs-header">
                    <div className="section-tag" style={{ display: 'inline-block' }}>// guides</div>
                    <h1 className="docs-title">How to use Turnip VPN</h1>
                    <p className="docs-sub">Setup guides, protocol explainers, and troubleshooting — everything you need to get connected.</p>
                </div>

                <div className="articles">
                    {articles.map((a) => {
                        const isOpen = openId === a.id;
                        const tagStyle = tagColors[a.tag] || {};
                        return (
                            <div key={a.id} className={`article-card ${isOpen ? 'open' : ''}`}>
                                <button className="article-header" onClick={() => toggle(a.id)} aria-expanded={isOpen}>
                                    <div className="article-left">
                                        <span className="article-icon">{a.icon}</span>
                                        <span className="article-title">{a.title}</span>
                                    </div>
                                    <div className="article-right">
                                        <span className="article-tag" style={{ background: tagStyle.bg, border: `1px solid ${tagStyle.border}`, color: tagStyle.color }}>
                                            {a.tag}
                                        </span>
                                        <ChevronDown size={16} className={`chevron ${isOpen ? 'rotated' : ''}`} />
                                    </div>
                                </button>
                                {isOpen && (
                                    <div className="article-body">
                                        {a.content}
                                    </div>
                                )}
                            </div>
                        );
                    })}
                </div>

                <div className="docs-footer">
                    <HelpCircle size={16} />
                    <span>Can't find what you need? Email <a href="mailto:turnipvpn0x@gmail.com">turnipvpn0x@gmail.com</a> and we'll help.</span>
                </div>
            </div>

            <style jsx>{`
        .docs-page { padding: 6rem 0 5rem; min-height: 80vh; }
        .docs-header { text-align: center; margin-bottom: 3.5rem; }
        .docs-title { font-size: clamp(28px, 4vw, 42px); font-weight: 800; letter-spacing: -1.5px; color: var(--text); margin: 0.75rem 0 1rem; }
        .docs-sub { color: var(--text2); font-size: 16px; max-width: 520px; margin: 0 auto; line-height: 1.6; }

        .articles { display: flex; flex-direction: column; gap: 12px; max-width: 800px; margin: 0 auto; }

        .article-card {
          background: var(--bg2); border: 1px solid var(--border); border-radius: 14px;
          overflow: hidden; transition: border-color 0.2s;
        }
        .article-card.open { border-color: var(--accent); }

        .article-header {
          display: flex; align-items: center; justify-content: space-between;
          width: 100%; padding: 1.25rem 1.5rem; background: none; border: none;
          cursor: pointer; text-align: left; gap: 1rem;
        }
        .article-header:hover { background: var(--bg3); }

        .article-left { display: flex; align-items: center; gap: 12px; }
        .article-icon { color: var(--accent); display: flex; align-items: center; flex-shrink: 0; }
        .article-title { font-size: 15px; font-weight: 700; color: var(--text); }

        .article-right { display: flex; align-items: center; gap: 10px; flex-shrink: 0; }
        .article-tag {
          font-size: 10px; font-weight: 800; font-family: var(--mono);
          text-transform: uppercase; letter-spacing: .06em;
          padding: 3px 9px; border-radius: 5px;
        }
        .chevron { color: var(--text3); transition: transform 0.2s; }
        .chevron.rotated { transform: rotate(180deg); }

        .article-body {
          padding: 0 1.5rem 1.75rem;
          border-top: 1px solid var(--border);
          padding-top: 1.5rem;
        }
        .article-body p { color: var(--text2); font-size: 14.5px; line-height: 1.75; margin: 0 0 1rem; }
        .article-body h4 { font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: .07em; color: var(--text3); margin: 1.5rem 0 0.6rem; }
        .article-body ol, .article-body ul { color: var(--text2); font-size: 14.5px; line-height: 2; padding-left: 1.25rem; margin: 0 0 1rem; }
        .article-body li { margin-bottom: 2px; }
        .article-body strong { color: var(--text); }
        .article-body code { font-family: var(--mono); font-size: 12px; background: var(--bg3); border: 1px solid var(--border); padding: 1px 6px; border-radius: 4px; color: var(--accent); }
        .article-body pre {
          font-family: var(--mono); font-size: 12px; background: var(--bg3);
          border: 1px solid var(--border); border-radius: 8px;
          padding: 1rem 1.25rem; overflow-x: auto; color: var(--text2);
          line-height: 1.8; margin: 0 0 1rem;
          white-space: pre;
        }
        .article-body a { color: var(--accent); text-decoration: none; }
        .article-body a:hover { text-decoration: underline; }
        .article-body .tip {
          background: rgba(0,200,150,0.06); border: 1px solid rgba(0,200,150,0.18);
          border-radius: 8px; padding: 10px 14px; font-size: 13px;
          color: var(--text2); margin-top: 0.5rem;
        }

        .docs-footer {
          display: flex; align-items: center; justify-content: center;
          gap: 8px; margin-top: 3rem; color: var(--text3); font-size: 13.5px;
        }
        .docs-footer a { color: var(--accent); text-decoration: none; }
        .docs-footer a:hover { text-decoration: underline; }
      `}</style>
        </section>
    );
};

export default Docs;
