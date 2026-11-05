import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Award, Clock, CheckCircle, XCircle, AlertCircle, ArrowLeft, BarChart3, Users } from 'lucide-react';
import api from '../services/api';
import { formatDateTime } from '../utils/dateFormat';

export default function QuizResults() {
  const { quizId } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [stats, setStats] = useState(null);
  const [attempts, setAttempts] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [view, setView] = useState('summary'); // student: summary | review; teacher: stats | attempts

  const role = localStorage.getItem('role');
  const isTeacher = role === 'teacher' || role === 'admin';

  useEffect(() => {
    const fetch = async () => {
      try {
        if (isTeacher) {
          const [statsRes, attemptsRes] = await Promise.all([
            api.get(`/quizzes/${quizId}/stats`),
            api.get(`/quizzes/${quizId}/attempts`),
          ]);
          setStats(statsRes.data);
          setAttempts(attemptsRes.data);
        } else {
          const res = await api.get(`/quizzes/${quizId}/my-attempt`);
          setData(res.data);
        }
      } catch (err) {
        setError(err.response?.data?.detail || 'Failed to load results');
      } finally {
        setLoading(false);
      }
    };
    fetch();
  }, [quizId, isTeacher]);

  if (loading) return <div className="loading-state">Loading results...</div>;

  if (error) {
    return (
      <div className="dashboard-wrapper fade-in">
        <div className="error-banner" style={{ marginBottom: '1rem' }}>{error}</div>
        <button className="btn-secondary" onClick={() => navigate('/')}>← Back</button>
      </div>
    );
  }

  return (
    <div className="dashboard-wrapper fade-in">
      <button className="btn-secondary" onClick={() => navigate('/')} style={{ marginBottom: '1rem' }}>
        <ArrowLeft size={16} /> Back to Dashboard
      </button>

      {isTeacher && stats && (
        <TeacherView quizId={quizId} stats={stats} attempts={attempts} view={view} setView={setView} />
      )}

      {!isTeacher && data && (
        <StudentView data={data} view={view} setView={setView} />
      )}
    </div>
  );
}

// ── Student View ────────────────────────────────────────────────────────────
function StudentView({ data, view, setView }) {
  const passed = data.percentage >= 50;
  const m = Math.floor(data.time_taken_seconds / 60);
  const s = data.time_taken_seconds % 60;

  return (
    <>
      <div className="glass-panel" style={{ padding: '2rem', marginBottom: '1.5rem', textAlign: 'center' }}>
        <div style={{
          width: 100, height: 100, borderRadius: '50%',
          background: passed ? 'var(--status-graded-bg)' : 'var(--status-failed-bg)',
          color: passed ? 'var(--status-graded)' : 'var(--status-failed)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          margin: '0 auto 1rem',
          fontSize: '2rem', fontWeight: 800,
        }}>
          {data.percentage}%
        </div>
        <h2 style={{ marginBottom: '0.5rem' }}>{data.quiz_title}</h2>
        <p className="text-secondary" style={{ fontSize: '1.05rem', marginBottom: '1.25rem' }}>
          You scored <strong>{data.score} / {data.total_marks}</strong>
          {' '}({data.correct_count} of {data.question_count} correct)
        </p>
        {data.auto_submitted && (
          <p style={{ color: 'var(--warning)', fontSize: '0.85rem', marginBottom: '0.75rem' }}>
            <AlertCircle size={14} style={{ verticalAlign: 'middle' }} /> Quiz was auto-submitted because the timer expired
          </p>
        )}
        <div style={{ display: 'flex', gap: '1.5rem', justifyContent: 'center', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
          <span><Clock size={14} style={{ verticalAlign: 'middle' }} /> Time: {m}m {s}s</span>
          <span>Submitted: {formatDateTime(data.submitted_at)}</span>
        </div>
      </div>

      {data.show_correct_after && (
        <>
          <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem' }}>
            <TabBtn active={view === 'summary'} onClick={() => setView('summary')}>Summary</TabBtn>
            <TabBtn active={view === 'review'} onClick={() => setView('review')}>Question Review</TabBtn>
          </div>

          {view === 'summary' && (
            <div className="glass-panel" style={{ padding: '1.5rem' }}>
              <h3 style={{ fontSize: '1.05rem', marginBottom: '1rem' }}>Question Overview</h3>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(60px, 1fr))', gap: '0.4rem' }}>
                {data.questions.map((q, i) => (
                  <button
                    key={i}
                    onClick={() => setView('review')}
                    style={{
                      padding: '0.6rem',
                      borderRadius: '0.4rem',
                      border: '1px solid var(--border-color)',
                      background: q.is_correct ? 'var(--status-graded-bg)' : 'var(--status-failed-bg)',
                      color: q.is_correct ? 'var(--status-graded)' : 'var(--status-failed)',
                      cursor: 'pointer',
                      fontSize: '0.78rem',
                      fontWeight: 600,
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: 'center',
                      gap: '0.2rem',
                    }}
                  >
                    {q.is_correct ? <CheckCircle size={14} /> : <XCircle size={14} />}
                    Q{i + 1}
                  </button>
                ))}
              </div>
            </div>
          )}

          {view === 'review' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              {data.questions.map((q, i) => (
                <QuestionReview key={i} q={q} index={i} />
              ))}
            </div>
          )}
        </>
      )}

      {!data.show_correct_after && (
        <div className="glass-panel" style={{ padding: '1.5rem', textAlign: 'center' }}>
          <p className="text-secondary">Your teacher has chosen not to reveal the correct answers.</p>
        </div>
      )}
    </>
  );
}

