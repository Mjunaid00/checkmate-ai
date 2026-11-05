import { useState } from 'react';
import { X, Save, Edit3 } from 'lucide-react';
import api from '../services/api';
import './UploadWidget.css';

export default function ManualGradeModal({ submission, onClose, onSaved }) {
  const totalMarks = submission.total_marks || 100;
  const [score, setScore] = useState(submission.manual_score ?? submission.score ?? 0);
  const [feedback, setFeedback] = useState(submission.manual_feedback || submission.feedback || '');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const handleSave = async (e) => {
    e?.preventDefault();
    const numScore = parseFloat(score);
    if (isNaN(numScore) || numScore < 0) {
      setError('Score must be a non-negative number.');
      return;
    }
    if (numScore > totalMarks) {
      setError(`Score cannot exceed ${totalMarks}.`);
      return;
    }
    setSaving(true);
    setError('');
    try {
      await api.patch(`/submissions/${submission.submission_id}/grade`, {
        score: numScore,
        feedback: feedback.trim() || null,
      });
      onSaved();
      onClose();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to save grade.');
    } finally {
      setSaving(false);
    }
  };

  const aiOriginal = submission.score;
  const wasManuallyGraded = submission.manually_graded_at;

  return (
    <div className="modal-overlay fade-in">
      <div className="modal-content glass-panel" style={{ maxWidth: '520px' }}>
        <button className="close-btn" onClick={onClose}><X size={20} /></button>

        <h2 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.25rem' }}>
          <Edit3 size={20} /> {wasManuallyGraded ? 'Update Grade' : 'Grade Submission'}
        </h2>
        <p className="text-secondary" style={{ fontSize: '0.9rem', marginBottom: '1rem' }}>
          {submission.original_name}
        </p>

        {error && <div className="error-banner">{error}</div>}

        {aiOriginal !== null && aiOriginal !== undefined && !wasManuallyGraded && (
          <div style={{
            padding: '0.7rem 0.85rem', borderRadius: '0.5rem',
            background: 'var(--accent-soft)', color: 'var(--accent-primary)',
            fontSize: '0.83rem', marginBottom: '1rem',
          }}>
            AI graded this <strong>{aiOriginal}/{totalMarks}</strong>. You can override the score below.
          </div>
        )}

        <form onSubmit={handleSave}>
          <div style={{ marginBottom: '1rem' }}>
            <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: '0.4rem' }}>
              Score (out of {totalMarks})
            </label>
            <input
              type="number"
              className="input-field"
              min="0"
              max={totalMarks}
              step="0.5"
              value={score}
              onChange={e => setScore(e.target.value)}
              autoFocus
            />
          </div>

          <div style={{ marginBottom: '1.25rem' }}>
            <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: '0.4rem' }}>
              Feedback for student
            </label>
            <textarea
              className="input-field"
              rows={4}
              value={feedback}
              onChange={e => setFeedback(e.target.value)}
              placeholder="Add comments, corrections, or notes for the student..."
              style={{ resize: 'vertical', fontFamily: 'inherit' }}
            />
          </div>

          <div className="modal-actions">
            <button type="button" className="btn-secondary" onClick={onClose} disabled={saving}>Cancel</button>
            <button type="submit" className="btn-primary" disabled={saving}>
              <Save size={16} /> {saving ? 'Saving...' : 'Save Grade'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
