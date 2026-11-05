import { useState, useEffect } from 'react';
import { X, Download, FileText, Users, Award, TrendingUp, BarChart3, ChevronRight } from 'lucide-react';
import api from '../services/api';
import { formatDate } from '../utils/dateFormat';
import './UploadWidget.css';

export default function ClassReportModal({ classData, onClose }) {
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('overview'); // overview | assignments | students
  const [selectedStudent, setSelectedStudent] = useState(null);

  useEffect(() => {
    fetchReport();
  }, []);

  const fetchReport = async () => {
    try {
      const res = await api.get(`/reports/class/${classData.class_id}/summary`);
      setSummary(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const downloadFile = async (url, filename) => {
    try {
      const res = await api.get(url, { responseType: 'blob' });
      const blob = new Blob([res.data], { type: 'text/csv' });
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = filename;
      a.click();
      URL.revokeObjectURL(a.href);
    } catch (err) {
      console.error(err);
    }
  };

  const downloadClassReport = () => {
    downloadFile(`/reports/class/${classData.class_id}/csv`, `${classData.name}_report.csv`);
  };

  const downloadStudentReport = (student) => {
    downloadFile(
      `/reports/student/${student.student_id}/class/${classData.class_id}/csv`,
      `${student.name}_${classData.name}_report.csv`
    );
  };

  if (loading) {
    return (
      <div className="modal-overlay fade-in">
        <div className="modal-content glass-panel" style={{ maxWidth: '800px' }}>
          <p style={{ textAlign: 'center', padding: '2rem' }}>Loading class report...</p>
        </div>
      </div>
    );
  }

  if (!summary) return null;

  return (
    <div className="modal-overlay fade-in">
      <div className="modal-content glass-panel" style={{ maxWidth: '900px', maxHeight: '90vh', overflowY: 'auto' }}>
        <button className="close-btn" onClick={onClose}><X size={20} /></button>

        <div style={{ marginBottom: '1.5rem' }}>
          <h2 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.25rem' }}>
            <BarChart3 size={22} /> {summary.class_name}
          </h2>
          <p className="text-secondary" style={{ fontSize: '0.9rem' }}>Class Report & Analytics</p>
        </div>

        {/* ── Top Stats ─────────────────────────────────────────── */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '0.75rem', marginBottom: '1.5rem' }}>
          <StatTile
            icon={Users}
            label="Enrolled"
            value={`${summary.enrolled_count}${summary.max_students ? ` / ${summary.max_students}` : ''}`}
            color="#3B82F6"
          />
          <StatTile icon={FileText} label="Assignments" value={summary.total_assignments} color="#8B5CF6" />
          <StatTile icon={Award} label="Submissions" value={summary.total_submissions} color="#10B981" />
          <StatTile
            icon={TrendingUp}
            label="Class Average"
            value={summary.class_average !== null ? `${summary.class_average}%` : 'N/A'}
            color="#F59E0B"
          />
        </div>

        {/* ── Download All ──────────────────────────────────────── */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '1rem' }}>
          <button className="btn-primary" onClick={downloadClassReport} style={{ fontSize: '0.85rem', padding: '0.55rem 1rem' }}>
            <Download size={15} /> Download Class CSV
          </button>
        </div>

        {/* ── Tabs ──────────────────────────────────────────────── */}
        <div style={{ display: 'flex', gap: '0.25rem', borderBottom: '1px solid var(--border-color)', marginBottom: '1.25rem' }}>
          {[
            { key: 'overview', label: 'Overview' },
            { key: 'assignments', label: `Assignments (${summary.total_assignments})` },
            { key: 'students', label: `Students (${summary.enrolled_count})` },
          ].map(t => (
            <button
              key={t.key}
              onClick={() => { setActiveTab(t.key); setSelectedStudent(null); }}
              style={{
                background: 'none',
                border: 'none',
                padding: '0.6rem 1rem',
                fontSize: '0.9rem',
                fontWeight: activeTab === t.key ? 600 : 500,
                color: activeTab === t.key ? 'var(--accent-primary)' : 'var(--text-secondary)',
                borderBottom: activeTab === t.key ? '2px solid var(--accent-primary)' : '2px solid transparent',
                cursor: 'pointer',
                marginBottom: '-1px',
                fontFamily: 'inherit',
              }}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* ── Overview Tab ──────────────────────────────────────── */}
        {activeTab === 'overview' && (
          <div>
            <p className="text-secondary" style={{ fontSize: '0.9rem', marginBottom: '1rem' }}>
              Quick view of submission rates and grading status across all assignments.
            </p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
              {summary.assignments.map(a => (
                <div key={a.assignment_id} style={{ padding: '0.85rem 1rem', borderRadius: '0.55rem', border: '1px solid var(--border-color)', background: 'var(--bg-tertiary)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.4rem' }}>
                    <strong style={{ fontSize: '0.92rem' }}>{a.title}</strong>
                    <span style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
                      {a.submitted_count} / {a.enrolled_students} submitted ({a.submission_rate}%)
                    </span>
                  </div>
                  <div style={{ display: 'flex', height: '6px', borderRadius: '3px', overflow: 'hidden', background: 'var(--border-color)' }}>
                    <div style={{ width: `${a.submission_rate}%`, background: 'var(--accent-primary)' }} />
                  </div>
                  <div style={{ display: 'flex', gap: '0.75rem', marginTop: '0.5rem', fontSize: '0.78rem', color: 'var(--text-secondary)', flexWrap: 'wrap' }}>
                    <span><span style={{ color: 'var(--success)' }}>●</span> {a.graded_count} graded</span>
                    {a.pending_count > 0 && <span><span style={{ color: 'var(--warning)' }}>●</span> {a.pending_count} pending</span>}
                    {a.failed_count > 0 && <span><span style={{ color: 'var(--danger)' }}>●</span> {a.failed_count} failed</span>}
                    {a.average_score !== null && <span><strong>Avg: {a.average_score}%</strong></span>}
                  </div>
                </div>
              ))}
              {summary.assignments.length === 0 && <p className="text-muted">No assignments yet.</p>}
            </div>
          </div>
        )}

        {/* ── Assignments Tab ───────────────────────────────────── */}
        {activeTab === 'assignments' && (
          <div className="table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Assignment</th>
                  <th>Submitted</th>
                  <th>Graded</th>
                  <th>Avg %</th>
                  <th>High</th>
                  <th>Low</th>
                </tr>
              </thead>
              <tbody>
                {summary.assignments.map(a => (
                  <tr key={a.assignment_id}>
                    <td><strong>{a.title}</strong><br /><small className="text-muted">{a.total_marks} marks</small></td>
                    <td>{a.submitted_count} / {a.enrolled_students}</td>
                    <td>{a.graded_count}</td>
                    <td>{a.average_score !== null ? `${a.average_score}%` : '-'}</td>
                    <td>{a.highest_score !== null ? `${a.highest_score}%` : '-'}</td>
                    <td>{a.lowest_score !== null ? `${a.lowest_score}%` : '-'}</td>
                  </tr>
                ))}
                {summary.assignments.length === 0 && (
                  <tr><td colSpan="6" style={{ textAlign: 'center', padding: '2rem' }}>No assignments yet.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        )}

        {/* ── Students Tab ──────────────────────────────────────── */}
        {activeTab === 'students' && (
          <div>
            {selectedStudent ? (
              <StudentDetail
                studentId={selectedStudent.student_id}
                classId={classData.class_id}
                onBack={() => setSelectedStudent(null)}
                onDownload={() => downloadStudentReport(selectedStudent)}
              />
            ) : (
              <div className="table-wrapper">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Student</th>
                      <th>Submitted</th>
                      <th>Graded</th>
                      <th>Avg %</th>
                      <th>Completion</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {summary.students.map(s => (
                      <tr key={s.student_id}>
                        <td>
                          <strong>{s.name}</strong><br />
                          <small className="text-muted">{s.email}</small>
                        </td>
                        <td>{s.submitted} / {s.total_assignments}</td>
                        <td>{s.graded}</td>
                        <td>
                          {s.average_score !== null ? (
                            <span style={{ fontWeight: 600, color: s.average_score >= 70 ? 'var(--success)' : s.average_score >= 50 ? 'var(--warning)' : 'var(--danger)' }}>
                              {s.average_score}%
                            </span>
                          ) : '-'}
                        </td>
                        <td>{s.completion_rate}%</td>
                        <td>
                          <div style={{ display: 'flex', gap: '0.4rem' }}>
                            <button
                              className="btn-secondary"
                              onClick={() => setSelectedStudent(s)}
                              style={{ padding: '0.3rem 0.6rem', fontSize: '0.78rem' }}
                              title="View details"
                            >
                              <ChevronRight size={13} />
                            </button>
                            <button
                              className="btn-secondary"
                              onClick={() => downloadStudentReport(s)}
                              style={{ padding: '0.3rem 0.6rem', fontSize: '0.78rem' }}
                              title="Download CSV"
                            >
                              <Download size={13} />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                    {summary.students.length === 0 && (
                      <tr><td colSpan="6" style={{ textAlign: 'center', padding: '2rem' }}>No students enrolled yet.</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function StatTile({ icon: Icon, label, value, color }) {
  return (
    <div style={{ padding: '0.85rem 1rem', borderRadius: '0.6rem', border: '1px solid var(--border-color)', background: 'var(--bg-tertiary)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-secondary)', fontSize: '0.78rem', fontWeight: 600, marginBottom: '0.3rem' }}>
        <Icon size={14} style={{ color }} /> {label.toUpperCase()}
      </div>
      <div style={{ fontSize: '1.4rem', fontWeight: 700 }}>{value}</div>
    </div>
  );
}

function StudentDetail({ studentId, classId, onBack, onDownload }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get(`/reports/student/${studentId}/class/${classId}`)
      .then(res => setData(res.data))
      .catch(err => console.error(err))
      .finally(() => setLoading(false));
  }, [studentId, classId]);

  if (loading) return <p style={{ textAlign: 'center', padding: '2rem' }}>Loading...</p>;
  if (!data) return null;

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
        <div>
          <button onClick={onBack} className="btn-secondary" style={{ fontSize: '0.85rem', padding: '0.4rem 0.8rem' }}>← Back</button>
        </div>
        <button onClick={onDownload} className="btn-primary" style={{ fontSize: '0.85rem', padding: '0.5rem 0.9rem' }}>
          <Download size={14} /> Download CSV
        </button>
      </div>

      <div style={{ marginBottom: '1.25rem', padding: '1rem', borderRadius: '0.6rem', background: 'var(--bg-tertiary)' }}>
        <h3 style={{ fontSize: '1.05rem', marginBottom: '0.25rem' }}>{data.student.name}</h3>
        <p className="text-muted" style={{ marginBottom: '0.75rem' }}>{data.student.email}</p>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(110px, 1fr))', gap: '0.6rem' }}>
          <StatTile icon={FileText} label="Total" value={data.summary.total_assignments} color="#8B5CF6" />
          <StatTile icon={Award} label="Submitted" value={data.summary.submitted} color="#3B82F6" />
          <StatTile icon={TrendingUp} label="Graded" value={data.summary.graded} color="#10B981" />
          <StatTile icon={BarChart3} label="Avg %" value={data.summary.average_score !== null ? `${data.summary.average_score}%` : 'N/A'} color="#F59E0B" />
        </div>
      </div>

      <div className="table-wrapper">
        <table className="data-table">
          <thead>
            <tr>
              <th>Assignment</th>
              <th>Status</th>
              <th>Score</th>
              <th>%</th>
              <th>Submitted</th>
            </tr>
          </thead>
          <tbody>
            {data.submissions.map(s => (
              <tr key={s.assignment_id}>
                <td><strong>{s.assignment_title}</strong><br /><small className="text-muted">{s.total_marks} marks</small></td>
                <td><span className={`status-badge status-${s.status}`}>{s.status.replace('_', ' ')}</span></td>
                <td>{s.score !== null ? `${s.score} / ${s.total_marks}` : '-'}</td>
                <td>{s.percentage !== null ? `${s.percentage}%` : '-'}</td>
                <td>{s.submitted_at ? formatDate(s.submitted_at) : '-'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
