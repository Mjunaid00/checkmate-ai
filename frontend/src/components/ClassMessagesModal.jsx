import { useState, useEffect } from 'react';
import { X, MessageSquare, IdCard, ChevronRight, ArrowLeft, Search } from 'lucide-react';
import api from '../services/api';
import MessagesPanel from './MessagesPanel';
import { formatDate } from '../utils/dateFormat';
import './UploadWidget.css';

/**
 * Teacher-only modal — list every enrolled student's class chat thread.
 * Click a thread to open a per-student MessagesPanel.
 */
export default function ClassMessagesModal({ classData, onClose }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [active, setActive] = useState(null);  // selected thread (student)
  const [search, setSearch] = useState('');

  const fetch = async () => {
    setLoading(true);
    try {
      const res = await api.get(`/messages/class/${classData.class_id}/threads`);
      setData(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load threads.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetch(); }, [classData.class_id]);

  // Refresh threads after returning from a chat (so unread counts update)
  const handleCloseChat = () => {
    setActive(null);
    fetch();
  };

  // Render the per-student chat panel
  if (active) {
    return (
      <MessagesPanel
        classId={classData.class_id}
        otherUserId={active.student_id}
        otherUserName={active.student_name}
        otherStudentId={active.student_id_number}
        onClose={handleCloseChat}
      />
    );
  }

  const filtered = (data?.threads || []).filter(t => {
    if (!search.trim()) return true;
    const q = search.toLowerCase();
    return (
      (t.student_name || '').toLowerCase().includes(q) ||
      (t.student_id_number || '').toLowerCase().includes(q) ||
      (t.student_email || '').toLowerCase().includes(q)
    );
  });

  return (
    <div className="modal-overlay fade-in" onClick={onClose}>
      <div
        className="modal-content glass-panel"
        style={{ maxWidth: '620px', maxHeight: '85vh', display: 'flex', flexDirection: 'column', padding: 0 }}
        onClick={e => e.stopPropagation()}
      >
        <div style={{ padding: '1.25rem 1.5rem', borderBottom: '1px solid var(--border-color)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
            <MessageSquare size={20} style={{ color: 'var(--accent-primary)' }} />
            <div>
              <h3 style={{ fontSize: '1rem', margin: 0 }}>Class Messages</h3>
              <p className="text-muted" style={{ marginTop: '0.15rem' }}>{classData.name}</p>
            </div>
          </div>
          <button className="close-btn" onClick={onClose} style={{ position: 'static' }}><X size={20} /></button>
        </div>

        {/* Search */}
        <div style={{ padding: '0.85rem 1.25rem', borderBottom: '1px solid var(--border-color)' }}>
          <div style={{ position: 'relative' }}>
            <Search size={14} style={{ position: 'absolute', left: '0.7rem', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-secondary)' }} />
            <input
              type="text"
              className="input-field"
              placeholder="Search by name or student ID"
              value={search}
              onChange={e => setSearch(e.target.value)}
              style={{ paddingLeft: '2rem', fontSize: '0.85rem' }}
            />
          </div>
        </div>

        <div style={{ flex: 1, overflowY: 'auto', minHeight: '200px' }}>
          {loading && <p className="text-muted" style={{ textAlign: 'center', padding: '2rem' }}>Loading threads...</p>}
          {error && <div className="error-banner" style={{ margin: '1rem' }}>{error}</div>}

          {!loading && !error && filtered.length === 0 && (
            <div style={{ textAlign: 'center', padding: '2rem 1rem', color: 'var(--text-secondary)' }}>
              <MessageSquare size={32} style={{ opacity: 0.4, marginBottom: '0.5rem' }} />
              <p>{data?.threads?.length === 0 ? 'No students enrolled yet.' : 'No matches.'}</p>
            </div>
          )}

          {filtered.map(t => (
            <button
              key={t.student_id}
              onClick={() => setActive(t)}
              style={{
                width: '100%', textAlign: 'left',
                padding: '0.85rem 1.25rem',
                borderBottom: '1px solid var(--border-color)',
                background: t.unread_count > 0 ? 'var(--accent-soft)' : 'transparent',
                border: 'none',
                borderLeft: t.unread_count > 0 ? '3px solid var(--accent-primary)' : '3px solid transparent',
                cursor: 'pointer',
                display: 'flex', alignItems: 'center', gap: '0.85rem',
                fontFamily: 'inherit',
                color: 'inherit',
              }}
            >
              <div style={{
                width: 38, height: 38, borderRadius: '50%',
                background: 'var(--accent-primary)', color: 'white',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontWeight: 700, fontSize: '0.85rem',
                flexShrink: 0,
              }}>
                {(t.student_name || '?').split(' ').map(p => p[0]).join('').slice(0, 2).toUpperCase()}
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.5rem' }}>
                  <strong style={{ fontSize: '0.92rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {t.student_name || 'Unknown'}
                  </strong>
                  {t.last_message_at && (
                    <span style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', flexShrink: 0 }}>
                      {timeAgo(t.last_message_at)}
                    </span>
                  )}
                </div>
                <div style={{ display: 'flex', gap: '0.4rem', alignItems: 'center', marginTop: '0.15rem', flexWrap: 'wrap' }}>
                  {t.student_id_number && (
                    <span style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', display: 'inline-flex', alignItems: 'center', gap: '0.2rem' }}>
                      <IdCard size={10} /> {t.student_id_number}
                    </span>
                  )}
                  {t.unread_count > 0 && (
                    <span style={{
                      fontSize: '0.65rem', fontWeight: 700,
                      padding: '0.05rem 0.4rem', borderRadius: '999px',
                      background: 'var(--danger)', color: 'white',
                    }}>
                      {t.unread_count} new
                    </span>
                  )}
                </div>
                <p style={{
                  margin: '0.25rem 0 0 0', fontSize: '0.82rem',
                  color: 'var(--text-secondary)',
                  overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                }}>
                  {t.last_message
                    ? `${t.last_message_from_role === 'teacher' ? 'You: ' : ''}${t.last_message}`
                    : <span style={{ fontStyle: 'italic', opacity: 0.6 }}>No messages yet — click to start</span>}
                </p>
              </div>
              <ChevronRight size={16} style={{ color: 'var(--text-secondary)', flexShrink: 0 }} />
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

function timeAgo(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  const diff = Math.floor((Date.now() - d.getTime()) / 1000);
  if (diff < 60) return 'just now';
  if (diff < 3600) return `${Math.floor(diff / 60)}m`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h`;
  if (diff < 604800) return `${Math.floor(diff / 86400)}d`;
  return formatDate(d);
}
