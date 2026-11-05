import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Clock, AlertTriangle, ChevronLeft, ChevronRight, Send, CheckCircle, EyeOff, ClipboardX, Save } from 'lucide-react';
import api from '../services/api';

export default function QuizTaker() {
  const { quizId } = useParams();
  const navigate = useNavigate();
  const storageKey = `quiz_progress_${quizId}`;

  const [quiz, setQuiz] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [answers, setAnswers] = useState({}); // { displayIdx: optionIdx (display) }
  const [currentIdx, setCurrentIdx] = useState(0);
  const [timeLeft, setTimeLeft] = useState(0);
  const [submitting, setSubmitting] = useState(false);
  const [confirmSubmit, setConfirmSubmit] = useState(false);

  // Integrity tracking
  const [tabSwitches, setTabSwitches] = useState(0);
  const [timeAway, setTimeAway] = useState(0); // seconds
  const [copyAttempts, setCopyAttempts] = useState(0);
  const [pasteAttempts, setPasteAttempts] = useState(0);
  const [violationToast, setViolationToast] = useState('');
  const [showTabWarning, setShowTabWarning] = useState(false);
  const [autosaveLabel, setAutosaveLabel] = useState('');

  const submittedRef = useRef(false);
  const hiddenAtRef = useRef(null);
  const violationTimerRef = useRef(null);

  // ── Start quiz ────────────────────────────────────────────────────────────
  useEffect(() => {
    let cancelled = false;
    const start = async () => {
      try {
        const res = await api.post(`/quizzes/${quizId}/start`);
        if (cancelled) return;
        setQuiz(res.data);
        const startMs = new Date(res.data.started_at).getTime();
        const limitMs = res.data.time_limit_minutes * 60 * 1000;
        const remaining = Math.max(0, Math.floor((startMs + limitMs - Date.now()) / 1000));
        setTimeLeft(remaining);

        // Restore autosaved progress for this quiz
        try {
          const saved = JSON.parse(localStorage.getItem(storageKey) || '{}');
          if (saved && saved.answers && typeof saved.answers === 'object') {
            setAnswers(saved.answers);
          }
          if (typeof saved.tab_switches === 'number') setTabSwitches(saved.tab_switches);
          if (typeof saved.time_away_seconds === 'number') setTimeAway(saved.time_away_seconds);
          if (typeof saved.copy_attempts === 'number') setCopyAttempts(saved.copy_attempts);
          if (typeof saved.paste_attempts === 'number') setPasteAttempts(saved.paste_attempts);
        } catch {}
      } catch (err) {
        if (cancelled) return;
        setError(err.response?.data?.detail || 'Failed to start quiz');
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    start();
    return () => { cancelled = true; };
  }, [quizId, storageKey]);

  // ── Autosave ──────────────────────────────────────────────────────────────
  useEffect(() => {
    if (!quiz || submittedRef.current) return;
    const payload = {
      answers,
      tab_switches: tabSwitches,
      time_away_seconds: timeAway,
      copy_attempts: copyAttempts,
      paste_attempts: pasteAttempts,
      saved_at: Date.now(),
    };
    try {
      localStorage.setItem(storageKey, JSON.stringify(payload));
      const t = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
      setAutosaveLabel(`Saved at ${t}`);
    } catch {}
  }, [answers, tabSwitches, timeAway, copyAttempts, pasteAttempts, quiz, storageKey]);

  // ── Submit ────────────────────────────────────────────────────────────────
  const handleSubmit = useCallback(async (autoSubmit = false) => {
    if (submittedRef.current || !quiz) return;
    submittedRef.current = true;
    setSubmitting(true);

    const originalAnswers = quiz.questions.map((q, displayIdx) => {
      const selected = answers[displayIdx];
      if (selected === undefined || selected < 0) return -1;
      return q._option_map[selected];
    });

    const orderedAnswers = new Array(quiz.questions.length).fill(-1);
    quiz.questions.forEach((q, displayIdx) => {
      orderedAnswers[q._orig_idx] = originalAnswers[displayIdx];
    });

    try {
      await api.post(`/quizzes/${quizId}/submit`, {
        answers: orderedAnswers,
        started_at: quiz.started_at,
        auto_submitted: autoSubmit,
        tab_switches: tabSwitches,
        time_away_seconds: timeAway,
        copy_attempts: copyAttempts,
        paste_attempts: pasteAttempts,
      });
      // Clear autosave on success
      try { localStorage.removeItem(storageKey); } catch {}
      navigate(`/quiz/${quizId}/result`);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to submit');
      submittedRef.current = false;
      setSubmitting(false);
    }
  }, [quiz, answers, quizId, navigate, tabSwitches, timeAway, copyAttempts, pasteAttempts, storageKey]);

  // ── Timer ─────────────────────────────────────────────────────────────────
  useEffect(() => {
    if (!quiz || submittedRef.current) return;
    if (timeLeft <= 0) {
      handleSubmit(true);
      return;
    }
    const t = setTimeout(() => setTimeLeft(s => s - 1), 1000);
    return () => clearTimeout(t);
  }, [timeLeft, quiz, handleSubmit]);

  // ── Warn before leaving ───────────────────────────────────────────────────
  useEffect(() => {
    const handler = (e) => {
      if (!submittedRef.current) {
        e.preventDefault();
        e.returnValue = '';
      }
    };
    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
  }, []);

  // ── Tab switch / visibility detection ─────────────────────────────────────
  useEffect(() => {
    if (!quiz || submittedRef.current) return;

    const onVis = () => {
      if (submittedRef.current) return;
      if (document.visibilityState === 'hidden') {
        hiddenAtRef.current = Date.now();
        setTabSwitches(c => c + 1);
        setShowTabWarning(true);
      } else if (document.visibilityState === 'visible') {
        if (hiddenAtRef.current) {
          const away = Math.round((Date.now() - hiddenAtRef.current) / 1000);
          setTimeAway(t => t + away);
          hiddenAtRef.current = null;
        }
      }
    };

    const onBlur = () => {
      if (submittedRef.current) return;
      if (!hiddenAtRef.current) {
        hiddenAtRef.current = Date.now();
        setTabSwitches(c => c + 1);
        setShowTabWarning(true);
      }
    };

    const onFocus = () => {
      if (submittedRef.current) return;
      if (hiddenAtRef.current) {
        const away = Math.round((Date.now() - hiddenAtRef.current) / 1000);
        setTimeAway(t => t + away);
        hiddenAtRef.current = null;
      }
    };

    document.addEventListener('visibilitychange', onVis);
    window.addEventListener('blur', onBlur);
    window.addEventListener('focus', onFocus);
    return () => {
      document.removeEventListener('visibilitychange', onVis);
      window.removeEventListener('blur', onBlur);
      window.removeEventListener('focus', onFocus);
    };
  }, [quiz]);

  // ── Copy / Paste / Cut / Context menu blocking ────────────────────────────
  const showViolation = (msg) => {
    setViolationToast(msg);
    if (violationTimerRef.current) clearTimeout(violationTimerRef.current);
    violationTimerRef.current = setTimeout(() => setViolationToast(''), 2200);
  };

  useEffect(() => {
    if (!quiz || submittedRef.current) return;

    const onCopy = (e) => {
      e.preventDefault();
      setCopyAttempts(c => c + 1);
      showViolation('Copying is not allowed during the quiz');
    };
    const onPaste = (e) => {
      e.preventDefault();
      setPasteAttempts(c => c + 1);
      showViolation('Pasting is not allowed during the quiz');
    };
    const onCut = (e) => {
      e.preventDefault();
      setCopyAttempts(c => c + 1);
      showViolation('Cutting is not allowed during the quiz');
    };
    const onContext = (e) => {
      e.preventDefault();
      showViolation('Right-click is disabled during the quiz');
    };

    document.addEventListener('copy', onCopy);
    document.addEventListener('paste', onPaste);
    document.addEventListener('cut', onCut);
    document.addEventListener('contextmenu', onContext);
    return () => {
      document.removeEventListener('copy', onCopy);
      document.removeEventListener('paste', onPaste);
      document.removeEventListener('cut', onCut);
      document.removeEventListener('contextmenu', onContext);
    };
  }, [quiz]);

  // ── Loading / error states ───────────────────────────────────────────────
  if (loading) return <div className="loading-state">Loading quiz...</div>;

  if (error) {
    return (
      <div className="dashboard-wrapper fade-in">
        <div className="error-banner" style={{ marginBottom: '1rem' }}>{error}</div>
        <button className="btn-secondary" onClick={() => navigate('/')}>← Back to Dashboard</button>
      </div>
    );
  }

  if (!quiz) return null;

  const totalQuestions = quiz.questions.length;
  const currentQ = quiz.questions[currentIdx];
  const answeredCount = Object.values(answers).filter(v => v !== undefined && v >= 0).length;

  const m = Math.floor(timeLeft / 60);
  const s = timeLeft % 60;
  const timeStr = `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  const timeWarning = timeLeft <= 60;

  return (
    <div
      className="dashboard-wrapper fade-in"
      style={{ maxWidth: '900px', userSelect: 'none', WebkitUserSelect: 'none' }}
      onCopy={e => { e.preventDefault(); setCopyAttempts(c => c + 1); showViolation('Copying is not allowed'); }}
    >
      {/* ── Header with timer ─────────────────────────── */}
      <div className="glass-panel" style={{ padding: '1rem 1.5rem', marginBottom: '1rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h2 style={{ fontSize: '1.15rem', margin: 0 }}>{quiz.title}</h2>
          {quiz.description && <p className="text-muted" style={{ marginTop: '0.2rem' }}>{quiz.description}</p>}
        </div>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '0.5rem',
          padding: '0.5rem 1rem',
          borderRadius: '0.5rem',
          background: timeWarning ? 'var(--status-failed-bg)' : 'var(--accent-soft)',
          color: timeWarning ? 'var(--danger)' : 'var(--accent-primary)',
          fontWeight: 700,
          fontSize: '1.1rem',
        }}>
          <Clock size={18} />
          {timeStr}
        </div>
      </div>

      {/* ── Integrity / autosave status row ─────────────── */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginBottom: '1rem', fontSize: '0.78rem' }}>
        <Pill icon={Save} label={autosaveLabel || 'Autosave on'} color="var(--success)" />
        <Pill icon={EyeOff} label={`Tab switches: ${tabSwitches}`} color={tabSwitches > 0 ? 'var(--warning)' : 'var(--text-secondary)'} />
        <Pill icon={ClipboardX} label={`Copy: ${copyAttempts} • Paste: ${pasteAttempts}`} color={(copyAttempts + pasteAttempts) > 0 ? 'var(--warning)' : 'var(--text-secondary)'} />
      </div>

      {/* ── Progress ──────────────────────────────────── */}
      <div style={{ marginBottom: '1.25rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
        <span>Question {currentIdx + 1} of {totalQuestions}</span>
        <span>{answeredCount} / {totalQuestions} answered</span>
      </div>
      <div style={{ height: 6, borderRadius: 3, background: 'var(--border-color)', marginBottom: '1.5rem', overflow: 'hidden' }}>
        <div style={{ width: `${((currentIdx + 1) / totalQuestions) * 100}%`, height: '100%', background: 'var(--accent-primary)', transition: 'width 0.3s' }} />
      </div>

      {/* ── Question ──────────────────────────────────── */}
      <div className="glass-panel" style={{ padding: '1.75rem', marginBottom: '1.5rem' }}>
        <div style={{ marginBottom: '0.5rem', fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          {currentQ.marks} {currentQ.marks === 1 ? 'mark' : 'marks'}
        </div>
        <h3 style={{ fontSize: '1.1rem', marginBottom: '1.25rem', lineHeight: 1.5 }}>{currentQ.question_text}</h3>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
          {currentQ.options.map((opt, i) => {
            const selected = answers[currentIdx] === i;
            return (
              <button
                key={i}
                onClick={() => setAnswers(a => ({ ...a, [currentIdx]: i }))}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.85rem',
                  padding: '0.85rem 1rem',
                  borderRadius: '0.5rem',
                  border: selected ? '2px solid var(--accent-primary)' : '1px solid var(--border-color)',
                  background: selected ? 'var(--accent-soft)' : 'var(--bg-secondary)',
                  cursor: 'pointer',
                  textAlign: 'left',
                  fontSize: '0.95rem',
                  color: 'var(--text-primary)',
                  fontFamily: 'inherit',
                  transition: 'all 0.15s ease',
                }}
              >
                <div style={{
                  width: 28,
                  height: 28,
                  borderRadius: '50%',
                  background: selected ? 'var(--accent-primary)' : 'var(--bg-tertiary)',
                  color: selected ? 'white' : 'var(--text-secondary)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontWeight: 700,
                  fontSize: '0.85rem',
                  flexShrink: 0,
                }}>
                  {String.fromCharCode(65 + i)}
                </div>
                <span style={{ flex: 1 }}>{opt}</span>
                {selected && <CheckCircle size={18} style={{ color: 'var(--accent-primary)' }} />}
              </button>
            );
          })}
        </div>
      </div>

      {/* ── Navigation ──────────────────────────────────── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.75rem' }}>
        <button
          className="btn-secondary"
          onClick={() => setCurrentIdx(i => Math.max(0, i - 1))}
          disabled={currentIdx === 0}
        >
          <ChevronLeft size={16} /> Previous
        </button>

        <div style={{ display: 'flex', gap: '0.3rem', flexWrap: 'wrap', justifyContent: 'center', flex: 1, maxWidth: '400px' }}>
          {quiz.questions.map((_, i) => {
            const ans = answers[i];
            const isAnswered = ans !== undefined && ans >= 0;
            const isCurrent = currentIdx === i;
            return (
              <button
                key={i}
                onClick={() => setCurrentIdx(i)}
                style={{
                  width: 30,
                  height: 30,
                  borderRadius: '50%',
                  border: isCurrent ? '2px solid var(--accent-primary)' : '1px solid var(--border-color)',
                  background: isAnswered ? 'var(--accent-primary)' : 'var(--bg-secondary)',
                  color: isAnswered ? 'white' : 'var(--text-secondary)',
                  cursor: 'pointer',
                  fontSize: '0.78rem',
                  fontWeight: 600,
                }}
              >
                {i + 1}
              </button>
            );
          })}
        </div>

        {currentIdx < totalQuestions - 1 ? (
          <button className="btn-primary" onClick={() => setCurrentIdx(i => i + 1)}>
            Next <ChevronRight size={16} />
          </button>
        ) : (
          <button className="btn-primary" onClick={() => setConfirmSubmit(true)}>
            <Send size={15} /> Submit
          </button>
        )}
      </div>

      {/* ── Submit confirmation ──────────────────────── */}
      {confirmSubmit && (
        <div className="modal-overlay fade-in" onClick={() => !submitting && setConfirmSubmit(false)}>
          <div className="modal-content glass-panel" style={{ maxWidth: '420px' }} onClick={e => e.stopPropagation()}>
            <h3 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem' }}>
              <AlertTriangle size={20} style={{ color: 'var(--warning)' }} /> Submit Quiz?
            </h3>
            <p style={{ color: 'var(--text-secondary)', marginBottom: '1rem' }}>
              You answered <strong>{answeredCount} / {totalQuestions}</strong> questions.
              {answeredCount < totalQuestions && ' Unanswered questions will be marked wrong.'}
            </p>
            <p style={{ color: 'var(--text-secondary)', marginBottom: '1.5rem', fontSize: '0.85rem' }}>
              You cannot change your answers after submitting.
            </p>
            <div className="modal-actions">
              <button className="btn-secondary" onClick={() => setConfirmSubmit(false)} disabled={submitting}>
                Continue Quiz
              </button>
              <button className="btn-primary" onClick={() => handleSubmit(false)} disabled={submitting}>
                <Send size={15} /> {submitting ? 'Submitting...' : 'Confirm Submit'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Tab switch warning ──────────────────────── */}
      {showTabWarning && (
        <div className="modal-overlay fade-in" style={{ zIndex: 1200 }}>
          <div className="modal-content glass-panel" style={{ maxWidth: '440px' }}>
            <h3 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem', color: 'var(--danger)' }}>
              <AlertTriangle size={20} /> Tab Switch Detected
            </h3>
            <p style={{ color: 'var(--text-secondary)', marginBottom: '1rem' }}>
              You left the quiz tab. This event has been logged ({tabSwitches} time{tabSwitches !== 1 ? 's' : ''} so far).
            </p>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginBottom: '1.5rem' }}>
              Repeated tab switches may be flagged as suspicious behavior in your teacher's report.
            </p>
            <div className="modal-actions">
              <button className="btn-primary" onClick={() => setShowTabWarning(false)}>I Understand — Continue</button>
            </div>
          </div>
        </div>
      )}

      {/* ── Violation toast ──────────────────────────── */}
      {violationToast && (
        <div style={{
          position: 'fixed', bottom: '1.5rem', left: '50%', transform: 'translateX(-50%)',
          padding: '0.75rem 1.25rem', borderRadius: '0.5rem',
          background: 'var(--status-failed-bg)', color: 'var(--status-failed)',
          border: '1px solid var(--danger)', boxShadow: 'var(--shadow-lg)',
          zIndex: 1300, fontSize: '0.88rem', fontWeight: 500,
          display: 'flex', alignItems: 'center', gap: '0.5rem',
        }}>
          <ClipboardX size={16} /> {violationToast}
        </div>
      )}
    </div>
  );
}

function Pill({ icon: Icon, label, color }) {
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: '0.35rem',
      padding: '0.3rem 0.65rem', borderRadius: '999px',
      border: '1px solid var(--border-color)', background: 'var(--bg-tertiary)',
      color, fontWeight: 600,
    }}>
      <Icon size={12} /> {label}
    </span>
  );
}
