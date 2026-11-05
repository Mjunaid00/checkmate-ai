import { useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  Brain, Sparkles, ShieldCheck, FileText, Code, BarChart3, Users, Eye,
  ArrowRight, Mail, MapPin, GitBranch, ExternalLink, Check
} from 'lucide-react';
import './LandingPage.css';

export default function LandingPage() {
  const location = useLocation();

  // Smooth-scroll to anchor on hash navigation
  useEffect(() => {
    if (location.hash) {
      const id = location.hash.replace('#', '');
      setTimeout(() => {
        document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 50);
    } else {
      window.scrollTo(0, 0);
    }
  }, [location]);

  return (
    <div className="landing-page">
      {/* ── Hero Section ──────────────────────────────────────────── */}
      <section id="home" className="hero-section">
        <div className="hero-bg-gradient" />
        <div className="hero-content fade-in">
          <span className="hero-badge">
            <Sparkles size={14} /> AI-Powered Grading Platform
          </span>
          <h1 className="hero-title">
            Grade smarter with <span className="text-gradient">Explainable AI</span>
          </h1>
          <p className="hero-subtitle">
            CheckMate AI automates exam grading using local vision-language models.
            Get instant, detailed feedback that explains every mark — for both teachers and students.
          </p>
          <div className="hero-actions">
            <Link to="/register" className="btn-primary hero-cta">
              Get Started Free <ArrowRight size={18} />
            </Link>
            <a href="#features" className="btn-secondary hero-cta">See Features</a>
          </div>

          <div className="hero-stats">
            <div className="hero-stat">
              <div className="hero-stat-value">12+</div>
              <div className="hero-stat-label">AI Modules</div>
            </div>
            <div className="hero-stat">
              <div className="hero-stat-value">90+</div>
              <div className="hero-stat-label">Languages (OCR)</div>
            </div>
            <div className="hero-stat">
              <div className="hero-stat-value">5</div>
              <div className="hero-stat-label">Code Languages</div>
            </div>
            <div className="hero-stat">
              <div className="hero-stat-value">100%</div>
              <div className="hero-stat-label">Local & Private</div>
            </div>
          </div>
        </div>
      </section>

      {/* ── Features Section ──────────────────────────────────────── */}
      <section id="features" className="features-section">
        <div className="section-container">
          <div className="section-heading">
            <span className="section-eyebrow">Features</span>
            <h2>Everything you need for fair, fast grading</h2>
            <p>From handwritten exams to programming assignments — all graded transparently.</p>
          </div>

          <div className="features-grid">
            <FeatureCard
              icon={Brain}
              title="AI-Powered Grading"
              description="Local vision-language models evaluate descriptive answers and code with teacher-defined rubrics."
              color="#3B82F6"
            />
            <FeatureCard
              icon={Eye}
              title="Explainable AI (XAI)"
              description="See exactly why each mark was awarded — criterion breakdown, keyword coverage, mistakes detected."
              color="#10B981"
            />
            <FeatureCard
              icon={FileText}
              title="OCR for Handwriting"
              description="Chandra OCR 2 reads scanned exams, handwritten work, tables, and forms in 90+ languages."
              color="#F59E0B"
            />
            <FeatureCard
              icon={Code}
              title="Code Execution"
              description="Sandboxed grading for Python, C, C++, Java, and JavaScript — compares output against test cases."
              color="#8B5CF6"
            />
            <FeatureCard
              icon={BarChart3}
              title="Performance Prediction"
              description="Linear-regression analytics identify at-risk students early so teachers can intervene."
              color="#EC4899"
            />
            <FeatureCard
              icon={ShieldCheck}
              title="Role-Based Access"
              description="Separate teacher and student portals with strict permission boundaries on every endpoint."
              color="#14B8A6"
            />
            <FeatureCard
              icon={Users}
              title="Class Enrollment"
              description="Teachers create classes, students enroll. Deadlines, prompts, and rubrics per assignment."
              color="#F43F5E"
            />
            <FeatureCard
              icon={Sparkles}
              title="Multi-Theme UI"
              description="Light, Dark, Gray, and Night Light modes — your preferences saved across sessions."
              color="#6366F1"
            />
          </div>
        </div>
      </section>

      {/* ── About Section ─────────────────────────────────────────── */}
      <section id="about" className="about-section">
        <div className="section-container">
          <div className="about-grid">
            <div className="about-text">
              <span className="section-eyebrow">About</span>
              <h2>Built to make grading transparent</h2>
              <p>
                CheckMate AI was developed as a BS Artificial Intelligence final year project at <strong>SZABIST Islamabad</strong> to solve
                a real problem: traditional grading is slow, inconsistent, and rarely explains the reasoning
                behind a score.
              </p>
              <p>
                By combining local vision-language models, document OCR, and a custom Explainable AI layer,
                CheckMate produces feedback that students can actually learn from — and that teachers can audit.
              </p>

              <ul className="about-checklist">
                <li><Check size={18} className="check-icon" /> 100% local processing — no data leaves your machine</li>
                <li><Check size={18} className="check-icon" /> Open-source and customizable for any institution</li>
                <li><Check size={18} className="check-icon" /> Designed with teacher feedback at every step</li>
                <li><Check size={18} className="check-icon" /> Supports descriptive, programming, and mixed answers</li>
              </ul>
            </div>

            <div className="about-team">
              <h3>Meet the Team</h3>
              <div className="team-cards">
                {[
                  { name: 'Hassan Jahangir', role: 'Full-Stack Development' },
                  { name: 'Muhammad Ibad', role: 'Backend / AI Integration' },
                  { name: 'Muhammad Muneeb', role: 'Frontend / UI/UX · AI, XAI & LLM' },
                ].map((m, i) => (
                  <div key={i} className="team-mini-card glass-panel">
                    <div className="team-mini-avatar">
                      {m.name.split(' ').map(p => p[0]).join('').slice(0, 2)}
                    </div>
                    <div>
                      <strong>{m.name}</strong>
                      <p>{m.role}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── Contact Section ───────────────────────────────────────── */}
      <section id="contact" className="contact-section">
        <div className="section-container">
          <div className="section-heading">
            <span className="section-eyebrow">Contact</span>
            <h2>Get in touch</h2>
            <p>Questions, feedback, or interested in deploying CheckMate at your institution?</p>
          </div>

          <div className="contact-grid">
            <ContactCard
              icon={Mail}
              title="Email"
              value="checkmate.ai@fast.edu.pk"
              link="mailto:checkmate.ai@fast.edu.pk"
            />
            <ContactCard
              icon={MapPin}
              title="Location"
              value="SZABIST Islamabad, Pakistan"
            />
            <ContactCard
              icon={GitBranch}
              title="GitHub"
              value="View source"
              link="https://github.com"
            />
            <ContactCard
              icon={ExternalLink}
              title="LinkedIn"
              value="Connect with the team"
              link="https://linkedin.com"
            />
          </div>

          <ContactForm />
        </div>
      </section>

      {/* ── Footer ────────────────────────────────────────────────── */}
      <footer className="landing-footer">
        <div className="section-container">
          <div className="footer-content">
            <div className="footer-brand">
              <div className="logo-icon">C</div>
              <strong>CheckMate AI</strong>
            </div>
            <p className="footer-text">
              © 2026 CheckMate AI. BS-AI Final Year Project, SZABIST Islamabad.
            </p>
            <div className="footer-links">
              <Link to="/login">Sign In</Link>
              <Link to="/register">Register</Link>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}

function FeatureCard({ icon: Icon, title, description, color }) {
  return (
    <div className="feature-card glass-panel">
      <div className="feature-icon" style={{ background: `${color}20`, color }}>
        <Icon size={22} />
      </div>
      <h3>{title}</h3>
      <p>{description}</p>
    </div>
  );
}

function ContactCard({ icon: Icon, title, value, link }) {
  const Wrapper = link ? 'a' : 'div';
  const props = link ? { href: link, target: link.startsWith('http') ? '_blank' : undefined, rel: 'noopener noreferrer' } : {};
  return (
    <Wrapper className="contact-card glass-panel" {...props}>
      <div className="contact-card-icon">
        <Icon size={20} />
      </div>
      <div>
        <strong>{title}</strong>
        <p>{value}</p>
      </div>
    </Wrapper>
  );
}

function ContactForm() {
  return (
    <form
      className="contact-form glass-panel"
      onSubmit={(e) => {
        e.preventDefault();
        // Simple mailto fallback — no backend endpoint needed
        const formData = new FormData(e.currentTarget);
        const subject = encodeURIComponent(`CheckMate AI Inquiry from ${formData.get('name')}`);
        const body = encodeURIComponent(`From: ${formData.get('name')} <${formData.get('email')}>\n\n${formData.get('message')}`);
        window.location.href = `mailto:checkmate.ai@fast.edu.pk?subject=${subject}&body=${body}`;
      }}
    >
      <h3>Send us a message</h3>
      <div className="contact-form-row">
        <div className="form-group">
          <label>Name</label>
          <input type="text" name="name" required className="input-field" placeholder="Your name" />
        </div>
        <div className="form-group">
          <label>Email</label>
          <input type="email" name="email" required className="input-field" placeholder="you@example.com" />
        </div>
      </div>
      <div className="form-group">
        <label>Message</label>
        <textarea name="message" required rows={4} className="input-field" placeholder="How can we help?" style={{ resize: 'vertical', fontFamily: 'inherit' }} />
      </div>
      <button type="submit" className="btn-primary" style={{ alignSelf: 'flex-start' }}>
        Send Message <ArrowRight size={16} />
      </button>
    </form>
  );
}
