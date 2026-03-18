import React, { useState, useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Menu, X, Shield } from 'lucide-react';

const Navbar = () => {
  const [isScrolled, setIsScrolled] = useState(false);
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const location = useLocation();

  useEffect(() => {
    const handleScroll = () => {
      setIsScrolled(window.scrollY > 40);
    };
    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  const navLinks = [
    { name: 'Features', href: '/#features' },
    { name: 'Protocol', href: '/#how' },
    { name: 'Pricing', href: '/pricing' },
  ];

  return (
    <nav className={`nav ${isScrolled ? 'scrolled' : ''}`}>
      <div className="container">
        <div className="nav-inner">
          <Link to="/" className="logo">
            Tur<span>nip</span>
          </Link>

          {/* Desktop Links */}
          <div className="nav-links">
            {navLinks.map((link) => (
              <a key={link.name} href={link.href}>
                {link.name}
              </a>
            ))}
          </div>

          <div className="nav-ctas">
            <Link to="/login" className="btn btn-outline btn-nav">
              Sign in
            </Link>
            <Link to="/pricing" className="btn btn-primary btn-nav">
              Get started
            </Link>
          </div>

          <button className="hamburger" onClick={() => setIsMenuOpen(!isMenuOpen)}>
            {isMenuOpen ? <X size={24} /> : <Menu size={24} />}
          </button>
        </div>
      </div>

      {/* Mobile Menu */}
      {isMenuOpen && (
        <div className="mobile-menu">
          {navLinks.map((link) => (
            <a
              key={link.name}
              href={link.href}
              onClick={() => setIsMenuOpen(false)}
            >
              {link.name}
            </a>
          ))}
          <Link to="/login" onClick={() => setIsMenuOpen(false)}>Login</Link>
          <Link to="/pricing" className="btn btn-primary" onClick={() => setIsMenuOpen(false)}>Get Started</Link>
        </div>
      )}

      <style jsx>{`
        .nav {
          position: fixed;
          top: 0;
          left: 0;
          right: 0;
          z-index: 100;
          padding: 1.1rem 0;
          border-bottom: 1px solid transparent;
          transition: all 0.3s;
        }
        .nav.scrolled {
          background: rgba(5, 8, 16, 0.96);
          border-color: var(--border);
          backdrop-filter: blur(8px);
        }
        .nav-inner {
          display: flex;
          align-items: center;
          justify-content: space-between;
        }
        .logo {
          font-size: 18px;
          font-weight: 800;
          letter-spacing: -0.5px;
          color: var(--text);
        }
        .logo span {
          color: var(--accent);
        }
        .nav-links {
          display: flex;
          gap: 2rem;
        }
        .nav-links a {
          font-size: 13px;
          font-weight: 600;
          color: var(--text2);
          transition: color 0.2s;
        }
        .nav-links a:hover {
          color: var(--text);
        }
        .nav-ctas {
          display: flex;
          gap: 10px;
          align-items: center;
        }
        .btn-nav {
          padding: 8px 18px;
          font-size: 13px;
          border-radius: 7px;
        }
        .hamburger {
          display: none;
          background: none;
          border: none;
          color: var(--text);
          cursor: pointer;
        }
        .mobile-menu {
          position: absolute;
          top: 100%;
          left: 0;
          right: 0;
          background: var(--bg2);
          padding: 2rem;
          display: flex;
          flex-direction: column;
          gap: 1.5rem;
          border-bottom: 1px solid var(--border);
        }
        .btn {
          display: inline-flex;
          align-items: center;
          gap: 8px;
          padding: 13px 28px;
          border-radius: 8px;
          font-family: var(--sans);
          font-size: 14px;
          font-weight: 700;
          cursor: pointer;
          transition: all 0.2s;
          border: none;
        }
        .btn-primary {
          background: var(--accent);
          color: #050810;
        }
        .btn-primary:hover {
          background: var(--accent2);
          transform: translateY(-1px);
        }
        .btn-outline {
          background: transparent;
          border: 1px solid var(--border2);
          color: var(--text);
        }
        .btn-outline:hover {
          border-color: var(--accent);
          color: var(--accent);
        }

        @media (max-width: 900px) {
          .nav-links {
            display: none;
          }
          .nav-ctas {
            display: none;
          }
          .hamburger {
            display: block;
          }
        }
      `}</style>
    </nav>
  );
};

export default Navbar;
