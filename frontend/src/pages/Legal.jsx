import React from 'react';

const Page = ({ title }) => (
    <div className="container" style={{ paddingTop: '10rem', paddingBottom: '5rem', minHeight: '80vh' }}>
        <h1 style={{ marginBottom: '2rem' }}>{title}</h1>
        <div style={{ color: 'var(--text2)', lineHeight: '1.8' }}>
            <p>This is a placeholder for the {title} page. Turnip VPN takes your privacy and security seriously.</p>
            <p style={{ marginTop: '1rem' }}>We implement industry-standard AES-256 encryption and follow a strict zero-logs policy.</p>
        </div>
    </div>
);

export const Security = () => <Page title="Security Architecture" />;
export const Terms = () => <Page title="Terms of Service" />;
export const Privacy = () => <Page title="Privacy Policy" />;
