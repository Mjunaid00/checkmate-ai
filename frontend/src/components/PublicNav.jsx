import { useState, useEffect } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { Menu, X } from 'lucide-react';
import ThemeSwitcher from './ThemeSwitcher';
import './PublicNav.css';

export default function PublicNav() {
  const [scrolled, setScrolled] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const onLanding = location.pathname === '/';

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener('scroll', onScroll);
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  const scrollToSection = (id) => {
    setMobileOpen(false);
    if (!onLanding) {
      navigate(`/#${id}`);
      setTimeout(() => {
        document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 100);
    } else {
      document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  };

  return (
    <nav className={`public-nav ${scrolled ? 'scrolled' : ''}`}>
      <div className="public-nav-inner">
        <Link to="/" className="public-nav-brand" onClick={() => setMobileOpen(false)}>
          <div className="logo-icon">C</div>
          <span>CheckMate</span>
        </Link>

        <button className="mobile-toggle" onClick={() => setMobileOpen(!mobileOpen)}>
          {mobileOpen ? <X size={22} /> : <Menu size={22} />}
        </button>

        <div className={`public-nav-links ${mobileOpen ? 'open' : ''}`}>
          <button onClick={() => scrollToSection('home')} className="nav-link">Home</button>
          <button onClick={() => scrollToSection('features')} className="nav-link">Features</button>
          <button onClick={() => scrollToSection('about')} className="nav-link">About</button>
          <button onClick={() => scrollToSection('contact')} className="nav-link">Contact</button>

          <div className="public-nav-actions">
            <ThemeSwitcher compact />
            <Link to="/login" className="btn-secondary nav-cta" onClick={() => setMobileOpen(false)}>Sign In</Link>
            <Link to="/register" className="btn-primary nav-cta" onClick={() => setMobileOpen(false)}>Get Started</Link>
          </div>
        </div>
      </div>
    </nav>
  );
}
