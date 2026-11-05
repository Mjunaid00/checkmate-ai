import { useState, useEffect } from 'react';
import { X, ScanLine, Trash2, RefreshCw, Award, CheckCircle, XCircle, MinusCircle } from 'lucide-react';
import api from '../services/api';
import './UploadWidget.css';

export default function OMRResultsModal({ template, onClose }) {
  const [submissions, setSubmissions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState(null);

  const fetch = async () => {
    setLoading(true);
    try {
      const res = await api.get(`/omr/submissions/template/${template.template_id}`);
      setSubmissions(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetch(); }, [template.template_id]);

  // Auto-refresh while sheets are still processing
  useEffect(() => {
    const stillProcessing = submissions.some(s => s.status === 'pending' || s.status === 'processing');
    if (!stillProcessing) return;
    const t = setTimeout(fetch, 5000);
    return () => clearTimeout(t);
  }, [submissions]);

  const handleDelete = async (subId) => {
    if (!window.confirm('Delete this submission?')) return;
    try {
      await api.delete(`/omr/submissions/${subId}`);
      fetch();
    } catch (err) {
      console.error(err);
    }
  };

  const total = submissions.length;
  const graded = submissions.filter(s => s.status === 'graded');
  const avgPct = graded.length ? (graded.reduce((s, sub) => s + (sub.percentage || 0), 0) / graded.length).toFixed(1) : null;

  return (
    <div className="modal-overlay fade-in">
      <div className="modal-content glass-panel" style={{ maxWidth: '900px', maxHeight: '90vh', overflowY: 'auto' }}>
        <button className="close-btn" onClick={onClose}><X size={20} /></button>

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '0.5rem', marginBottom: '1rem' }}>
          <div>
            <h2 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.2rem' }}>
              <ScanLine size={20} /> {template.title}
            </h2>
            <p className="text-muted">
              {template.sheet_type === 'true_false' ? 'True/False' : 'Multiple Choice'} · {template.num_questions} questions · {template.total_marks} marks
            </p>
          </div>
          <button className="btn-secondary" onClick={fetch} title="Refresh" style={{ padding: '0.4rem 0.7rem', fontSize: '0.8rem' }}>
            <RefreshCw size={14} /> Refresh
          </button>
        </div>

        {/* Stats row */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '0.6rem', marginBottom: '1rem' }}>
          <Stat icon={ScanLine} label="Sheets" value={total} color="#3B82F6" />
          <Stat icon={CheckCircle} label="Graded" value={graded.length} color="#10B981" />
          <Stat icon={Award} label="Class Avg" value={avgPct !== null ? `${avgPct}%` : 'N/A'} color="#F59E0B" />
        </div>

        {loading && <p className="text-muted" style={{ textAlign: 'center', padding: '1rem' }}>Loading...</p>}

        {!loading && submissions.length === 0 && (
          <div style={{ textAlign: 'center', padding: '2rem 1rem', color: 'var(--text-secondary)' }}>
            <ScanLine size={36} style={{ opacity: 0.4, marginBottom: '0.5rem' }} />
            <p>No submissions yet.</p>
          </div>
        )}

        {submissions.length > 0 && (
          <div className="table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Submitter</th>
                  <th>Source</th>
                  <th>Status</th>
                  <th>Score</th>
                  <th>Detail</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {submissions.map(s => (
                  <>
                    <tr key={s.submission_id}>
                      <td>
                        <strong>{s.submitter_name || s.candidate_label || 'Unknown'}</strong>
                        {s.student_id_number && (
                          <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>ID: {s.student_id_number}</div>
                        )}
                      </td>
                      <td>
                        <span style={{
                          fontSize: '0.72rem', fontWeight: 600,
                          padding: '0.2rem 0.5rem', borderRadius: '999px',
                          background: s.submitter_role === 'student' ? 'var(--accent-soft)' : 'var(--bg-tertiary)',
                          color: s.submitter_role === 'student' ? 'var(--accent-primary)' : 'var(--text-secondary)',
                        }}>
                          {s.submitter_role === 'student' ? 'Student' : 'Batch'}
                        </span>
                      </td>
                      <td>
                        <span className={`status-badge status-${s.status}`}>{s.status}</span>
                      </td>
                      <td>
                        {s.score !== null && s.score !== undefined ? (
                          <span style={{ fontWeight: 600, color: (s.percentage ?? 0) >= 70 ? 'var(--success)' : (s.percentage ?? 0) >= 50 ? 'var(--warning)' : 'var(--danger)' }}>
                            {s.score}/{s.total_marks} ({s.percentage}%)
                          </span>
                        ) : '-'}
                      </td>
                      <td>
                        {s.status === 'graded' && (
                          <div style={{ display: 'flex', gap: '0.5rem', fontSize: '0.78rem' }}>
                            <span style={{ color: 'var(--success)' }}><CheckCircle size={11} style={{ verticalAlign: 'middle' }} /> {s.correct_count}</span>
                            <span style={{ color: 'var(--danger)' }}><XCircle size={11} style={{ verticalAlign: 'middle' }} /> {s.incorrect_count}</span>
                            <span style={{ color: 'var(--text-secondary)' }}><MinusCircle size={11} style={{ verticalAlign: 'middle' }} /> {s.blank_count}</span>
                          </div>
                        )}
                        {s.status === 'failed' && (
                          <span title={s.error_message} style={{ color: 'var(--danger)', fontSize: '0.78rem', cursor: 'help' }}>
                            {s.error_message ? s.error_message.slice(0, 40) + '...' : 'Failed'}
                          </span>
                        )}
                      </td>
                      <td>
                        <div style={{ display: 'flex', gap: '0.3rem' }}>
                          {s.status === 'graded' && (
                            <button
                              className="btn-secondary"
                              onClick={() => setExpanded(expanded === s.submission_id ? null : s.submission_id)}
                              style={{ padding: '0.3rem 0.5rem', fontSize: '0.78rem' }}
                            >
                              {expanded === s.submission_id ? 'Hide' : 'Answers'}
                            </button>
                          )}
                          <button
                            className="btn-secondary"
                            onClick={() => handleDelete(s.submission_id)}
                            style={{ padding: '0.3rem 0.5rem', color: 'var(--danger)' }}
                            title="Delete"
                          >
                            <Trash2 size={13} />
                          </button>
                        </div>
                      </td>
                    </tr>
                    {expanded === s.submission_id && s.detected_answers && (
                      <tr>
                        <td colSpan="6" style={{ padding: 0 }}>
                          <AnswerBreakdown
                            detected={s.detected_answers}
                            answerKey={template.answer_key || []}
                            sheetType={template.sheet_type}
                            optionsPerQuestion={template.options_per_question}
                          />
                        </td>
                      </tr>
                    )}
                  </>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

function Stat({ icon: Icon, label, value, color }) {
  return (
    <div style={{ padding: '0.75rem 0.9rem', borderRadius: '0.5rem', border: '1px solid var(--border-color)', background: 'var(--bg-tertiary)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: 'var(--text-secondary)', fontSize: '0.72rem', fontWeight: 600, marginBottom: '0.25rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
        <Icon size={12} style={{ color }} /> {label}
      </div>
      <div style={{ fontSize: '1.25rem', fontWeight: 700 }}>{value}</div>
    </div>
  );
}

function AnswerBreakdown({ detected, answerKey, sheetType, optionsPerQuestion }) {
  const labels = sheetType === 'true_false'
    ? ['T', 'F']
    : Array.from({ length: optionsPerQuestion }, (_, i) => String.fromCharCode(65 + i));

  return (
    <div style={{ padding: '1rem 1.25rem', background: 'var(--bg-tertiary)', borderTop: '1px solid var(--border-color)' }}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(75px, 1fr))', gap: '0.4rem' }}>
        {detected.map((d, qi) => {
          const correct = answerKey[qi];
          const isBlank = d === -1;
          const isCorrect = !isBlank && d === correct;
          return (
            <div key={qi} style={{
              padding: '0.45rem 0.5rem', borderRadius: '0.4rem',
              border: '1px solid var(--border-color)',
              background: isBlank ? 'var(--bg-secondary)' : isCorrect ? 'var(--status-graded-bg)' : 'var(--status-failed-bg)',
              textAlign: 'center',
            }}>
              <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', fontWeight: 600 }}>Q{qi + 1}</div>
              <div style={{ fontSize: '0.85rem', fontWeight: 700, color: isBlank ? 'var(--text-muted)' : isCorrect ? 'var(--status-graded)' : 'var(--status-failed)' }}>
                {isBlank ? '—' : labels[d]}
              </div>
              {!isCorrect && !isBlank && (
                <div style={{ fontSize: '0.65rem', color: 'var(--text-secondary)' }}>
                  ✓ {labels[correct]}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
