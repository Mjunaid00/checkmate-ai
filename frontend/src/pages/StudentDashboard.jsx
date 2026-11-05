import { useState, useEffect } from 'react';
import { UploadCloud, CheckCircle, XCircle, ChevronDown, ChevronUp, Clock, FileCheck, Target, Activity, TrendingUp, TrendingDown, MessageSquare } from 'lucide-react';
import api from '../services/api';
import UploadWidget from '../components/UploadWidget';
import QuizList from '../components/QuizList';
import OMRList from '../components/OMRList';
import EnrollModal from '../components/EnrollModal';
import MessagesPanel from '../components/MessagesPanel';
import DeadlinesWidget from '../components/DeadlinesWidget';
import EnrolledClassesPanel from '../components/EnrolledClassesPanel';
import WelcomeHeader from '../components/WelcomeHeader';
import { formatDateTime } from '../utils/dateFormat';
import './Dashboard.css';

export default function StudentDashboard() {
  const [classes, setClasses] = useState([]);
  const [assignments, setAssignments] = useState([]);
  const [submissions, setSubmissions] = useState([]);
  const [selectedClass, setSelectedClass] = useState(null);
  const [activeAssignmentToUpload, setActiveAssignment] = useState(null);
  const [enrollingClass, setEnrollingClass] = useState(null);
  const [messagingSubmission, setMessagingSubmission] = useState(null);
  const [classChat, setClassChat] = useState(null);
  const [expandedSubmission, setExpandedSubmission] = useState(null);
  const [analytics, setAnalytics] = useState(null);
  const [prediction, setPrediction] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchAnalytics = async () => {
    try {
      const [analyticsRes, predRes] = await Promise.all([
        api.get('/analytics/student/me'),
        api.get('/analytics/predict/me'),
      ]);
      setAnalytics(analyticsRes.data);
      setPrediction(predRes.data);
    } catch (err) {
      // Analytics are optional — don't block dashboard
    }
  };

  const fetchBaseData = async () => {
    try {
      const [classRes, subRes] = await Promise.all([
        api.get('/classes/'),
        api.get('/submissions/student')
      ]);
      setClasses(classRes.data);
      setSubmissions(subRes.data);

      // Auto-select first enrolled class, or first class
      const enrolled = classRes.data.filter(c => c.enrolled);
      if (enrolled.length > 0) {
        handleClassSelect(enrolled[0].class_id, classRes.data);
      } else if (classRes.data.length > 0) {
        handleClassSelect(classRes.data[0].class_id, classRes.data);
      } else {
        setLoading(false);
      }
    } catch (err) {
      console.error("Student dashboard base fetch error", err);
      setLoading(false);
    }
  };

  // `classList` lets the initial fetch pass the fresh list — the `classes`
  // state is still [] inside that closure, which hid the first class's assignments.
  const handleClassSelect = async (class_id, classList) => {
    setSelectedClass(class_id);
    const list = Array.isArray(classList) ? classList : classes;
    const cls = list.find(c => c.class_id === class_id);
    if (!cls?.enrolled) {
      setAssignments([]);
      setLoading(false);
      return;
    }
    try {
      const res = await api.get(`/assignments/class/${class_id}`);
      setAssignments(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const openEnrollModal = (cls) => {
    setEnrollingClass(cls);
  };

  const handleEnrolled = async () => {
    if (!enrollingClass) return;
    const class_id = enrollingClass.class_id;
    setClasses(prev => prev.map(c => c.class_id === class_id ? { ...c, enrolled: true } : c));
    if (selectedClass === class_id) {
      try {
        const res = await api.get(`/assignments/class/${class_id}`);
        setAssignments(res.data);
      } catch (err) { console.error(err); }
    }
  };

  const handleUnenroll = async (class_id) => {
    try {
      await api.delete(`/enrollment/${class_id}`);
      setClasses(prev => prev.map(c => c.class_id === class_id ? { ...c, enrolled: false } : c));
      // If unenrolling from selected class, clear its assignments
      if (selectedClass === class_id) {
        setAssignments([]);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const toggleFeedback = (submissionId) => {
    setExpandedSubmission(prev => prev === submissionId ? null : submissionId);
  };

  useEffect(() => {
    fetchBaseData();
    fetchAnalytics();
  }, []);

  // Grading runs in the background on the server. Poll while any submission
  // is still pending so the status flips to "graded" without a page refresh.
  useEffect(() => {
    const pending = submissions.some(s => s.status === 'uploaded' || s.status === 'processing');
    if (!pending) return undefined;
    const timer = setInterval(async () => {
      try {
        const res = await api.get('/submissions/student');
        setSubmissions(res.data);
      } catch {
        // transient network error — keep polling
      }
    }, 5000);
    return () => clearInterval(timer);
  }, [submissions]);

  if (loading) return <div className="loading-state">Loading dashboard...</div>;

  return (
    <div className="dashboard-wrapper fade-in">
      {activeAssignmentToUpload && (
        <UploadWidget
          assignmentId={activeAssignmentToUpload.assignment_id}
          isStudent={true}
          onClose={() => setActiveAssignment(null)}
          onUploadSuccess={fetchBaseData}
        />
      )}

      {enrollingClass && (
        <EnrollModal
          classData={enrollingClass}
          onClose={() => setEnrollingClass(null)}
          onEnrolled={handleEnrolled}
        />
      )}

      {messagingSubmission && (
        <MessagesPanel
          submissionId={messagingSubmission.submission_id}
          otherUserName="Teacher"
          onClose={() => setMessagingSubmission(null)}
        />
      )}

      {classChat && (
        <MessagesPanel
          classId={classChat.class_id}
          otherUserName={`Teacher · ${classChat.name}`}
          onClose={() => setClassChat(null)}
        />
      )}

      <WelcomeHeader title="Student Portal" subtitle="Browse classes, enroll, and upload your answers." />


      {/* Performance Analytics */}
      {analytics && analytics.total_submissions > 0 && (
        <section className="stats-grid" style={{marginBottom: "2rem"}}>
          <div className="stat-card glass-panel">
            <div className="stat-icon bg-blue"><FileCheck size={24} /></div>
            <div className="stat-info">
              <span className="stat-label">Submissions</span>
              <span className="stat-value">{analytics.total_submissions}</span>
            </div>
          </div>
          <div className="stat-card glass-panel">
            <div className="stat-icon bg-emerald"><Target size={24} /></div>
            <div className="stat-info">
              <span className="stat-label">Average Score</span>
              <span className="stat-value">{analytics.average_score}%</span>
            </div>
          </div>
          <div className="stat-card glass-panel">
            <div className="stat-icon" style={{
              background: analytics.trend === 'improving' ? 'linear-gradient(135deg, #10B981, #059669)' :
                analytics.trend === 'declining' ? 'linear-gradient(135deg, #EF4444, #DC2626)' :
                'linear-gradient(135deg, #6366F1, #4F46E5)',
              width: 54, height: 54, borderRadius: '1rem', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'white'
            }}>
              {analytics.trend === 'improving' ? <TrendingUp size={24} /> : analytics.trend === 'declining' ? <TrendingDown size={24} /> : <Activity size={24} />}
            </div>
            <div className="stat-info">
              <span className="stat-label">Trend</span>
              <span className="stat-value" style={{fontSize: "1.2rem", textTransform: "capitalize"}}>{analytics.trend}</span>
            </div>
          </div>
        </section>
      )}

      {/* Performance Prediction */}
      {prediction && prediction.prediction === 'available' && (
        <section className="glass-panel" style={{marginBottom: "2rem", padding: "1.25rem", display: "flex", alignItems: "center", gap: "1rem",
          border: prediction.risk_level === 'high' ? '1px solid #FECACA' : prediction.risk_level === 'medium' ? '1px solid #FDE68A' : '1px solid #BBF7D0',
          background: prediction.risk_level === 'high' ? '#FEF2F2' : prediction.risk_level === 'medium' ? '#FFFBEB' : '#F0FDF4',
        }}>
          <div style={{
            width: 42, height: 42, borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700, fontSize: '0.85rem',
            background: prediction.risk_level === 'high' ? '#DC2626' : prediction.risk_level === 'medium' ? '#D97706' : '#059669', color: 'white'
          }}>
            {Math.round(prediction.predicted_next_score)}%
          </div>
          <div>
            <strong style={{fontSize: "0.9rem"}}>Performance Prediction</strong>
            <p style={{margin: "0.15rem 0 0 0", fontSize: "0.83rem", color: "var(--text-secondary)"}}>{prediction.message}</p>
          </div>
        </section>
      )}

      {/* Deadlines + assignments overview */}
      <DeadlinesWidget isStudent={true} />

      {/* Enrolled classes — primary view */}
      <EnrolledClassesPanel
        classes={classes}
        selectedClass={selectedClass}
        onSelect={(id) => handleClassSelect(id)}
        onMessage={(c) => setClassChat(c)}
      />

      {/* Class Selector — also keeps discovery / browsing flow */}
      <section className="glass-panel" style={{marginBottom: "2.5rem", padding: "1.5rem"}}>
        <h3 className="section-title">Available Classes</h3>
        <div style={{display: "flex", gap: "1rem", overflowX: "auto", flexWrap: "wrap"}}>
          {classes.length === 0 && <span className="text-muted">No classes currently open.</span>}
          {classes.map(c => (
            <div key={c.class_id} style={{display: "flex", alignItems: "center", gap: "0.5rem"}}>
              <button
                className={`btn-secondary ${selectedClass === c.class_id ? 'active' : ''}`}
                style={{background: selectedClass === c.class_id ? 'var(--bg-primary)' : 'transparent'}}
                onClick={() => handleClassSelect(c.class_id)}
              >
                {c.name}
              </button>
              {c.enrolled ? (
                <>
                  <button
                    className="btn-secondary"
                    onClick={() => setClassChat(c)}
                    title="Message teacher (always available)"
                    style={{padding: "0.4rem 0.6rem", fontSize: "0.75rem", color: "var(--accent-primary)"}}
                  >
                    <MessageSquare size={14} /> Message
                  </button>
                  <button
                    className="btn-secondary"
                    onClick={() => handleUnenroll(c.class_id)}
                    title="Leave class"
                    style={{padding: "0.4rem 0.6rem", fontSize: "0.75rem", color: "var(--status-graded)"}}
                  >
                    <CheckCircle size={14} /> Enrolled
                  </button>
                </>
              ) : (
                <button
                  className="btn-primary"
                  onClick={() => openEnrollModal(c)}
                  title="Join class"
                  style={{padding: "0.4rem 0.6rem", fontSize: "0.75rem"}}
                >
                  Enroll
                </button>
              )}
            </div>
          ))}
        </div>
      </section>

      {/* Assignments list for selected class */}
      {selectedClass && !classes.find(c => c.class_id === selectedClass)?.enrolled && (
        <section className="glass-panel" style={{marginBottom: "2.5rem", padding: "1.5rem", textAlign: "center"}}>
          <p className="text-muted">Enroll in this class to view assignments and submit answers.</p>
        </section>
      )}
      {selectedClass && classes.find(c => c.class_id === selectedClass)?.enrolled && (
        <section className="table-section glass-panel" style={{marginBottom: "2.5rem"}}>
          <h3 className="section-title">Open Assignments</h3>
          <div className="table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Assignment Title</th>
                  <th>Points</th>
                  <th>Deadline</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {assignments.length === 0 && (
                  <tr><td colSpan="4" style={{textAlign: 'center', padding: '2rem'}}>No assignments in this class.</td></tr>
                )}
                {assignments.map(a => {
                  const deadlinePassed = a.deadline && new Date(a.deadline) < new Date();
                  return (
                    <tr key={a.assignment_id}>
                      <td><strong>{a.title}</strong></td>
                      <td>{a.total_marks}</td>
                      <td>
                        {a.deadline ? (
                          <span style={{
                            fontSize: '0.83rem',
                            fontWeight: 600,
                            color: deadlinePassed ? 'var(--status-failed)' : 'var(--status-graded)'
                          }}>
                            <Clock size={13} style={{verticalAlign: 'middle', marginRight: '0.25rem'}} />
                            {formatDateTime(a.deadline)}
                            {deadlinePassed && ' (Closed)'}
                          </span>
                        ) : (
                          <span className="text-muted">No deadline</span>
                        )}
                      </td>
                      <td>
                        {deadlinePassed ? (
                          <span style={{fontSize: '0.83rem', color: 'var(--status-failed)', fontWeight: 600}}>Closed</span>
                        ) : (
                          <button className="btn-primary" onClick={() => setActiveAssignment(a)} style={{padding: "0.5rem 1rem", fontSize: "0.85rem"}}>
                            <UploadCloud size={16} /> Submit Answer
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* Quizzes for selected class */}
      {selectedClass && classes.find(c => c.class_id === selectedClass)?.enrolled && (
        <section style={{ marginBottom: '2rem' }}>
          <QuizList classId={selectedClass} isStudent={true} />
        </section>
      )}

      {/* OMR sheets for selected class */}
      {selectedClass && classes.find(c => c.class_id === selectedClass)?.enrolled && (
        <section style={{ marginBottom: '2rem' }}>
          <OMRList classId={selectedClass} isStudent={true} />
        </section>
      )}

      {/* Submissions list with explainable feedback */}
      <section className="table-section glass-panel">
        <h3 className="section-title">My Past Submissions</h3>
        <div className="table-wrapper">
          <table className="data-table">
            <thead>
              <tr>
                <th>File Submitted</th>
                <th>Status</th>
                <th>Result</th>
                <th>Details</th>
              </tr>
            </thead>
            <tbody>
              {submissions.length === 0 && (
                <tr><td colSpan="4" style={{textAlign: 'center', padding: '2rem'}}>You haven't submitted anything yet.</td></tr>
              )}
              {submissions.map(s => (
                <>
                  <tr key={s.submission_id}>
                    <td><strong>{s.original_name}</strong></td>
                    <td><span className={`status-badge status-${s.status}`}>{s.status}</span></td>
                    <td>{s.score !== null ? `${s.score}/${s.total_marks}` : '-'}</td>
                    <td>
                      <div style={{display: 'flex', gap: '0.4rem', flexWrap: 'wrap'}}>
                        {s.status === 'graded' && (
                          <button
                            className="btn-secondary"
                            onClick={() => toggleFeedback(s.submission_id)}
                            style={{padding: "0.3rem 0.6rem", fontSize: "0.8rem", display: "flex", alignItems: "center", gap: "0.3rem"}}
                          >
                            {expandedSubmission === s.submission_id ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                            {expandedSubmission === s.submission_id ? 'Hide' : 'View'} Feedback
                          </button>
                        )}
                        <button
                          className="btn-secondary"
                          onClick={() => setMessagingSubmission(s)}
                          style={{padding: "0.3rem 0.6rem", fontSize: "0.8rem", display: "flex", alignItems: "center", gap: "0.3rem"}}
                          title="Message teacher about this submission"
                        >
                          <MessageSquare size={14} /> Message
                        </button>
                      </div>
                    </td>
                  </tr>
                  {expandedSubmission === s.submission_id && s.explainable_feedback && (
                    <tr key={`${s.submission_id}-feedback`}>
                      <td colSpan="4" style={{padding: 0}}>
                        <ExplainableFeedbackPanel feedback={s.explainable_feedback} summary={s.feedback} />
                      </td>
                    </tr>
                  )}
                  {expandedSubmission === s.submission_id && !s.explainable_feedback && s.feedback && (
                    <tr key={`${s.submission_id}-feedback`}>
                      <td colSpan="4" style={{padding: "1rem 1.5rem", background: "var(--bg-secondary)"}}>
                        <strong>Feedback:</strong> {s.feedback}
                      </td>
                    </tr>
                  )}
                </>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function ExplainableFeedbackPanel({ feedback, summary }) {
  const xai = feedback?.xai;
  const contentInfo = feedback?.content_analysis;

  return (
    <div style={{
      padding: "1.5rem",
      background: "var(--bg-secondary)",
      borderTop: "1px solid var(--border-color)",
    }}>
      {/* Performance badge + content type */}
      <div style={{display: "flex", gap: "0.75rem", marginBottom: "1rem", flexWrap: "wrap"}}>
        {xai?.performance_level && (
          <span style={{
            padding: "0.25rem 0.7rem", borderRadius: "999px", fontSize: "0.78rem", fontWeight: 600,
            background: xai.performance_level === "excellent" ? "#D1FAE5" : xai.performance_level === "good" ? "#DBEAFE" : xai.performance_level === "average" ? "#FEF3C7" : "#FEE2E2",
            color: xai.performance_level === "excellent" ? "#059669" : xai.performance_level === "good" ? "#2563EB" : xai.performance_level === "average" ? "#D97706" : "#DC2626",
          }}>
            {xai.performance_level.replace("_", " ").toUpperCase()}
          </span>
        )}
        {contentInfo?.content_type && (
          <span style={{padding: "0.25rem 0.7rem", borderRadius: "999px", fontSize: "0.78rem", fontWeight: 600, background: "#E0E7FF", color: "#4338CA"}}>
            {contentInfo.content_type}{contentInfo.programming_language ? ` (${contentInfo.programming_language})` : ''}
          </span>
        )}
        {contentInfo?.ocr_extracted && (
          <span style={{padding: "0.25rem 0.7rem", borderRadius: "999px", fontSize: "0.78rem", fontWeight: 600, background: "#F3E8FF", color: "#7C3AED"}}>
            OCR Processed
          </span>
        )}
      </div>

      {/* Overall comment */}
      <div style={{marginBottom: "1rem"}}>
        <strong style={{fontSize: "0.9rem", color: "var(--text-secondary)"}}>Overall Assessment</strong>
        <p style={{margin: "0.3rem 0 0 0"}}>{feedback.overall_comment || summary}</p>
      </div>

      {/* Criteria breakdown */}
      {feedback.criteria && feedback.criteria.length > 0 && (
        <div style={{marginBottom: "1rem"}}>
          <strong style={{fontSize: "0.9rem", color: "var(--text-secondary)"}}>Grading Breakdown</strong>
          <div style={{display: "flex", flexDirection: "column", gap: "0.5rem", marginTop: "0.5rem"}}>
            {feedback.criteria.map((c, i) => (
              <div key={i} style={{
                padding: "0.75rem", background: "var(--bg-primary)", borderRadius: "8px", border: "1px solid var(--border-color)"
              }}>
                <div style={{display: "flex", justifyContent: "space-between", marginBottom: "0.3rem"}}>
                  <strong>{c.criterion}</strong>
                  <span style={{fontWeight: 600, color: c.marks_awarded >= c.marks_possible * 0.7 ? "var(--status-graded)" : "var(--status-failed)"}}>
                    {c.marks_awarded}/{c.marks_possible}
                  </span>
                </div>
                <p style={{margin: 0, fontSize: "0.85rem", color: "var(--text-secondary)"}}>{c.reason}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Keyword Analysis */}
      {xai?.keyword_analysis && (
        <div style={{marginBottom: "1rem"}}>
          <strong style={{fontSize: "0.9rem", color: "var(--text-secondary)"}}>
            Keyword Coverage: {xai.keyword_analysis.keyword_coverage}%
          </strong>
          {xai.keyword_analysis.hidden_until_deadline ? (
            <p className="text-muted" style={{fontSize: "0.78rem", marginTop: "0.35rem"}}>
              The matched and missing keywords become visible after the assignment deadline.
            </p>
          ) : (
            <div style={{display: "flex", gap: "0.4rem", flexWrap: "wrap", marginTop: "0.5rem"}}>
              {xai.keyword_analysis.matched_keywords?.map((kw, i) => (
                <span key={i} style={{padding: "0.2rem 0.5rem", borderRadius: "4px", fontSize: "0.75rem", background: "#D1FAE5", color: "#059669"}}>{kw}</span>
              ))}
              {xai.keyword_analysis.missing_keywords?.map((kw, i) => (
                <span key={i} style={{padding: "0.2rem 0.5rem", borderRadius: "4px", fontSize: "0.75rem", background: "#FEE2E2", color: "#DC2626", textDecoration: "line-through"}}>{kw}</span>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Mistakes Detected */}
      {xai?.mistakes_detected && xai.mistakes_detected.length > 0 && (
        <div style={{marginBottom: "1rem"}}>
          <strong style={{fontSize: "0.9rem", color: "#DC2626"}}>Issues Detected</strong>
          {xai.mistakes_detected.map((m, i) => (
            <div key={i} style={{
              padding: "0.5rem 0.75rem", marginTop: "0.4rem", borderRadius: "6px", fontSize: "0.83rem",
              background: m.severity === "high" ? "#FEE2E2" : "#FEF3C7",
              color: m.severity === "high" ? "#991B1B" : "#92400E",
              border: `1px solid ${m.severity === "high" ? "#FECACA" : "#FDE68A"}`,
            }}>
              <strong>{m.type}:</strong> {m.description}
            </div>
          ))}
        </div>
      )}

      {/* Strengths & Improvements */}
      <div style={{display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem", marginBottom: "1rem"}}>
        {feedback.strengths && feedback.strengths.length > 0 && (
          <div>
            <strong style={{fontSize: "0.9rem", color: "var(--status-graded)"}}>Strengths</strong>
            <ul style={{margin: "0.3rem 0 0 0", paddingLeft: "1.2rem"}}>
              {feedback.strengths.map((s, i) => <li key={i} style={{fontSize: "0.85rem"}}>{s}</li>)}
            </ul>
          </div>
        )}
        {feedback.improvements && feedback.improvements.length > 0 && (
          <div>
            <strong style={{fontSize: "0.9rem", color: "var(--status-failed)"}}>Areas to Improve</strong>
            <ul style={{margin: "0.3rem 0 0 0", paddingLeft: "1.2rem"}}>
              {feedback.improvements.map((s, i) => <li key={i} style={{fontSize: "0.85rem"}}>{s}</li>)}
            </ul>
          </div>
        )}
      </div>

      {/* Recommendations */}
      {xai?.recommendations && xai.recommendations.length > 0 && (
        <div style={{padding: "0.75rem", background: "#EFF6FF", borderRadius: "8px", border: "1px solid #BFDBFE"}}>
          <strong style={{fontSize: "0.85rem", color: "#1D4ED8"}}>Recommendations</strong>
          <ul style={{margin: "0.3rem 0 0 0", paddingLeft: "1.2rem"}}>
            {xai.recommendations.map((r, i) => <li key={i} style={{fontSize: "0.83rem", color: "#1E40AF"}}>{r}</li>)}
          </ul>
        </div>
      )}

      {/* Code Grading Results */}
      {feedback.code_grading && (
        <div style={{marginTop: "1rem", padding: "0.75rem", background: "#F0FDF4", borderRadius: "8px", border: "1px solid #BBF7D0"}}>
          <strong style={{fontSize: "0.85rem", color: "#166534"}}>Code Execution Results ({feedback.code_grading.language})</strong>
          <p style={{margin: "0.3rem 0 0 0", fontSize: "0.83rem"}}>{feedback.code_grading.execution?.summary}</p>
        </div>
      )}
    </div>
  );
}
