import { Link, useLocation } from 'react-router-dom';
import { LogOut, Home, FileText, Settings, Users, Info, BarChart3, ShieldCheck } from 'lucide-react';
import ThemeSwitcher from './ThemeSwitcher';
import NotificationsBell from './NotificationsBell';
import SidebarWidgets from './SidebarWidgets';
import './Sidebar.css';

export default function Sidebar({ role, onLogout }) {
  const location = useLocation();
  const isActive = (path) => location.pathname === path ? 'active' : '';
  return (
    <div className="sidebar">
      <div className="sidebar-header">
        <div className="logo-icon">C</div>
        <h2>CheckMate</h2>
      </div>

      <nav className="sidebar-nav">
        <Link to="/" className={`nav-item ${isActive('/')}`}>
          <Home size={20} />
          <span>Dashboard</span>
        </Link>

        {(role === 'teacher' || role === 'admin') && (
          <Link to="/classes" className={`nav-item ${isActive('/classes')}`}>
            <Users size={20} />
            <span>Class Groups</span>
          </Link>
        )}

        {(role === 'teacher' || role === 'admin') && (
          <Link to="/analytics" className={`nav-item ${isActive('/analytics')}`}>
            <BarChart3 size={20} />
            <span>Analytics</span>
          </Link>
        )}

        {role === 'admin' && (
          <Link to="/admin" className={`nav-item ${isActive('/admin')}`}>
            <ShieldCheck size={20} />
            <span>Admin Panel</span>
          </Link>
        )}

        <Link to="/archive" className={`nav-item ${isActive('/archive')}`}>
          <FileText size={20} />
          <span>Exams Archive</span>
        </Link>

        <Link to="/about" className={`nav-item ${isActive('/about')}`}>
          <Info size={20} />
          <span>About Us</span>
        </Link>

        <Link to="/settings" className={`nav-item ${isActive('/settings')}`}>
          <Settings size={20} />
          <span>Settings</span>
        </Link>

        {/* Sign-out lives right next to Settings, as requested */}
        <button className="nav-item logout-btn" onClick={onLogout}>
          <LogOut size={20} />
          <span>Sign Out</span>
        </button>
      </nav>

      <div className="sidebar-footer">
        <SidebarWidgets />
        <NotificationsBell />
        <div className="theme-switcher-row">
          <ThemeSwitcher compact />
        </div>
      </div>
    </div>
  );
}
