import React, { useState } from 'react';
import { motion } from 'framer-motion';
import {
    Shield, Globe, EyeOff, Activity, Server, Zap,
    Smartphone, Monitor, Laptop, Terminal, ChevronDown, CheckCircle2
} from 'lucide-react';

const Home = () => {
    return (
        <div className="home">
            <Hero />
            <Stats />
            <Features />
            <HowItWorks />
            <Platforms />
            <FAQ />
            <CTABanner />
            <Footer />
        </div>
    );
};

const Hero = () => (
    <section className="hero">
        <div className="container">
            <div className="hero-grid">
                <motion.div
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: 0.8 }}
                >
                    <div className="hero-badge">
                        <div className="pulse"></div>
                        IKEv2 / IPsec · AES-256 · Zero Logs
                    </div>
                    <h1>Encrypt<br />everything.<br /><em>Expose nothing.</em></h1>
                    <p>Enterprise-grade VPN built on StrongSwan IKEv2/IPsec. Connect any device directly through native OS settings — no app required. Your IP, private.</p>
                    <div className="hero-ctas">
                        <a href="/pricing" className="btn btn-primary btn-lg">Start for ₦1,500/mo</a>
                        <a href="#how" className="btn btn-outline btn-lg">See how it works</a>
                    </div>
                    <div className="hero-trust">
                        <div className="trust-item"><CheckCircle2 size={14} color="var(--accent)" /> No app install</div>
                        <div className="trust-item"><CheckCircle2 size={14} color="var(--accent)" /> Instant activation</div>
                        <div className="trust-item"><CheckCircle2 size={14} color="var(--accent)" /> Zero traffic logs</div>
                    </div>
                </motion.div>

                <motion.div
                    className="hero-visual"
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ duration: 1, delay: 0.2 }}
                >
                    <div className="terminal">
                        <div className="terminal-bar">
                            <div className="t-dot" style={{ background: '#ff5f57' }}></div>
                            <div className="t-dot" style={{ background: '#febc2e' }}></div>
                            <div className="t-dot" style={{ background: '#28c840' }}></div>
                            <div className="t-title">turnip — tunnel</div>
                        </div>
                        <div className="terminal-body">
                            <div className="t-line"><span className="t-prompt">$</span><span className="t-cmd"> ipsec statusall</span></div>
                            <div className="t-line"><span className="t-out">Security Associations (3 up, 0 connecting):</span></div>
                            <div className="t-line"><span className="t-out t-ok">turnip[1]: ESTABLISHED 2 minutes ago</span></div>
                            <div className="t-line"><span className="t-out">IKEv2 SPIs: a3f2c1d4_i b8e7a6f5_r</span></div>
                            <div className="t-line"><span className="t-out t-ok">AES_CBC_256/HMAC_SHA2_256_128/PRF_HMAC_SHA2_256/ECP_384</span></div>
                            <div className="t-line"><span className="t-prompt">$</span><span className="t-cmd"> cat /etc/ipsec.secrets | grep EAP | wc -l</span></div>
                            <div className="t-line"><span className="t-out">47</span></div>
                            <div className="status-row">
                                <span className="s-label">TUNNEL STATUS</span>
                                <span className="s-val">● ACTIVE · 47/80 users</span>
                            </div>
                        </div>
                    </div>
                </motion.div>
            </div>
        </div>

        <style jsx>{`
      .hero { padding: 11rem 0 6rem; position: relative; overflow: hidden; }
      .hero-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 4rem; align-items: center; }
      .hero-badge { 
        display: inline-flex; align-items: center; gap: 8px; 
        background: var(--adim); border: 1px solid var(--border2); 
        color: var(--accent); font-family: var(--mono); font-size: 11px; 
        padding: 6px 14px; border-radius: 100px; margin-bottom: 1.5rem; letter-spacing: .06em;
      }
      .pulse { width: 6px; height: 6px; border-radius: 50%; background: var(--accent); animation: pulse 2s infinite; }
      @keyframes pulse { 0%, 100% { opacity: 1; transform: scale(1); } 50% { opacity: .4; transform: scale(.8); } }
      h1 { font-size: clamp(38px, 5vw, 64px); font-weight: 800; line-height: 1.05; letter-spacing: -2px; margin-bottom: 1.25rem; }
      h1 em { font-style: normal; color: var(--accent); }
      p { font-size: 17px; color: var(--text2); max-width: 480px; line-height: 1.7; margin-bottom: 2.5rem; }
      .hero-ctas { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 2rem; }
      .hero-trust { display: flex; gap: 1.5rem; flex-wrap: wrap; }
      .trust-item { display: flex; align-items: center; gap: 7px; font-size: 12px; color: var(--text3); font-family: var(--mono); }
      
      .terminal { background: var(--bg2); border: 1px solid var(--border); border-radius: 14px; overflow: hidden; box-shadow: 0 40px 100px rgba(0,0,0,0.5); }
      .terminal-bar { display: flex; align-items: center; gap: 8px; padding: 12px 16px; border-bottom: 1px solid var(--border); background: var(--bg3); }
      .t-dot { width: 10px; height: 10px; border-radius: 50%; }
      .t-title { flex: 1; text-align: center; font-family: var(--mono); font-size: 11px; color: var(--text3); }
      .terminal-body { padding: 1.25rem 1.5rem; font-family: var(--mono); font-size: 12px; line-height: 2; }
      .t-line { display: flex; gap: 10px; }
      .t-prompt { color: var(--accent); }
      .t-cmd { color: var(--text); }
      .t-out { color: var(--text2); padding-left: 20px; }
      .t-ok { color: var(--accent); }
      .status-row { 
        display: flex; align-items: center; justify-content: space-between; 
        background: rgba(0,200,150,.06); border: 1px solid var(--border2); 
        border-radius: 8px; padding: 10px 14px; margin-top: 12px; 
      }
      .s-label { font-family: var(--mono); font-size: 11px; color: var(--text2); }
      .s-val { font-family: var(--mono); font-size: 11px; color: var(--accent); font-weight: 700; }

      @media (max-width: 900px) {
        .hero-grid { grid-template-columns: 1fr; text-align: center; }
        p { margin: 0 auto 2.5rem; }
        .hero-ctas, .hero-trust { justify-content: center; }
        .hero-visual { display: none; }
      }
    `}</style>
    </section>
);

