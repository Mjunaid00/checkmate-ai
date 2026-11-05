import { useState, useEffect } from 'react';
import { Plus, Users, Pencil, Trash2, FileText, BarChart3, MessageSquare } from 'lucide-react';
import api from '../services/api';
import UploadWidget from '../components/UploadWidget';
import EditClassModal from '../components/EditClassModal';
import ClassReportModal from '../components/ClassReportModal';
import ClassMessagesModal from '../components/ClassMessagesModal';

export default function TeacherClasses() {
  const [classes, setClasses] = useState([]);
  const [newClassName, setNewClassName] = useState('');
  const [newMaxStudents, setNewMaxStudents] = useState('');
  const [activeClassToUpload, setActiveClassToUpload] = useState(null);
  const [editingClass, setEditingClass] = useState(null);
  const [reportingClass, setReportingClass] = useState(null);
  const [classChats, setClassChats] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchClasses = async () => {
    try {
      const res = await api.get('/classes/');
      setClasses(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchClasses();
  }, []);

  const handleCreateClass = async (e) => {
    e.preventDefault();
    if (!newClassName.trim()) return;
    try {
      const payload = { name: newClassName.trim() };
      const max = parseInt(newMaxStudents);
      if (!isNaN(max) && max > 0) payload.max_students = max;
      await api.post('/classes/', payload);
      setNewClassName('');
      setNewMaxStudents('');
      fetchClasses();
    } catch (err) {
      console.error(err);
    }
  };

  const handleDeleteClass = async (classId) => {
    if (!window.confirm('Delete this class? All assignments, submissions, and enrollments will be permanently removed.')) return;
    try {
      await api.delete(`/classes/${classId}`);
      fetchClasses();
    } catch (err) {
      console.error(err);
    }
  };

  if (loading) return <div className="loading-state">Loading classes...</div>;

  return (
    <div className="dashboard-wrapper fade-in">
      {activeClassToUpload && (
        <UploadWidget
          classId={activeClassToUpload}
          isStudent={false}
          onClose={() => setActiveClassToUpload(null)}
          onUploadSuccess={fetchClasses}
        />
      )}

      {editingClass && (
        <EditClassModal
          classData={editingClass}
          onClose={() => setEditingClass(null)}
          onSaved={fetchClasses}
        />
      )}

      {reportingClass && (
        <ClassReportModal
          classData={reportingClass}
          onClose={() => setReportingClass(null)}
        />
      )}

      {classChats && (
        <ClassMessagesModal
          classData={classChats}
          onClose={() => setClassChats(null)}
        />
      )}

      <header className="dashboard-header">
        <div>
          <h1 className="page-title">Class Management</h1>
          <p className="page-subtitle">Create, edit, and manage class groups.</p>
        </div>
      </header>

      {/* Class Creator */}
      <section className="glass-panel" style={{ marginBottom: '2.5rem', padding: '1.5rem' }}>
        <h3 className="section-title">Establish New Class Group</h3>
        <form onSubmit={handleCreateClass} style={{ display: 'flex', gap: '1rem', maxWidth: '700px', flexWrap: 'wrap' }}>
          <input
            type="text"
            className="input-field"
            placeholder="e.g. Physics 101 - Fall 2026"
            value={newClassName}
            onChange={e => setNewClassName(e.target.value)}
            style={{ flex: 2, minWidth: '220px' }}
          />
          <input
            type="number"
            className="input-field"
            placeholder="Max students (optional)"
            min="1"
            value={newMaxStudents}
            onChange={e => setNewMaxStudents(e.target.value)}
            style={{ flex: 1, minWidth: '160px' }}
          />
          <button type="submit" className="btn-primary" style={{ whiteSpace: 'nowrap' }}>
            <Plus size={18} /> Create
          </button>
        </form>
      </section>

      {/* Class List */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '1.5rem' }}>
        {classes.length === 0 && <p className="text-muted">No classes created yet. Establish one above.</p>}
        {classes.map(c => (
          <div key={c.class_id} className="stat-card glass-panel" style={{ flexDirection: 'column', alignItems: 'flex-start' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.75rem', width: '100%' }}>
              <div className="stat-icon bg-indigo"><Users size={20} /></div>
              <h3 style={{ fontSize: '1.1rem', margin: 0, flex: 1 }}>{c.name}</h3>
            </div>

            <div style={{ display: 'flex', gap: '0.75rem', marginBottom: '0.85rem', fontSize: '0.82rem', color: 'var(--text-secondary)', flexWrap: 'wrap' }}>
              <span>
                <Users size={13} style={{ verticalAlign: 'middle', marginRight: '0.2rem' }} />
                <strong style={{ color: 'var(--text-primary)' }}>{c.enrollment_count ?? 0}</strong>
                {c.max_students ? ` / ${c.max_students}` : ''} students
              </span>
              <span>
                <FileText size={13} style={{ verticalAlign: 'middle', marginRight: '0.2rem' }} />
                <strong style={{ color: 'var(--text-primary)' }}>{c.assignments_count ?? 0}</strong> assignments
              </span>
            </div>

            <div style={{ display: 'flex', gap: '0.4rem', width: '100%', flexWrap: 'wrap' }}>
              <button
                className="btn-secondary"
                style={{ flex: '1 1 auto', display: 'flex', justifyContent: 'center', gap: '0.4rem', fontSize: '0.82rem', minWidth: '120px' }}
                onClick={() => setActiveClassToUpload(c.class_id)}
              >
                <Plus size={14} /> Assignment
              </button>
              <button
                className="btn-secondary"
                style={{ padding: '0.5rem 0.6rem', color: 'var(--accent-primary)' }}
                title="Class messages with students"
                onClick={() => setClassChats(c)}
              >
                <MessageSquare size={14} />
              </button>
              <button
                className="btn-secondary"
                style={{ padding: '0.5rem 0.6rem', color: 'var(--accent-primary)' }}
                title="View report"
                onClick={() => setReportingClass(c)}
              >
                <BarChart3 size={14} />
              </button>
              <button
                className="btn-secondary"
                style={{ padding: '0.5rem 0.6rem' }}
                title="Edit class & assignments"
                onClick={() => setEditingClass(c)}
              >
                <Pencil size={14} />
              </button>
              <button
                className="btn-secondary"
                style={{ padding: '0.5rem 0.6rem', color: '#DC2626' }}
                title="Delete class"
                onClick={() => handleDeleteClass(c.class_id)}
              >
                <Trash2 size={14} />
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
