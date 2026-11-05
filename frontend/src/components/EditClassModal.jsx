import { useState, useEffect } from 'react';
import { X, Save, Pencil, Clock, FileText, Trash2 } from 'lucide-react';
import api from '../services/api';
import DateTimeField from './DateTimeField';
import { formatDateTime, nowForDatetimeLocal, toDatetimeLocalValue, toApiDatetime } from '../utils/dateFormat';
import './UploadWidget.css';

export default function EditClassModal({ classData, onClose, onSaved }) {
  const [className, setClassName] = useState(classData.name);
  const [maxStudents, setMaxStudents] = useState(classData.max_students || '');
  const [assignments, setAssignments] = useState([]);
  const [editingAssignment, setEditingAssignment] = useState(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  useEffect(() => {
    fetchAssignments();
  }, []);

  const fetchAssignments = async () => {
    try {
      const res = await api.get(`/assignments/class/${classData.class_id}`);
      setAssignments(res.data);
    } catch (err) {
      console.error(err);
    }
  };

  const handleSaveClassDetails = async () => {
    const trimmedName = className.trim();
    const newMax = maxStudents === '' ? null : parseInt(maxStudents);

    const nameChanged = trimmedName && trimmedName !== classData.name;
    const maxChanged = newMax !== (classData.max_students || null);

    if (!nameChanged && !maxChanged) return;

    setSaving(true);
    setError('');
    try {
      const payload = {};
      if (nameChanged) payload.name = trimmedName;
      if (maxChanged && newMax !== null) payload.max_students = newMax;

      await api.patch(`/classes/${classData.class_id}`, payload);
      setSuccess('Class details updated.');
      setTimeout(() => setSuccess(''), 2000);
      onSaved();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to update class.');
    } finally {
      setSaving(false);
    }
  };

  const handleSaveAssignment = async (assignmentId, updates) => {
    setSaving(true);
    setError('');
    try {
      const params = new URLSearchParams();
      if (updates.title !== undefined) params.append('title', updates.title);
      if (updates.total_marks !== undefined) params.append('total_marks', updates.total_marks);
      if (updates.grading_prompt !== undefined) params.append('grading_prompt', updates.grading_prompt);
      if (updates.deadline !== undefined) params.append('deadline', toApiDatetime(updates.deadline) || 'none');

      await api.patch(`/assignments/${assignmentId}?${params.toString()}`);
      setEditingAssignment(null);
      setSuccess('Assignment updated.');
      setTimeout(() => setSuccess(''), 2000);
      fetchAssignments();
      onSaved();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to update assignment.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="modal-overlay fade-in">
      <div className="modal-content glass-panel" style={{ maxWidth: '650px', maxHeight: '85vh', overflowY: 'auto' }}>
        <button className="close-btn" onClick={onClose}><X size={20} /></button>

        <h2 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Pencil size={20} /> Edit Class
        </h2>

        {error && <div className="error-banner">{error}</div>}
        {success && <div style={{ padding: '0.6rem 1rem', borderRadius: '0.5rem', background: '#D1FAE5', color: '#059669', marginBottom: '1rem', fontSize: '0.9rem' }}>{success}</div>}

        {/* Class Details */}
        <div style={{ marginBottom: '1.5rem' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '0.75rem', marginBottom: '0.75rem' }}>
            <div>
              <label style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: '0.4rem' }}>Class Name</label>
              <input
                type="text"
                className="input-field"
                value={className}
                onChange={e => setClassName(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') handleSaveClassDetails(); }}
              />
            </div>
            <div>
              <label style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: '0.4rem' }}>Max Students</label>
              <input
                type="number"
                className="input-field"
                value={maxStudents}
                min="1"
                placeholder="Unlimited"
                onChange={e => setMaxStudents(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') handleSaveClassDetails(); }}
              />
            </div>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <small className="text-muted">
              Currently {classData.enrollment_count ?? 0} enrolled
              {classData.max_students && ` (cap: ${classData.max_students})`}
            </small>
            <button
              className="btn-primary"
              onClick={handleSaveClassDetails}
              disabled={saving}
              style={{ whiteSpace: 'nowrap', display: 'flex', alignItems: 'center', gap: '0.4rem' }}
            >
              <Save size={15} /> Save Details
            </button>
          </div>
        </div>

        {/* Assignments */}
        <div>
          <h3 style={{ fontSize: '1rem', marginBottom: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <FileText size={16} /> Assignments ({assignments.length})
          </h3>

          {assignments.length === 0 && (
            <p className="text-muted">No assignments in this class yet.</p>
          )}

          {assignments.map(a => (
            <div key={a.assignment_id} style={{
              padding: '1rem',
              marginBottom: '0.75rem',
              borderRadius: '8px',
              border: '1px solid var(--border-color)',
              background: 'var(--bg-primary)',
            }}>
              {editingAssignment === a.assignment_id ? (
                <AssignmentEditForm
                  assignment={a}
                  onSave={(updates) => handleSaveAssignment(a.assignment_id, updates)}
                  onCancel={() => setEditingAssignment(null)}
                  saving={saving}
                />
              ) : (
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.4rem' }}>
                    <strong>{a.title}</strong>
                    <button
                      className="btn-secondary"
                      onClick={() => setEditingAssignment(a.assignment_id)}
                      style={{ padding: '0.3rem 0.5rem', fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '0.3rem' }}
                    >
                      <Pencil size={13} /> Edit
                    </button>
                  </div>
                  <div style={{ fontSize: '0.83rem', color: 'var(--text-secondary)', display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
                    <span>Marks: {a.total_marks}</span>
                    <span>
                      <Clock size={12} style={{ verticalAlign: 'middle' }} />{' '}
                      {a.deadline ? formatDateTime(a.deadline) : 'No deadline'}
                    </span>
                    <span>Prompt: {a.grading_prompt ? a.grading_prompt.slice(0, 40) + (a.grading_prompt.length > 40 ? '...' : '') : 'Default AI'}</span>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>

        <div className="modal-actions" style={{ marginTop: '1rem' }}>
          <button type="button" className="btn-secondary" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
}

function AssignmentEditForm({ assignment, onSave, onCancel, saving }) {
  const [title, setTitle] = useState(assignment.title);
  const [totalMarks, setTotalMarks] = useState(assignment.total_marks);
  const [gradingPrompt, setGradingPrompt] = useState(assignment.grading_prompt || '');
  const [deadline, setDeadline] = useState(
    assignment.deadline ? toDatetimeLocalValue(assignment.deadline) : ''
  );

  const originalDeadlineLocal = assignment.deadline
    ? toDatetimeLocalValue(assignment.deadline)
    : '';

  const handleSubmit = () => {
    if (deadline && deadline !== originalDeadlineLocal) {
      const picked = new Date(deadline);
      if (!Number.isNaN(picked.getTime()) && picked < new Date()) {
        alert('Deadline cannot be in the past.');
        return;
      }
    }
    onSave({
      title,
      total_marks: totalMarks,
      grading_prompt: gradingPrompt,
      deadline,
    });
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
      <div>
        <label style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-secondary)' }}>Title</label>
        <input type="text" className="input-field" value={title} onChange={e => setTitle(e.target.value)} style={{ marginTop: '0.2rem' }} />
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
        <div>
          <label style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-secondary)' }}>Total Marks</label>
          <input type="number" className="input-field" value={totalMarks} min={1} onChange={e => setTotalMarks(parseInt(e.target.value) || 0)} style={{ marginTop: '0.2rem' }} />
        </div>
        <div>
          <label style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-secondary)' }}>Deadline</label>
          <div style={{ marginTop: '0.2rem' }}>
            <DateTimeField
              value={deadline}
              min={nowForDatetimeLocal()}
              onChange={setDeadline}
            />
          </div>
        </div>
      </div>
      <div>
        <label style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-secondary)' }}>Grading Prompt</label>
        <textarea
          className="input-field"
          rows={3}
          value={gradingPrompt}
          onChange={e => setGradingPrompt(e.target.value)}
          placeholder="Instructions for AI grading..."
          style={{ marginTop: '0.2rem', resize: 'vertical', fontFamily: 'inherit' }}
        />
      </div>
      <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end' }}>
        <button className="btn-secondary" onClick={onCancel} style={{ fontSize: '0.85rem' }}>Cancel</button>
        <button className="btn-primary" onClick={handleSubmit} disabled={saving} style={{ fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
          <Save size={14} /> {saving ? 'Saving...' : 'Save Changes'}
        </button>
      </div>
    </div>
  );
}
