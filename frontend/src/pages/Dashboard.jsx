import { useEffect, useState } from 'react';
import TeacherDashboard from './TeacherDashboard';
import StudentDashboard from './StudentDashboard';

export default function Dashboard() {
  const [role, setRole] = useState('student');

  useEffect(() => {
    setRole(localStorage.getItem('role') || 'student');
  }, []);

  return (
    <>
      {role === 'teacher' || role === 'admin' ? <TeacherDashboard /> : <StudentDashboard />}
    </>
  );
}
