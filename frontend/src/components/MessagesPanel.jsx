import { useState, useEffect, useRef } from 'react';
import { Send, MessageSquare, X, IdCard } from 'lucide-react';
import api from '../services/api';
import { formatDateTime } from '../utils/dateFormat';
import './UploadWidget.css';

/**
 * MessagesPanel — modal chat between current user and the other party.
 *
 * Modes:
 *  - submission scope: pass `submissionId` (used for assignment-specific chat)
 *  - class scope:      pass `classId`. Optionally pass `otherUserId` (teachers
 *                      use this to reply to a specific student in the class).
 *
 * Other props:
 *  - otherUserName   display label
 *  - otherStudentId  optional academic ID shown in header
 *  - onClose
 */
export default function MessagesPanel({
  submissionId,
  classId,
  otherUserId,
  otherUserName,
  otherStudentId,
  onClose,
}) {
  const [messages, setMessages] = useState([]);
  const [text, setText] = useState('');
  const [sending, setSending] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const myId = localStorage.getItem('userId');
  const myRole = localStorage.getItem('role');
  const listEndRef = useRef(null);

  const fetchMessages = async () => {
    try {
      const params = {};
      if (submissionId) params.submission_id = submissionId;
      if (classId) {
        params.class_id = classId;
        if (otherUserId) params.other_user_id = otherUserId;
      }
      const res = await api.get('/messages/', { params });
      setMessages(res.data);
      // Mark unread incoming messages as read
      for (const m of res.data) {
        if (!m.read && m.to_user_id === myId) {
          api.patch(`/messages/${m.message_id}/read`).catch(() => {});
        }
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMessages();
    const t = setInterval(fetchMessages, 8000);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [submissionId, classId, otherUserId]);

  useEffect(() => {
    listEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async (e) => {
    e?.preventDefault();
    const txt = text.trim();
    if (!txt) return;
    setSending(true);
    setError('');
    try {
      const payload = { text: txt };
      if (submissionId) {
        payload.submission_id = submissionId;
      } else if (classId) {
        payload.class_id = classId;
        // Teachers must specify recipient on class threads
        if (myRole === 'teacher' && otherUserId) {
          payload.to_user_id = otherUserId;
        }
      }
      await api.post('/messages/', payload);
      setText('');
      fetchMessages();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to send message.');
    } finally {
      setSending(false);
    }
  };

  const subtitle = classId
    ? `Class chat${otherUserName ? ` · ${otherUserName}` : ''}`
    : (otherUserName || 'Conversation');

  return (
    <div className="modal-overlay fade-in" onClick={onClose}>
      <div
        className="modal-content glass-panel"
        style={{ maxWidth: '560px', maxHeight: '80vh', display: 'flex', flexDirection: 'column', padding: 0 }}
        onClick={e => e.stopPropagation()}
      >
        <div style={{ padding: '1.25rem 1.5rem', borderBottom: '1px solid var(--border-color)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
            <MessageSquare size={20} style={{ color: 'var(--accent-primary)' }} />
            <div>
              <h3 style={{ fontSize: '1rem', margin: 0 }}>Messages</h3>
              <p className="text-muted" style={{ marginTop: '0.15rem' }}>{subtitle}</p>
              {otherStudentId && (
                <p style={{ marginTop: '0.15rem', fontSize: '0.72rem', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                  <IdCard size={11} /> Student ID: <strong>{otherStudentId}</strong>
                </p>
              )}
            </div>
          </div>
          <button className="close-btn" onClick={onClose} style={{ position: 'static' }}><X size={20} /></button>
        </div>

        <div style={{ flex: 1, overflowY: 'auto', padding: '1rem 1.25rem', minHeight: '200px', maxHeight: '50vh', display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
          {loading && <p className="text-muted" style={{ textAlign: 'center' }}>Loading...</p>}
          {!loading && messages.length === 0 && (
            <div style={{ textAlign: 'center', padding: '2rem 1rem', color: 'var(--text-secondary)' }}>
              <MessageSquare size={32} style={{ opacity: 0.4, marginBottom: '0.5rem' }} />
              <p>No messages yet. Start the conversation below.</p>
            </div>
          )}
          {messages.map(m => {
            const mine = m.from_user_id === myId;
            return (
              <div key={m.message_id} style={{ display: 'flex', justifyContent: mine ? 'flex-end' : 'flex-start' }}>
                <div style={{
                  maxWidth: '75%',
                  padding: '0.6rem 0.85rem',
                  borderRadius: '0.7rem',
                  background: mine ? 'var(--accent-primary)' : 'var(--bg-tertiary)',
                  color: mine ? 'white' : 'var(--text-primary)',
                  fontSize: '0.9rem',
                  lineHeight: 1.45,
                  wordBreak: 'break-word',
                  boxShadow: 'var(--shadow-sm)',
                }}>
                  {!mine && (
                    <div style={{ fontSize: '0.72rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.2rem', display: 'flex', alignItems: 'center', gap: '0.3rem', flexWrap: 'wrap' }}>
                      <span>{m.from_name}</span>
                      {m.from_role === 'teacher' && <span style={{ color: 'var(--accent-primary)' }}>(teacher)</span>}
                      {m.from_student_id_number && (
                        <span style={{ background: 'var(--bg-secondary)', padding: '0.05rem 0.35rem', borderRadius: '0.25rem', fontSize: '0.68rem' }}>
                          ID: {m.from_student_id_number}
                        </span>
                      )}
                    </div>
                  )}
                  <div>{m.text}</div>
                  <div style={{ fontSize: '0.68rem', opacity: 0.75, marginTop: '0.25rem', textAlign: mine ? 'right' : 'left' }}>
                    {formatDateTime(m.created_at)}
                  </div>
                </div>
              </div>
            );
          })}
          <div ref={listEndRef} />
        </div>

        {error && <div className="error-banner" style={{ margin: '0 1.25rem' }}>{error}</div>}

        <form onSubmit={handleSend} style={{ padding: '0.85rem 1.25rem', borderTop: '1px solid var(--border-color)', display: 'flex', gap: '0.5rem' }}>
          <input
            type="text"
            className="input-field"
            placeholder="Type a message..."
            value={text}
            onChange={e => setText(e.target.value)}
            disabled={sending}
            maxLength={2000}
          />
          <button type="submit" className="btn-primary" disabled={sending || !text.trim()} style={{ padding: '0.55rem 0.9rem' }}>
            <Send size={16} />
          </button>
        </form>
      </div>
    </div>
  );
}