function QuestionReview({ q, index }) {
  return (
    <div className="glass-panel" style={{ padding: '1.25rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '1rem', marginBottom: '0.75rem' }}>
        <strong style={{ fontSize: '0.95rem' }}>Q{index + 1}. {q.question_text}</strong>
        <span style={{
          fontSize: '0.78rem', fontWeight: 600,
          padding: '0.25rem 0.6rem', borderRadius: '999px', whiteSpace: 'nowrap',
          background: q.is_correct ? 'var(--status-graded-bg)' : 'var(--status-failed-bg)',
          color: q.is_correct ? 'var(--status-graded)' : 'var(--status-failed)',
        }}>
          {q.marks_earned} / {q.marks}
        </span>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
        {q.options.map((opt, i) => {
          const isStudent = q.student_answer === i;
          const isCorrect = q.correct_answer === i;
          let bg = 'var(--bg-tertiary)';
          let border = '1px solid var(--border-color)';
          let icon = null;

          if (isCorrect) {
            bg = 'var(--status-graded-bg)';
            border = '1px solid var(--success)';
            icon = <CheckCircle size={15} style={{ color: 'var(--success)' }} />;
          } else if (isStudent && !isCorrect) {
            bg = 'var(--status-failed-bg)';
            border = '1px solid var(--danger)';
            icon = <XCircle size={15} style={{ color: 'var(--danger)' }} />;
          }

          return (
            <div key={i} style={{
              display: 'flex', alignItems: 'center', gap: '0.6rem',
              padding: '0.6rem 0.85rem', borderRadius: '0.4rem',
              background: bg, border,
              fontSize: '0.9rem',
            }}>
              <span style={{ fontWeight: 600, minWidth: '20px' }}>{String.fromCharCode(65 + i)}.</span>
              <span style={{ flex: 1 }}>{opt}</span>
              {isStudent && <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', fontWeight: 600 }}>YOUR ANSWER</span>}
              {icon}
            </div>
          );
        })}
      </div>

      {q.explanation && (
        <div style={{ marginTop: '0.75rem', padding: '0.75rem', borderRadius: '0.4rem', background: 'var(--accent-soft)', fontSize: '0.85rem' }}>
          <strong style={{ color: 'var(--accent-primary)' }}>Explanation: </strong>
          <span>{q.explanation}</span>
        </div>
      )}
    </div>
  );
}

// ── Teacher View ────────────────────────────────────────────────────────────
function TeacherView({ quizId, stats, attempts, view, setView }) {
  if (!stats || stats.attempt_count === 0) {
    return (
      <div className="glass-panel" style={{ padding: '2rem', textAlign: 'center' }}>
        <h2>{stats?.title || 'Quiz Results'}</h2>
        <p className="text-secondary" style={{ marginTop: '0.5rem' }}>No student has attempted this quiz yet.</p>
      </div>
    );
  }

  const m = Math.floor(stats.average_time_seconds / 60);
  const s = stats.average_time_seconds % 60;

  return (
    <>
      <div className="glass-panel" style={{ padding: '1.5rem', marginBottom: '1.5rem' }}>
        <h2 style={{ marginBottom: '0.25rem' }}>{stats.title}</h2>
        <p className="text-secondary">{stats.attempt_count} student{stats.attempt_count !== 1 ? 's' : ''} attempted this quiz</p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '0.75rem', marginBottom: '1.5rem' }}>
        <StatTile icon={Users} label="Attempts" value={stats.attempt_count} color="#3B82F6" />
        <StatTile icon={Award} label="Avg Score" value={`${stats.average_percentage}%`} color="#10B981" />
        <StatTile icon={BarChart3} label="Highest" value={stats.highest_score} color="#8B5CF6" />
        <StatTile icon={BarChart3} label="Lowest" value={stats.lowest_score} color="#F59E0B" />
        <StatTile icon={Clock} label="Avg Time" value={`${m}m ${s}s`} color="#6366F1" />
      </div>

      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem' }}>
        <TabBtn active={view === 'summary' || view === 'stats'} onClick={() => setView('stats')}>Question Stats</TabBtn>
        <TabBtn active={view === 'attempts'} onClick={() => setView('attempts')}>Attempts ({attempts.length})</TabBtn>
      </div>

      {(view === 'summary' || view === 'stats') && (
        <div className="glass-panel" style={{ padding: '1.5rem' }}>
          <h3 style={{ fontSize: '1.05rem', marginBottom: '1rem' }}>Question-by-Question Performance</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            {stats.question_stats.map((q, i) => (
              <div key={i} style={{ padding: '0.75rem 1rem', borderRadius: '0.5rem', border: '1px solid var(--border-color)', background: 'var(--bg-tertiary)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.4rem' }}>
                  <strong style={{ fontSize: '0.9rem' }}>Q{i + 1}. {q.question_text}</strong>
                  <span style={{ fontSize: '0.82rem', fontWeight: 600, color: q.correct_rate >= 70 ? 'var(--success)' : q.correct_rate >= 40 ? 'var(--warning)' : 'var(--danger)' }}>
                    {q.correct_rate}% correct
                  </span>
                </div>
                <div style={{ height: 5, borderRadius: 3, background: 'var(--border-color)', overflow: 'hidden' }}>
                  <div style={{ width: `${q.correct_rate}%`, height: '100%', background: q.correct_rate >= 70 ? 'var(--success)' : q.correct_rate >= 40 ? 'var(--warning)' : 'var(--danger)' }} />
                </div>
                <div style={{ display: 'flex', gap: '1rem', marginTop: '0.4rem', fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                  <span><CheckCircle size={11} style={{ color: 'var(--success)', verticalAlign: 'middle' }} /> {q.correct_count} correct</span>
                  <span><XCircle size={11} style={{ color: 'var(--danger)', verticalAlign: 'middle' }} /> {q.incorrect_count} wrong</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {view === 'attempts' && (
        <div className="glass-panel" style={{ padding: '1.5rem' }}>
          <div className="table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Student</th>
                  <th>Score</th>
                  <th>%</th>
                  <th>Correct</th>
                  <th>Time</th>
                  <th>Integrity</th>
                  <th>Submitted</th>
                </tr>
              </thead>
              <tbody>
                {attempts.map(a => {
                  const am = Math.floor(a.time_taken_seconds / 60);
                  const as = a.time_taken_seconds % 60;
                  const tabSwitches = a.tab_switches ?? 0;
                  const copyAttempts = a.copy_attempts ?? 0;
                  const pasteAttempts = a.paste_attempts ?? 0;
                  const timeAway = a.time_away_seconds ?? 0;
                  const flags = [];
                  if (tabSwitches > 0) flags.push({ label: `${tabSwitches} tab switch${tabSwitches > 1 ? 'es' : ''}`, severity: tabSwitches >= 3 ? 'high' : 'medium' });
                  if (copyAttempts > 0) flags.push({ label: `${copyAttempts} copy`, severity: 'low' });
                  if (pasteAttempts > 0) flags.push({ label: `${pasteAttempts} paste`, severity: 'high' });
                  if (timeAway > 30) flags.push({ label: `${timeAway}s away`, severity: timeAway > 120 ? 'high' : 'medium' });
                  return (
                    <tr key={a.attempt_id}>
                      <td><strong>{a.student_name}</strong></td>
                      <td>{a.score} / {a.total_marks}</td>
                      <td><span style={{ fontWeight: 600, color: a.percentage >= 70 ? 'var(--success)' : a.percentage >= 50 ? 'var(--warning)' : 'var(--danger)' }}>{a.percentage}%</span></td>
                      <td>{a.correct_count} / {a.question_count}</td>
                      <td>{am}m {as}s {a.auto_submitted && <span style={{ fontSize: '0.7rem', color: 'var(--warning)', marginLeft: '0.25rem' }}>(auto)</span>}</td>
                      <td>
                        {flags.length === 0 ? (
                          <span style={{ fontSize: '0.78rem', color: 'var(--success)' }}>Clean</span>
                        ) : (
                          <div style={{ display: 'flex', gap: '0.3rem', flexWrap: 'wrap' }}>
                            {flags.map((f, i) => (
                              <span
                                key={i}
                                title={f.label}
                                style={{
                                  fontSize: '0.7rem', fontWeight: 600,
                                  padding: '0.15rem 0.45rem', borderRadius: '999px',
                                  background: f.severity === 'high' ? 'var(--status-failed-bg)' : f.severity === 'medium' ? 'var(--status-pending-bg)' : 'var(--bg-tertiary)',
                                  color: f.severity === 'high' ? 'var(--danger)' : f.severity === 'medium' ? 'var(--warning)' : 'var(--text-secondary)',
                                }}
                              >
                                {f.label}
                              </span>
                            ))}
                          </div>
                        )}
                      </td>
                      <td>{formatDateTime(a.submitted_at)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </>
  );
}

function StatTile({ icon: Icon, label, value, color }) {
  return (
    <div className="glass-panel" style={{ padding: '0.85rem 1rem' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: 'var(--text-secondary)', fontSize: '0.78rem', fontWeight: 600, marginBottom: '0.3rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
        <Icon size={13} style={{ color }} /> {label}
      </div>
      <div style={{ fontSize: '1.4rem', fontWeight: 700 }}>{value}</div>
    </div>
  );
}

function TabBtn({ active, onClick, children }) {
  return (
    <button
      onClick={onClick}
      style={{
        background: 'none',
        border: 'none',
        padding: '0.6rem 1rem',
        fontSize: '0.9rem',
        fontWeight: active ? 600 : 500,
        color: active ? 'var(--accent-primary)' : 'var(--text-secondary)',
        borderBottom: active ? '2px solid var(--accent-primary)' : '2px solid transparent',
        cursor: 'pointer',
        marginBottom: '-1px',
        fontFamily: 'inherit',
      }}
    >
      {children}
    </button>
  );
}