const Stats = () => (
    <div className="stats">
        <div className="container">
            <div className="stats-grid">
                {[
                    { val: 'AES-256', label: 'Encryption standard' },
                    { val: '4', label: 'Global server regions' },
                    { val: '0', label: 'Traffic logs stored' },
                    { val: '5', label: 'Platforms supported' }
                ].map((s, i) => (
                    <div className="stat-item" key={i}>
                        <div className="stat-num">{s.val}</div>
                        <div className="stat-label">{s.label}</div>
                    </div>
                ))}
            </div>
        </div>
        <style jsx>{`
      .stats { border-top: 1px solid var(--border); border-bottom: 1px solid var(--border); background: var(--bg2); }
      .stats-grid { display: grid; grid-template-columns: repeat(4, 1fr); }
      .stat-item { padding: 2rem; text-align: center; border-right: 1px solid var(--border); }
      .stat-item:last-child { border-right: none; }
      .stat-num { font-size: 34px; font-weight: 800; color: var(--accent); font-family: var(--mono); letter-spacing: -1px; }
      .stat-label { font-size: 12px; color: var(--text3); margin-top: 4px; font-weight: 600; letter-spacing: .05em; text-transform: uppercase; }
      @media (max-width: 900px) {
        .stats-grid { grid-template-columns: repeat(2, 1fr); }
        .stat-item:nth-child(2) { border-right: none; }
        .stat-item { border-bottom: 1px solid var(--border); }
      }
    `}</style>
    </div>
);

