import { useState, useEffect } from 'react';
import { X, Plus, Trash2, Sparkles, Save, Check, ChevronDown, ChevronUp, FileUp } from 'lucide-react';
import api from '../services/api';
import DateTimeField from './DateTimeField';
import { nowForDatetimeLocal, isPast, toApiDatetime } from '../utils/dateFormat';
import './UploadWidget.css';

export default function QuizBuilderModal({ classId, onClose, onSaved }) {
  const [step, setStep] = useState('mode'); // mode | ai | manual | review
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const [meta, setMeta] = useState({
    title: '',
    description: '',
    time_limit_minutes: 30,
    deadline: '',
    shuffle_questions: true,
    shuffle_options: true,
    show_correct_after: true,
  });

  const [questions, setQuestions] = useState([blankQuestion()]);

  // AI generation form
  const [aiForm, setAiForm] = useState({
    topic: '',
    num_questions: 5,
    difficulty: 'medium',
    question_type: 'mcq', // mcq | true_false | mixed
    subject: '',
    grade_level: '',
    objectives: '',
  });
  const [pdfFile, setPdfFile] = useState(null); // PDF, TXT, MD or DOCX reference material
  const [genNote, setGenNote] = useState(''); // shown when the AI returned fewer questions than asked

  function blankQuestion(type = 'mcq') {
    return {
      type,
      question_text: '',
      options: type === 'true_false' ? ['True', 'False'] : type === 'short_answer' ? [] : ['', '', '', ''],
      correct_index: type === 'short_answer' ? null : 0,
      accepted_answers: type === 'short_answer' ? [''] : null,
      marks: 1,
      explanation: '',
    };
  }

  // Other quizzes of this class, so their questions can be reused.
  const [classQuizzes, setClassQuizzes] = useState([]);
  const [importFrom, setImportFrom] = useState('');
  useEffect(() => {
    if (!classId) return;
    api.get(`/quizzes/class/${classId}`).then(r => setClassQuizzes(r.data || [])).catch(() => {});
  }, [classId]);

  const importQuestions = () => {
    const src = classQuizzes.find(z => z.quiz_id === importFrom);
    if (!src || !src.questions) return;
    const imported = src.questions.map(q => ({
      type: q.type || 'mcq',
      question_text: q.question_text || '',
      options: q.options || [],
      correct_index: q.correct_index ?? null,
      accepted_answers: q.accepted_answers || null,
      marks: q.marks || 1,
      explanation: q.explanation || '',
    }));
    setQuestions(qs => {
      const onlyBlank = qs.length === 1 && !qs[0].question_text.trim();
      return onlyBlank ? imported : [...qs, ...imported];
    });
    setImportFrom('');
  };

  // ── AI Generation ────────────────────────────────────────
  const handleGenerateAI = async () => {
    if (!pdfFile && !aiForm.topic.trim()) {
      setError('Enter a topic or upload a PDF, TXT or DOCX file to generate from.');
      return;
    }
    setLoading(true);
    setError('');
    try {
      let res;
      let derivedTopic = aiForm.topic.trim();
      if (pdfFile) {
        const form = new FormData();
        form.append('file', pdfFile);
        if (aiForm.topic.trim()) form.append('topic', aiForm.topic.trim());
        form.append('num_questions', String(aiForm.num_questions));
        form.append('difficulty', aiForm.difficulty);
        form.append('question_type', aiForm.question_type);
        if (aiForm.subject.trim()) form.append('subject', aiForm.subject.trim());
        if (aiForm.grade_level.trim()) form.append('grade_level', aiForm.grade_level.trim());
        if (aiForm.objectives.trim()) form.append('objectives', aiForm.objectives.trim());
        res = await api.post('/quizzes/generate-from-document', form, {
          headers: { 'Content-Type': 'multipart/form-data' },
        });
        derivedTopic = res.data.topic || derivedTopic || pdfFile.name.replace(/\.(pdf|txt|md|docx)$/i, '');
      } else {
        res = await api.post('/quizzes/generate', aiForm);
      }
      if (!res.data.questions || res.data.questions.length === 0) {
        setError('AI did not return any valid questions. Try again.');
        setLoading(false);
        return;
      }
      setQuestions(res.data.questions);
      const got = res.data.questions.length;
      setGenNote(got < aiForm.num_questions
        ? `The AI returned ${got} of the ${aiForm.num_questions} requested questions. Add the rest below, or go back and generate again.`
        : '');
      setMeta(m => ({ ...m, title: m.title || `Quiz on ${derivedTopic}` }));
      setStep('review');
    } catch (err) {
      setError(err.response?.data?.detail || 'AI generation failed. Make sure LM Studio is running.');
    } finally {
      setLoading(false);
    }
  };

  // ── Question editing ────────────────────────────────────
  const updateQuestion = (idx, patch) => {
    setQuestions(qs => qs.map((q, i) => i === idx ? { ...q, ...patch } : q));
  };

  const updateOption = (qIdx, oIdx, value) => {
    setQuestions(qs => qs.map((q, i) =>
      i === qIdx ? { ...q, options: q.options.map((o, j) => j === oIdx ? value : o) } : q
    ));
  };

  const addQuestion = () => setQuestions(qs => [...qs, blankQuestion()]);
  const removeQuestion = (idx) => setQuestions(qs => qs.filter((_, i) => i !== idx));

  // ── Save ─────────────────────────────────────────────────
  const handleSave = async () => {
    if (!meta.title.trim()) {
      setError('Quiz title is required');
      return;
    }
    if (questions.length === 0) {
      setError('Add at least one question');
      return;
    }
    if (meta.deadline && isPast(meta.deadline)) {
      setError('Deadline cannot be in the past.');
      return;
    }
    for (let i = 0; i < questions.length; i++) {
      const q = questions[i];
      if (!q.question_text.trim()) {
        setError(`Question ${i + 1}: text required`);
        return;
      }
      if ((q.type || 'mcq') === 'short_answer') {
        if (!(q.accepted_answers || []).some(a => a && a.trim())) {
          setError(`Question ${i + 1}: add at least one accepted answer`);
          return;
        }
        continue;
      }
      if (q.options.some(o => !o.trim())) {
        setError(`Question ${i + 1}: all options must be filled`);
        return;
      }
      if (q.correct_index === null || q.correct_index < 0 || q.correct_index >= q.options.length) {
        setError(`Question ${i + 1}: select a correct answer`);
        return;
      }
    }

    setLoading(true);
    setError('');
    try {
      const payload = {
        class_id: classId,
        ...meta,
        deadline: toApiDatetime(meta.deadline) || null,
        questions: questions.map(q => {
          const type = q.type || 'mcq';
          const isShort = type === 'short_answer';
          return {
            type,
            question_text: q.question_text.trim(),
            options: isShort ? [] : q.options.map(o => o.trim()),
            correct_index: isShort ? null : q.correct_index,
            accepted_answers: isShort ? (q.accepted_answers || []).map(a => a.trim()).filter(Boolean) : null,
            marks: parseInt(q.marks) || 1,
            explanation: q.explanation?.trim() || null,
          };
        }),
      };
      await api.post('/quizzes/', payload);
      onSaved();
      onClose();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to save quiz');
    } finally {
      setLoading(false);
    }
  };

  // ── UI ───────────────────────────────────────────────────
  return (
    <div className="modal-overlay fade-in">
      <div className="modal-content glass-panel" style={{ maxWidth: '760px', maxHeight: '90vh', overflowY: 'auto' }}>
        <button className="close-btn" onClick={onClose}><X size={20} /></button>

        <h2 style={{ marginBottom: '0.25rem' }}>Create Quiz</h2>
        <p className="text-secondary" style={{ fontSize: '0.9rem', marginBottom: '1.5rem' }}>
          {step === 'mode' && 'Choose how to create your quiz.'}
          {step === 'ai' && 'AI will generate multiple-choice and/or true/false questions you can review and edit.'}
          {step === 'manual' && 'Add and edit questions manually.'}
          {step === 'review' && 'Review the generated questions, then add details and save.'}
        </p>

        {error && <div className="error-banner">{error}</div>}

        {/* ── Mode selection ──────────────────────────────── */}
        {step === 'mode' && (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
            <ModeCard
              icon={Sparkles}
              title="Generate with AI"
              desc="Provide a topic — AI creates the questions."
              onClick={() => setStep('ai')}
              color="#8B5CF6"
            />
            <ModeCard
              icon={Plus}
              title="Build Manually"
              desc="Write each question and options yourself."
              onClick={() => { setQuestions([blankQuestion()]); setStep('manual'); }}
              color="#3B82F6"
            />
          </div>
        )}

        {/* ── AI Generation form ──────────────────────────── */}
        {step === 'ai' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div>
              <Label>Topic {pdfFile && <span style={{ color: 'var(--text-secondary)', fontWeight: 400, textTransform: 'none', letterSpacing: 0 }}>(optional when using PDF)</span>}</Label>
              <input
                type="text"
                className="input-field"
                placeholder="e.g. Newton's laws of motion, Photosynthesis, Python data types"
                value={aiForm.topic}
                onChange={e => setAiForm({ ...aiForm, topic: e.target.value })}
              />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
              <div>
                <Label>Question type</Label>
                <select
                  className="input-field"
                  value={aiForm.question_type}
                  onChange={e => setAiForm({ ...aiForm, question_type: e.target.value })}
                >
                  <option value="mcq">Multiple choice</option>
                  <option value="true_false">True / False</option>
                  <option value="mixed">Mixed (MCQ + True/False)</option>
                </select>
              </div>
              <div>
                <Label>Subject (optional)</Label>
                <input
                  type="text"
                  className="input-field"
                  placeholder="e.g. Biology"
                  value={aiForm.subject}
                  onChange={e => setAiForm({ ...aiForm, subject: e.target.value })}
                />
              </div>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '1rem' }}>
              <div>
                <Label>Grade level (optional)</Label>
                <input
                  type="text"
                  className="input-field"
                  placeholder="e.g. Grade 10, BS 2nd year"
                  value={aiForm.grade_level}
                  onChange={e => setAiForm({ ...aiForm, grade_level: e.target.value })}
                />
              </div>
              <div>
                <Label>Learning objectives (optional)</Label>
                <input
                  type="text"
                  className="input-field"
                  placeholder="What the questions should assess, e.g. explain osmosis; apply Ohm's law"
                  value={aiForm.objectives}
                  onChange={e => setAiForm({ ...aiForm, objectives: e.target.value })}
                />
              </div>
            </div>

            <div>
              <Label>Reference document (optional: PDF, TXT, DOCX)</Label>
              <div
                onClick={() => document.getElementById('quizPdfUpload').click()}
                style={{
                  border: '1px dashed var(--border-color)',
                  borderRadius: '0.5rem',
                  padding: '0.85rem 1rem',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.6rem',
                  cursor: 'pointer',
                  background: 'var(--bg-tertiary)',
                  fontSize: '0.88rem',
                }}
              >
                <FileUp size={18} style={{ color: 'var(--accent-primary)' }} />
                <span style={{ flex: 1 }}>
                  {pdfFile ? pdfFile.name : 'Click to choose a PDF, TXT or DOCX file — questions will be generated from its text'}
                </span>
                {pdfFile && (
                  <button
                    type="button"
                    className="btn-secondary"
                    style={{ padding: '0.25rem 0.55rem', fontSize: '0.78rem' }}
                    onClick={(e) => { e.stopPropagation(); setPdfFile(null); }}
                  >
                    Remove
                  </button>
                )}
                <input
                  id="quizPdfUpload"
                  type="file"
                  accept=".pdf,.txt,.md,.docx,application/pdf,text/plain,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                  style={{ display: 'none' }}
                  onChange={(e) => {
                    const f = e.target.files?.[0] || null;
                    setPdfFile(f);
                  }}
                />
              </div>
              <small style={{ color: 'var(--text-secondary)', fontSize: '0.72rem' }}>
                PDFs must contain selectable text (scanned or handwritten PDFs are not supported here). TXT and DOCX files work as they are.
              </small>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
              <div>
                <Label>Number of questions</Label>
                <input
                  type="number"
                  className="input-field"
                  min={1}
                  max={25}
                  value={aiForm.num_questions}
                  onChange={e => setAiForm({ ...aiForm, num_questions: parseInt(e.target.value) || 5 })}
                />
              </div>
              <div>
                <Label>Difficulty</Label>
                <select
                  className="input-field"
                  value={aiForm.difficulty}
                  onChange={e => setAiForm({ ...aiForm, difficulty: e.target.value })}
                >
                  <option value="easy">Easy</option>
                  <option value="medium">Medium</option>
                  <option value="hard">Hard</option>
                </select>
              </div>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: '0.5rem', marginTop: '0.5rem' }}>
              <button className="btn-secondary" onClick={() => setStep('mode')}>← Back</button>
              <button className="btn-primary" onClick={handleGenerateAI} disabled={loading}>
                <Sparkles size={16} /> {loading ? 'Generating...' : 'Generate Questions'}
              </button>
            </div>
          </div>
        )}

        {/* ── Manual / Review (question editor) ──────────── */}
        {(step === 'manual' || step === 'review') && (
          <div>
            <QuizMetaForm meta={meta} onChange={setMeta} />

            <div style={{ borderTop: '1px solid var(--border-color)', margin: '1.25rem 0', paddingTop: '1rem' }}>
              <h3 style={{ fontSize: '1rem', marginBottom: '0.75rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span>Questions ({questions.length})</span>
                <span className="text-muted" style={{ fontSize: '0.82rem' }}>
                  Total: {questions.reduce((s, q) => s + (parseInt(q.marks) || 0), 0)} marks
                </span>
              </h3>
              {step === 'review' && genNote && (
                <div style={{ fontSize: '0.83rem', color: 'var(--status-pending)', background: 'var(--status-pending-bg)', border: '1px solid var(--warning)', borderRadius: '0.5rem', padding: '0.6rem 0.8rem', marginBottom: '0.75rem' }}>
                  {genNote}
                </div>
              )}

              {classQuizzes.length > 0 && (
                <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', marginBottom: '0.75rem', flexWrap: 'wrap' }}>
                  <span style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>Reuse questions from</span>
                  <select className="input-field" style={{ width: 'auto', flex: '1 1 200px' }} value={importFrom} onChange={e => setImportFrom(e.target.value)}>
                    <option value="">choose a quiz of this class...</option>
                    {classQuizzes.map(z => <option key={z.quiz_id} value={z.quiz_id}>{z.title} ({z.question_count} q)</option>)}
                  </select>
                  <button className="btn-secondary" onClick={importQuestions} disabled={!importFrom} style={{ padding: '0.4rem 0.7rem', fontSize: '0.82rem' }}>
                    Import
                  </button>
                </div>
              )}

              {questions.map((q, idx) => (
                <QuestionEditor
                  key={idx}
                  q={q}
                  index={idx}
                  onChange={patch => updateQuestion(idx, patch)}
                  onOptionChange={(oi, val) => updateOption(idx, oi, val)}
                  onRemove={() => removeQuestion(idx)}
                  canRemove={questions.length > 1}
                />
              ))}

              <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.5rem' }}>
                <button
                  onClick={addQuestion}
                  className="btn-secondary"
                  style={{ flex: 1, justifyContent: 'center' }}
                >
                  <Plus size={16} /> Add MCQ
                </button>
                <button
                  onClick={() => setQuestions(qs => [...qs, blankQuestion('true_false')])}
                  className="btn-secondary"
                  style={{ flex: 1, justifyContent: 'center' }}
                >
                  <Plus size={16} /> Add True / False
                </button>
                <button
                  onClick={() => setQuestions(qs => [...qs, blankQuestion('short_answer')])}
                  className="btn-secondary"
                  style={{ flex: 1, justifyContent: 'center' }}
                >
                  <Plus size={16} /> Add Short answer
                </button>
              </div>
            </div>

            <div className="modal-actions">
              <button className="btn-secondary" onClick={() => setStep('mode')}>← Start Over</button>
              <button className="btn-primary" onClick={handleSave} disabled={loading}>
                <Save size={16} /> {loading ? 'Saving...' : 'Save Quiz'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function Label({ children }) {
  return (
    <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: '0.4rem' }}>
      {children}
    </label>
  );
}

function ModeCard({ icon: Icon, title, desc, onClick, color }) {
  return (
    <button
      onClick={onClick}
      className="glass-panel"
      style={{
        background: 'var(--bg-secondary)',
        border: '1px solid var(--border-color)',
        padding: '1.5rem',
        textAlign: 'left',
        cursor: 'pointer',
        display: 'flex',
        flexDirection: 'column',
        gap: '0.5rem',
        transition: 'all 0.2s ease',
        fontFamily: 'inherit',
      }}
    >
      <div style={{ width: 42, height: 42, borderRadius: '0.5rem', background: `${color}20`, color, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Icon size={20} />
      </div>
      <strong style={{ fontSize: '1rem' }}>{title}</strong>
      <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', margin: 0 }}>{desc}</p>
    </button>
  );
}

function QuizMetaForm({ meta, onChange }) {
  const set = (k, v) => onChange({ ...meta, [k]: v });
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
      <div>
        <Label>Title</Label>
        <input
          type="text"
          className="input-field"
          value={meta.title}
          onChange={e => set('title', e.target.value)}
          placeholder="e.g. Chapter 3 Quiz"
        />
      </div>
      <div>
        <Label>Description (optional)</Label>
        <input
          type="text"
          className="input-field"
          value={meta.description}
          onChange={e => set('description', e.target.value)}
          placeholder="Short note for students"
        />
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
        <div>
          <Label>Time limit (minutes)</Label>
          <input
            type="number"
            className="input-field"
            min={1}
            value={meta.time_limit_minutes}
            onChange={e => set('time_limit_minutes', parseInt(e.target.value) || 30)}
          />
        </div>
        <div>
          <Label>Deadline (optional)</Label>
          <DateTimeField
            value={meta.deadline}
            min={nowForDatetimeLocal()}
            onChange={(v) => set('deadline', v)}
          />
        </div>
      </div>
      <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap', fontSize: '0.85rem' }}>
        <CheckboxLabel checked={meta.shuffle_questions} onChange={v => set('shuffle_questions', v)}>Shuffle questions</CheckboxLabel>
        <CheckboxLabel checked={meta.shuffle_options} onChange={v => set('shuffle_options', v)}>Shuffle options</CheckboxLabel>
        <CheckboxLabel checked={meta.show_correct_after} onChange={v => set('show_correct_after', v)}>Show correct answers after submission</CheckboxLabel>
      </div>
    </div>
  );
}

function CheckboxLabel({ checked, onChange, children }) {
  return (
    <label style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', cursor: 'pointer' }}>
      <input
        type="checkbox"
        checked={checked}
        onChange={e => onChange(e.target.checked)}
        style={{ width: '16px', height: '16px', cursor: 'pointer' }}
      />
      {children}
    </label>
  );
}

function QuestionEditor({ q, index, onChange, onOptionChange, onRemove, canRemove }) {
  const [expanded, setExpanded] = useState(true);
  const isTrueFalse = (q.type || 'mcq') === 'true_false';
  const isShort = (q.type || 'mcq') === 'short_answer';
  const accepted = (q.accepted_answers && q.accepted_answers.length) ? q.accepted_answers : [''];
  const changeType = (type) => {
    if (type === (q.type || 'mcq')) return;
    if (type === 'true_false') {
      onChange({ type, options: ['True', 'False'], correct_index: Math.min(q.correct_index || 0, 1), accepted_answers: null });
    } else if (type === 'short_answer') {
      onChange({ type, options: [], correct_index: null, accepted_answers: accepted });
    } else {
      onChange({ type: 'mcq', options: ['', '', '', ''], correct_index: 0, accepted_answers: null });
    }
  };
  return (
    <div style={{ padding: '1rem', borderRadius: '0.6rem', border: '1px solid var(--border-color)', background: 'var(--bg-tertiary)', marginBottom: '0.75rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: expanded ? '0.75rem' : 0, gap: '0.5rem' }}>
        <strong style={{ fontSize: '0.9rem' }}>Question {index + 1}</strong>
        <div style={{ display: 'flex', gap: '0.4rem', alignItems: 'center' }}>
          <select
            className="input-field"
            value={isTrueFalse ? 'true_false' : 'mcq'}
            onChange={e => changeType(e.target.value)}
            style={{ width: 'auto', padding: '0.3rem 0.5rem', fontSize: '0.8rem' }}
            title="Question type"
          >
            <option value="mcq">MCQ</option>
            <option value="true_false">True / False</option>
            <option value="short_answer">Short answer</option>
          </select>
          <button onClick={() => setExpanded(e => !e)} className="btn-secondary" style={{ padding: '0.3rem 0.5rem' }}>
            {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          </button>
          {canRemove && (
            <button onClick={onRemove} className="btn-secondary" style={{ padding: '0.3rem 0.5rem', color: '#DC2626' }}>
              <Trash2 size={14} />
            </button>
          )}
        </div>
      </div>

      {expanded && (
        <>
          <textarea
            className="input-field"
            rows={2}
            value={q.question_text}
            onChange={e => onChange({ question_text: e.target.value })}
            placeholder="Enter the question..."
            style={{ resize: 'vertical', fontFamily: 'inherit', marginBottom: '0.5rem' }}
          />

          {isShort ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem', marginBottom: '0.5rem' }}>
              <span style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                Accepted answers (any of these counts; letter case, spacing and punctuation are ignored)
              </span>
              {accepted.map((ans, i) => (
                <div key={i} style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                  <input
                    type="text"
                    className="input-field"
                    value={ans}
                    placeholder={i === 0 ? 'Model answer' : 'Alternative wording'}
                    onChange={e => onChange({ accepted_answers: accepted.map((a, j) => (j === i ? e.target.value : a)) })}
                  />
                  {accepted.length > 1 && (
                    <button onClick={() => onChange({ accepted_answers: accepted.filter((_, j) => j !== i) })} className="btn-secondary" style={{ padding: '0.3rem 0.5rem', color: '#DC2626' }}>
                      <Trash2 size={14} />
                    </button>
                  )}
                </div>
              ))}
              <button onClick={() => onChange({ accepted_answers: [...accepted, ''] })} className="btn-secondary" style={{ alignSelf: 'flex-start', padding: '0.3rem 0.6rem', fontSize: '0.8rem' }}>
                <Plus size={14} /> Alternative answer
              </button>
            </div>
          ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem', marginBottom: '0.5rem' }}>
            {q.options.map((opt, i) => (
              <div key={i} style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                <button
                  onClick={() => onChange({ correct_index: i })}
                  title="Mark as correct answer"
                  style={{
                    width: 28,
                    height: 28,
                    borderRadius: '50%',
                    border: q.correct_index === i ? '2px solid var(--success)' : '1px solid var(--border-color)',
                    background: q.correct_index === i ? 'var(--success)' : 'transparent',
                    color: q.correct_index === i ? 'white' : 'var(--text-secondary)',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    flexShrink: 0,
                  }}
                >
                  {q.correct_index === i ? <Check size={14} /> : <span style={{ fontSize: '0.75rem' }}>{String.fromCharCode(65 + i)}</span>}
                </button>
                <input
                  type="text"
                  className="input-field"
                  value={opt}
                  onChange={e => onOptionChange(i, e.target.value)}
                  placeholder={`Option ${String.fromCharCode(65 + i)}`}
                  readOnly={isTrueFalse}
                  style={isTrueFalse ? { opacity: 0.8, cursor: 'default' } : undefined}
                />
              </div>
            ))}
          </div>
          )}

          <div style={{ display: 'grid', gridTemplateColumns: '120px 1fr', gap: '0.5rem' }}>
            <div>
              <Label>Marks</Label>
              <input
                type="number"
                className="input-field"
                min={1}
                value={q.marks}
                onChange={e => onChange({ marks: parseInt(e.target.value) || 1 })}
              />
            </div>
            <div>
              <Label>Explanation (optional)</Label>
              <input
                type="text"
                className="input-field"
                value={q.explanation || ''}
                onChange={e => onChange({ explanation: e.target.value })}
                placeholder="Why the correct answer is right"
              />
            </div>
          </div>
        </>
      )}
    </div>
  );
}
