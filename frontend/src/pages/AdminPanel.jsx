import { useEffect, useMemo, useState } from 'react';
import {
  ShieldCheck, Users, GraduationCap, UserCog, Plus, Trash2, KeyRound,
  Search, RefreshCw, Save, X, CheckCircle2, XCircle,
} from 'lucide-react';
import api from '../services/api';
import { formatDate } from '../utils/dateFormat';
import './Dashboard.css';

const ROLES = ['student', 'teacher', 'admin'];

export default function AdminPanel() {
  const [stats, setStats] = useState(null);
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState('');
  const [error, setError] = useState('');
  const [info, setInfo] = useState('');

  const [showCreate, setShowCreate] = useState(false);
  const [editingUser, setEditingUser] = useState(null);
  const [resetting, setResetting] = useState(null);

  const myId = typeof window !== 'undefined' ? localStorage.getItem('userId') : null;

  const fetchAll = async () => {
    setLoading(true);
    setError('');
    try {
      const [s, u] = await Promise.all([
        api.get('/admin/stats'),
        api.get('/admin/users', {
          params: {
            ...(roleFilter ? { role: roleFilter } : {}),
            ...(search.trim() ? { q: search.trim() } : {}),
          },
        }),
      ]);
      setStats(s.data);
      setUsers(u.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load admin data.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchAll(); /* eslint-disable-next-line */ }, []);
  useEffect(() => {
    const t = setTimeout(fetchAll, 250);
    return () => clearTimeout(t);
    // eslint-disable-next-line
  }, [search, roleFilter]);

  const flash = (msg) => {
    setInfo(msg);
    setTimeout(() => setInfo(''), 2500);
  };

  const handleDelete = async (u) => {
    if (!window.confirm(`Delete ${u.name} (${u.email})? This removes their data too.`)) return;
    try {
      await api.delete(`/admin/users/${u.id}`);
      flash('Account deleted.');
      fetchAll();
    } catch (err) {
      setError(err.response?.data?.detail || 'Delete failed.');
    }
  };

  const handleToggleActive = async (u) => {
    try {
      await api.patch(`/admin/users/${u.id}`, { is_active: !u.is_active });
      flash(`${u.email} ${u.is_active ? 'deactivated' : 'activated'}.`);
      fetchAll();
    } catch (err) {
      setError(err.response?.data?.detail || 'Update failed.');
    }
  };

  const rolePill = (role) => {
    const palette = {
      admin:   { bg: '#FEE2E2', fg: '#B91C1C' },
      teacher: { bg: '#DBEAFE', fg: '#1D4ED8' },
      student: { bg: '#DCFCE7', fg: '#15803D' },
    }[role] || { bg: '#E5E7EB', fg: '#374151' };
    return (
      <span style={{
        fontSize: '0.72rem', fontWeight: 700, padding: '0.15rem 0.5rem',
        borderRadius: '999px', textTransform: 'uppercase', letterSpacing: '0.04em',
        background: palette.bg, color: palette.fg,
      }}>
        {role}
      </span>
    );
  };

  const sortedUsers = useMemo(() => {
    // Pin yourself (the current admin) at the top so it's easy to find/avoid.
    return [...users].sort((a, b) => {
      if (a.id === myId) return -1;
      if (b.id === myId) return 1;
      return 0;
    });
  }, [users, myId]);

  if (loading && !users.length) return <div className="loading-state">Loading admin panel...</div>;

  return (
    <div className="dashboard-wrapper fade-in">
      <header className="dashboard-header">
        <div>
          <h1 className="page-title" style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
            <ShieldCheck size={24} /> Admin Panel
          </h1>
          <p className="page-subtitle">Manage every account in the system: roles, passwords, and access.</p>
        </div>
        <button className="btn-secondary" onClick={fetchAll} title="Refresh">
          <RefreshCw size={16} /> Refresh
        </button>
      </header>

      {error && <div className="error-banner">{error}</div>}
      {info && (
        <div style={{ padding: '0.6rem 1rem', borderRadius: '0.5rem', background: 'var(--accent-soft)', color: 'var(--accent-primary)', marginBottom: '1rem', fontSize: '0.9rem' }}>
          {info}
        </div>
      )}

      {/* ── Stat cards ─────────────────────────────────── */}
      {stats && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '0.85rem', marginBottom: '1.25rem' }}>
          <StatCard icon={Users} label="Total users" value={stats.users.total} />
          <StatCard icon={GraduationCap} label="Students" value={stats.users.students} />
          <StatCard icon={UserCog} label="Teachers" value={stats.users.teachers} />
          <StatCard icon={ShieldCheck} label="Admins" value={stats.users.admins} />
          <StatCard label="Classes" value={stats.classes} />
          <StatCard label="Assignments" value={stats.assignments} />
          <StatCard label="Quizzes" value={stats.quizzes} />
        </div>
      )}

      {/* ── Controls ───────────────────────────────────── */}
      <section className="glass-panel" style={{ padding: '1rem', marginBottom: '1rem' }}>
        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', alignItems: 'center' }}>
          <div style={{ position: 'relative', flex: 1, minWidth: '220px' }}>
            <Search size={15} style={{ position: 'absolute', left: '0.65rem', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-secondary)' }} />
            <input
              type="text"
              className="input-field"
              placeholder="Search by name or email"
              value={search}
              onChange={e => setSearch(e.target.value)}
              style={{ paddingLeft: '2rem' }}
            />
          </div>
          <select className="input-field" value={roleFilter} onChange={e => setRoleFilter(e.target.value)} style={{ maxWidth: '180px' }}>
            <option value="">All roles</option>
            {ROLES.map(r => <option key={r} value={r}>{r[0].toUpperCase() + r.slice(1)}s</option>)}
          </select>
          <button className="btn-primary" onClick={() => setShowCreate(true)}>
            <Plus size={16} /> New User
          </button>
        </div>
      </section>

      {/* ── User table ─────────────────────────────────── */}
      <section className="glass-panel" style={{ padding: 0, overflow: 'hidden' }}>
        <div style={{ overflowX: 'auto' }}>
          <table className="data-table" style={{ width: '100%' }}>
            <thead>
              <tr>
                <th>Name</th>
                <th>Email</th>
                <th>Role</th>
                <th>Institution</th>
                <th>Status</th>
                <th>Created</th>
                <th style={{ textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {sortedUsers.length === 0 && (
                <tr><td colSpan={7} className="text-muted" style={{ textAlign: 'center', padding: '1.5rem' }}>No users found.</td></tr>
              )}
              {sortedUsers.map(u => (
                <tr key={u.id} style={{ opacity: u.is_active === false ? 0.55 : 1 }}>
                  <td>
                    <strong>{u.name}</strong>{u.id === myId && <span className="text-muted" style={{ marginLeft: '0.4rem', fontSize: '0.78rem' }}>(you)</span>}
                  </td>
                  <td>{u.email}</td>
                  <td>{rolePill(u.role)}</td>
                  <td>{u.institution || <span className="text-muted">—</span>}</td>
                  <td>
                    {u.is_active === false ? (
                      <span style={{ color: 'var(--danger)', fontSize: '0.82rem', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                        <XCircle size={13} /> Disabled
                      </span>
                    ) : (
                      <span style={{ color: 'var(--success)', fontSize: '0.82rem', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                        <CheckCircle2 size={13} /> Active
                      </span>
                    )}
                  </td>
                  <td>{u.created_at ? formatDate(u.created_at) : '—'}</td>
                  <td style={{ textAlign: 'right' }}>
                    <div style={{ display: 'inline-flex', gap: '0.3rem' }}>
                      <button className="btn-secondary" title="Edit" onClick={() => setEditingUser(u)} style={{ padding: '0.35rem 0.55rem' }}>
                        <UserCog size={14} />
                      </button>
                      <button className="btn-secondary" title="Reset password" onClick={() => setResetting(u)} style={{ padding: '0.35rem 0.55rem' }}>
                        <KeyRound size={14} />
                      </button>
                      <button className="btn-secondary" title={u.is_active === false ? 'Activate' : 'Deactivate'} onClick={() => handleToggleActive(u)} style={{ padding: '0.35rem 0.55rem' }}>
                        {u.is_active === false ? <CheckCircle2 size={14} /> : <XCircle size={14} />}
                      </button>
                      <button className="btn-secondary" title="Delete" onClick={() => handleDelete(u)} style={{ padding: '0.35rem 0.55rem', color: 'var(--danger)' }}>
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {showCreate && (
        <CreateUserModal
          onClose={() => setShowCreate(false)}
          onCreated={() => { setShowCreate(false); flash('User created.'); fetchAll(); }}
        />
      )}
      {editingUser && (
        <EditUserModal
          user={editingUser}
          onClose={() => setEditingUser(null)}
          onSaved={() => { setEditingUser(null); flash('User updated.'); fetchAll(); }}
        />
      )}
      {resetting && (
        <ResetPasswordModal
          user={resetting}
          onClose={() => setResetting(null)}
          onSaved={() => { setResetting(null); flash('Password reset.'); }}
        />
      )}
    </div>
  );
}

function StatCard({ icon: Icon, label, value }) {
  return (
    <div className="glass-panel" style={{ padding: '0.9rem 1rem' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.78rem', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
        {Icon && <Icon size={14} />} {label}
      </div>
      <div style={{ fontSize: '1.5rem', fontWeight: 700, marginTop: '0.2rem' }}>{value ?? '—'}</div>
    </div>
  );
}

// Must contain at least 3 letters; only letters/digits/underscore allowed.
const NAME_REGEX = /^(?=(?:[^A-Za-z]*[A-Za-z]){3,})[A-Za-z0-9_]+$/;
const NAME_HELP = 'Name must contain at least 3 letters. Only letters, numbers, and underscore (_) are allowed.';

function CreateUserModal({ onClose, onCreated }) {
  const [form, setForm] = useState({ name: '', email: '', password: '', role: 'student' });
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setError('');
    const cleaned = form.name.trim();
    if (!NAME_REGEX.test(cleaned)) {
      setError(NAME_HELP);
      return;
    }
    if (form.password.length < 6) {
      setError('Password must be at least 6 characters.');
      return;
    }
    setBusy(true);
    try {
      await api.post('/admin/users', { ...form, name: cleaned });
      onCreated();
    } catch (err) {
      setError(err.response?.data?.detail || 'Create failed.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal title="Create User" onClose={onClose}>
      {error && <div className="error-banner">{error}</div>}
      <form onSubmit={submit} style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
        <Field label="Full Name">
          <input type="text" className="input-field" value={form.name}
            onChange={e => setForm(f => ({ ...f, name: e.target.value.replace(/[^A-Za-z0-9_]/g, '') }))}
            required />
          <small className="text-muted">Letters, numbers, and underscore only. At least 3 letters.</small>
        </Field>
        <Field label="Email">
          <input type="email" className="input-field" value={form.email}
            onChange={e => setForm(f => ({ ...f, email: e.target.value }))} required />
        </Field>
        <Field label="Password">
          <input type="text" className="input-field" value={form.password} minLength={6}
            onChange={e => setForm(f => ({ ...f, password: e.target.value }))} required />
        </Field>
        <Field label="Role">
          <select className="input-field" value={form.role}
            onChange={e => setForm(f => ({ ...f, role: e.target.value }))}>
            {ROLES.map(r => <option key={r} value={r}>{r[0].toUpperCase() + r.slice(1)}</option>)}
          </select>
        </Field>
        <div className="modal-actions">
          <button type="button" className="btn-secondary" onClick={onClose}>Cancel</button>
          <button type="submit" className="btn-primary" disabled={busy}>
            <Plus size={16} /> {busy ? 'Creating...' : 'Create'}
          </button>
        </div>
      </form>
    </Modal>
  );
}

function EditUserModal({ user, onClose, onSaved }) {
  const [form, setForm] = useState({
    name: user.name || '',
    role: user.role,
    institution: user.institution || '',
    is_active: user.is_active !== false,
  });
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setError('');
    if (!NAME_REGEX.test(form.name.trim())) {
      setError(NAME_HELP);
      return;
    }
    setBusy(true);
    try {
      await api.patch(`/admin/users/${user.id}`, {
        name: form.name.trim(),
        role: form.role,
        institution: form.institution.trim() || null,
        is_active: form.is_active,
      });
      onSaved();
    } catch (err) {
      setError(err.response?.data?.detail || 'Save failed.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal title={`Edit ${user.email}`} onClose={onClose}>
      {error && <div className="error-banner">{error}</div>}
      <form onSubmit={submit} style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
        <Field label="Full Name">
          <input type="text" className="input-field" value={form.name}
            onChange={e => setForm(f => ({ ...f, name: e.target.value.replace(/[^A-Za-z0-9_]/g, '') }))}
            required />
        </Field>
        <Field label="Role">
          <select className="input-field" value={form.role}
            onChange={e => setForm(f => ({ ...f, role: e.target.value }))}>
            {ROLES.map(r => <option key={r} value={r}>{r[0].toUpperCase() + r.slice(1)}</option>)}
          </select>
        </Field>
        <Field label="Institution">
          <input type="text" className="input-field" value={form.institution}
            onChange={e => setForm(f => ({ ...f, institution: e.target.value }))} />
        </Field>
        <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}>
          <input type="checkbox" checked={form.is_active}
            onChange={e => setForm(f => ({ ...f, is_active: e.target.checked }))}
            style={{ width: 16, height: 16 }} />
          Active (can sign in)
        </label>
        <div className="modal-actions">
          <button type="button" className="btn-secondary" onClick={onClose}>Cancel</button>
          <button type="submit" className="btn-primary" disabled={busy}>
            <Save size={16} /> {busy ? 'Saving...' : 'Save'}
          </button>
        </div>
      </form>
    </Modal>
  );
}

function ResetPasswordModal({ user, onClose, onSaved }) {
  const [pwd, setPwd] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    if (pwd.length < 6) { setError('Password must be at least 6 characters.'); return; }
    setBusy(true);
    try {
      await api.post(`/admin/users/${user.id}/password`, { new_password: pwd });
      onSaved();
    } catch (err) {
      setError(err.response?.data?.detail || 'Reset failed.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal title={`Reset password — ${user.email}`} onClose={onClose}>
      {error && <div className="error-banner">{error}</div>}
      <form onSubmit={submit} style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
        <Field label="New Password">
          <input type="text" className="input-field" value={pwd} minLength={6}
            onChange={e => setPwd(e.target.value)} placeholder="At least 6 characters" required />
        </Field>
        <div className="modal-actions">
          <button type="button" className="btn-secondary" onClick={onClose}>Cancel</button>
          <button type="submit" className="btn-primary" disabled={busy}>
            <KeyRound size={16} /> {busy ? 'Saving...' : 'Set Password'}
          </button>
        </div>
      </form>
    </Modal>
  );
}

function Modal({ title, onClose, children }) {
  return (
    <div className="modal-overlay fade-in">
      <div className="modal-content glass-panel" style={{ maxWidth: '480px' }}>
        <button className="close-btn" onClick={onClose}><X size={20} /></button>
        <h2 style={{ marginBottom: '0.75rem' }}>{title}</h2>
        {children}
      </div>
    </div>
  );
}

function Field({ label, children }) {
  return (
    <div>
      <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: '0.35rem' }}>
        {label}
      </label>
      {children}
    </div>
  );
}