const Features = () => (
    <section className="section" id="features">
        <div className="container">
            <div className="section-tag">// capabilities</div>
            <h2 className="section-title">Security-first by design.</h2>
            <p className="section-sub">Built on battle-tested IKEv2/IPsec — the same protocol trusted by enterprise networks worldwide.</p>
            <div className="features-grid">
                {[
                    { icon: <Shield />, title: 'IKEv2/IPsec tunneling', desc: 'Military-grade key exchange with AES-256 encryption and SHA-256 integrity verification. Unique session keys generated per connection.' },
                    { icon: <Zap />, title: 'No app required', desc: 'Configure directly in your OS VPN settings. iOS, Android, Windows, macOS, and Linux all supported natively. Zero downloads.' },
                    { icon: <EyeOff />, title: 'Zero traffic logs', desc: 'We log connection timestamps and server health only. Your browsing activity, DNS queries, and traffic are never recorded.' },
                    { icon: <Activity />, title: 'Dead peer detection', desc: 'Stale connections are automatically cleaned up. Your session stays lean, and reconnection is near-instant on any device.' },
                    { icon: <Server />, title: 'StrongSwan engine', desc: 'Powered by the industry-standard StrongSwan IPsec daemon on dedicated Linux VPS infrastructure with full NAT traversal.' },
                    { icon: <Zap />, title: 'Instant activation', desc: 'Pay once, receive credentials and a one-tap .mobileconfig profile by email within seconds. No manual setup, no waiting.' }
                ].map((f, i) => (
                    <motion.div
                        className="feat-card"
                        key={i}
                        whileHover={{ y: -5, background: 'var(--surf)' }}
                        transition={{ type: 'spring', stiffness: 300 }}
                    >
                        <div className="feat-icon">{f.icon}</div>
                        <h3>{f.title}</h3>
                        <p>{f.desc}</p>
                    </motion.div>
                ))}
            </div>
        </div>
        <style jsx>{`
      .section-tag { font-family: var(--mono); font-size: 11px; color: var(--accent); letter-spacing: .12em; text-transform: uppercase; margin-bottom: .75rem; }
      .section-title { font-size: clamp(28px, 3.5vw, 42px); font-weight: 800; letter-spacing: -1.5px; margin-bottom: .75rem; }
      .section-sub { color: var(--text2); font-size: 16px; max-width: 500px; line-height: 1.7; margin-bottom: 3rem; }
      .features-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1px; background: var(--border); border: 1px solid var(--border); border-radius: 14px; overflow: hidden; }
      .feat-card { background: var(--bg2); padding: 2.5rem; transition: background 0.2s; cursor: pointer; }
      .feat-icon { width: 42px; height: 42px; border-radius: 10px; background: var(--adim); border: 1px solid var(--border2); display: flex; align-items: center; justify-content: center; margin-bottom: 1.25rem; color: var(--accent); }
      h3 { font-size: 16px; font-weight: 700; margin-bottom: 10px; }
      p { font-size: 14px; color: var(--text2); line-height: 1.7; }
      @media (max-width: 900px) { .features-grid { grid-template-columns: 1fr 1fr; } }
      @media (max-width: 600px) { .features-grid { grid-template-columns: 1fr; } }
    `}</style>
    </section>
);

