import { useEffect, useState } from 'react';
import api from '../services/api';

/**
 * Top-of-page header for dashboards.
 * Left: page title + subtitle.
 * Right: greeting card with the user's name + role-aware welcome message.
 */
export default function WelcomeHeader({ title, subtitle }) {
  const [name, setName] = useState(() => localStorage.getItem('userName') || '');
  const [role, setRole] = useState(() => localStorage.getItem('role') || 'student');

  // If userName isn't in localStorage yet, fetch /auth/me silently
  useEffect(() => {
    if (name) return;
    let cancelled = false;
    api.get('/auth/me')
      .then(res => {
        if (cancelled) return;
        if (res.data?.name) {
          localStorage.setItem('userName', res.data.name);
          setName(res.data.name);
        }
        if (res.data?.role) {
          localStorage.setItem('role', res.data.role);
          setRole(res.data.role);
        }
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [name]);

  const hour = new Date().getHours();
  let greeting = 'Welcome back';
  if (hour < 12) greeting = 'Good morning';
  else if (hour < 17) greeting = 'Good afternoon';
  else if (hour < 21) greeting = 'Good evening';
  else greeting = 'Good night';

  const initials = (name || '?')
    .split(' ')
    .map(p => p[0])
    .join('')
    .slice(0, 2)
    .toUpperCase();

  return (
    <header
      className="dashboard-header"
      style={{
        display: 'flex',
        flexWrap: 'wrap',
        gap: '1rem',
        alignItems: 'center',
        justifyContent: 'space-between',
        marginBottom: '2.5rem',
      }}
    >
      <div>
        <h1 className="page-title">{title}</h1>
        {subtitle && <p className="page-subtitle">{subtitle}</p>}
      </div>

      <div
        className="glass-panel"
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '0.85rem',
          padding: '0.7rem 1rem',
          minWidth: '220px',
        }}
      >
        <div
          style={{
            width: 42,
            height: 42,
            borderRadius: '50%',
            background: 'linear-gradient(135deg, var(--accent-primary), #8B5CF6)',
            color: 'white',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontWeight: 700,
            fontSize: '0.95rem',
            flexShrink: 0,
          }}
        >
          {initials}
        </div>
        <div style={{ minWidth: 0 }}>
          <div
            style={{
              fontSize: '0.75rem',
              color: 'var(--text-secondary)',
              fontWeight: 500,
            }}
          >
            {greeting},
          </div>
          <div
            style={{
              fontSize: '1rem',
              fontWeight: 700,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {name || (role === 'admin' ? 'Admin' : role === 'teacher' ? 'Teacher' : 'Student')} 👋
          </div>
          <div
            style={{
              fontSize: '0.7rem',
              color: 'var(--text-secondary)',
              textTransform: 'capitalize',
            }}
          >
            Signed in as {role}
          </div>
        </div>
      </div>
    </header>
  );
}
