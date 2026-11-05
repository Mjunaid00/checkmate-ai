import { Routes, Route, Navigate } from 'react-router-dom';
import { useState, useEffect } from 'react';
import { ThemeProvider } from './contexts/ThemeContext';
import { ToastProvider } from './contexts/ToastContext';
import Login from './pages/Login';
import LandingPage from './pages/LandingPage';
import Dashboard from './pages/Dashboard';
import TeacherClasses from './pages/TeacherClasses';
import AboutUs from './pages/AboutUs';
import Settings from './pages/Settings';
import QuizTaker from './pages/QuizTaker';
import QuizResults from './pages/QuizResults';
import Analytics from './pages/Analytics';
import AdminPanel from './pages/AdminPanel';
import Sidebar from './components/Sidebar';
import PublicNav from './components/PublicNav';

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [role, setRole] = useState('student');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem('token');
    const savedRole = localStorage.getItem('role');
    setIsAuthenticated(!!token);
    if (savedRole) setRole(savedRole);
    setLoading(false);
  }, []);

  // Wrap setIsAuthenticated so we re-read the role from localStorage right
  // after the Login page stores it — keeps the sidebar and route guards in sync.
  const handleAuth = (next) => {
    if (next) {
      const savedRole = localStorage.getItem('role');
      if (savedRole) setRole(savedRole);
    }
    setIsAuthenticated(next);
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('role');
    localStorage.removeItem('userId');
    localStorage.removeItem('userName');
    setRole('student');
    setIsAuthenticated(false);
  };

  if (loading) return null;

  // Admins get every teacher page plus the Admin Panel.
  const isTeacherLike = role === 'teacher' || role === 'admin';

  return (
    <ThemeProvider>
      <ToastProvider>
        <div className="app-container">
          {isAuthenticated && <Sidebar role={role} onLogout={handleLogout} />}
          {!isAuthenticated && <PublicNav />}

          <main className={isAuthenticated ? "main-content" : "main-content public-layout"}>
            <Routes>
              {/* Public routes */}
              <Route
                path="/"
                element={
                  isAuthenticated
                    ? <Dashboard />
                    : <LandingPage />
                }
              />
              <Route path="/login" element={!isAuthenticated ? <AuthLayout><Login setAuth={handleAuth} /></AuthLayout> : <Navigate to="/" />} />
              <Route path="/register" element={!isAuthenticated ? <AuthLayout><Login setAuth={handleAuth} defaultRegister /></AuthLayout> : <Navigate to="/" />} />

              {/* Protected routes */}
              <Route path="/classes" element={isAuthenticated && isTeacherLike ? <TeacherClasses /> : <Navigate to="/" />} />
              <Route path="/archive" element={isAuthenticated ? <div style={{padding:'2rem'}}><h2>Archive</h2><p style={{color:'var(--text-secondary)', marginTop:'0.5rem'}}>Historical assignment records will appear here.</p></div> : <Navigate to="/login" />} />
              <Route path="/about" element={isAuthenticated ? <AboutUs /> : <Navigate to="/" />} />
              <Route path="/settings" element={isAuthenticated ? <Settings onLogout={handleLogout} /> : <Navigate to="/login" />} />
              <Route path="/analytics" element={isAuthenticated && isTeacherLike ? <Analytics /> : <Navigate to="/" />} />
              <Route path="/admin" element={isAuthenticated && role === 'admin' ? <AdminPanel /> : <Navigate to="/" />} />
              <Route path="/quiz/:quizId/take" element={isAuthenticated && role === 'student' ? <QuizTaker /> : <Navigate to="/" />} />
              <Route path="/quiz/:quizId/result" element={isAuthenticated ? <QuizResults /> : <Navigate to="/login" />} />
            </Routes>
          </main>
        </div>
      </ToastProvider>
    </ThemeProvider>
  );
}

// Wrapper to give Login/Register the centered auth layout
function AuthLayout({ children }) {
  return <div className="auth-layout">{children}</div>;
}

export default App;