const HowItWorks = () => (
    <section className="section how-section" id="how">
        <div className="container">
            <div className="how-grid">
                <div>
                    <div className="section-tag">// how it works</div>
                    <h2 className="section-title">The IKEv2<br />handshake.</h2>
                    <p style={{ color: 'var(--text2)', fontSize: '15px', marginBottom: '2.5rem' }}>Seven steps from your device to fully encrypted internet.</p>
                    <div className="steps-list">
                        {[
                            { n: '01', t: 'Enter credentials', p: 'Username, password, and server address entered in native OS VPN settings.' },
                            { n: '02', t: 'IKE_SA_INIT', p: 'Client initiates cryptographic handshake with the gateway on UDP 500/4500.' },
                            { n: '03', t: 'Server responds', p: 'Gateway sends encryption parameters and X.509 certificate for verification.' },
                            { n: '04', t: 'EAP-MSCHAPv2 auth', p: 'Credentials authenticated. Session keys derived via Diffie-Hellman key exchange.' },
                            { n: '05', t: 'IPsec tunnel established', p: 'ESP encrypts all packets at the network layer with AES-256-GCM.' },
                            { n: '06', t: 'Virtual IP assigned', p: 'StrongSwan allocates a virtual IP from the 10.10.10.0/24 subnet.' },
                            { n: '07', t: 'NAT + full routing', p: "All traffic exits through the server's public IP. Your real IP is hidden." }
                        ].map((s, i) => (
                            <div className="step-item" key={i}>
                                <div className="step-num">{s.n}</div>
                                <div><h4>{s.t}</h4><p>{s.p}</p></div>
                            </div>
                        ))}
                    </div>
                </div>
                <div>
                    <div className="tunnel-card">
                        <div style={{ fontFamily: 'var(--mono)', fontSize: '10px', color: 'var(--text3)', letterSpacing: '.1em', textTransform: 'uppercase', marginBottom: '1.25rem' }}>Live packet view</div>
                        <div className="tunnel-row"><div className="t-label">Your device</div><div className="t-bar t-raw">PLAINTEXT HTTP REQUEST</div></div>
                        <div className="tunnel-divider">▼ AES-256 ESP encrypt</div>
                        <div className="tunnel-row"><div className="t-label">IPsec tunnel</div><div className="t-bar t-enc">■ ■ ■ ENCRYPTED ESP PACKET ■ ■ ■</div></div>
                        <div className="tunnel-divider">▼ gateway decrypts + NAT</div>
                        <div className="tunnel-row"><div className="t-label">Exit node</div><div className="t-bar t-raw">HTTP + MASKED PUBLIC IP</div></div>
                        <div style={{ marginTop: '1.25rem', paddingTop: '1.25rem', borderTop: '1px solid var(--border)' }}>
                            <div style={{ fontFamily: 'var(--mono)', fontSize: '10px', color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '.1em', marginBottom: '.75rem' }}>Session keys</div>
                            <div className="tunnel-row"><div className="t-label">Cipher</div><div className="t-bar t-key">AES-256-GCM</div></div>
                            <div className="tunnel-row"><div className="t-label">Integrity</div><div className="t-bar t-key">SHA2-256-HMAC</div></div>
                            <div className="tunnel-row"><div className="t-label">DH Group</div><div className="t-bar t-key">MODP-2048 (Group 14)</div></div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        <style jsx>{`
      .how-section { background: var(--bg2); border-top: 1px solid var(--border); border-bottom: 1px solid var(--border); }
      .how-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 5rem; align-items: center; }
      .step-item { display: flex; gap: 1rem; padding: 1.1rem 0; border-bottom: 1px solid var(--border); }
      .step-item:last-child { border-bottom: none; }
      .step-num { font-family: var(--mono); font-size: 11px; color: var(--accent); font-weight: 700; min-width: 24px; padding-top: 2px; }
      h4 { font-size: 14px; font-weight: 700; margin-bottom: 3px; }
      .step-item p { font-size: 13px; color: var(--text2); line-height: 1.6; }
      .tunnel-card { background: var(--bg3); border: 1px solid var(--border); border-radius: 12px; padding: 2rem; box-shadow: 0 20px 50px rgba(0,0,0,0.3); }
      .tunnel-row { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; font-family: var(--mono); font-size: 11px; }
      .t-label { color: var(--text3); min-width: 80px; }
      .t-bar { flex: 1; height: 30px; border-radius: 4px; display: flex; align-items: center; padding: 0 12px; font-size: 10px; font-weight: 700; letter-spacing: .04em; }
      .t-enc { background: var(--adim); border: 1px solid var(--border2); color: var(--accent); }
      .t-raw { background: rgba(255, 71, 87, .07); border: 1px solid rgba(255, 71, 87, .2); color: var(--red); }
      .t-key { background: rgba(255, 184, 48, .07); border: 1px solid rgba(255, 184, 48, .2); color: var(--amber); margin-bottom: 4px; }
      .tunnel-divider { display: flex; align-items: center; gap: 8px; margin: 4px 0 4px 88px; font-family: var(--mono); font-size: 9px; color: var(--accent); }
      @media (max-width: 900px) { .how-grid { grid-template-columns: 1fr; } }
    `}</style>
    </section>
);

