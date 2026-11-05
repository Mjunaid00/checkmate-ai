import { useState } from 'react';
import { UploadCloud, X, AlertTriangle } from 'lucide-react';
import api from '../services/api';
import DateTimeField from './DateTimeField';
import { nowForDatetimeLocal, isPast, toApiDatetime } from '../utils/dateFormat';
import './UploadWidget.css';

export default function UploadWidget({ assignmentId, classId, isStudent, onClose, onUploadSuccess }) {
  const [file, setFile] = useState(null);
  const [title, setTitle] = useState('');
  const [marks, setMarks] = useState(100);
  const [gradingPrompt, setGradingPrompt] = useState('');
  const [deadline, setDeadline] = useState('');
  const [plagiarismCheck, setPlagiarismCheck] = useState(false);
  const [allowedFormats, setAllowedFormats] = useState({ pdf: true, png: true, jpg: true });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [showConfirm, setShowConfirm] = useState(false);

  const handleDrop = (e) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      setFile(e.dataTransfer.files[0]);
    }
  };

  const validate = () => {
    if (!file) {
      setError('Please select or drop a file first.');
      return false;
    }
    if (!isStudent && deadline && isPast(deadline)) {
      setError('Deadline cannot be in the past.');
      return false;
    }
    setError('');
    return true;
  };

  const handleClickSubmit = (e) => {
    e.preventDefault();
    if (!validate()) return;
    if (isStudent) {
      // Student submissions need explicit confirmation (cannot reupload)
      setShowConfirm(true);
    } else {
      doUpload();
    }
  };

  const doUpload = async () => {
    setShowConfirm(false);
    setLoading(true);
    setError('');

    const formData = new FormData();
    formData.append('file', file);

    let endpoint = '';
    if (isStudent) {
      endpoint = '/submissions/';
      formData.append('assignment_id', assignmentId);
    } else {
      endpoint = '/assignments/';
      formData.append('class_id', classId);
      formData.append('title', title);
      formData.append('total_marks', marks);
      formData.append('grading_prompt', gradingPrompt);
      if (deadline) formData.append('deadline', toApiDatetime(deadline));
      formData.append('plagiarism_check', plagiarismCheck ? 'true' : 'false');
      const allowedList = Object.entries(allowedFormats).filter(([_, v]) => v).map(([k]) => k);
      if (allowedList.length > 0 && allowedList.length < 3) {
        formData.append('allowed_formats', allowedList.join(','));
      }
    }

    try {
      await api.post(endpoint, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      onUploadSuccess();
      onClose();
    } catch (err) {
      setError(err.response?.data?.detail || 'Upload failed.');
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay fade-in">
      <div className="modal-content glass-panel">
        <button className="close-btn" onClick={onClose}><X size={20} /></button>
        
        <h2>{isStudent ? "Upload Answer" : "Upload Assignment"}</h2>
        <p className="modal-subtitle">
          {isStudent ? "Upload a PDF or Image of your answers." : "Upload the assignment rubric/question paper."}
        </p>

        {error && <div className="error-banner">{error}</div>}

        {isStudent && (
          <>
            <div style={{
              padding: '0.7rem 0.85rem',
              borderRadius: '0.5rem',
              background: 'var(--status-pending-bg)',
              color: 'var(--status-pending)',
              fontSize: '0.83rem',
              display: 'flex',
              gap: '0.5rem',
              alignItems: 'flex-start',
              marginBottom: '0.75rem',
              border: '1px solid var(--warning)',
            }}>
              <AlertTriangle size={16} style={{ flexShrink: 0, marginTop: '2px' }} />
              <span><strong>One-time submission.</strong> You cannot re-upload after submitting. Make sure your file is correct.</span>
            </div>
            <div style={{
              padding: '0.7rem 0.85rem',
              borderRadius: '0.5rem',
              background: 'var(--status-pending-bg)',
              color: 'var(--status-pending)',
              fontSize: '0.83rem',
              display: 'flex',
              gap: '0.5rem',
              alignItems: 'flex-start',
              marginBottom: '1rem',
              border: '1px solid var(--warning)',
            }}>
              <AlertTriangle size={16} style={{ flexShrink: 0, marginTop: '2px' }} />
              <span><strong>Required header.</strong> The first page of your file must include "Shaheed Zulfikar Ali Bhutto Institute of Science and Technology University". Submissions without this header will be rejected.</span>
            </div>
          </>
        )}

        <form onSubmit={handleClickSubmit}>
          {!isStudent && (
            <>
              <div className="form-group">
                <label>Assignment Title</label>
                <input 
                  type="text" 
                  className="input-field" 
                  required 
                  value={title}
                  onChange={e => setTitle(e.target.value)}
                  placeholder="e.g. Intro Biology Midterm"
                />
              </div>

              <div className="form-group">
                <label>Total Possible Marks</label>
                <input
                  type="number"
                  className="input-field"
                  required
                  min="1"
                  value={marks}
                  onChange={e => setMarks(e.target.value)}
                />
              </div>

              <div className="form-group">
                <label>Submission Deadline <span style={{color: 'var(--text-secondary)', fontWeight: 'normal'}}>(optional)</span></label>
                <DateTimeField
                  value={deadline}
                  min={nowForDatetimeLocal()}
                  onChange={setDeadline}
                />
                <small style={{color: 'var(--text-secondary)', fontSize: '0.75rem'}}>
                  Students won't be able to submit after this date/time.
                </small>
              </div>

              <div className="form-group">
                <label>Grading Prompt <span style={{color: 'var(--text-secondary)', fontWeight: 'normal'}}>(optional)</span></label>
                <textarea
                  className="input-field"
                  rows={4}
                  value={gradingPrompt}
                  onChange={e => setGradingPrompt(e.target.value)}
                  placeholder="e.g. Focus on conceptual understanding. Award partial marks for correct approach even if final answer is wrong. Deduct marks for missing units."
                  style={{resize: 'vertical', fontFamily: 'inherit'}}
                />
                <small style={{color: 'var(--text-secondary)', fontSize: '0.75rem'}}>
                  These instructions will guide the AI when grading student submissions.
                </small>
              </div>

              <div className="form-group">
                <label>Allowed Formats</label>
                <div style={{ display: 'flex', gap: '0.6rem', flexWrap: 'wrap' }}>
                  {['pdf', 'png', 'jpg'].map(fmt => (
                    <label key={fmt} style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', fontSize: '0.85rem', cursor: 'pointer' }}>
                      <input
                        type="checkbox"
                        checked={allowedFormats[fmt]}
                        onChange={e => setAllowedFormats({ ...allowedFormats, [fmt]: e.target.checked })}
                      />
                      .{fmt}
                    </label>
                  ))}
                </div>
                <small style={{color: 'var(--text-secondary)', fontSize: '0.75rem'}}>
                  Students will only be able to upload these file types.
                </small>
              </div>

              <div className="form-group">
                <label style={{display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer'}}>
                  <input
                    type="checkbox"
                    checked={plagiarismCheck}
                    onChange={e => setPlagiarismCheck(e.target.checked)}
                  />
                  Enable Plagiarism Detection
                </label>
                <small style={{color: 'var(--text-secondary)', fontSize: '0.75rem'}}>
                  Submissions will be auto-compared for similarity after grading. You can also run checks manually.
                </small>
              </div>
            </>
          )}

          <div 
            className={`drop-zone ${file ? 'has-file' : ''}`}
            onDragOver={(e) => e.preventDefault()}
            onDrop={handleDrop}
            onClick={() => document.getElementById('fileUpload').click()}
          >
            <UploadCloud size={40} className="upload-icon" />
            <p>{file ? file.name : "Drag & Drop file here, or click to browse"}</p>
            <span className="drop-hint">Supports .PDF, .PNG, .JPG</span>
            <input 
              id="fileUpload" 
              type="file" 
              accept=".pdf,image/png,image/jpeg"
              style={{display: 'none'}} 
              onChange={(e) => setFile(e.target.files[0])} 
            />
          </div>

          <div className="modal-actions">
            <button type="button" className="btn-secondary" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn-primary" disabled={loading}>
              {loading ? 'Uploading...' : (isStudent ? 'Submit Answer' : 'Create Assignment')}
            </button>
          </div>
        </form>

        {showConfirm && (
          <div className="modal-overlay" onClick={() => !loading && setShowConfirm(false)} style={{ zIndex: 1100 }}>
            <div className="modal-content glass-panel" style={{ maxWidth: '440px' }} onClick={e => e.stopPropagation()}>
              <h3 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem' }}>
                <AlertTriangle size={20} style={{ color: 'var(--warning)' }} /> Confirm Submission
              </h3>
              <p style={{ color: 'var(--text-secondary)', marginBottom: '0.75rem' }}>
                You are about to submit <strong>{file?.name}</strong>.
              </p>
              <div style={{
                padding: '0.85rem',
                borderRadius: '0.5rem',
                background: 'var(--status-failed-bg)',
                color: 'var(--status-failed)',
                fontSize: '0.88rem',
                marginBottom: '1.25rem',
                border: '1px solid var(--danger)',
              }}>
                <strong>Warning:</strong> This is your <u>only</u> submission for this assignment. The system will <u>not allow re-uploads</u> once submitted.
                Make sure the file is correct before continuing.
              </div>
              <div className="modal-actions">
                <button type="button" className="btn-secondary" onClick={() => setShowConfirm(false)} disabled={loading}>
                  Review File
                </button>
                <button type="button" className="btn-primary" onClick={doUpload} disabled={loading}>
                  {loading ? 'Submitting...' : 'Yes, Submit Final Answer'}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
