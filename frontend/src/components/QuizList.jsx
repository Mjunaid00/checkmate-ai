import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Sparkles, Clock, Trash2, BarChart3, CheckCircle, Play, FileText, Pencil } from 'lucide-react';
import api from '../services/api';
import QuizBuilderModal from './QuizBuilderModal';
import QuizEditModal from './QuizEditModal';
import { formatDateTime } from '../utils/dateFormat';

export default function QuizList({ classId, isStudent }) {
  const navigate = useNavigate();
  const [quizzes, setQuizzes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showBuilder, setShowBuilder] = useState(false);
  const [editingQuiz, setEditingQuiz] = useState(null);

  const fetchQuizzes = async () => {
    if (!classId) {
      setQuizzes([]);
      setLoading(false);
      return;
    }
    try {
      const res = await api.get(`/quizzes/class/${classId}`);
      setQuizzes(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchQuizzes();
  }, [classId]);

  const handleDelete = async (quizId) => {
    if (!window.confirm('Delete this quiz and all attempts?')) return;
    try {
      await api.delete(`/quizzes/${quizId}`);
      fetchQuizzes();
    } catch (err) {
      console.error(err);
    }
  };

  if (loading) return <p className="text-muted" style={{ padding: '1rem' }}>Loading quizzes...</p>;

  return (
    <>
      {showBuilder && (
        <QuizBuilderModal
          classId={classId}
          onClose={() => setShowBuilder(false)}
          onSaved={fetchQuizzes}
        />
      )}

      {editingQuiz && (
        <QuizEditModal
          quiz={editingQuiz}
          onClose={() => setEditingQuiz(null)}
          onSaved={fetchQuizzes}
        />
      )}

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
        <h3 className="section-title" style={{ margin: 0 }}>
          <FileText size={18} style={{ verticalAlign: 'middle', marginRight: '0.4rem' }} />
          Quizzes ({quizzes.length})
        </h3>
        {!isStudent && (
          <button className="btn-primary" onClick={() => setShowBuilder(true)} style={{ padding: '0.5rem 1rem', fontSize: '0.85rem' }}>
            <Sparkles size={14} /> New Quiz
          </button>
        )}
      </div>

      {quizzes.length === 0 ? (
        <div className="glass-panel" style={{ padding: '1.5rem', textAlign: 'center' }}>
          <p className="text-muted">
            {isStudent ? 'No quizzes available yet.' : 'No quizzes yet. Click "New Quiz" to create one.'}
          </p>
        </div>
      ) : (
        <div style={{ display: 'grid', gap: '0.75rem' }}>
          {quizzes.map(q => (
            <QuizCard
              key={q.quiz_id}
              quiz={q}
              isStudent={isStudent}
              onTake={() => navigate(`/quiz/${q.quiz_id}/take`)}
              onResult={() => navigate(`/quiz/${q.quiz_id}/result`)}
              onEdit={() => setEditingQuiz(q)}
              onDelete={() => handleDelete(q.quiz_id)}
            />
          ))}
        </div>
      )}
    </>
  );
}

function QuizCard({ quiz, isStudent, onTake, onResult, onEdit, onDelete }) {
  const deadlinePassed = quiz.deadline && new Date(quiz.deadline) < new Date();
  const hasAttempted = quiz.has_attempted;

  return (
    <div className="glass-panel" style={{ padding: '1rem 1.25rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '1rem', flexWrap: 'wrap' }}>
        <div style={{ flex: 1, minWidth: '200px' }}>
          <h4 style={{ fontSize: '1rem', marginBottom: '0.25rem' }}>{quiz.title}</h4>
          {quiz.description && (
            <p className="text-secondary" style={{ fontSize: '0.85rem', marginBottom: '0.5rem' }}>{quiz.description}</p>
          )}
          <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap', fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
            <span><FileText size={12} style={{ verticalAlign: 'middle' }} /> {quiz.question_count} questions</span>
            <span><Clock size={12} style={{ verticalAlign: 'middle' }} /> {quiz.time_limit_minutes} min</span>
            <span><strong>{quiz.total_marks}</strong> marks</span>
            {quiz.deadline && (
              <span style={{ color: deadlinePassed ? 'var(--danger)' : 'var(--success)', fontWeight: 600 }}>
                {deadlinePassed
                  ? 'Closed'
                  : `Due ${formatDateTime(quiz.deadline)}`}
              </span>
            )}
            {!isStudent && (
              <span><strong>{quiz.attempt_count ?? 0}</strong> attempt{quiz.attempt_count !== 1 ? 's' : ''}</span>
            )}
          </div>
        </div>

        <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
          {isStudent ? (
            hasAttempted ? (
              <button className="btn-secondary" onClick={onResult} style={{ fontSize: '0.83rem', padding: '0.45rem 0.85rem' }}>
                <CheckCircle size={14} /> View Result
              </button>
            ) : deadlinePassed ? (
              <span style={{ color: 'var(--danger)', fontSize: '0.83rem', padding: '0.45rem' }}>Closed</span>
            ) : (
              <button className="btn-primary" onClick={onTake} style={{ fontSize: '0.83rem', padding: '0.45rem 0.85rem' }}>
                <Play size={14} /> Take Quiz
              </button>
            )
          ) : (
            <>
              <button className="btn-secondary" onClick={onResult} title="View results & stats" style={{ padding: '0.45rem 0.65rem' }}>
                <BarChart3 size={14} />
              </button>
              <button className="btn-secondary" onClick={onEdit} title="Edit quiz (deadline, time, settings)" style={{ padding: '0.45rem 0.65rem' }}>
                <Pencil size={14} />
              </button>
              <button className="btn-secondary" onClick={onDelete} title="Delete quiz" style={{ padding: '0.45rem 0.65rem', color: 'var(--danger)' }}>
                <Trash2 size={14} />
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
