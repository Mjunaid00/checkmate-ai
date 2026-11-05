import { useEffect, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import api, { API_BASE_URL } from '../services/api';
import './Login.css';

// Name: only letters/digits/underscore are allowed AND it must contain at
// least three letters. The lookahead `(?=(?:[^A-Za-z]*[A-Za-z]){3,})` skips
// non-letters and counts three letter occurrences anywhere in the string.
const NAME_REGEX = /^(?=(?:[^A-Za-z]*[A-Za-z]){3,})[A-Za-z0-9_]+$/;
const NAME_PATTERN = '^(?=(?:[^A-Za-z]*[A-Za-z]){3,})[A-Za-z0-9_]+$';

const PLACEHOLDERS = {
  student: {
    name: 'e.g. John Doe (student)',
    email: 'student@university.edu',
    password: 'Your student password',
  },
  teacher: {
    name: 'e.g. Prof. John Doe',
    email: 'teacher@university.edu',
    password: 'Your teacher password',
  },
  admin: {
    name: 'e.g. Admin User',
    email: 'admin@checkmate.ai',
    password: 'Admin password',
  },
};

export default function Login({ setAuth, defaultRegister = false }) {
  const navigate = useNavigate();
  const location = useLocation();
  const [isRegister, setIsRegister] = useState(defaultRegister);
  const [formData, setFormData] = useState({ name: '', email: '', password: '', role: 'student' });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  // /login and /register both render this same component instance, so the
  // `defaultRegister` prop alone wouldn't flip the form when the user clicks
  // "Get Started" from inside /login. Sync on pathname change instead.
  useEffect(() => {
    setIsRegister(location.pathname === '/register');
    setError('');
  }, [location.pathname]);

  const ph = PLACEHOLDERS[formData.role] || PLACEHOLDERS.student;

  const handleNameChange = (raw) => {
    // Strip every character except letters, digits, and underscore so the user
    // can't even type illegal characters. Validation below ensures it contains
    // at least one letter before submission.
    const cleaned = raw.replace(/[^A-Za-z0-9_]/g, '');
    setFormData({ ...formData, name: cleaned });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (isRegister) {
      const name = formData.name.trim();
      if (!name) {
        setError('Please enter your full name.');
        return;
      }
      if (!NAME_REGEX.test(name)) {
        setError('Name must contain at least 3 letters. Only letters, numbers, and underscore (_) are allowed — no other special characters or all-digit names.');
        return;
      }
    }

    setLoading(true);

    try {
      if (isRegister) {
        await api.post('/auth/register', {
          name: formData.name.trim(),
          email: formData.email,
          password: formData.password,
          role: formData.role,
        });
      }

      const form = new FormData();
      form.append('username', formData.email);
      form.append('password', formData.password);

      const res = await api.post('/auth/login', form);
      localStorage.setItem('token', res.data.access_token);
      localStorage.setItem('role', res.data.role);

      // Fetch and cache the user id (needed for messaging)
      try {
        const me = await api.get('/auth/me');
        if (me.data?.id) localStorage.setItem('userId', me.data.id);
        if (me.data?.name) localStorage.setItem('userName', me.data.name);
      } catch {}

      setAuth(true);
    } catch (err) {
      if (err?.code === 'ERR_NETWORK' || err?.message === 'Network Error') {
        setError(`Cannot reach the server at ${API_BASE_URL}. Make sure the backend is running.`);
      } else {
        setError(err.response?.data?.detail || 'An error occurred during authentication.');
      }
    } finally {
      setLoading(false);
    }
  };

  const toggleMode = () => {
    const next = !isRegister;
    setIsRegister(next);
    navigate(next ? '/register' : '/login', { replace: true });
  };

  return (
    <div className="login-wrapper fade-in">
      <Link to="/" className="login-back-link">← Back to home</Link>

      <div className="login-card glass-panel">
        <h1 className="login-title">CheckMate AI</h1>
        <p className="login-subtitle">{isRegister ? 'Create your account' : 'Welcome back'}</p>

        {error && <div className="error-banner">{error}</div>}

        <form onSubmit={handleSubmit} className="login-form">
          <div className="form-group">
            <label>I am a...</label>
            <select
              className="input-field"
              value={formData.role}
              onChange={(e) => setFormData({ ...formData, role: e.target.value })}
            >
              <option value="student">Student</option>
              <option value="teacher">Teacher</option>
              {!isRegister && <option value="admin">Admin</option>}
            </select>
          </div>

          {isRegister && (
            <div className="form-group">
              <label>Full Name</label>
              <input
                type="text"
                className="input-field"
                placeholder={ph.name}
                value={formData.name}
                onChange={(e) => handleNameChange(e.target.value)}
                pattern={NAME_PATTERN}
                title="Letters, numbers, and underscore (_) only. Must contain at least 3 letters."
                required
              />
              <small style={{ color: 'var(--text-secondary)', fontSize: '0.75rem' }}>
                Letters, numbers, and underscore (_) only. Must include at least 3 letters.
              </small>
            </div>
          )}

          <div className="form-group">
            <label>Email Address</label>
            <input
              type="email"
              className="input-field"
              required
              placeholder={ph.email}
              value={formData.email}
              onChange={(e) => setFormData({ ...formData, email: e.target.value })}
            />
          </div>

          <div className="form-group">
            <label>Password</label>
            <input
              type="password"
              className="input-field"
              required
              placeholder={ph.password}
              value={formData.password}
              onChange={(e) => setFormData({ ...formData, password: e.target.value })}
            />
          </div>

          <button type="submit" className="btn-primary login-btn" disabled={loading}>
            {loading ? 'Processing...' : (isRegister ? 'Create Account' : 'Sign In')}
          </button>
        </form>

        <p className="toggle-auth">
          {isRegister ? "Already have an account? " : "New to CheckMate? "}
          <span className="toggle-link" onClick={toggleMode}>
            {isRegister ? "Sign In" : "Register"}
          </span>
        </p>
      </div>
    </div>
  );
}
