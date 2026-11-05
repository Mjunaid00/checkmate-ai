import { useState, useMemo } from 'react';
import { X, Save, ScanLine, Check } from 'lucide-react';
import api from '../services/api';
import DateTimeField from './DateTimeField';
import { nowForDatetimeLocal, isPast, toApiDatetime } from '../utils/dateFormat';
import './UploadWidget.css';

export default function OMRTemplateModal({ classId, onClose, onSaved }) {
  const [meta, setMeta] = useState({
    title: '',
    description: '',
    sheet_type: 'mcq',
    num_questions: 10,
    options_per_question: 4,
    marks_per_question: 1,
    negative_marking: 0,
    deadline: '',
  });
  const [answerKey, setAnswerKey] = useState(Array(10).fill(0));
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  // Resync answerKey when num_questions / sheet_type changes
  const opts = meta.sheet_type === 'true_false' ? 2 : meta.options_per_question;

  const updateMeta = (patch) => {
    const newMeta = { ...meta, ...patch };
    if (patch.sheet_type === 'true_false') newMeta.options_per_question = 2;
    setMeta(newMeta);

    if (patch.num_questions !== undefined) {
      const newCount = parseInt(patch.num_questions) || 1;
      setAnswerKey(prev => {
        const arr = [...prev];
        while (arr.length < newCount) arr.push(0);
        arr.length = newCount;
        return arr.map(a => Math.min(a, (patch.options_per_question || newMeta.options_per_question) - 1));
      });
    }
    if (patch.options_per_question !== undefined || patch.sheet_type !== undefined) {
      const newOpts = patch.sheet_type === 'true_false' ? 2 : (patch.options_per_question ?? newMeta.options_per_question);
      setAnswerKey(prev => prev.map(a => Math.min(a, newOpts - 1)));
    }
  };

  const setAnswer = (qIdx, optIdx) => {
    setAnswerKey(prev => prev.map((a, i) => i === qIdx ? optIdx : a));
  };

  const totalMarks = (parseInt(meta.num_questions) || 0) * (parseInt(meta.marks_per_question) || 1);

  const optionLabels = useMemo(() => {
    if (meta.sheet_type === 'true_false') return ['T', 'F'];
    return Array.from({ length: opts }, (_, i) => String.fromCharCode(65 + i));
  }, [meta.sheet_type, opts]);

  const handleSave = async () => {
    if (!meta.title.trim()) {
      setError('Title is required');
      return;
    }
    if (answerKey.length !== meta.num_questions) {
      setError(`Answer key must have ${meta.num_questions} entries`);
      return;
    }
    if (meta.deadline && isPast(meta.deadline)) {
      setError('Deadline cannot be in the past.');
      return;
    }
    setLoading(true);
    setError('');
    try {
      await api.post('/omr/templates', {
        class_id: classId,
        title: meta.title.trim(),
        description: meta.description.trim() || null,
        sheet_type: meta.sheet_type,
        num_questions: parseInt(meta.num_questions),
        options_per_question: meta.sheet_type === 'true_false' ? 2 : parseInt(meta.options_per_question),
        answer_key: answerKey,
        marks_per_question: parseInt(meta.marks_per_question) || 1,
        negative_marking: parseFloat(meta.negative_marking) || 0,
        deadline: toApiDatetime(meta.deadline) || null,
      });
      onSaved();
      onClose();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to save template');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay fade-in">
      <div className="modal-content glass-panel" style={{ maxWidth: '720px', maxHeight: '90vh', overflowY: 'auto' }}>
        <button className="close-btn" onClick={onClose}><X size={20} /></button>

        <h2 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.25rem' }}>
          <ScanLine size={22} /> Create OMR Template
        </h2>
        <p className="text-secondary" style={{ fontSize: '0.9rem', marginBottom: '1.25rem' }}>
          Define the answer key. Students upload filled sheets and the AI grades them automatically.
        </p>

        {error && <div className="error-banner">{error}</div>}

        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
          {/* Sheet type toggle */}
          <div>
            <Label>Sheet Type</Label>
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <TypeChip
                active={meta.sheet_type === 'mcq'}
                onClick={() => updateMeta({ sheet_type: 'mcq' })}
              >
                Multiple Choice (A/B/C/D)
              </TypeChip>
              <TypeChip
                active={meta.sheet_type === 'true_false'}
                onClick={() => updateMeta({ sheet_type: 'true_false' })}
              >
                True / False
              </TypeChip>
            </div>
          </div>

          <div>
            <Label>Title</Label>
            <input
              type="text"
              className="input-field"
              value={meta.title}
              onChange={e => updateMeta({ title: e.target.value })}
              placeholder="e.g. Chapter 5 OMR Quiz"
            />
          </div>

          <div>
            <Label>Description (optional)</Label>
            <input
              type="text"
              className="input-field"
              value={meta.description}
              onChange={e => updateMeta({ description: e.target.value })}
            />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: meta.sheet_type === 'mcq' ? '1fr 1fr 1fr' : '1fr 1fr', gap: '0.75rem' }}>
            <div>
              <Label>Questions</Label>
              <input
                type="number"
                className="input-field"
                min={1}
                max={200}
                value={meta.num_questions}
                onChange={e => updateMeta({ num_questions: parseInt(e.target.value) || 1 })}
              />
            </div>
            {meta.sheet_type === 'mcq' && (
              <div>
                <Label>Options per Q</Label>
                <select
                  className="input-field"
                  value={meta.options_per_question}
                  onChange={e => updateMeta({ options_per_question: parseInt(e.target.value) })}
                >
                  <option value={2}>2 (A,B)</option>
                  <option value={3}>3 (A,B,C)</option>
                  <option value={4}>4 (A,B,C,D)</option>
                  <option value={5}>5 (A-E)</option>
                  <option value={6}>6 (A-F)</option>
                </select>
              </div>
            )}
            <div>
              <Label>Marks / Q</Label>
              <input
                type="number"
                className="input-field"
                min={1}
                value={meta.marks_per_question}
                onChange={e => updateMeta({ marks_per_question: parseInt(e.target.value) || 1 })}
              />
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
            <div>
              <Label>Negative Marking (per wrong)</Label>
              <input
                type="number"
                className="input-field"
                min={0}
                step={0.25}
                value={meta.negative_marking}
                onChange={e => updateMeta({ negative_marking: e.target.value })}
              />
            </div>
            <div>
              <Label>Deadline (optional)</Label>
              <DateTimeField
                value={meta.deadline}
                min={nowForDatetimeLocal()}
                onChange={(v) => updateMeta({ deadline: v })}
              />
            </div>
          </div>

          <div style={{ padding: '0.7rem 0.85rem', borderRadius: '0.5rem', background: 'var(--accent-soft)', color: 'var(--accent-primary)', fontSize: '0.85rem' }}>
            <strong>Total marks: {totalMarks}</strong>
            {meta.negative_marking > 0 && ` · −${meta.negative_marking} per wrong answer`}
          </div>

          {/* Answer Key Grid */}
          <div style={{ borderTop: '1px solid var(--border-color)', paddingTop: '1rem' }}>
            <h3 style={{ fontSize: '1rem', marginBottom: '0.75rem' }}>Answer Key</h3>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: '0.5rem' }}>
              {answerKey.map((sel, qi) => (
                <div key={qi} style={{ padding: '0.5rem 0.65rem', borderRadius: '0.45rem', border: '1px solid var(--border-color)', background: 'var(--bg-tertiary)', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                  <strong style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', minWidth: '28px' }}>Q{qi + 1}</strong>
                  <div style={{ display: 'flex', gap: '0.25rem', flex: 1, justifyContent: 'flex-end' }}>
                    {optionLabels.map((label, oi) => (
                      <button
                        key={oi}
                        onClick={() => setAnswer(qi, oi)}
                        style={{
                          width: 30, height: 30, borderRadius: '50%',
                          border: sel === oi ? '2px solid var(--success)' : '1px solid var(--border-color)',
                          background: sel === oi ? 'var(--success)' : 'transparent',
                          color: sel === oi ? 'white' : 'var(--text-secondary)',
                          cursor: 'pointer', fontWeight: 700, fontSize: '0.78rem',
                          display: 'flex', alignItems: 'center', justifyContent: 'center',
                        }}
                        title={`Mark ${label} as correct`}
                      >
                        {sel === oi ? <Check size={13} /> : label}
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="modal-actions" style={{ marginTop: '1.5rem' }}>
          <button className="btn-secondary" onClick={onClose} disabled={loading}>Cancel</button>
          <button className="btn-primary" onClick={handleSave} disabled={loading}>
            <Save size={16} /> {loading ? 'Saving...' : 'Save Template'}
          </button>
        </div>
      </div>
    </div>
  );
}

function Label({ children }) {
  return (
    <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: '0.35rem' }}>
      {children}
    </label>
  );
}

function TypeChip({ active, onClick, children }) {
  return (
    <button
      onClick={onClick}
      style={{
        padding: '0.55rem 1rem',
        borderRadius: '0.5rem',
        border: active ? '2px solid var(--accent-primary)' : '1px solid var(--border-color)',
        background: active ? 'var(--accent-soft)' : 'var(--bg-secondary)',
        color: active ? 'var(--accent-primary)' : 'var(--text-secondary)',
        fontWeight: 600,
        fontSize: '0.85rem',
        cursor: 'pointer',
        fontFamily: 'inherit',
      }}
    >
      {children}
    </button>
  );
}
