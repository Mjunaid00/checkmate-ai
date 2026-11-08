import { useEffect, useMemo, useState } from 'react';
import {
  ShieldCheck, Users, GraduationCap, UserCog, Plus, Trash2, KeyRound,
  Search, RefreshCw, Save, X, CheckCircle2, XCircle, BookOpen, CalendarClock, Eye,
} from 'lucide-react';
import api from '../services/api';
import DateTimeField from '../components/DateTimeField';
import { formatDate, formatDateTime, toDatetimeLocalValue, toApiDatetime, isPast, nowForDatetimeLocal } from '../utils/dateFormat';
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
          <p className="page-subtitle">Full control: every account (roles, emails, passwords, access), assignment and quiz deadlines, and student submissions.</p>
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
      <ClassOversightSection users={users} flash={flash} setError={setError} />
      <AuditLogSection />

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

function AuditLogSection() {
  const [entries, setEntries] = useState(null);
  useEffect(() => {
    api.get('/audit/', { params: { limit: 100 } }).then(r => setEntries(r.data)).catch(() => setEntries([]));
  }, []);
  const label = (a) => ({
    quiz_attempt_reset: 'Quiz retake allowed', submission_reset: 'Submission removed / resubmission allowed',
    assignment_updated: 'Assignment changed by admin', quiz_updated: 'Quiz changed by admin',
    user_updated: 'Account updated', password_reset: 'Password reset', user_deleted: 'Account deleted', user_created: 'Account created',
  }[a] || a);
  const target = (e) => {
    const d = e.details || {};
    const what = d.quiz_title || d.assignment_title || d.email || e.target_type;
    return d.student_id ? `${what} · student …${String(d.student_id).slice(-6)}` : what;
  };
  const fmtVal = (v) => {
    if (v === null || v === undefined || v === '') return 'none';
    if (typeof v === 'string' && /^\d{4}-\d{2}-\d{2}T/.test(v)) return formatDateTime(v);
    return String(v);
  };
  const changes = (e) => {
    const c = (e.details || {}).changes;
    if (!c || typeof c !== 'object') return '';
    return Object.entries(c).map(([k, v]) => `${k}: ${fmtVal(v.from)} → ${fmtVal(v.to)}`).join('; ');
  };
  return (
    <section className="glass-panel" style={{ padding: '1rem', marginTop: '1rem' }}>
      <h3 className="section-title" style={{ marginBottom: '0.25rem' }}>Audit log</h3>
      <p className="text-muted" style={{ fontSize: '0.82rem', marginBottom: '0.75rem' }}>
        Teacher and admin overrides (retakes, removed submissions, deadline changes on other teachers' work) with the reason given, and admin account actions.
      </p>
      {entries === null ? (
        <p className="text-muted">Loading...</p>
      ) : entries.length === 0 ? (
        <p className="text-muted">No overrides recorded yet.</p>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <table className="data-table" style={{ width: '100%' }}>
            <thead>
              <tr><th>When</th><th>Who</th><th>Action</th><th>Target</th><th>Reason / change</th></tr>
            </thead>
            <tbody>
              {entries.map(e => (
                <tr key={e.audit_id}>
                  <td style={{ whiteSpace: 'nowrap' }}>{formatDate(e.created_at)}</td>
                  <td>{e.actor_name} <span className="text-muted">({e.actor_role})</span></td>
                  <td>{label(e.action)}</td>
                  <td style={{ fontSize: '0.82rem' }}>{target(e)}</td>
                  <td style={{ fontSize: '0.85rem' }}>
                    {e.reason}
                    {changes(e) && <div className="text-muted" style={{ fontSize: '0.78rem' }}>{changes(e)}</div>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
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
    email: user.email || '',
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
        email: form.email.trim(),
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
        <Field label="Email">
          <input type="email" className="input-field" value={form.email}
            onChange={e => setForm(f => ({ ...f, email: e.target.value }))}
            required />
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

// ── Classes, deadlines and submissions (admin oversight) ─────────────────────
function ClassOversightSection({ users, flash, setError }) {
  const [classes, setClasses] = useState(null);
  const [selected, setSelected] = useState(null);
  const [assignments, setAssignments] = useState([]);
  const [quizzes, setQuizzes] = useState([]);
  const [subsFor, setSubsFor] = useState(null);
  const [subs, setSubs] = useState(null);
  const [deadlineTarget, setDeadlineTarget] = useState(null);

  const userName = (id) => users.find(u => u.id === id)?.name || `student …${String(id || '').slice(-6)}`;
  const loadClasses = () => api.get('/admin/classes').then(r => setClasses(r.data)).catch(() => setClasses([]));
  useEffect(() => { loadClasses(); }, []);

  const openClass = async (c) => {
    setSelected(c); setSubsFor(null); setSubs(null);
    try {
      const [a, q] = await Promise.all([api.get(`/assignments/class/${c.class_id}`), api.get(`/quizzes/class/${c.class_id}`)]);
      setAssignments(a.data); setQuizzes(q.data);
    } catch (err) { setError(err.response?.data?.detail || 'Could not load the class.'); }
  };
  const reloadClass = () => selected && openClass(selected);

  const showSubs = async (a) => {
    setSubsFor(a); setSubs(null);
    try { const r = await api.get(`/submissions/assignment/${a.assignment_id}`); setSubs(r.data); }
    catch (err) { setError(err.response?.data?.detail || 'Could not load submissions.'); setSubs([]); }
  };

  const removeSub = async (sub) => {
    const reason = window.prompt(`Remove the submission of ${userName(sub.student_id)} for "${subsFor.title}"?\nGive the reason for the audit log (the student is notified and may upload again):`);
    if (reason === null) return;
    try {
      await api.post(`/submissions/${sub.submission_id}/allow-resubmission`, { reason });
      flash('Submission removed; the student may upload again.');
      showSubs(subsFor);
    } catch (err) { setError(err.response?.data?.detail || 'Could not remove the submission.'); }
  };

  const statusPill = (st) => <span style={{ fontSize: '0.75rem', fontWeight: 700, textTransform: 'uppercase' }}>{st || '—'}</span>;

  // The modal is rendered outside the glass-panel: its backdrop-filter would otherwise become the
  // containing block of the fixed-position dialog and push it out of the viewport.
  return (
    <>
    <section className="glass-panel" style={{ padding: '1rem', marginTop: '1rem' }}>
      <h3 className="section-title" style={{ marginBottom: '0.25rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        <BookOpen size={18} /> Classes, deadlines and submissions
      </h3>
      <p className="text-muted" style={{ fontSize: '0.82rem', marginBottom: '0.75rem' }}>
        Every class in the system. Open one to change assignment or quiz deadlines (the teacher is notified) and to review or remove student submissions on request. Each change needs a reason and is written to the audit log.
      </p>
      {classes === null ? <p className="text-muted">Loading...</p> : classes.length === 0 ? <p className="text-muted">No classes yet.</p> : (
        <div style={{ overflowX: 'auto' }}>
          <table className="data-table" style={{ width: '100%' }}>
            <thead><tr><th>Class</th><th>Teacher</th><th>Students</th><th>Assignments</th><th>Quizzes</th><th style={{ textAlign: 'right' }}></th></tr></thead>
            <tbody>
              {classes.map(c => (
                <tr key={c.class_id} style={{ background: selected?.class_id === c.class_id ? 'var(--accent-soft)' : undefined }}>
                  <td><strong>{c.name}</strong></td>
                  <td>{c.teacher_name || '—'} <span className="text-muted" style={{ fontSize: '0.78rem' }}>{c.teacher_email}</span></td>
                  <td>{c.student_count}</td>
                  <td>{c.assignment_count}</td>
                  <td>{c.quiz_count}</td>
                  <td style={{ textAlign: 'right' }}>
                    <button className="btn-secondary" onClick={() => openClass(c)} style={{ padding: '0.35rem 0.7rem', fontSize: '0.82rem' }}>
                      <Eye size={14} /> {selected?.class_id === c.class_id ? 'Reload' : 'Open'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {selected && (
        <div style={{ marginTop: '1rem', display: 'grid', gap: '1rem' }}>
          <div>
            <h4 style={{ fontSize: '0.95rem', marginBottom: '0.5rem' }}>Assignments in {selected.name}</h4>
            {assignments.length === 0 ? <p className="text-muted" style={{ fontSize: '0.85rem' }}>No assignments.</p> : (
              <table className="data-table" style={{ width: '100%' }}>
                <thead><tr><th>Title</th><th>Marks</th><th>Deadline</th><th style={{ textAlign: 'right' }}>Actions</th></tr></thead>
                <tbody>
                  {assignments.map(a => (
                    <tr key={a.assignment_id}>
                      <td><strong>{a.title}</strong></td>
                      <td>{a.total_marks}</td>
                      <td>{a.deadline ? formatDateTime(a.deadline) : <span className="text-muted">none</span>}</td>
                      <td style={{ textAlign: 'right' }}>
                        <div style={{ display: 'inline-flex', gap: '0.3rem' }}>
                          <button className="btn-secondary" onClick={() => setDeadlineTarget({ kind: 'assignment', item: a })} style={{ padding: '0.35rem 0.6rem', fontSize: '0.82rem' }}>
                            <CalendarClock size={14} /> Deadline
                          </button>
                          <button className="btn-secondary" onClick={() => showSubs(a)} style={{ padding: '0.35rem 0.6rem', fontSize: '0.82rem' }}>
                            <Eye size={14} /> Submissions
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {subsFor && (
            <div className="glass-panel" style={{ padding: '0.85rem' }}>
              <h4 style={{ fontSize: '0.95rem', marginBottom: '0.5rem' }}>Submissions for "{subsFor.title}"</h4>
              {subs === null ? <p className="text-muted">Loading...</p> : subs.length === 0 ? <p className="text-muted" style={{ fontSize: '0.85rem' }}>No submissions yet.</p> : (
                <table className="data-table" style={{ width: '100%' }}>
                  <thead><tr><th>Student</th><th>Submitted</th><th>Status</th><th>Score</th><th style={{ textAlign: 'right' }}></th></tr></thead>
                  <tbody>
                    {subs.map(sub => (
                      <tr key={sub.submission_id}>
                        <td>{userName(sub.student_id)}</td>
                        <td>{sub.created_at ? formatDateTime(sub.created_at) : '—'}</td>
                        <td>{statusPill(sub.status)}</td>
                        <td>{sub.score ?? '—'}</td>
                        <td style={{ textAlign: 'right' }}>
                          <button className="btn-secondary" onClick={() => removeSub(sub)} style={{ padding: '0.35rem 0.6rem', fontSize: '0.82rem', color: 'var(--danger)' }} title="Remove this submission so the student can upload again">
                            <Trash2 size={14} /> Remove
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}

          <div>
            <h4 style={{ fontSize: '0.95rem', marginBottom: '0.5rem' }}>Quizzes in {selected.name}</h4>
            {quizzes.length === 0 ? <p className="text-muted" style={{ fontSize: '0.85rem' }}>No quizzes.</p> : (
              <table className="data-table" style={{ width: '100%' }}>
                <thead><tr><th>Title</th><th>Questions</th><th>Time limit</th><th>Deadline</th><th style={{ textAlign: 'right' }}>Actions</th></tr></thead>
                <tbody>
                  {quizzes.map(q => (
                    <tr key={q.quiz_id}>
                      <td><strong>{q.title}</strong></td>
                      <td>{q.question_count ?? (q.questions || []).length}</td>
                      <td>{q.time_limit_minutes} min</td>
                      <td>{q.deadline ? formatDateTime(q.deadline) : <span className="text-muted">none</span>}</td>
                      <td style={{ textAlign: 'right' }}>
                        <button className="btn-secondary" onClick={() => setDeadlineTarget({ kind: 'quiz', item: q })} style={{ padding: '0.35rem 0.6rem', fontSize: '0.82rem' }}>
                          <CalendarClock size={14} /> Deadline
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}

    </section>
    {deadlineTarget && (
      <ChangeDeadlineModal
        target={deadlineTarget}
        onClose={() => setDeadlineTarget(null)}
        onSaved={() => { setDeadlineTarget(null); flash('Deadline changed; the teacher has been notified.'); reloadClass(); }}
      />
    )}
    </>
  );
}

function ChangeDeadlineModal({ target, onClose, onSaved }) {
  const { kind, item } = target;
  const [value, setValue] = useState(item.deadline ? toDatetimeLocalValue(item.deadline) : '');
  const [reason, setReason] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setError('');
    if (reason.trim().length < 3) { setError('Give a reason (at least 3 characters); it goes into the audit log.'); return; }
    if (value && isPast(value)) { setError('Deadline cannot be in the past.'); return; }
    setBusy(true);
    try {
      if (kind === 'assignment') {
        await api.patch(`/assignments/${item.assignment_id}`, null, { params: { deadline: value ? toApiDatetime(value) : 'none', reason: reason.trim() } });
      } else {
        await api.patch(`/quizzes/${item.quiz_id}`, { deadline: value ? toApiDatetime(value) : '', reason: reason.trim() });
      }
      onSaved();
    } catch (err) {
      setError(err.response?.data?.detail || 'Save failed.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal title={`Change deadline: ${item.title}`} onClose={onClose}>
      {error && <div className="error-banner">{error}</div>}
      <form onSubmit={submit} style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
        <Field label={`New ${kind} deadline (leave empty to remove it)`}>
          <DateTimeField value={value} min={nowForDatetimeLocal()} onChange={setValue} />
        </Field>
        <Field label="Reason (shown to the teacher and kept in the audit log)">
          <input type="text" className="input-field" value={reason} onChange={e => setReason(e.target.value)} placeholder="e.g. Extension requested by the class" required />
        </Field>
        <div className="modal-actions">
          <button type="button" className="btn-secondary" onClick={onClose}>Cancel</button>
          <button type="submit" className="btn-primary" disabled={busy}>
            <Save size={16} /> {busy ? 'Saving...' : 'Save deadline'}
          </button>
        </div>
      </form>
    </Modal>
  );
}
