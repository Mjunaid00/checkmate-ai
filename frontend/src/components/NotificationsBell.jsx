import { useState, useEffect, useRef } from 'react';
import { Bell, X, Check, CheckCheck, Trash2 } from 'lucide-react';
import api from '../services/api';
import { formatDate } from '../utils/dateFormat';

export default function NotificationsBell() {
  const [open, setOpen] = useState(false);
  const [notifications, setNotifications] = useState([]);
  const [unread, setUnread] = useState(0);
  const [loading, setLoading] = useState(false);
  const dropdownRef = useRef(null);

  const fetchUnreadCount = async () => {
    try {
      const res = await api.get('/notifications/unread-count');
      setUnread(res.data.unread || 0);
    } catch {}
  };

  const fetchNotifications = async () => {
    setLoading(true);
    try {
      const res = await api.get('/notifications/?limit=30');
      setNotifications(res.data);
    } catch {}
    finally { setLoading(false); }
  };

  useEffect(() => {
    fetchUnreadCount();
    const t = setInterval(fetchUnreadCount, 20000); // poll every 20s
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    if (open) fetchNotifications();
  }, [open]);

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    const handler = (e) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  const markRead = async (id) => {
    try {
      await api.patch(`/notifications/${id}/read`);
      setNotifications(ns => ns.map(n => n.notification_id === id ? { ...n, read: true } : n));
      setUnread(u => Math.max(0, u - 1));
    } catch {}
  };

  const markAllRead = async () => {
    try {
      await api.post('/notifications/read-all');
      setNotifications(ns => ns.map(n => ({ ...n, read: true })));
      setUnread(0);
    } catch {}
  };

  const removeOne = async (id) => {
    try {
      await api.delete(`/notifications/${id}`);
      setNotifications(ns => ns.filter(n => n.notification_id !== id));
      fetchUnreadCount();
    } catch {}
  };

  return (
    <div ref={dropdownRef} style={{ position: 'relative', width: '100%' }}>
      <button
        onClick={() => setOpen(o => !o)}
        title="Notifications"
        style={{
          width: '100%',
          display: 'flex',
          alignItems: 'center',
          gap: '0.75rem',
          padding: '0.7rem 1rem',
          background: 'transparent',
          border: '1px solid var(--border-color)',
          borderRadius: '0.5rem',
          color: 'var(--text-secondary)',
          fontWeight: 500,
          fontSize: '0.93rem',
          fontFamily: 'inherit',
          cursor: 'pointer',
          position: 'relative',
        }}
      >
        <Bell size={18} />
        <span style={{ flex: 1, textAlign: 'left' }}>Notifications</span>
        {unread > 0 && (
          <span style={{
            background: 'var(--danger)',
            color: 'white',
            fontSize: '0.7rem',
            fontWeight: 700,
            padding: '0.1rem 0.4rem',
            borderRadius: '999px',
            minWidth: '20px',
            textAlign: 'center',
          }}>
            {unread > 99 ? '99+' : unread}
          </span>
        )}
      </button>

      {open && (
        <div
          className="glass-panel"
          style={{
            position: 'absolute',
            bottom: 'calc(100% + 0.5rem)',
            left: 0,
            right: 0,
            maxHeight: '420px',
            display: 'flex',
            flexDirection: 'column',
            background: 'var(--bg-secondary)',
            border: '1px solid var(--border-color)',
            boxShadow: 'var(--shadow-lg)',
            zIndex: 1000,
            overflow: 'hidden',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.75rem 1rem', borderBottom: '1px solid var(--border-color)' }}>
            <strong style={{ fontSize: '0.9rem' }}>Notifications</strong>
            <div style={{ display: 'flex', gap: '0.4rem' }}>
              {unread > 0 && (
                <button onClick={markAllRead} title="Mark all as read" style={iconBtn}>
                  <CheckCheck size={15} />
                </button>
              )}
              <button onClick={() => setOpen(false)} title="Close" style={iconBtn}>
                <X size={15} />
              </button>
            </div>
          </div>

          <div style={{ flex: 1, overflowY: 'auto' }}>
            {loading && <p className="text-muted" style={{ textAlign: 'center', padding: '1.5rem' }}>Loading...</p>}
            {!loading && notifications.length === 0 && (
              <div style={{ textAlign: 'center', padding: '2rem 1rem', color: 'var(--text-secondary)' }}>
                <Bell size={28} style={{ opacity: 0.4, marginBottom: '0.4rem' }} />
                <p style={{ fontSize: '0.85rem' }}>You're all caught up.</p>
              </div>
            )}
            {notifications.map(n => (
              <div
                key={n.notification_id}
                style={{
                  padding: '0.75rem 1rem',
                  borderBottom: '1px solid var(--border-color)',
                  background: n.read ? 'transparent' : 'var(--accent-soft)',
                  cursor: 'pointer',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '0.2rem',
                  position: 'relative',
                }}
                onClick={() => !n.read && markRead(n.notification_id)}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '0.5rem' }}>
                  <strong style={{ fontSize: '0.85rem', flex: 1, color: n.read ? 'var(--text-primary)' : 'var(--accent-primary)' }}>
                    {n.title}
                  </strong>
                  <button
                    onClick={(e) => { e.stopPropagation(); removeOne(n.notification_id); }}
                    title="Remove"
                    style={{ ...iconBtn, padding: '0.2rem' }}
                  >
                    <Trash2 size={12} />
                  </button>
                </div>
                <span style={{ fontSize: '0.83rem', color: 'var(--text-secondary)', lineHeight: 1.4 }}>{n.body}</span>
                <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '0.15rem' }}>
                  {timeAgo(n.created_at)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

const iconBtn = {
  background: 'transparent',
  border: 'none',
  color: 'var(--text-secondary)',
  cursor: 'pointer',
  padding: '0.3rem',
  borderRadius: '0.25rem',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
};

function timeAgo(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  const diff = Math.floor((Date.now() - d.getTime()) / 1000);
  if (diff < 60) return 'just now';
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  if (diff < 604800) return `${Math.floor(diff / 86400)}d ago`;
  return formatDate(d);
}
