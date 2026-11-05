import { useState, useEffect } from 'react';
import { ScanLine, Plus, Trash2, BarChart3, CheckCircle, UploadCloud, Files, Clock } from 'lucide-react';
import api from '../services/api';
import OMRTemplateModal from './OMRTemplateModal';
import OMRUploadModal from './OMRUploadModal';
import OMRResultsModal from './OMRResultsModal';
import { formatDate } from '../utils/dateFormat';

export default function OMRList({ classId, isStudent }) {
  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showBuilder, setShowBuilder] = useState(false);
  const [uploadFor, setUploadFor] = useState(null);
  const [uploadMode, setUploadMode] = useState('single');
  const [resultsFor, setResultsFor] = useState(null);

  const fetchTemplates = async () => {
    if (!classId) {
      setTemplates([]);
      setLoading(false);
      return;
    }
    try {
      const res = await api.get(`/omr/templates/class/${classId}`);
      setTemplates(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchTemplates(); }, [classId]);

  const handleDelete = async (templateId) => {
    if (!window.confirm('Delete this OMR template and all its submissions?')) return;
    try {
      await api.delete(`/omr/templates/${templateId}`);
      fetchTemplates();
    } catch (err) {
      console.error(err);
    }
  };

  if (loading) return <p className="text-muted" style={{ padding: '1rem' }}>Loading OMR sheets...</p>;

  return (
    <>
      {showBuilder && (
        <OMRTemplateModal
          classId={classId}
          onClose={() => setShowBuilder(false)}
          onSaved={fetchTemplates}
        />
      )}

      {uploadFor && (
        <OMRUploadModal
          template={uploadFor}
          mode={uploadMode}
          onClose={() => setUploadFor(null)}
          onUploaded={fetchTemplates}
        />
      )}

      {resultsFor && (
        <OMRResultsModal
          template={resultsFor}
          onClose={() => setResultsFor(null)}
        />
      )}

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
        <h3 className="section-title" style={{ margin: 0 }}>
          <ScanLine size={18} style={{ verticalAlign: 'middle', marginRight: '0.4rem' }} />
          OMR Sheets ({templates.length})
        </h3>
        {!isStudent && (
          <button className="btn-primary" onClick={() => setShowBuilder(true)} style={{ padding: '0.5rem 1rem', fontSize: '0.85rem' }}>
            <Plus size={14} /> New OMR Template
          </button>
        )}
      </div>

      {templates.length === 0 ? (
        <div className="glass-panel" style={{ padding: '1.5rem', textAlign: 'center' }}>
          <p className="text-muted">
            {isStudent ? 'No OMR sheets available yet.' : 'No OMR templates yet. Click "New OMR Template" to create one.'}
          </p>
        </div>
      ) : (
        <div style={{ display: 'grid', gap: '0.75rem' }}>
          {templates.map(t => (
            <TemplateCard
              key={t.template_id}
              template={t}
              isStudent={isStudent}
              onUploadSingle={() => { setUploadFor(t); setUploadMode('single'); }}
              onUploadBatch={() => { setUploadFor(t); setUploadMode('batch'); }}
              onResults={() => setResultsFor(t)}
              onDelete={() => handleDelete(t.template_id)}
            />
          ))}
        </div>
      )}
    </>
  );
}

function TemplateCard({ template, isStudent, onUploadSingle, onUploadBatch, onResults, onDelete }) {
  const deadlinePassed = template.deadline && new Date(template.deadline) < new Date();
  const hasSubmitted = template.has_submitted;

  return (
    <div className="glass-panel" style={{ padding: '1rem 1.25rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '1rem', flexWrap: 'wrap' }}>
        <div style={{ flex: 1, minWidth: '200px' }}>
          <h4 style={{ fontSize: '1rem', marginBottom: '0.25rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            {template.title}
            <span style={{
              fontSize: '0.7rem', fontWeight: 600,
              padding: '0.15rem 0.5rem', borderRadius: '999px',
              background: template.sheet_type === 'true_false' ? 'rgba(139, 92, 246, 0.15)' : 'var(--accent-soft)',
              color: template.sheet_type === 'true_false' ? '#8B5CF6' : 'var(--accent-primary)',
              textTransform: 'uppercase',
            }}>
              {template.sheet_type === 'true_false' ? 'T/F' : 'MCQ'}
            </span>
          </h4>
          {template.description && (
            <p className="text-secondary" style={{ fontSize: '0.85rem', marginBottom: '0.5rem' }}>{template.description}</p>
          )}
          <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap', fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
            <span><strong>{template.num_questions}</strong> questions</span>
            <span><strong>{template.total_marks}</strong> marks</span>
            {template.negative_marking > 0 && <span style={{ color: 'var(--warning)' }}>−{template.negative_marking} per wrong</span>}
            {template.deadline && (
              <span style={{ color: deadlinePassed ? 'var(--danger)' : 'var(--success)', fontWeight: 600 }}>
                <Clock size={11} style={{ verticalAlign: 'middle' }} />{' '}
                {deadlinePassed ? 'Closed' : formatDate(template.deadline)}
              </span>
            )}
            {!isStudent && (
              <span><strong>{template.submission_count ?? 0}</strong> submission{template.submission_count !== 1 ? 's' : ''}</span>
            )}
          </div>
        </div>

        <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
          {isStudent ? (
            hasSubmitted ? (
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.83rem', color: 'var(--success)', fontWeight: 600, padding: '0.45rem 0.85rem' }}>
                <CheckCircle size={14} /> Submitted
              </span>
            ) : deadlinePassed ? (
              <span style={{ color: 'var(--danger)', fontSize: '0.83rem', padding: '0.45rem' }}>Closed</span>
            ) : (
              <button className="btn-primary" onClick={onUploadSingle} style={{ fontSize: '0.83rem', padding: '0.45rem 0.85rem' }}>
                <UploadCloud size={14} /> Upload Sheet
              </button>
            )
          ) : (
            <>
              <button className="btn-secondary" onClick={onUploadBatch} title="Batch upload sheets" style={{ fontSize: '0.82rem', padding: '0.45rem 0.7rem' }}>
                <Files size={13} /> Batch Upload
              </button>
              <button className="btn-secondary" onClick={onResults} title="View submissions" style={{ padding: '0.45rem 0.65rem' }}>
                <BarChart3 size={14} />
              </button>
              <button className="btn-secondary" onClick={onDelete} title="Delete template" style={{ padding: '0.45rem 0.65rem', color: 'var(--danger)' }}>
                <Trash2 size={14} />
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
