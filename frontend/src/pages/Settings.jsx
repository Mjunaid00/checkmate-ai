import { useState, useEffect } from 'react';
import { User, Lock, Trash2, Save, AlertTriangle, Palette } from 'lucide-react';
import api from '../services/api';
import ThemeSwitcher from '../components/ThemeSwitcher';
import './Settings.css';

export default function Settings({ onLogout }) {
  const [profile, setProfile] = useState({ name: '', email: '', role: '', bio: '', phone: '', institution: '' });
  const [profileMsg, setProfileMsg] = useState('');
  const [profileErr, setProfileErr] = useState('');

  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [pwMsg, setPwMsg] = useState('');
  const [pwErr, setPwErr] = useState('');

  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleteLoading, setDeleteLoading] = useState(false);

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [pwSaving, setPwSaving] = useState(false);

  useEffect(() => {
    fetchProfile();
  }, []);

  const fetchProfile = async () => {
    try {
      const res = await api.get('/auth/me');
      setProfile({
        name: res.data.name || '',
        email: res.data.email || '',
        role: res.data.role || '',
        bio: res.data.bio || '',
        phone: res.data.phone || '',
        institution: res.data.institution || '',
      });
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleProfileSave = async (e) => {
    e.preventDefault();
    setSaving(true);
    setProfileMsg('');
    setProfileErr('');
    try {
      const res = await api.patch('/auth/profile', {
        name: profile.name,
        bio: profile.bio,
        phone: profile.phone,
        institution: profile.institution,
      });
      setProfile(prev => ({ ...prev, ...res.data }));
      setProfileMsg('Profile updated successfully.');
      // Update name in localStorage so sidebar reflects it
      if (res.data.name) localStorage.setItem('userName', res.data.name);
    } catch (err) {
      setProfileErr(err.response?.data?.detail || 'Failed to update profile.');
    } finally {
      setSaving(false);
    }
  };

  const handlePasswordChange = async (e) => {
    e.preventDefault();
    setPwMsg('');
    setPwErr('');

    if (newPassword !== confirmPassword) {
      setPwErr('New passwords do not match.');
      return;
    }

    setPwSaving(true);
    try {
      await api.post('/auth/change-password', {
        current_password: currentPassword,
        new_password: newPassword,
      });
      setPwMsg('Password changed successfully.');
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
    } catch (err) {
      setPwErr(err.response?.data?.detail || 'Failed to change password.');
    } finally {
      setPwSaving(false);
    }
  };

  const handleDeleteAccount = async () => {
    setDeleteLoading(true);
    try {
      await api.delete('/auth/account');
      // Log out after deletion
      if (onLogout) onLogout();
    } catch (err) {
      console.error(err);
      setDeleteLoading(false);
    }
  };

  if (loading) return <div className="loading-state">Loading settings...</div>;

  return (
    <div className="dashboard-wrapper fade-in">
      <header className="dashboard-header">
        <div>
          <h1 className="page-title">Account Settings</h1>
          <p className="page-subtitle">Manage your profile, password, and account.</p>
        </div>
      </header>

      {/* ── Appearance Section ─────────────────────────────────── */}
      <section className="settings-section glass-panel">
        <div className="settings-section-header">
          <Palette size={20} />
          <h3>Appearance</h3>
        </div>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginBottom: '1rem' }}>
          Choose a theme that suits your preference.
        </p>
        <ThemeSwitcher />
      </section>

      {/* ── Profile Section ────────────────────────────────────── */}
      <section className="settings-section glass-panel">
        <div className="settings-section-header">
          <User size={20} />
          <h3>Profile Information</h3>
        </div>

        {profileMsg && <div className="success-banner">{profileMsg}</div>}
        {profileErr && <div className="error-banner">{profileErr}</div>}

        <form onSubmit={handleProfileSave} className="settings-form">
          <div className="form-row">
            <div className="form-group">
              <label>Full Name</label>
              <input
                type="text"
                className="input-field"
                value={profile.name}
                onChange={e => setProfile(p => ({ ...p, name: e.target.value }))}
                required
                minLength={2}
              />
            </div>
            <div className="form-group">
              <label>Email</label>
              <input
                type="email"
                className="input-field"
                value={profile.email}
                disabled
                title="Email cannot be changed"
              />
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>Phone</label>
              <input
                type="tel"
                className="input-field"
                value={profile.phone}
                onChange={e => setProfile(p => ({ ...p, phone: e.target.value }))}
                placeholder="e.g. +92 300 1234567"
              />
            </div>
            <div className="form-group">
              <label>Institution</label>
              <input
                type="text"
                className="input-field"
                value={profile.institution}
                onChange={e => setProfile(p => ({ ...p, institution: e.target.value }))}
                placeholder="e.g. SZABIST, NUST, LUMS"
              />
            </div>
          </div>

          <div className="form-group">
            <label>Bio</label>
            <textarea
              className="input-field"
              rows={3}
              value={profile.bio}
              onChange={e => setProfile(p => ({ ...p, bio: e.target.value }))}
              placeholder="Tell us a bit about yourself..."
              style={{ resize: 'vertical', fontFamily: 'inherit' }}
              maxLength={300}
            />
          </div>

          <div className="form-group" style={{ marginBottom: 0 }}>
            <span className="role-badge">{profile.role}</span>
          </div>

          <button type="submit" className="btn-primary settings-save-btn" disabled={saving}>
            <Save size={16} /> {saving ? 'Saving...' : 'Save Profile'}
          </button>
        </form>
      </section>

      {/* ── Password Section ───────────────────────────────────── */}
      <section className="settings-section glass-panel">
        <div className="settings-section-header">
          <Lock size={20} />
          <h3>Change Password</h3>
        </div>

        {pwMsg && <div className="success-banner">{pwMsg}</div>}
        {pwErr && <div className="error-banner">{pwErr}</div>}

        <form onSubmit={handlePasswordChange} className="settings-form">
          <div className="form-group">
            <label>Current Password</label>
            <input
              type="password"
              className="input-field"
              value={currentPassword}
              onChange={e => setCurrentPassword(e.target.value)}
              required
            />
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>New Password</label>
              <input
                type="password"
                className="input-field"
                value={newPassword}
                onChange={e => setNewPassword(e.target.value)}
                required
                minLength={6}
                placeholder="Min 6 characters"
              />
            </div>
            <div className="form-group">
              <label>Confirm New Password</label>
              <input
                type="password"
                className="input-field"
                value={confirmPassword}
                onChange={e => setConfirmPassword(e.target.value)}
                required
                minLength={6}
              />
            </div>
          </div>

          <button type="submit" className="btn-primary settings-save-btn" disabled={pwSaving}>
            <Lock size={16} /> {pwSaving ? 'Updating...' : 'Update Password'}
          </button>
        </form>
      </section>

      {/* ── Danger Zone ────────────────────────────────────────── */}
      <section className="settings-section glass-panel danger-zone">
        <div className="settings-section-header">
          <AlertTriangle size={20} />
          <h3>Danger Zone</h3>
        </div>

        <p className="danger-text">
          Permanently delete your account and all associated data. This action cannot be undone.
        </p>

        {!showDeleteConfirm ? (
          <button
            className="btn-danger"
            onClick={() => setShowDeleteConfirm(true)}
          >
            <Trash2 size={16} /> Delete My Account
          </button>
        ) : (
          <div className="delete-confirm">
            <p><strong>Are you sure?</strong> All your data will be permanently removed.</p>
            <div style={{ display: 'flex', gap: '0.75rem' }}>
              <button
                className="btn-danger"
                onClick={handleDeleteAccount}
                disabled={deleteLoading}
              >
                {deleteLoading ? 'Deleting...' : 'Yes, Delete Everything'}
              </button>
              <button
                className="btn-secondary"
                onClick={() => setShowDeleteConfirm(false)}
              >
                Cancel
              </button>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
