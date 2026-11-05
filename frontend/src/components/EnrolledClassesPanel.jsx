import { useState, useEffect } from 'react';
import { Users, Clock, FileText, ClipboardCheck, ScanLine, AlertTriangle, CheckCircle, MessageSquare, ArrowRight } from 'lucide-react';
import api from '../services/api';

/**
 * Shows each class the student is enrolled in with a breakdown of:
 * - Open / Completed / Closed counts (assignments, quizzes, OMR)
 * - Next upcoming deadline + countdown
 * - Quick "Open" and "Message" buttons
 *
 * Props:
 * - classes        : array of class docs (with .enrolled flag)
 * - selectedClass  : currently selected class_id
 * - onSelect(class_id)
 * - onMessage(class)
 */
export default function EnrolledClassesPanel({ classes, selectedClass, onSelect, onMessage }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const res = await api.get('/analytics/student/deadlines');
        if (!cancelled) setItems(res.data?.items || []);
      } catch {
        // Non-fatal — panel still renders class cards even without deadlines
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    load();
    return () => { cancelled = true; };
  }, []);

  const enrolled = (classes || []).filter(c => c.enrolled);

  if (enrolled.length === 0) {
    return (
      <section className="glass-panel" style={{ marginBottom: '2rem', padding: '1.5rem' }}>
        <h3 className="section-title" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Users size={18} /> My Enrolled Classes
        </h3>
        <div style={{ textAlign: 'center', padding: '1.5rem 1rem', color: 'var(--text-secondary)' }}>
          <p>You haven't enrolled in any class yet. Browse "Available Classes" below and click <strong>Enroll</strong>.</p>
        </div>
      </section>
    );
  }

  return (
    <section className="glass-panel" style={{ marginBottom: '2rem', padding: '1.5rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.5rem' }}>
        <h3 className="section-title" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', margin: 0 }}>
          <Users size={18} /> My Enrolled Classes ({enrolled.length})
        </h3>
        {loading && <span className="text-muted" style={{ fontSize: '0.78rem' }}>Loading deadlines...</span>}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '1rem' }}>
        {enrolled.map(c => {
          const classItems = items.filter(i => i.class_id === c.class_id);
          const counts = {
            assignments: classItems.filter(i => i.type === 'assignment').length,
            quizzes: classItems.filter(i => i.type === 'quiz').length,
            omr: classItems.filter(i => i.type === 'omr').length,
            open: classItems.filter(i => i.status === 'open').length,
            completed: classItems.filter(i => i.status === 'completed').length,
            closed: classItems.filter(i => i.status === 'closed').length,
          };

          // Next upcoming deadline (open items with a deadline, soonest first)
          const upcoming = classItems
            .filter(i => i.status === 'open' && i.deadline)
            .sort((a, b) => (a.time_remaining_seconds ?? 0) - (b.time_remaining_seconds ?? 0))[0];

          const isSelected = selectedClass === c.class_id;

          return (
            <div
              key={c.class_id}
              className="glass-panel"
              style={{
                padding: '1rem 1.25rem',
                border: isSelected ? '2px solid var(--accent-primary)' : '1px solid var(--border-color)',
                background: isSelected ? 'var(--accent-soft)' : 'var(--bg-secondary)',
                cursor: 'pointer',
                transition: 'all 0.15s ease',
                display: 'flex',
                flexDirection: 'column',
                gap: '0.6rem',
              }}
              onClick={() => onSelect(c.class_id)}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                <div style={{
                  width: 36, height: 36, borderRadius: '0.45rem',
                  background: 'linear-gradient(135deg, var(--accent-primary), #8B5CF6)',
                  color: 'white',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  flexShrink: 0,
                }}>
                  <Users size={16} />
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <h4 style={{
                    fontSize: '0.95rem', margin: 0,
                    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                  }}>{c.name}</h4>
                  <p style={{ margin: '0.1rem 0 0 0', fontSize: '0.72rem', color: 'var(--text-secondary)' }}>
                    {c.enrollment_count ?? 0} enrolled · {c.assignments_count ?? counts.assignments} assignments
                  </p>
                </div>
              </div>

              {/* Type breakdown row */}
              <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap', fontSize: '0.72rem' }}>
                <Pill icon={FileText} label={`${counts.assignments} assign`} color="#3B82F6" />
                <Pill icon={ClipboardCheck} label={`${counts.quizzes} quiz`} color="#10B981" />
                <Pill icon={ScanLine} label={`${counts.omr} OMR`} color="#EC4899" />
              </div>

              {/* Status breakdown */}
              <div style={{
                display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '0.4rem',
                padding: '0.45rem 0', borderTop: '1px solid var(--border-color)',
              }}>
                <StatusCount icon={Clock} count={counts.open} label="Open" color="var(--accent-primary)" />
                <StatusCount icon={CheckCircle} count={counts.completed} label="Done" color="var(--success)" />
                <StatusCount icon={AlertTriangle} count={counts.closed} label="Missed" color="var(--danger)" />
              </div>

              {/* Next deadline highlight */}
              {upcoming ? (
                <div style={{
                  padding: '0.5rem 0.7rem', borderRadius: '0.4rem',
                  background: getUrgencyBg(upcoming.time_remaining_seconds),
                  color: getUrgencyColor(upcoming.time_remaining_seconds),
                  fontSize: '0.78rem', fontWeight: 500,
                  display: 'flex', alignItems: 'center', gap: '0.4rem',
                }}>
                  <Clock size={12} />
                  <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    Next: {upcoming.title}
                  </span>
                  <strong>{formatRemaining(upcoming.time_remaining_seconds)}</strong>
                </div>
              ) : counts.open === 0 ? (
                <div style={{
                  padding: '0.5rem 0.7rem', borderRadius: '0.4rem',
                  background: 'var(--status-graded-bg)', color: 'var(--success)',
                  fontSize: '0.78rem', fontWeight: 500,
                  display: 'flex', alignItems: 'center', gap: '0.4rem',
                }}>
                  <CheckCircle size={12} /> All caught up
                </div>
              ) : (
                <div style={{
                  padding: '0.5rem 0.7rem', borderRadius: '0.4rem',
                  background: 'var(--bg-tertiary)', color: 'var(--text-secondary)',
                  fontSize: '0.78rem',
                }}>
                  {counts.open} open item{counts.open !== 1 ? 's' : ''} · no deadline set
                </div>
              )}

              <div style={{ display: 'flex', gap: '0.4rem', marginTop: '0.25rem' }}>
                <button
                  className="btn-primary"
                  style={{ flex: 1, justifyContent: 'center', fontSize: '0.78rem', padding: '0.4rem 0.6rem' }}
                  onClick={(e) => { e.stopPropagation(); onSelect(c.class_id); }}
                >
                  Open <ArrowRight size={13} />
                </button>
                <button
                  className="btn-secondary"
                  style={{ padding: '0.4rem 0.6rem', color: 'var(--accent-primary)' }}
                  title="Message teacher"
                  onClick={(e) => { e.stopPropagation(); onMessage(c); }}
                >
                  <MessageSquare size={14} />
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function Pill({ icon: Icon, label, color }) {
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: '0.25rem',
      padding: '0.18rem 0.5rem', borderRadius: '999px',
      background: `${color}18`, color, fontWeight: 600,
    }}>
      <Icon size={10} /> {label}
    </span>
  );
}

function StatusCount({ icon: Icon, count, label, color }) {
  return (
    <div style={{ textAlign: 'center' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.25rem', color, fontWeight: 700, fontSize: '1.05rem' }}>
        <Icon size={11} /> {count}
      </div>
      <div style={{ fontSize: '0.65rem', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.04em', fontWeight: 600 }}>
        {label}
      </div>
    </div>
  );
}

function formatRemaining(secs) {
  if (secs === null || secs === undefined) return '—';
  if (secs <= 0) return 'closing';
  if (secs < 3600) return `${Math.ceil(secs / 60)}m`;
  if (secs < 86400) return `${Math.ceil(secs / 3600)}h`;
  return `${Math.ceil(secs / 86400)}d`;
}

function getUrgencyColor(secs) {
  if (secs === null || secs === undefined) return 'var(--text-secondary)';
  if (secs < 3600) return 'var(--danger)';
  if (secs < 86400) return 'var(--warning)';
  return 'var(--accent-primary)';
}

function getUrgencyBg(secs) {
  if (secs === null || secs === undefined) return 'var(--bg-tertiary)';
  if (secs < 3600) return 'var(--status-failed-bg)';
  if (secs < 86400) return 'var(--status-pending-bg)';
  return 'var(--accent-soft)';
}
