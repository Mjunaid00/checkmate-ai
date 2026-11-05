import { useState, useEffect } from 'react';
import { Clock, Calendar as CalendarIcon, StickyNote, ChevronDown, ChevronUp } from 'lucide-react';
import { formatWeekdayDate, formatMonthYear } from '../utils/dateFormat';

/**
 * Stacked sidebar widgets: live clock, mini calendar, and a memo pad.
 * Calendar and memo are collapsible to save space.
 */
export default function SidebarWidgets() {
  const [now, setNow] = useState(new Date());

  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', marginBottom: '0.5rem' }}>
      <ClockCard now={now} />
      <CalendarCard now={now} />
      <MemoCard />
    </div>
  );
}

// ── Clock ────────────────────────────────────────────────────────────────────
function ClockCard({ now }) {
  const time = now.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
  const date = formatWeekdayDate(now);

  return (
    <div style={{
      padding: '0.6rem 0.85rem',
      borderRadius: '0.5rem',
      border: '1px solid var(--border-color)',
      background: 'var(--bg-tertiary)',
      display: 'flex',
      alignItems: 'center',
      gap: '0.6rem',
    }}>
      <Clock size={16} style={{ color: 'var(--accent-primary)', flexShrink: 0 }} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontFamily: 'monospace', fontSize: '0.95rem', fontWeight: 700, letterSpacing: '0.02em' }}>
          {time}
        </div>
        <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>{date}</div>
      </div>
    </div>
  );
}

