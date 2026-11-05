import { useState, useEffect } from 'react';
import { X, IdCard, Check } from 'lucide-react';
import api from '../services/api';
import './UploadWidget.css';

export default function EnrollModal({ classData, onClose, onEnrolled }) {
  const [studentIdNumber, setStudentIdNumber] = useState(() => localStorage.getItem('lastStudentIdNumber') || '');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  // Focus the input on mount
  useEffect(() => {
    const t = setTimeout(() => {
      document.getElementById('student-id-input')?.focus();
    }, 100);
    return () => clearTimeout(t);
  }, []);

  const handleEnroll = async (e) => {
    e?.preventDefault();
    const sid = studentIdNumber.trim();
    if (!sid) {
      setError('Student ID is required.');
      return;
    }
    setLoading(true);
    setError('');
    try {
      await api.post(`/enrollment/${classData.class_id}`, { student_id_number: sid });
      // Remember for next enrollment
      localStorage.setItem('lastStudentIdNumber', sid);
      onEnrolled();
      onClose();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to enroll.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay fade-in" onClick={() => !loading && onClose()}>
      <div className="modal-content glass-panel" style={{ maxWidth: '440px' }} onClick={e => e.stopPropagation()}>
        <button className="close-btn" onClick={onClose}><X size={20} /></button>

        <div style={{
          width: 56, height: 56, borderRadius: '0.75rem',
          background: 'var(--accent-soft)', color: 'var(--accent-primary)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          marginBottom: '1rem',
        }}>
          <IdCard size={26} />
        </div>

        <h2 style={{ marginBottom: '0.25rem' }}>Enroll in {classData.name}</h2>
        <p className="text-secondary" style={{ fontSize: '0.9rem', marginBottom: '1.5rem' }}>
          Enter your academic Student ID to join this class. The teacher will see this ID on your submissions.
        </p>

        {error && <div className="error-banner">{error}</div>}

        <form onSubmit={handleEnroll}>
          <div style={{ marginBottom: '1.25rem' }}>
            <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: '0.4rem' }}>
              Student ID
            </label>
            <input
              id="student-id-input"
              type="text"
              className="input-field"
              value={studentIdNumber}
              onChange={e => setStudentIdNumber(e.target.value)}
              placeholder="e.g. 22K-1234"
              disabled={loading}
              autoComplete="off"
            />
            <small className="text-muted" style={{ marginTop: '0.4rem', display: 'block' }}>
              This will be reused for future enrollments.
            </small>
          </div>

          <div className="modal-actions">
            <button type="button" className="btn-secondary" onClick={onClose} disabled={loading}>
              Cancel
            </button>
            <button type="submit" className="btn-primary" disabled={loading || !studentIdNumber.trim()}>
              <Check size={16} /> {loading ? 'Enrolling...' : 'Confirm Enrollment'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
