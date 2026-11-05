import { useState, useEffect } from 'react';
import { X, Save, Pencil, AlertTriangle } from 'lucide-react';
import api from '../services/api';
import DateTimeField from './DateTimeField';
import { nowForDatetimeLocal, isPast, toDatetimeLocalValue, toApiDatetime } from '../utils/dateFormat';
import './UploadWidget.css';

/**
 * Edit a quiz's metadata and settings (title, description, time limit, deadline,
 * shuffle/show options). Question editing is intentionally NOT exposed here so
 * a teacher cannot accidentally change the answer key after students have attempted.
 */
export default function QuizEditModal({ quiz, onClose, onSaved }) {
  const [title, setTitle] = useState(quiz.title || '');
  const [description, setDescription] = useState(quiz.description || '');
  const [timeLimit, setTimeLimit] = useState(quiz.time_limit_minutes || 30);
  const [deadline, setDeadline] = useState(
    quiz.deadline ? toDatetimeLocalValue(quiz.deadline) : ''
  );
  const [shuffleQuestions, setShuffleQuestions] = useState(quiz.shuffle_questions ?? true);
  const [shuffleOptions, setShuffleOptions] = useState(quiz.shuffle_options ?? true);
  const [showCorrect, setShowCorrect] = useState(quiz.show_correct_after ?? true);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const [attemptCount, setAttemptCount] = useState(quiz.attempt_count ?? null);

  // Re-fetch attempt count to show the warning if any
  useEffect(() => {
    let cancelled = false;
    if (attemptCount === null) {
      api.get(`/quizzes/${quiz.quiz_id}/attempts`)
        .then(res => { if (!cancelled) setAttemptCount(res.data.length); })
        .catch(() => { if (!cancelled) setAttemptCount(0); });
    }
    return () => { cancelled = true; };
  }, [quiz.quiz_id]);

  const deadlineHasPassed = quiz.deadline && new Date(quiz.deadline) < new Date();

  const handleSave = async (e) => {
    e?.preventDefault();
    if (!title.trim()) {
      setError('Title is required.');
      return;
    }
    if (timeLimit < 1) {
      setError('Time limit must be at least 1 minute.');
      return;
    }
    // Only block past deadlines when the user is setting a NEW value — leaving
    // the original past deadline untouched should still be allowed.
    if (deadline && deadline !== toDatetimeLocalValue(quiz.deadline) && isPast(deadline)) {
      setError('Deadline cannot be in the past.');
      return;
    }
    setSaving(true);
    setError('');

    const payload = {};
    if (title.trim() !== (quiz.title || '')) payload.title = title.trim();
    if (description !== (quiz.description || '')) payload.description = description.trim() || null;
    if (parseInt(timeLimit) !== quiz.time_limit_minutes) payload.time_limit_minutes = parseInt(timeLimit);
    // Always send deadline so it can be cleared
    payload.deadline = toApiDatetime(deadline); // '' clears the deadline server-side
    if (shuffleQuestions !== quiz.shuffle_questions) payload.shuffle_questions = shuffleQuestions;
    if (shuffleOptions !== quiz.shuffle_options) payload.shuffle_options = shuffleOptions;
    if (showCorrect !== quiz.show_correct_after) payload.show_correct_after = showCorrect;

    try {
      await api.patch(`/quizzes/${quiz.quiz_id}`, payload);
      onSaved();
      onClose();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to save changes.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="modal-overlay fade-in">
      <div className="modal-content glass-panel" style={{ maxWidth: '600px', maxHeight: '90vh', overflowY: 'auto' }}>
        <button className="close-btn" onClick={onClose}><X size={20} /></button>

        <h2 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.25rem' }}>
          <Pencil size={20} /> Edit Quiz
        </h2>
        <p className="text-secondary" style={{ fontSize: '0.9rem', marginBottom: '1rem' }}>
          Update timing, deadline, or settings. Questions and answer key are locked.
        </p>

        {error && <div className="error-banner">{error}</div>}

        {attemptCount > 0 && (
          <div style={{
            padding: '0.7rem 0.85rem', borderRadius: '0.5rem',
            background: 'var(--status-pending-bg)', color: 'var(--status-pending)',
            fontSize: '0.85rem', display: 'flex', gap: '0.5rem', alignItems: 'flex-start',
            marginBottom: '1rem', border: '1px solid var(--warning)',
          }}>
            <AlertTriangle size={16} style={{ flexShrink: 0, marginTop: '2px' }} />
            <span>
              <strong>{attemptCount} student{attemptCount !== 1 ? 's have' : ' has'} already attempted this quiz.</strong>
              {' '}Changes to deadline / time limit will affect future attempts only.
            </span>
          </div>
        )}

        {deadlineHasPassed && (
          <div style={{
            padding: '0.7rem 0.85rem', borderRadius: '0.5rem',
            background: 'var(--status-failed-bg)', color: 'var(--status-failed)',
            fontSize: '0.85rem', marginBottom: '1rem', border: '1px solid var(--danger)',
          }}>
            The current deadline has already passed. Updating it below will reopen the quiz for unsubmitted students.
          </div>
        )}

        <form onSubmit={handleSave}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
            <div>
              <Label>Title</Label>
              <input type="text" className="input-field" value={title} onChange={e => setTitle(e.target.value)} />
            </div>

            <div>
              <Label>Description</Label>
              <input type="text" className="input-field" value={description} onChange={e => setDescription(e.target.value)} placeholder="Optional" />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
              <div>
                <Label>Time Limit (minutes)</Label>
                <input type="number" className="input-field" min={1} value={timeLimit} onChange={e => setTimeLimit(parseInt(e.target.value) || 1)} />
              </div>
              <div>
                <Label>Deadline</Label>
                <DateTimeField
                  value={deadline}
                  min={nowForDatetimeLocal()}
                  onChange={setDeadline}
                />
                {deadline && (
                  <small style={{ display: 'block', color: 'var(--text-muted)', fontSize: '0.72rem', marginTop: '0.3rem' }}>
                    Click the field and clear to remove the deadline.
                  </small>
                )}
              </div>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', padding: '0.75rem', background: 'var(--bg-tertiary)', borderRadius: '0.5rem' }}>
              <strong style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Settings</strong>
              <CheckboxLabel checked={shuffleQuestions} onChange={setShuffleQuestions}>Shuffle questions</CheckboxLabel>
              <CheckboxLabel checked={shuffleOptions} onChange={setShuffleOptions}>Shuffle options</CheckboxLabel>
              <CheckboxLabel checked={showCorrect} onChange={setShowCorrect}>Show correct answers after submission</CheckboxLabel>
            </div>

            <div style={{ padding: '0.6rem 0.8rem', background: 'var(--accent-soft)', color: 'var(--accent-primary)', borderRadius: '0.5rem', fontSize: '0.82rem' }}>
              {quiz.question_count ?? '—'} questions · {quiz.total_marks} total marks (locked)
            </div>
          </div>

          <div className="modal-actions" style={{ marginTop: '1.25rem' }}>
            <button type="button" className="btn-secondary" onClick={onClose} disabled={saving}>Cancel</button>
            <button type="submit" className="btn-primary" disabled={saving}>
              <Save size={16} /> {saving ? 'Saving...' : 'Save Changes'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function Label({ children }) {
  return (
    <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: '0.35rem' }}>
      {children}
    </label>
  );
}

function CheckboxLabel({ checked, onChange, children }) {
  return (
    <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer', fontSize: '0.88rem' }}>
      <input
        type="checkbox"
        checked={checked}
        onChange={e => onChange(e.target.checked)}
        style={{ width: '16px', height: '16px', cursor: 'pointer' }}
      />
      {children}
    </label>
  );
}