// ── Calendar ─────────────────────────────────────────────────────────────────
function CalendarCard({ now }) {
  const STORAGE_KEY = 'sidebar.calendarOpen';
  const [open, setOpen] = useState(() => {
    const saved = localStorage.getItem(STORAGE_KEY);
    return saved === null ? true : saved === '1';
  });
  const [view, setView] = useState({ year: now.getFullYear(), month: now.getMonth() });

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, open ? '1' : '0');
  }, [open]);

  const monthName = formatMonthYear(new Date(view.year, view.month));
  const firstDow = new Date(view.year, view.month, 1).getDay();
  const daysInMonth = new Date(view.year, view.month + 1, 0).getDate();
  const today = now;
  const isToday = (d) =>
    d === today.getDate() && view.month === today.getMonth() && view.year === today.getFullYear();

  const cells = [];
  for (let i = 0; i < firstDow; i++) cells.push(null);
  for (let d = 1; d <= daysInMonth; d++) cells.push(d);
  while (cells.length % 7 !== 0) cells.push(null);

  const prevMonth = () => {
    setView(v => v.month === 0 ? { year: v.year - 1, month: 11 } : { year: v.year, month: v.month - 1 });
  };
  const nextMonth = () => {
    setView(v => v.month === 11 ? { year: v.year + 1, month: 0 } : { year: v.year, month: v.month + 1 });
  };
  const jumpToday = () => setView({ year: today.getFullYear(), month: today.getMonth() });

  return (
    <div style={{ borderRadius: '0.5rem', border: '1px solid var(--border-color)', background: 'var(--bg-tertiary)' }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          width: '100%',
          padding: '0.55rem 0.85rem',
          background: 'transparent',
          border: 'none',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          cursor: 'pointer',
          fontFamily: 'inherit',
          color: 'var(--text-primary)',
        }}
      >
        <span style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.82rem', fontWeight: 600 }}>
          <CalendarIcon size={14} style={{ color: 'var(--accent-primary)' }} />
          Calendar
        </span>
        {open ? <ChevronUp size={13} style={{ color: 'var(--text-secondary)' }} /> : <ChevronDown size={13} style={{ color: 'var(--text-secondary)' }} />}
      </button>

      {open && (
        <div style={{ padding: '0 0.65rem 0.65rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.4rem' }}>
            <button onClick={prevMonth} style={navBtnStyle} aria-label="Previous month">‹</button>
            <button onClick={jumpToday} style={{
              ...navBtnStyle,
              padding: '0.15rem 0.5rem',
              fontSize: '0.72rem',
              fontWeight: 600,
              color: 'var(--text-primary)',
            }}>
              {monthName}
            </button>
            <button onClick={nextMonth} style={navBtnStyle} aria-label="Next month">›</button>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: '2px' }}>
            {['S', 'M', 'T', 'W', 'T', 'F', 'S'].map((d, i) => (
              <div key={i} style={{
                fontSize: '0.62rem', fontWeight: 700, textAlign: 'center',
                color: 'var(--text-muted)', padding: '0.15rem 0',
              }}>{d}</div>
            ))}
            {cells.map((d, i) => (
              <div
                key={i}
                style={{
                  textAlign: 'center',
                  padding: '0.25rem 0',
                  fontSize: '0.7rem',
                  borderRadius: '0.25rem',
                  background: d && isToday(d) ? 'var(--accent-primary)' : 'transparent',
                  color: d && isToday(d) ? 'white' : (d ? 'var(--text-primary)' : 'transparent'),
                  fontWeight: d && isToday(d) ? 700 : 500,
                }}
              >
                {d || '·'}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Memo Pad ─────────────────────────────────────────────────────────────────
function MemoCard() {
  // Scope by user so each account has its own memo on the same machine.
  // Falls back to a per-role bucket if userId hasn't been cached yet.
  const userId = localStorage.getItem('userId');
  const role = localStorage.getItem('role') || 'guest';
  const scope = userId || `role:${role}`;
  const STORAGE_KEY = `sidebar.memo:${scope}`;
  const OPEN_KEY = 'sidebar.memoOpen';
  const [open, setOpen] = useState(() => {
    const saved = localStorage.getItem(OPEN_KEY);
    return saved === null ? true : saved === '1';
  });
  const [text, setText] = useState(() => localStorage.getItem(STORAGE_KEY) || '');
  const [savedAt, setSavedAt] = useState(null);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    localStorage.setItem(OPEN_KEY, open ? '1' : '0');
  }, [open]);

  // One-time migration: copy a legacy single-key memo into the per-user bucket
  // (only if this user doesn't already have their own).
  useEffect(() => {
    const legacy = localStorage.getItem('sidebar.memo');
    if (legacy && !localStorage.getItem(STORAGE_KEY)) {
      localStorage.setItem(STORAGE_KEY, legacy);
      setText(legacy);
    }
    localStorage.removeItem('sidebar.memo');
    setHydrated(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Debounced save — but only after hydration so we don't overwrite with empty
  useEffect(() => {
    if (!hydrated) return;
    const t = setTimeout(() => {
      localStorage.setItem(STORAGE_KEY, text);
      setSavedAt(new Date());
    }, 400);
    return () => clearTimeout(t);
  }, [text, hydrated, STORAGE_KEY]);

  return (
    <div style={{ borderRadius: '0.5rem', border: '1px solid var(--border-color)', background: 'var(--bg-tertiary)' }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          width: '100%',
          padding: '0.55rem 0.85rem',
          background: 'transparent',
          border: 'none',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          cursor: 'pointer',
          fontFamily: 'inherit',
          color: 'var(--text-primary)',
        }}
      >
        <span style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.82rem', fontWeight: 600 }}>
          <StickyNote size={14} style={{ color: '#F59E0B' }} />
          Memo
        </span>
        {open ? <ChevronUp size={13} style={{ color: 'var(--text-secondary)' }} /> : <ChevronDown size={13} style={{ color: 'var(--text-secondary)' }} />}
      </button>

      {open && (
        <div style={{ padding: '0 0.65rem 0.65rem' }}>
          <textarea
            value={text}
            onChange={e => setText(e.target.value)}
            placeholder="Quick notes…"
            rows={4}
            style={{
              width: '100%',
              padding: '0.5rem',
              borderRadius: '0.35rem',
              border: '1px solid var(--border-color)',
              background: 'var(--bg-secondary)',
              color: 'var(--text-primary)',
              fontSize: '0.78rem',
              fontFamily: 'inherit',
              resize: 'vertical',
              outline: 'none',
              minHeight: '70px',
            }}
            onFocus={e => e.target.style.borderColor = 'var(--accent-primary)'}
            onBlur={e => e.target.style.borderColor = 'var(--border-color)'}
          />
          <div style={{
            fontSize: '0.65rem',
            color: 'var(--text-muted)',
            marginTop: '0.2rem',
            textAlign: 'right',
            minHeight: '0.85rem',
          }}>
            {savedAt && `Saved · ${savedAt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`}
          </div>
        </div>
      )}
    </div>
  );
}

const navBtnStyle = {
  background: 'transparent',
  border: '1px solid var(--border-color)',
  borderRadius: '0.3rem',
  padding: '0.1rem 0.45rem',
  cursor: 'pointer',
  color: 'var(--text-secondary)',
  fontFamily: 'inherit',
  fontSize: '0.85rem',
  lineHeight: 1,
};
