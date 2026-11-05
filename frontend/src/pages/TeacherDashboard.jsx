import { useState, useEffect } from 'react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { FileCheck, Target, Activity, ChevronDown, ChevronUp, Plus, Users, FileText, Clock, Eye, Trash2, Pencil, BarChart3, MessageSquare, Edit3, Shield, AlertTriangle, Sparkles, ScanLine, RotateCcw } from 'lucide-react';
import api from '../services/api';
import UploadWidget from '../components/UploadWidget';
import EditClassModal from '../components/EditClassModal';
import ClassReportModal from '../components/ClassReportModal';
import QuizList from '../components/QuizList';
import OMRList from '../components/OMRList';
import QuizBuilderModal from '../components/QuizBuilderModal';
import OMRTemplateModal from '../components/OMRTemplateModal';
import MessagesPanel from '../components/MessagesPanel';
import ManualGradeModal from '../components/ManualGradeModal';
import ClassMessagesModal from '../components/ClassMessagesModal';
import DeadlinesWidget from '../components/DeadlinesWidget';
import WelcomeHeader from '../components/WelcomeHeader';
import { formatDate, formatDateTime } from '../utils/dateFormat';
import './Dashboard.css';

export default function TeacherDashboard() {
  const [stats, setStats] = useState({ total_exams: 0, graded_exams: 0, average_percentage: 0 });
  const [submissions, setSubmissions] = useState([]);
  const [classes, setClasses] = useState([]);
  const [selectedClass, setSelectedClass] = useState(null);
  const [assignments, setAssignments] = useState([]);
  const [selectedAssignment, setSelectedAssignment] = useState(null);
  const [assignmentSubmissions, setAssignmentSubmissions] = useState([]);
  const [newClassName, setNewClassName] = useState('');
  const [newMaxStudents, setNewMaxStudents] = useState('');
  const [activeClassToUpload, setActiveClassToUpload] = useState(null);
  const [quizClass, setQuizClass] = useState(null);   // class id for the quiz builder
  const [omrClass, setOmrClass] = useState(null);     // class id for the OMR template modal
  const [listsVersion, setListsVersion] = useState(0); // bumps to refresh QuizList / OMRList
  const [editingClass, setEditingClass] = useState(null); // full class object for modal
  const [reportingClass, setReportingClass] = useState(null); // class to show report for
  const [classChats, setClassChats] = useState(null);
  const [messagingSubmission, setMessagingSubmission] = useState(null);
  const [gradingSubmission, setGradingSubmission] = useState(null);
  const [plagiarismRunning, setPlagiarismRunning] = useState(false);
  const [plagiarismResult, setPlagiarismResult] = useState(null);
  const [expandedSubmission, setExpandedSubmission] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchData = async () => {
    try {
      const [statsRes, subRes, classRes] = await Promise.all([
        api.get('/dashboard/stats'),
        api.get('/dashboard/exams'),
        api.get('/classes/')
      ]);
      setStats(statsRes.data);
      setSubmissions(subRes.data);
      setClasses(classRes.data);
    } catch (err) {
      console.error("Teacher Dashboard data error", err);
    } finally {
      setLoading(false);
    }
  };

  const handleClassSelect = async (classId) => {
    setSelectedClass(classId);
    setSelectedAssignment(null);
    setAssignmentSubmissions([]);
    try {
      const res = await api.get(`/assignments/class/${classId}`);
      setAssignments(res.data);
    } catch (err) {
      console.error(err);
    }
  };

  const handleViewSubmissions = async (assignment) => {
    setSelectedAssignment(assignment);
    try {
      const res = await api.get(`/submissions/assignment/${assignment.assignment_id}`);
      setAssignmentSubmissions(res.data);
    } catch (err) {
      console.error(err);
    }
  };

  const handleCreateClass = async (e) => {
    e.preventDefault();
    if (!newClassName.trim()) return;
    try {
      const payload = { name: newClassName.trim() };
      const max = parseInt(newMaxStudents);
      if (!isNaN(max) && max > 0) payload.max_students = max;
      await api.post('/classes/', payload);
      setNewClassName('');
      setNewMaxStudents('');
      fetchData();
    } catch (err) {
      console.error(err);
    }
  };

  const allowResubmission = async (sub) => {
    const reason = window.prompt('Allow this student to submit again? The current submission and its file will be deleted.\nReason (recorded in the audit log):');
    if (!reason || reason.trim().length < 3) return;
    try {
      await api.post(`/submissions/${sub.submission_id}/allow-resubmission`, { reason: reason.trim() });
      refreshSelectedAssignmentSubmissions();
    } catch (err) {
      window.alert(err.response?.data?.detail || 'Could not allow a resubmission');
    }
  };

  const refreshSelectedAssignmentSubmissions = async () => {
    if (!selectedAssignment) return;
    try {
      const res = await api.get(`/submissions/assignment/${selectedAssignment.assignment_id}`);
      setAssignmentSubmissions(res.data);
    } catch (err) { console.error(err); }
  };

  const handleRunPlagiarism = async () => {
    if (!selectedAssignment) return;
    setPlagiarismRunning(true);
    setPlagiarismResult(null);
    try {
      const res = await api.post(`/submissions/assignment/${selectedAssignment.assignment_id}/check-plagiarism`);
      setPlagiarismResult(res.data);
      await refreshSelectedAssignmentSubmissions();
    } catch (err) {
      setPlagiarismResult({ error: err.response?.data?.detail || 'Check failed' });
    } finally {
      setPlagiarismRunning(false);
    }
  };

  const handleDeleteClass = async (classId) => {
    if (!window.confirm('Delete this class? All assignments, submissions, and enrollments will be permanently removed.')) return;
    try {
      await api.delete(`/classes/${classId}`);
      if (selectedClass === classId) {
        setSelectedClass(null);
        setAssignments([]);
        setSelectedAssignment(null);
        setAssignmentSubmissions([]);
      }
      fetchData();
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  // Poll while any visible submission is still being graded so scores appear
  // without a manual refresh.
  useEffect(() => {
    const isPending = (s) => s.status === 'uploaded' || s.status === 'processing';
    if (!submissions.some(isPending) && !assignmentSubmissions.some(isPending)) return undefined;
    const timer = setInterval(async () => {
      try {
        const [statsRes, subRes] = await Promise.all([
          api.get('/dashboard/stats'),
          api.get('/dashboard/exams'),
        ]);
        setStats(statsRes.data);
        setSubmissions(subRes.data);
        if (selectedAssignment) {
          const res = await api.get(`/submissions/assignment/${selectedAssignment.assignment_id}`);
          setAssignmentSubmissions(res.data);
        }
      } catch {
        // transient network error — keep polling
      }
    }, 5000);
    return () => clearInterval(timer);
  }, [submissions, assignmentSubmissions, selectedAssignment]);

  const chartData = [...submissions]
    .filter(e => e.status === "graded")
    .reverse()
    .map((e, index) => ({
      name: `Ex ${index + 1}`,
      score: (e.score / e.total_marks) * 100
    }));

  const formatDeadline = (dl) => {
    if (!dl) return 'No deadline';
    const d = new Date(dl);
    const now = new Date();
    const isPast = d < now;
    return (
      <span style={{ color: isPast ? 'var(--status-failed)' : 'var(--status-graded)', fontWeight: 600, fontSize: '0.85rem' }}>
        <Clock size={13} style={{ verticalAlign: 'middle', marginRight: '0.25rem' }} />
        {formatDateTime(d)}
        {isPast && ' (Closed)'}
      </span>
    );
  };

  if (loading) return <div className="loading-state">Loading dashboard...</div>;

  return (
    <div className="dashboard-wrapper fade-in">
      {editingClass && (
        <EditClassModal
          classData={editingClass}
          onClose={() => setEditingClass(null)}
          onSaved={() => { fetchData(); if (selectedClass) handleClassSelect(selectedClass); }}
        />
      )}

      {reportingClass && (
        <ClassReportModal
          classData={reportingClass}
          onClose={() => setReportingClass(null)}
        />
      )}

      {messagingSubmission && (
        <MessagesPanel
          submissionId={messagingSubmission.submission_id}
          otherUserName="Student"
          onClose={() => setMessagingSubmission(null)}
        />
      )}

      {gradingSubmission && (
        <ManualGradeModal
          submission={gradingSubmission}
          onClose={() => setGradingSubmission(null)}
          onSaved={refreshSelectedAssignmentSubmissions}
        />
      )}

      {classChats && (
        <ClassMessagesModal
          classData={classChats}
          onClose={() => setClassChats(null)}
        />
      )}

      {quizClass && (
        <QuizBuilderModal
          classId={quizClass}
          onClose={() => setQuizClass(null)}
          onSaved={() => {
            setListsVersion(v => v + 1);
            if (selectedClass !== quizClass) handleClassSelect(quizClass);
          }}
        />
      )}

      {omrClass && (
        <OMRTemplateModal
          classId={omrClass}
          onClose={() => setOmrClass(null)}
          onSaved={() => {
            setListsVersion(v => v + 1);
            if (selectedClass !== omrClass) handleClassSelect(omrClass);
          }}
        />
      )}

      {activeClassToUpload && (
        <UploadWidget
          classId={activeClassToUpload}
          isStudent={false}
          onClose={() => setActiveClassToUpload(null)}
          onUploadSuccess={() => {
            fetchData();
            if (selectedClass === activeClassToUpload) handleClassSelect(activeClassToUpload);
          }}
        />
      )}

      <WelcomeHeader title="Teacher Dashboard" subtitle="Manage classes, assignments, quizzes, OMR sheets, grading prompts, and deadlines." />


      {/* ── Stats ────────────────────────────────────── */}
      <section className="stats-grid">
        <div className="stat-card glass-panel">
          <div className="stat-icon bg-blue"><FileCheck size={24} /></div>
          <div className="stat-info">
            <span className="stat-label">Total Answers</span>
            <span className="stat-value">{stats.total_exams}</span>
          </div>
        </div>
        <div className="stat-card glass-panel">
          <div className="stat-icon bg-emerald"><Activity size={24} /></div>
          <div className="stat-info">
            <span className="stat-label">AI Graded</span>
            <span className="stat-value">{stats.graded_exams}</span>
          </div>
        </div>
        <div className="stat-card glass-panel">
          <div className="stat-icon bg-indigo"><Target size={24} /></div>
          <div className="stat-info">
            <span className="stat-label">Class Average</span>
            <span className="stat-value">{stats.average_percentage.toFixed(1)}%</span>
          </div>
        </div>
      </section>

      {/* ── Deadlines & Submission Rates ────────────── */}
      <DeadlinesWidget isStudent={false} />

      {/* ── Create Class ─────────────────────────────── */}
      <section className="glass-panel" style={{ marginBottom: '2rem', padding: '1.5rem' }}>
        <h3 className="section-title">Create New Class</h3>
        <form onSubmit={handleCreateClass} style={{ display: 'flex', gap: '1rem', maxWidth: '700px', flexWrap: 'wrap' }}>
          <input
            type="text"
            className="input-field"
            placeholder="e.g. Physics 101 - Fall 2026"
            value={newClassName}
            onChange={e => setNewClassName(e.target.value)}
            style={{ flex: 2, minWidth: '220px' }}
          />
          <input
            type="number"
            className="input-field"
            placeholder="Max students (optional)"
            min="1"
            value={newMaxStudents}
            onChange={e => setNewMaxStudents(e.target.value)}
            style={{ flex: 1, minWidth: '160px' }}
          />
          <button type="submit" className="btn-primary" style={{ whiteSpace: 'nowrap' }}>
            <Plus size={18} /> Create
          </button>
        </form>
      </section>

      {/* ── Class Cards ──────────────────────────────── */}
      <section style={{ marginBottom: '2rem' }}>
        <h3 className="section-title" style={{ marginBottom: '1rem' }}>Your Classes</h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '1rem' }}>
          {classes.length === 0 && <p className="text-muted">No classes yet. Create one above.</p>}
          {classes.map(c => (
            <div
              key={c.class_id}
              className="stat-card glass-panel"
              style={{
                flexDirection: 'column',
                alignItems: 'flex-start',
                cursor: 'pointer',
                border: selectedClass === c.class_id ? '2px solid var(--accent-primary)' : '2px solid transparent',
                transition: 'border 0.2s ease',
              }}
              onClick={() => handleClassSelect(c.class_id)}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.75rem', width: '100%' }}>
                <div className="stat-icon bg-indigo"><Users size={18} /></div>
                <h3 style={{ fontSize: '1rem', margin: 0, flex: 1 }}>{c.name}</h3>
              </div>
              <div style={{ display: 'flex', gap: '0.75rem', marginBottom: '0.75rem', fontSize: '0.78rem', color: 'var(--text-secondary)', flexWrap: 'wrap' }}>
                <span title="Enrolled students">
                  <Users size={12} style={{ verticalAlign: 'middle', marginRight: '0.2rem' }} />
                  <strong style={{ color: 'var(--text-primary)' }}>{c.enrollment_count ?? 0}</strong>
                  {c.max_students ? ` / ${c.max_students}` : ''} students
                </span>
                <span title="Assignments">
                  <FileText size={12} style={{ verticalAlign: 'middle', marginRight: '0.2rem' }} />
                  <strong style={{ color: 'var(--text-primary)' }}>{c.assignments_count ?? 0}</strong> assignments
                </span>
              </div>
              <div style={{ display: 'flex', gap: '0.4rem', width: '100%', flexWrap: 'wrap' }}>
                <button
                  className="btn-secondary"
                  style={{ flex: '1 1 auto', display: 'flex', justifyContent: 'center', gap: '0.4rem', fontSize: '0.82rem', minWidth: '120px' }}
                  onClick={(e) => { e.stopPropagation(); setActiveClassToUpload(c.class_id); }}
                >
                  <Plus size={14} /> Assignment
                </button>
                <button
                  className="btn-secondary"
                  style={{ flex: '1 1 auto', display: 'flex', justifyContent: 'center', gap: '0.4rem', fontSize: '0.82rem', minWidth: '90px' }}
                  title="Create a quiz (AI-generated or manual, MCQ and true/false)"
                  onClick={(e) => { e.stopPropagation(); setQuizClass(c.class_id); }}
                >
                  <Sparkles size={14} /> Quiz
                </button>
                <button
                  className="btn-secondary"
                  style={{ flex: '1 1 auto', display: 'flex', justifyContent: 'center', gap: '0.4rem', fontSize: '0.82rem', minWidth: '90px' }}
                  title="Create an OMR answer-sheet template"
                  onClick={(e) => { e.stopPropagation(); setOmrClass(c.class_id); }}
                >
                  <ScanLine size={14} /> OMR sheet
                </button>
                <button
                  className="btn-secondary"
                  style={{ padding: '0.5rem 0.6rem', color: 'var(--accent-primary)' }}
                  title="Class messages with students"
                  onClick={(e) => { e.stopPropagation(); setClassChats(c); }}
                >
                  <MessageSquare size={14} />
                </button>
                <button
                  className="btn-secondary"
                  style={{ padding: '0.5rem 0.6rem', color: 'var(--accent-primary)' }}
                  title="View report"
                  onClick={(e) => { e.stopPropagation(); setReportingClass(c); }}
                >
                  <BarChart3 size={14} />
                </button>
                <button
                  className="btn-secondary"
                  style={{ padding: '0.5rem 0.6rem' }}
                  title="Edit class & assignments"
                  onClick={(e) => { e.stopPropagation(); setEditingClass(c); }}
                >
                  <Pencil size={14} />
                </button>
                <button
                  className="btn-secondary"
                  style={{ padding: '0.5rem 0.6rem', color: '#DC2626' }}
                  title="Delete class"
                  onClick={(e) => { e.stopPropagation(); handleDeleteClass(c.class_id); }}
                >
                  <Trash2 size={14} />
                </button>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ── Assignments for Selected Class ────────────── */}
      {selectedClass && (
        <section className="table-section glass-panel" style={{ marginBottom: '2rem' }}>
          <h3 className="section-title">
            Assignments — {classes.find(c => c.class_id === selectedClass)?.name}
          </h3>
          <div className="table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Title</th>
                  <th>Marks</th>
                  <th>Deadline</th>
                  <th>Grading Prompt</th>
                  <th>Question Paper</th>
                  <th>Submissions</th>
                </tr>
              </thead>
              <tbody>
                {assignments.length === 0 && (
                  <tr><td colSpan="6" style={{ textAlign: 'center', padding: '2rem' }}>No assignments yet. Click "Add Assignment" on the class card above.</td></tr>
                )}
                {assignments.map(a => (
                  <tr key={a.assignment_id}>
                    <td><strong>{a.title}</strong></td>
                    <td>{a.total_marks}</td>
                    <td>{formatDeadline(a.deadline)}</td>
                    <td>
                      {a.grading_prompt ? (
                        <span title={a.grading_prompt} style={{ fontSize: '0.83rem', color: 'var(--text-secondary)', cursor: 'help' }}>
                          {a.grading_prompt.length > 50 ? a.grading_prompt.slice(0, 50) + '...' : a.grading_prompt}
                        </span>
                      ) : (
                        <span className="text-muted">Default AI</span>
                      )}
                    </td>
                    <td>
                      <span style={{ fontSize: '0.83rem' }}>
                        <FileText size={13} style={{ verticalAlign: 'middle', marginRight: '0.25rem' }} />
                        {a.original_name}
                      </span>
                    </td>
                    <td>
                      <button
                        className="btn-secondary"
                        onClick={() => handleViewSubmissions(a)}
                        style={{ padding: '0.35rem 0.7rem', fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '0.3rem' }}
                      >
                        <Eye size={14} /> View
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* ── Quizzes for Selected Class ────────────────── */}
      {selectedClass && (
        <section style={{ marginBottom: '2rem' }}>
          <QuizList classId={selectedClass} isStudent={false} refreshKey={listsVersion} />
        </section>
      )}

      {/* ── OMR Sheets for Selected Class ─────────────── */}
      {selectedClass && (
        <section style={{ marginBottom: '2rem' }}>
          <OMRList classId={selectedClass} isStudent={false} refreshKey={listsVersion} />
        </section>
      )}

      {/* ── Submissions for Selected Assignment ────────── */}
      {selectedAssignment && (
        <section className="table-section glass-panel" style={{ marginBottom: '2rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.5rem' }}>
            <h3 className="section-title" style={{ margin: 0 }}>Student Submissions — {selectedAssignment.title}</h3>
            <button
              className="btn-secondary"
              onClick={handleRunPlagiarism}
              disabled={plagiarismRunning || assignmentSubmissions.length < 2}
              style={{ padding: '0.4rem 0.8rem', fontSize: '0.83rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}
              title={assignmentSubmissions.length < 2 ? 'Need at least 2 submissions to compare' : 'Run plagiarism check'}
            >
              <Shield size={14} /> {plagiarismRunning ? 'Checking...' : 'Check Plagiarism'}
            </button>
          </div>

          {plagiarismResult && !plagiarismResult.error && (
            <div style={{
              padding: '0.75rem 1rem', borderRadius: '0.5rem', marginBottom: '0.75rem',
              background: plagiarismResult.flagged_pairs > 0 ? 'var(--status-failed-bg)' : 'var(--status-graded-bg)',
              color: plagiarismResult.flagged_pairs > 0 ? 'var(--status-failed)' : 'var(--status-graded)',
              border: `1px solid ${plagiarismResult.flagged_pairs > 0 ? 'var(--danger)' : 'var(--success)'}`,
              fontSize: '0.85rem',
            }}>
              <strong>Plagiarism scan complete.</strong> Compared {plagiarismResult.checked} submission(s).
              {plagiarismResult.flagged_pairs > 0
                ? ` Found ${plagiarismResult.flagged_pairs} suspicious pair${plagiarismResult.flagged_pairs > 1 ? 's' : ''} (≥${Math.round(plagiarismResult.threshold * 100)}% similarity).`
                : ' No suspicious matches detected.'}
            </div>
          )}
          {plagiarismResult?.error && <div className="error-banner">{plagiarismResult.error}</div>}

          <div className="table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>File Name</th>
                  <th>Upload Date</th>
                  <th>Status</th>
                  <th>Result</th>
                  <th>Similarity</th>
                  <th>Details</th>
                </tr>
              </thead>
              <tbody>
                {assignmentSubmissions.length === 0 && (
                  <tr><td colSpan="6" style={{ textAlign: 'center', padding: '2rem' }}>No submissions yet for this assignment.</td></tr>
                )}
                {assignmentSubmissions.map(ex => {
                  const sim = ex.similarity_max;
                  const simPct = sim !== null && sim !== undefined ? Math.round(sim * 100) : null;
                  const simHigh = simPct !== null && simPct >= 30;
                  return (
                  <>
                    <tr key={ex.submission_id}>
                      <td>
                        <strong>{ex.original_name}</strong>
                        {ex.manually_graded_at && (
                          <div style={{ fontSize: '0.7rem', color: 'var(--accent-primary)', marginTop: '0.2rem' }}>
                            <Edit3 size={10} style={{ verticalAlign: 'middle' }} /> Manually graded
                          </div>
                        )}
                      </td>
                      <td>{formatDate(ex.created_at)}</td>
                      <td><span className={`status-badge status-${ex.status}`}>{ex.status}</span></td>
                      <td>{ex.score !== null ? `${ex.score}/${ex.total_marks}` : '-'}</td>
                      <td>
                        {simPct === null ? (
                          <span className="text-muted" style={{ fontSize: '0.78rem' }}>—</span>
                        ) : simPct === 0 ? (
                          <span style={{ fontSize: '0.78rem', color: 'var(--success)' }}>Clean</span>
                        ) : (
                          <span
                            title={simHigh ? `High similarity (≥30%) — likely duplicate` : 'Low similarity'}
                            style={{
                              fontSize: '0.78rem', fontWeight: 600,
                              padding: '0.2rem 0.5rem', borderRadius: '999px',
                              background: simHigh ? 'var(--status-failed-bg)' : 'var(--status-pending-bg)',
                              color: simHigh ? 'var(--danger)' : 'var(--warning)',
                              display: 'inline-flex', alignItems: 'center', gap: '0.25rem',
                            }}
                          >
                            {simHigh && <AlertTriangle size={11} />} {simPct}%
                          </span>
                        )}
                      </td>
                      <td>
                        <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
                          {ex.status === 'graded' && (
                            <button
                              className="btn-secondary"
                              onClick={() => setExpandedSubmission(prev => prev === ex.submission_id ? null : ex.submission_id)}
                              style={{ padding: "0.3rem 0.6rem", fontSize: "0.8rem", display: "flex", alignItems: "center", gap: "0.3rem" }}
                            >
                              {expandedSubmission === ex.submission_id ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                              {expandedSubmission === ex.submission_id ? 'Hide' : 'View'}
                            </button>
                          )}
                          <button
                            className="btn-secondary"
                            onClick={() => setGradingSubmission(ex)}
                            style={{ padding: "0.3rem 0.6rem", fontSize: "0.8rem", display: "flex", alignItems: "center", gap: "0.3rem" }}
                            title="Manually grade / override"
                          >
                            <Edit3 size={14} /> Grade
                          </button>
                          <button
                            className="btn-secondary"
                            onClick={() => allowResubmission(ex)}
                            style={{ padding: "0.3rem 0.6rem", fontSize: "0.8rem", display: "flex", alignItems: "center", gap: "0.3rem" }}
                            title="Delete this submission so the student can upload again (recorded in the audit log)"
                          >
                            <RotateCcw size={14} /> Allow resubmit
                          </button>
                          <button
                            className="btn-secondary"
                            onClick={() => setMessagingSubmission(ex)}
                            style={{ padding: "0.3rem 0.6rem", fontSize: "0.8rem", display: "flex", alignItems: "center", gap: "0.3rem" }}
                            title="Message student"
                          >
                            <MessageSquare size={14} /> Reply
                          </button>
                        </div>
                      </td>
                    </tr>
                    {expandedSubmission === ex.submission_id && (
                      <tr key={`${ex.submission_id}-feedback`}>
                        <td colSpan="6" style={{ padding: 0 }}>
                          <TeacherFeedbackPanel feedback={ex.explainable_feedback} summary={ex.feedback} />
                        </td>
                      </tr>
                    )}
                  </>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* ── Graded Trend Chart ───────────────────────── */}
      <section className="chart-section glass-panel" style={{ marginBottom: '2rem' }}>
        <h3 className="section-title">Global Graded Trend</h3>
        <div className="chart-container">
          {chartData.length > 0 ? (
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="colorScore" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="var(--accent-primary)" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="var(--accent-primary)" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="name" stroke="var(--text-secondary)" fontSize={12} tickLine={false} axisLine={false} />
                <YAxis stroke="var(--text-secondary)" fontSize={12} tickLine={false} axisLine={false} domain={[0, 100]} />
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border-color)" />
                <Tooltip contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: 'var(--shadow-md)' }} formatter={(value) => [`${value.toFixed(1)}%`, 'Score']} />
                <Area type="monotone" dataKey="score" stroke="var(--accent-primary)" strokeWidth={3} fillOpacity={1} fill="url(#colorScore)" />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <div className="empty-chart">No fully graded student answers yet.</div>
          )}
        </div>
      </section>
    </div>
  );
}

function TeacherFeedbackPanel({ feedback, summary }) {
  if (!feedback && !summary) return <div style={{ padding: "1rem" }}>No feedback available.</div>;

  if (!feedback) {
    return (
      <div style={{ padding: "1rem 1.5rem", background: "var(--bg-secondary)" }}>
        <strong>Feedback:</strong> {summary}
      </div>
    );
  }

  return (
    <div style={{
      padding: "1.5rem",
      background: "var(--bg-secondary)",
      borderTop: "1px solid var(--border-color)",
    }}>
      <div style={{ marginBottom: "1rem" }}>
        <strong style={{ fontSize: "0.9rem", color: "var(--text-secondary)" }}>Overall Assessment</strong>
        <p style={{ margin: "0.3rem 0 0 0" }}>{feedback.overall_comment || summary}</p>
      </div>

      {feedback.criteria && feedback.criteria.length > 0 && (
        <div style={{ marginBottom: "1rem" }}>
          <strong style={{ fontSize: "0.9rem", color: "var(--text-secondary)" }}>Grading Breakdown</strong>
          <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem", marginTop: "0.5rem" }}>
            {feedback.criteria.map((c, i) => (
              <div key={i} style={{
                padding: "0.75rem",
                background: "var(--bg-primary)",
                borderRadius: "8px",
                border: "1px solid var(--border-color)"
              }}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.3rem" }}>
                  <strong>{c.criterion}</strong>
                  <span style={{
                    fontWeight: 600,
                    color: c.marks_awarded >= c.marks_possible * 0.7 ? "var(--status-graded)" : "var(--status-failed)"
                  }}>
                    {c.marks_awarded}/{c.marks_possible}
                  </span>
                </div>
                <p style={{ margin: 0, fontSize: "0.85rem", color: "var(--text-secondary)" }}>{c.reason}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
        {feedback.strengths && feedback.strengths.length > 0 && (
          <div>
            <strong style={{ fontSize: "0.9rem", color: "var(--status-graded)" }}>Strengths</strong>
            <ul style={{ margin: "0.3rem 0 0 0", paddingLeft: "1.2rem" }}>
              {feedback.strengths.map((s, i) => <li key={i} style={{ fontSize: "0.85rem" }}>{s}</li>)}
            </ul>
          </div>
        )}
        {feedback.improvements && feedback.improvements.length > 0 && (
          <div>
            <strong style={{ fontSize: "0.9rem", color: "var(--status-failed)" }}>Areas to Improve</strong>
            <ul style={{ margin: "0.3rem 0 0 0", paddingLeft: "1.2rem" }}>
              {feedback.improvements.map((s, i) => <li key={i} style={{ fontSize: "0.85rem" }}>{s}</li>)}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
