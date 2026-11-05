import { useState, useEffect } from 'react';
import { PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';
import { Clock, CheckCircle, XCircle, FileText, ClipboardCheck, ScanLine, AlertTriangle } from 'lucide-react';
import api from '../services/api';
import { formatDateShort, formatDateTime } from '../utils/dateFormat';

/**
 * DeadlinesWidget — graph + list of upcoming/closed/completed work.
 * Student mode: tracks "completed" by their own submissions/attempts.
 * Teacher mode: tracks per-item submission rate.
 */
export default function DeadlinesWidget({ isStudent }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [tick, setTick] = useState(0);  // forces countdown re-render

  useEffect(() => {
    let cancelled = false;
    const url = isStudent ? '/analytics/student/deadlines' : '/analytics/teacher/deadlines';
    const load = async () => {
      try {
        const res = await api.get(url);
        if (!cancelled) setData(res.data);
      } catch (err) {
        if (!cancelled) setError(err.response?.data?.detail || 'Failed to load deadlines.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    load();
    return () => { cancelled = true; };
  }, [isStudent]);

  // Tick every minute so countdowns update
  useEffect(() => {
    const t = setInterval(() => setTick(x => x + 1), 60000);
    return () => clearInterval(t);
  }, []);

  if (loading) {
    return (
      <section className="glass-panel" style={{ padding: '1.5rem', marginBottom: '2rem' }}>
        <p className="text-muted" style={{ textAlign: 'center' }}>Loading deadlines...</p>
      </section>
    );
  }
  // Fail silently: if the data couldn't load (e.g. role mismatch),
  // don't surface an error banner — just hide the widget.
  if (error || !data) return null;

  const { items, stats } = data;

  // Pie chart data — student has 3 categories, teacher has 2
  const pieData = isStudent
    ? [
        { name: 'Open', value: stats.open, color: 'var(--accent-primary)' },
        { name: 'Completed', value: stats.completed, color: 'var(--success)' },
        { name: 'Closed', value: stats.closed, color: 'var(--danger)' },
      ].filter(d => d.value > 0)
    : [
        { name: 'Open', value: stats.open, color: 'var(--accent-primary)' },
        { name: 'Closed', value: stats.closed, color: 'var(--danger)' },
      ].filter(d => d.value > 0);

  // Bar chart: number of items by deadline day (next 14 days)
  const dayBuckets = {};
  const now = new Date();
  for (let i = 0; i < 14; i++) {
    const d = new Date(now);
    d.setHours(0, 0, 0, 0);
    d.setDate(d.getDate() + i);
    dayBuckets[localDateKey(d)] = 0;
  }
  for (const it of items) {
    if (!it.deadline || it.status !== 'open') continue;
    const dl = new Date(it.deadline);
    const key = localDateKey(dl);
    if (key in dayBuckets) dayBuckets[key]++;
  }
  const barData = Object.entries(dayBuckets).map(([date, count]) => ({
    date,
    count,
    label: formatDateShort(`${date}T00:00`),
  }));

  const showItems = isStudent ? items.slice(0, 8) : items.slice(0, 8);

  return (
    <section className="glass-panel" style={{ padding: '1.5rem', marginBottom: '2rem' }}>
      <h3 className="section-title" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        <Clock size={18} /> {isStudent ? 'My Deadlines' : 'Class Deadlines'}
      </h3>

      {stats.total === 0 ? (
        <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-secondary)' }}>
          <p>No assignments, quizzes, or OMR sheets {isStudent ? 'in your enrolled classes' : 'created yet'}.</p>
        </div>
      ) : (
        <>
          {/* ── Stat tiles ────────────────────────────────────── */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '0.6rem', marginBottom: '1.25rem' }}>
            <Tile icon={Clock} label="Total" value={stats.total} color="#6366F1" />
            <Tile icon={AlertTriangle} label="Open" value={stats.open} color="#3B82F6" />
            {isStudent && <Tile icon={CheckCircle} label="Completed" value={stats.completed} color="#10B981" />}
            <Tile icon={XCircle} label="Closed" value={stats.closed} color="#EF4444" />
          </div>

          {/* ── Charts row ────────────────────────────────────── */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1rem', marginBottom: '1.5rem' }}>
            {/* Status distribution pie */}
            {pieData.length > 0 && (
              <div style={{ height: 220, padding: '0.5rem', borderRadius: '0.5rem', background: 'var(--bg-tertiary)' }}>
                <p style={{ fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.4rem', textAlign: 'center' }}>
                  Status Distribution
                </p>
                <ResponsiveContainer width="100%" height="85%">
                  <PieChart>
                    <Pie
                      data={pieData}
                      dataKey="value"
                      nameKey="name"
                      cx="50%"
                      cy="50%"
                      innerRadius={40}
                      outerRadius={70}
                      paddingAngle={3}
                    >
                      {pieData.map((entry, i) => (
                        <Cell key={i} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: 'var(--shadow-md)', background: 'var(--bg-secondary)' }} />
                  </PieChart>
                </ResponsiveContainer>
                <div style={{ display: 'flex', justifyContent: 'center', gap: '0.6rem', flexWrap: 'wrap', fontSize: '0.75rem', marginTop: '-0.5rem' }}>
                  {pieData.map((d, i) => (
                    <span key={i} style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}>
                      <span style={{ width: 8, height: 8, borderRadius: '50%', background: d.color }} />
                      {d.name}: {d.value}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Deadlines per day bar */}
            <div style={{ height: 220, padding: '0.5rem', borderRadius: '0.5rem', background: 'var(--bg-tertiary)' }}>
              <p style={{ fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.4rem', textAlign: 'center' }}>
                Open Deadlines — Next 14 Days
              </p>
              <ResponsiveContainer width="100%" height="85%">
                <BarChart data={barData}>
                  <XAxis dataKey="label" fontSize={10} stroke="var(--text-secondary)" tickLine={false} axisLine={false} interval={1} />
                  <YAxis fontSize={10} stroke="var(--text-secondary)" tickLine={false} axisLine={false} allowDecimals={false} />
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border-color)" />
                  <Tooltip contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: 'var(--shadow-md)', background: 'var(--bg-secondary)' }} />
                  <Bar dataKey="count" fill="var(--accent-primary)" radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* ── Items list with countdown ───────────────────── */}
          <div>
            <h4 style={{ fontSize: '0.92rem', marginBottom: '0.5rem', color: 'var(--text-secondary)' }}>
              {isStudent ? 'Upcoming & Recent' : 'Active Items'} ({Math.min(showItems.length, 8)})
            </h4>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              {showItems.map(item => (
                <DeadlineRow key={`${item.type}-${item.id}`} item={item} isStudent={isStudent} />
              ))}
              {showItems.length === 0 && <p className="text-muted">Nothing here yet.</p>}
            </div>
          </div>
        </>
      )}
    </section>
  );
}

function Tile({ icon: Icon, label, value, color }) {
  return (
    <div style={{ padding: '0.75rem 0.9rem', borderRadius: '0.5rem', border: '1px solid var(--border-color)', background: 'var(--bg-tertiary)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: 'var(--text-secondary)', fontSize: '0.7rem', fontWeight: 600, marginBottom: '0.2rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
        <Icon size={11} style={{ color }} /> {label}
      </div>
      <div style={{ fontSize: '1.4rem', fontWeight: 700 }}>{value}</div>
    </div>
  );
}

function DeadlineRow({ item, isStudent }) {
  const TypeIcon = item.type === 'assignment' ? FileText : item.type === 'quiz' ? ClipboardCheck : ScanLine;
  const typeColor = item.type === 'assignment' ? '#3B82F6' : item.type === 'quiz' ? '#10B981' : '#EC4899';

  let badgeColor = 'var(--text-secondary)';
  let badgeBg = 'var(--bg-tertiary)';
  let badgeText = '';

  if (item.status === 'completed') {
    badgeColor = 'var(--success)';
    badgeBg = 'var(--status-graded-bg)';
    badgeText = 'Completed';
  } else if (item.status === 'closed') {
    badgeColor = 'var(--danger)';
    badgeBg = 'var(--status-failed-bg)';
    badgeText = 'Closed';
  } else if (item.status === 'open') {
    badgeColor = 'var(--accent-primary)';
    badgeBg = 'var(--accent-soft)';
    badgeText = 'Open';
  }

  const tr = item.time_remaining_seconds;
  let countdown = null;
  let urgency = 'normal';
  if (item.status === 'open' && tr !== null && tr !== undefined) {
    if (tr <= 0) {
      countdown = 'Just closed';
      urgency = 'urgent';
    } else if (tr < 3600) {
      countdown = `${Math.ceil(tr / 60)}m left`;
      urgency = 'urgent';
    } else if (tr < 86400) {
      countdown = `${Math.ceil(tr / 3600)}h left`;
      urgency = 'soon';
    } else if (tr < 7 * 86400) {
      countdown = `${Math.ceil(tr / 86400)}d left`;
      urgency = 'normal';
    } else {
      countdown = `${Math.ceil(tr / 86400)}d left`;
      urgency = 'far';
    }
  } else if (item.status === 'open' && !item.deadline) {
    countdown = 'No deadline';
  }

  const urgencyColor = urgency === 'urgent' ? 'var(--danger)' : urgency === 'soon' ? 'var(--warning)' : 'var(--text-secondary)';

  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: '0.85rem',
      padding: '0.7rem 0.9rem', borderRadius: '0.5rem',
      border: '1px solid var(--border-color)',
      background: urgency === 'urgent' && item.status === 'open' ? 'var(--status-failed-bg)' : 'var(--bg-tertiary)',
    }}>
      <div style={{
        width: 32, height: 32, borderRadius: '0.45rem',
        background: `${typeColor}20`, color: typeColor,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        flexShrink: 0,
      }}>
        <TypeIcon size={15} />
      </div>

      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', flexWrap: 'wrap' }}>
          <strong style={{ fontSize: '0.88rem' }}>{item.title}</strong>
          <span style={{
            fontSize: '0.65rem', fontWeight: 700, padding: '0.1rem 0.4rem', borderRadius: '999px',
            background: badgeBg, color: badgeColor, textTransform: 'uppercase',
          }}>{badgeText}</span>
        </div>
        <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '0.15rem', display: 'flex', gap: '0.6rem', flexWrap: 'wrap' }}>
          <span>{item.class_name}</span>
          <span>· {item.type === 'omr' ? 'OMR' : item.type}</span>
          {item.total_marks > 0 && <span>· {item.total_marks} marks</span>}
          {item.deadline && (
            <span>· Due {formatDateTime(item.deadline)}</span>
          )}
          {!isStudent && item.enrolled_count > 0 && (
            <span>· {item.submitted_count}/{item.enrolled_count} submitted ({item.submission_rate}%)</span>
          )}
        </div>
      </div>

      {countdown && (
        <div style={{
          fontSize: '0.78rem', fontWeight: 600,
          color: urgencyColor, whiteSpace: 'nowrap',
          flexShrink: 0,
        }}>
          {countdown}
        </div>
      )}
    </div>
  );
}

// "YYYY-MM-DD" in the viewer's local timezone (toISOString() would bucket by UTC day).
function localDateKey(d) {
  const pad = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}