const Platforms = () => (
    <section className="section" id="platforms">
        <div className="container" style={{ textAlign: 'center' }}>
            <div className="section-tag" style={{ display: 'inline-block' }}>// compatibility</div>
            <h2 className="section-title">Works on everything.</h2>
            <p className="section-sub" style={{ margin: '0 auto 3rem' }}>Native IKEv2 support built into every major OS. Connect in under two minutes with zero third-party software.</p>
            <div className="platforms-grid">
                {[
                    { icon: <Smartphone />, name: 'iOS', sub: 'iPhone & iPad · One-tap profile' },
                    { icon: <Activity />, name: 'Android', sub: 'Via strongSwan · Free app' },
                    { icon: <Monitor />, name: 'Windows', sub: 'Built-in VPN · Settings → Add' },
                    { icon: <Laptop />, name: 'macOS', sub: 'System Settings · One-tap profile' },
                    { icon: <Terminal />, name: 'Linux', sub: 'NetworkManager · or nmcli' }
                ].map((p, i) => (
                    <div className="platform-card" key={i}>
                        <div className="platform-icon">{p.icon}</div>
                        <div className="platform-name">{p.name}</div>
                        <div className="platform-sub">{p.sub}</div>
                    </div>
                ))}
            </div>
        </div>
        <style jsx>{`
      .platforms-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; }
      .platform-card { background: var(--bg2); border: 1px solid var(--border); border-radius: 10px; padding: 2rem 1rem; text-align: center; transition: all 0.2s; }
      .platform-card:hover { border-color: var(--border2); background: var(--surf); transform: translateY(-3px); }
      .platform-icon { font-size: 24px; margin-bottom: 1rem; color: var(--accent); display: flex; justify-content: center; }
      .platform-name { font-size: 14px; font-weight: 700; margin-bottom: 6px; }
      .platform-sub { font-size: 11px; color: var(--text3); line-height: 1.5; }
      @media (max-width: 900px) { .platforms-grid { grid-template-columns: repeat(3, 1fr); } }
      @media (max-width: 600px) { .platforms-grid { grid-template-columns: repeat(2, 1fr); } }
    `}</style>
    </section>
);

const FAQ = () => {
    const [openIndex, setOpenIndex] = useState(null);
    const faqs = [
        { q: 'Do I need to install an app?', a: 'No. Turnip VPN uses the IKEv2 protocol built into iOS, macOS, Windows, and Linux. On iOS and macOS, open the .mobileconfig file you receive and the VPN is configured in one tap.' },
        { q: 'How quickly is my account activated?', a: 'Instantly. As soon as your Paystack payment is confirmed, our system automatically creates your VPN credentials and emails you the setup profile. The whole process takes under 30 seconds.' },
        { q: 'Do you keep logs of my activity?', a: 'No. We log connection timestamps and server performance metrics only. Your DNS queries, browsing history, and traffic contents are never stored.' },
        { q: 'What encryption does it use?', a: 'AES-256-GCM for data encryption, SHA2-256 for integrity verification, and Diffie-Hellman Group 14 (MODP-2048) for key exchange.' }
    ];

    return (
        <section className="section" id="faq">
            <div className="container" style={{ textAlign: 'center' }}>
                <div className="section-tag" style={{ display: 'inline-block' }}>// faq</div>
                <h2 className="section-title" style={{ marginBottom: '3rem' }}>Common questions.</h2>
                <div className="faq-grid">
                    {faqs.map((f, i) => (
                        <div className={`faq-item ${openIndex === i ? 'open' : ''}`} key={i}>
                            <div className="faq-q" onClick={() => setOpenIndex(openIndex === i ? null : i)}>
                                {f.q}
                                <span className="faq-arrow">{openIndex === i ? '−' : '+'}</span>
                            </div>
                            <motion.div
                                className="faq-a"
                                initial={false}
                                animate={{ height: openIndex === i ? 'auto' : 0 }}
                                transition={{ duration: 0.3 }}
                            >
                                <div className="faq-a-inner">{f.a}</div>
                            </motion.div>
                        </div>
                    ))}
                </div>
            </div>
            <style jsx>{`
        .faq-grid { max-width: 720px; margin: 0 auto; display: flex; flex-direction: column; gap: 4px; }
        .faq-item { background: var(--bg2); border: 1px solid var(--border); border-radius: 10px; overflow: hidden; }
        .faq-q { display: flex; align-items: center; justify-content: space-between; padding: 1.25rem 1.5rem; cursor: pointer; font-size: 15px; font-weight: 700; transition: background 0.2s; user-select: none; }
        .faq-q:hover { background: var(--surf); }
        .faq-arrow { font-size: 18px; color: var(--accent); transition: transform 0.2s; }
        .faq-a { overflow: hidden; }
        .faq-a-inner { padding: 0 1.5rem 1.25rem; font-size: 14px; color: var(--text2); line-height: 1.7; text-align: left; border-top: 1px solid var(--border); }
      `}</style>
        </section>
    );
};

