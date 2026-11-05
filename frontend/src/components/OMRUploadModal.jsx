import { useState } from 'react';
import { X, UploadCloud, AlertTriangle, Files } from 'lucide-react';
import api from '../services/api';
import './UploadWidget.css';

/**
 * OMRUploadModal
 *  - mode="single"  → student uploads one filled sheet (no re-upload)
 *  - mode="batch"   → teacher uploads many sheets at once
 */
export default function OMRUploadModal({ template, mode, onClose, onUploaded }) {
  const [files, setFiles] = useState([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [batchResult, setBatchResult] = useState(null);
  const isSingle = mode === 'single';

  const handleSelect = (e) => {
    const fl = e.target.files ? Array.from(e.target.files) : [];
    if (isSingle) {
      setFiles(fl.slice(0, 1));
    } else {
      setFiles(fl);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    const fl = Array.from(e.dataTransfer.files || []);
    if (isSingle) {
      setFiles(fl.slice(0, 1));
    } else {
      setFiles(prev => [...prev, ...fl]);
    }
  };

  const removeFile = (idx) => {
    setFiles(fs => fs.filter((_, i) => i !== idx));
  };

  const handleClickSubmit = (e) => {
    e?.preventDefault();
    if (files.length === 0) {
      setError(isSingle ? 'Select your filled OMR sheet first.' : 'Add at least one sheet.');
      return;
    }
    setError('');
    if (isSingle) setShowConfirm(true);
    else doUpload();
  };

  const doUpload = async () => {
    setShowConfirm(false);
    setLoading(true);
    setError('');
    try {
      if (isSingle) {
        const fd = new FormData();
        fd.append('template_id', template.template_id);
        fd.append('file', files[0]);
        await api.post('/omr/submissions/single', fd, {
          headers: { 'Content-Type': 'multipart/form-data' }
        });
        onUploaded();
        onClose();
      } else {
        const fd = new FormData();
        fd.append('template_id', template.template_id);
        files.forEach(f => fd.append('files', f));
        const res = await api.post('/omr/submissions/batch', fd, {
          headers: { 'Content-Type': 'multipart/form-data' }
        });
        setBatchResult(res.data);
        onUploaded();
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Upload failed');
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay fade-in">
      <div className="modal-content glass-panel" style={{ maxWidth: '560px', maxHeight: '90vh', overflowY: 'auto' }}>
        <button className="close-btn" onClick={onClose}><X size={20} /></button>

        <h2 style={{ marginBottom: '0.25rem' }}>
          {isSingle ? 'Submit OMR Sheet' : 'Batch Upload OMR Sheets'}
        </h2>
        <p className="text-secondary" style={{ fontSize: '0.9rem', marginBottom: '1rem' }}>
          {template.title} · {template.num_questions} questions · {template.total_marks} marks
        </p>

        {isSingle && (
          <div style={{
            padding: '0.7rem 0.85rem', borderRadius: '0.5rem',
            background: 'var(--status-pending-bg)', color: 'var(--status-pending)',
            fontSize: '0.83rem', display: 'flex', gap: '0.5rem', alignItems: 'flex-start',
            marginBottom: '1rem', border: '1px solid var(--warning)',
          }}>
            <AlertTriangle size={16} style={{ flexShrink: 0, marginTop: '2px' }} />
            <span><strong>One-time submission.</strong> You cannot re-upload after submitting.</span>
          </div>
        )}

        {error && <div className="error-banner">{error}</div>}

        {batchResult ? (
          <div>
            <div style={{
              padding: '1rem',
              borderRadius: '0.5rem',
              background: 'var(--status-graded-bg)',
              color: 'var(--status-graded)',
              border: '1px solid var(--success)',
              marginBottom: '1rem',
            }}>
              <strong>{batchResult.created}</strong> sheet{batchResult.created !== 1 ? 's' : ''} uploaded — they'll be graded in the background.
            </div>
            {batchResult.skipped?.length > 0 && (
              <div style={{ marginBottom: '1rem' }}>
                <strong style={{ fontSize: '0.85rem' }}>Skipped:</strong>
                <ul style={{ marginTop: '0.4rem', paddingLeft: '1.2rem', fontSize: '0.83rem', color: 'var(--text-secondary)' }}>
                  {batchResult.skipped.map((s, i) => <li key={i}>{s.name} — {s.reason}</li>)}
                </ul>
              </div>
            )}
            <div className="modal-actions">
              <button className="btn-primary" onClick={onClose}>Done</button>
            </div>
          </div>
        ) : (
          <form onSubmit={handleClickSubmit}>
            <div
              className={`drop-zone ${files.length > 0 ? 'has-file' : ''}`}
              onDragOver={(e) => e.preventDefault()}
              onDrop={handleDrop}
              onClick={() => document.getElementById('omrFileUpload').click()}
            >
              {isSingle ? <UploadCloud size={40} className="upload-icon" /> : <Files size={40} className="upload-icon" />}
              <p>
                {files.length === 0
                  ? (isSingle
                      ? 'Drop your filled OMR sheet here, or click to browse'
                      : 'Drop multiple sheets here, or click to browse')
                  : `${files.length} file${files.length !== 1 ? 's' : ''} selected`}
              </p>
              <span className="drop-hint">Supports .PDF, .PNG, .JPG{isSingle ? '' : ' · One submission per sheet'}</span>
              <input
                id="omrFileUpload"
                type="file"
                accept=".pdf,image/png,image/jpeg"
                multiple={!isSingle}
                style={{ display: 'none' }}
                onChange={handleSelect}
              />
            </div>

            {files.length > 0 && (
              <div style={{ marginTop: '0.75rem', maxHeight: '200px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                {files.map((f, i) => (
                  <div key={i} style={{
                    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                    padding: '0.45rem 0.7rem', borderRadius: '0.4rem',
                    background: 'var(--bg-tertiary)', fontSize: '0.85rem',
                  }}>
                    <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {f.name}
                    </span>
                    <button
                      type="button"
                      onClick={() => removeFile(i)}
                      style={{ background: 'none', border: 'none', color: 'var(--danger)', cursor: 'pointer', padding: '0.2rem' }}
                    >
                      <X size={14} />
                    </button>
                  </div>
                ))}
              </div>
            )}

            <div className="modal-actions" style={{ marginTop: '1rem' }}>
              <button type="button" className="btn-secondary" onClick={onClose} disabled={loading}>Cancel</button>
              <button type="submit" className="btn-primary" disabled={loading || files.length === 0}>
                {loading ? 'Uploading...' : (isSingle ? 'Submit Sheet' : `Upload ${files.length} sheet${files.length !== 1 ? 's' : ''}`)}
              </button>
            </div>
          </form>
        )}

        {showConfirm && (
          <div className="modal-overlay" style={{ zIndex: 1100 }} onClick={() => !loading && setShowConfirm(false)}>
            <div className="modal-content glass-panel" style={{ maxWidth: '420px' }} onClick={e => e.stopPropagation()}>
              <h3 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem' }}>
                <AlertTriangle size={20} style={{ color: 'var(--warning)' }} /> Confirm OMR Submission
              </h3>
              <p style={{ color: 'var(--text-secondary)', marginBottom: '0.75rem' }}>
                You are about to submit <strong>{files[0]?.name}</strong>.
              </p>
              <div style={{
                padding: '0.85rem', borderRadius: '0.5rem',
                background: 'var(--status-failed-bg)', color: 'var(--status-failed)',
                fontSize: '0.88rem', marginBottom: '1.25rem', border: '1px solid var(--danger)',
              }}>
                <strong>Warning:</strong> This is your <u>only</u> submission for this sheet. Re-uploads are <u>not allowed</u>.
              </div>
              <div className="modal-actions">
                <button type="button" className="btn-secondary" onClick={() => setShowConfirm(false)} disabled={loading}>
                  Review File
                </button>
                <button type="button" className="btn-primary" onClick={doUpload} disabled={loading}>
                  {loading ? 'Submitting...' : 'Yes, Submit Final'}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
