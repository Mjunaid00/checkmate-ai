import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { Users, FileText, ClipboardCheck, ScanLine, ShieldAlert, TrendingUp, Award, Download, BarChart3 } from 'lucide-react';
import api from '../services/api';
import { formatDateShort } from '../utils/dateFormat';
import './Dashboard.css';

export default function Analytics() {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchData = async () => {
      try {
        const res = await api.get('/analytics/teacher/overview');
        setData(res.data);
      } catch (err) {
        setError(err.response?.data?.detail || 'Failed to load analytics');
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const handleDownloadClass = async (classId, className) => {
    try {
      const res = await api.get(`/reports/class/${classId}/csv`, { responseType: 'blob' });
      const blob = new Blob([res.data], { type: 'text/csv' });
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = `${className}_report.csv`;
      a.click();
      URL.revokeObjectURL(a.href);
    } catch (err) {
      console.error(err);
    }
  };

  if (loading) return <div className="loading-state">Loading analytics...</div>;

  if (error) {
    return (
      <div className="dashboard-wrapper fade-in">
        <div className="error-banner">{error}</div>
      </div>
    );
  }

  if (!data) return null;

  const { totals, averages, class_averages, submission_timeline } = data;
  const distribution = data.score_distribution || null;
  const weakQuestions = data.weak_questions || [];
  // One row per grade band with the three assessment kinds side by side.
  const distributionRows = distribution
    ? distribution.submissions.map((b, i) => ({
        range: b.range,
        Assignments: b.count,
        Quizzes: distribution.quizzes[i]?.count ?? 0,
        OMR: distribution.omr[i]?.count ?? 0,
      }))
    : [];
  const hasDistribution = distributionRows.some(r => r.Assignments + r.Quizzes + r.OMR > 0);

  return (
    <div className="dashboard-wrapper fade-in">
      <header className="dashboard-header">
        <div>
          <h1 className="page-title">
            <BarChart3 size={26} style={{ verticalAlign: 'middle', marginRight: '0.5rem' }} />
            Reports & Analytics
          </h1>
          <p className="page-subtitle">Aggregate view of your classes, students, and assessments.</p>
        </div>
      </header>

      {/* ── Top totals ─────────────────────────────────────────── */}
      <section className="stats-grid" style={{ marginBottom: '2rem' }}>
        <Tile icon={Users} label="Classes" value={totals.classes} color="#3B82F6" />
        <Tile icon={Users} label="Students" value={totals.students} color="#8B5CF6" />
        <Tile icon={FileText} label="Assignments" value={totals.assignments} color="#F59E0B" />
        <Tile icon={ClipboardCheck} label="Quizzes" value={totals.quizzes} color="#10B981" />
        <Tile icon={ScanLine} label="OMR Templates" value={totals.omr_templates} color="#EC4899" />
        {totals.plagiarism_flags > 0 && (
          <Tile icon={ShieldAlert} label="Plagiarism Flags" value={totals.plagiarism_flags} color="#DC2626" />
        )}
      </section>

      {/* ── Averages row ───────────────────────────────────────── */}
      <section className="stats-grid" style={{ marginBottom: '2rem' }}>
        <Tile
          icon={Award}
          label="Avg Submission Score"
          value={averages.submission_avg !== null ? `${averages.submission_avg}%` : 'N/A'}
          color="#10B981"
          subtitle={`${totals.graded_submissions} of ${totals.submissions} graded`}
        />
        <Tile
          icon={Award}
          label="Avg Quiz Score"
          value={averages.quiz_avg !== null ? `${averages.quiz_avg}%` : 'N/A'}
          color="#3B82F6"
          subtitle={`${totals.quiz_attempts} attempt${totals.quiz_attempts !== 1 ? 's' : ''}`}
        />
        <Tile
          icon={Award}
          label="Avg OMR Score"
          value={averages.omr_avg !== null ? `${averages.omr_avg}%` : 'N/A'}
          color="#EC4899"
          subtitle={`${totals.omr_submissions} submission${totals.omr_submissions !== 1 ? 's' : ''}`}
        />
      </section>

      {/* ── Submission timeline ────────────────────────────────── */}
      <section className="chart-section glass-panel" style={{ marginBottom: '2rem' }}>
        <h3 className="section-title">
          <TrendingUp size={16} style={{ verticalAlign: 'middle', marginRight: '0.4rem' }} />
          Submissions — Last 14 Days
        </h3>
        <div className="chart-container">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={submission_timeline} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="subFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="var(--accent-primary)" stopOpacity={0.4} />
                  <stop offset="100%" stopColor="var(--accent-primary)" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="date" stroke="var(--text-secondary)" fontSize={11} tickLine={false} axisLine={false}
                tickFormatter={(d) => formatDateShort(d)}
              />
              <YAxis stroke="var(--text-secondary)" fontSize={11} tickLine={false} axisLine={false} allowDecimals={false} />
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border-color)" />
              <Tooltip contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: 'var(--shadow-md)', background: 'var(--bg-secondary)' }} />
              <Area type="monotone" dataKey="submissions" stroke="var(--accent-primary)" strokeWidth={2} fillOpacity={1} fill="url(#subFill)" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </section>

      {/* ── Per-class averages chart ───────────────────────────── */}
      {class_averages.length > 0 && (
        <section className="chart-section glass-panel" style={{ marginBottom: '2rem' }}>
          <h3 className="section-title">Class Averages</h3>
          <div className="chart-container">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={class_averages.map(c => ({ ...c, average_score: c.average_score || 0 }))}>
                <XAxis dataKey="class_name" stroke="var(--text-secondary)" fontSize={11} tickLine={false} axisLine={false} />
                <YAxis stroke="var(--text-secondary)" fontSize={11} tickLine={false} axisLine={false} domain={[0, 100]} />
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border-color)" />
                <Tooltip contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: 'var(--shadow-md)', background: 'var(--bg-secondary)' }} formatter={(v) => [`${v}%`, 'Average']} />
                <Bar dataKey="average_score" fill="var(--accent-primary)" radius={[8, 8, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>
      )}

      {/* ── Score distribution ─────────────────────────────────── */}
      {hasDistribution && (
        <section className="chart-section glass-panel" style={{ marginBottom: '2rem' }}>
          <h3 className="section-title">Score Distribution</h3>
          <p className="text-muted" style={{ fontSize: '0.82rem', marginTop: '-0.5rem', marginBottom: '0.75rem' }}>
            How many results fall into each grade band, across all your classes.
          </p>
          <div className="chart-container">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={distributionRows}>
                <XAxis dataKey="range" stroke="var(--text-secondary)" fontSize={11} tickLine={false} axisLine={false} />
                <YAxis stroke="var(--text-secondary)" fontSize={11} tickLine={false} axisLine={false} allowDecimals={false} />
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border-color)" />
                <Tooltip contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: 'var(--shadow-md)', background: 'var(--bg-secondary)' }} />
                <Legend />
                <Bar dataKey="Assignments" fill="#10B981" radius={[6, 6, 0, 0]} />
                <Bar dataKey="Quizzes" fill="#3B82F6" radius={[6, 6, 0, 0]} />
                <Bar dataKey="OMR" fill="#EC4899" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>
      )}

      {/* ── Weakest quiz questions ─────────────────────────────── */}
      {weakQuestions.length > 0 && (
        <section className="table-section glass-panel" style={{ marginBottom: '2rem' }}>
          <h3 className="section-title">Questions Students Struggle With</h3>
          <p className="text-muted" style={{ fontSize: '0.82rem', marginTop: '-0.5rem', marginBottom: '0.75rem' }}>
            Lowest correct rates across your quizzes - the concepts worth revisiting in class.
          </p>
          <div className="table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Quiz</th>
                  <th>Question</th>
                  <th>Attempts</th>
                  <th>Correct</th>
                </tr>
              </thead>
              <tbody>
                {weakQuestions.map(w => (
                  <tr key={`${w.quiz_id}-${w.question_index}`}>
                    <td><strong>{w.quiz_title}</strong></td>
                    <td>Q{w.question_index + 1}. {w.question_text}</td>
                    <td>{w.attempts}</td>
                    <td>
                      <span style={{ fontWeight: 600, color: w.correct_rate >= 70 ? 'var(--success)' : w.correct_rate >= 40 ? 'var(--warning)' : 'var(--danger)' }}>
                        {w.correct_rate}%
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* ── Per-class table with download ──────────────────────── */}
      <section className="table-section glass-panel">
        <h3 className="section-title">Per-Class Details</h3>
        <div className="table-wrapper">
          <table className="data-table">
            <thead>
              <tr>
                <th>Class</th>
                <th>Enrolled</th>
                <th>Assignments</th>
                <th>Submissions</th>
                <th>Average</th>
                <th>Quizzes</th>
                <th>Quiz avg</th>
                <th>Download</th>
              </tr>
            </thead>
            <tbody>
              {class_averages.length === 0 && (
                <tr><td colSpan="8" style={{ textAlign: 'center', padding: '2rem' }}>No classes yet.</td></tr>
              )}
              {class_averages.map(c => (
                <tr key={c.class_id}>
                  <td><strong>{c.class_name}</strong></td>
                  <td>{c.enrolled}</td>
                  <td>{c.assignments}</td>
                  <td>{c.submissions}</td>
                  <td>
                    {c.average_score !== null ? (
                      <span style={{ fontWeight: 600, color: c.average_score >= 70 ? 'var(--success)' : c.average_score >= 50 ? 'var(--warning)' : 'var(--danger)' }}>
                        {c.average_score}%
                      </span>
                    ) : '-'}
                  </td>
                  <td>{c.quizzes ?? 0}</td>
                  <td>
                    {c.quiz_average !== null && c.quiz_average !== undefined ? (
                      <span style={{ fontWeight: 600, color: c.quiz_average >= 70 ? 'var(--success)' : c.quiz_average >= 50 ? 'var(--warning)' : 'var(--danger)' }}>
                        {c.quiz_average}%
                      </span>
                    ) : '-'}
                  </td>
                  <td>
                    <button
                      className="btn-secondary"
                      onClick={() => handleDownloadClass(c.class_id, c.class_name)}
                      style={{ padding: '0.35rem 0.7rem', fontSize: '0.8rem' }}
                    >
                      <Download size={13} /> CSV
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function Tile({ icon: Icon, label, value, color, subtitle }) {
  return (
    <div className="stat-card glass-panel">
      <div className="stat-icon" style={{ background: `${color}20`, color }}>
        <Icon size={22} />
      </div>
      <div className="stat-info">
        <span className="stat-label">{label}</span>
        <span className="stat-value">{value}</span>
        {subtitle && <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>{subtitle}</span>}
      </div>
    </div>
  );
}