const CTABanner = () => (
    <section className="section" style={{ paddingTop: 0 }}>
        <div className="container">
            <div className="cta-banner">
                <h2>Start encrypting<br />today.</h2>
                <p>Instant activation. Zero setup complexity. Connect in under 60 seconds.</p>
                <div className="cta-ctas">
                    <a href="/pricing" className="btn btn-primary btn-lg">Get started — ₦1,500/mo</a>
                    <a href="/login" className="btn btn-outline btn-lg">Sign in →</a>
                </div>
            </div>
        </div>
        <style jsx>{`
      .cta-banner { background: linear-gradient(135deg, var(--bg2) 0%, var(--bg3) 100%); border: 1px solid var(--border); border-radius: 24px; padding: 4.5rem; text-align: center; margin: 0 auto; max-width: 800px; box-shadow: 0 30px 60px rgba(0,0,0,0.4); }
      h2 { font-size: clamp(32px, 4vw, 42px); font-weight: 800; letter-spacing: -1.5px; margin-bottom: 1rem; }
      p { color: var(--text2); font-size: 17px; margin-bottom: 2.5rem; }
      .cta-ctas { display: flex; gap: 15px; justify-content: center; flex-wrap: wrap; }
    `}</style>
    </section>
);

const Footer = () => (
    <footer>
        <div className="container">
            <div className="footer-grid">
                <div>
                    <div className="footer-logo">Secure<span>Fast</span></div>
                    <div className="footer-desc">High-performance IKEv2/IPsec VPN. Encrypted, private, and fast — for individuals and teams.</div>
                </div>
                <div className="footer-col">
                    <h4>Product</h4>
                    <a href="#features">Features</a>
                    <a href="#pricing">Pricing</a>
                    <a href="#platforms">Platforms</a>
                    <a href="#faq">FAQ</a>
                </div>
                <div className="footer-col">
                    <h4>Account</h4>
                    <a href="/login">Sign in</a>
                    <a href="/pricing">Get started</a>
                    <a href="/dashboard">Dashboard</a>
                </div>
                <div className="footer-col">
                    <h4>Legal</h4>
                    <a href="/privacy">Privacy policy</a>
                    <a href="/terms">Terms of service</a>
                    <a href="/security">Security</a>
                </div>
            </div>
            <div className="footer-bottom">
                <div className="footer-copy">© 2025 Turnip VPN. All rights reserved.</div>
                <div className="enc-badges">
                    <div className="enc-badge">AES-256</div>
                    <div className="enc-badge">IKEv2</div>
                    <div className="enc-badge">ZERO LOGS</div>
                </div>
            </div>
        </div>
        <style jsx>{`
      footer { padding: 5rem 0 3rem; border-top: 1px solid var(--border); }
      .footer-grid { display: grid; grid-template-columns: 2fr 1fr 1fr 1fr; gap: 3rem; margin-bottom: 4rem; }
      .footer-logo { font-size: 20px; font-weight: 800; margin-bottom: 1rem; }
      .footer-logo span { color: var(--accent); }
      .footer-desc { font-size: 14px; color: var(--text2); line-height: 1.7; max-width: 250px; }
      h4 { font-size: 12px; font-weight: 700; color: var(--text); letter-spacing: .08em; text-transform: uppercase; margin-bottom: 1.2rem; }
      a { display: block; font-size: 14px; color: var(--text2); margin-bottom: 9px; transition: color 0.2s; }
      a:hover { color: var(--accent); }
      .footer-bottom { display: flex; align-items: center; justify-content: space-between; border-top: 1px solid var(--border); padding-top: 2rem; flex-wrap: wrap; gap: 1.5rem; }
      .footer-copy { font-size: 13px; color: var(--text3); font-family: var(--mono); }
      .enc-badges { display: flex; gap: 8px; }
      .enc-badge { background: var(--adim); border: 1px solid var(--border2); color: var(--accent); font-family: var(--mono); font-size: 11px; padding: 5px 12px; border-radius: 6px; }
      @media (max-width: 900px) { .footer-grid { grid-template-columns: 1fr 1fr; } }
      @media (max-width: 600px) { .footer-grid { grid-template-columns: 1fr; } }
    `}</style>
    </footer>
);

export default Home;
