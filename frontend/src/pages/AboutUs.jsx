import { Info, BrainCircuit, Lightbulb, ShieldCheck } from 'lucide-react';
import './AboutUs.css';

export default function AboutUs() {
  const team = [
    {
      name: "Hassan Jahangir",
      id: "22108177",
      role: "AI & Backend Engineering",
    },
    {
      name: "Muhammad Ibad",
      id: "22108228",
      role: "Frontend & UX Engineer",
    },
    {
      name: "Muhammad Muneeb",
      id: "22108190",
      role: "AI, XAI & LLM, Database & Systems Architecture",
    }
  ];

  return (
    <div className="dashboard-wrapper fade-in">
      <header className="dashboard-header" style={{ marginBottom: '1.5rem' }}>
        <div>
          <h1 className="page-title">About the Project</h1>
          <p className="page-subtitle">BS Artificial Intelligence (BS-AI) Final Year Project — SZABIST Islamabad</p>
        </div>
      </header>

      <section className="glass-panel project-overview">
        <h2 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
          <BrainCircuit className="icon-blue" />
          CheckMate AI: Intelligent Grading & Explainability
        </h2>
        <p className="overview-text">
          CheckMate AI was engineered to bridge the gap between traditional manual assessment and next-generation educational technologies. Leveraging advanced <strong>Large Language Models (LLMs)</strong> combined with native multimodal vision parsing, the platform provides automated, highly accurate grading for physical and digital assignment submissions.
        </p>
        <p className="overview-text">
          A core pillar of our research and implementation is <strong>Explainability</strong>. Rather than providing absolute black-box judgments, the system cross-references the student's handwritten or digital answer against the teacher's original rubric. The output guarantees actionable feedback, ensuring students and educators alike understand exactly why marks were awarded or deducted.
        </p>

        <div className="feature-grid">
          <div className="feature-item">
            <Lightbulb className="icon-emerald" size={24} />
            <div>
              <h4>Explainable AI (XAI)</h4>
              <p>Transparent grading rationale tracing outputs back to the prompt.</p>
            </div>
          </div>
          <div className="feature-item">
            <ShieldCheck className="icon-indigo" size={24} />
            <div>
              <h4>Role Segregation</h4>
              <p>Strict boundaries separating educator assignment definitions and localized student uploads.</p>
            </div>
          </div>
        </div>
      </section>

      <h3 className="section-title" style={{ marginTop: '3rem', marginBottom: '1.5rem' }}>Meet the Development Team</h3>
      
      <section className="team-grid">
        {team.map((member, idx) => (
          <div key={idx} className="glass-panel team-card">
            <div className="avatar-placeholder">
              <span className="avatar-initials">{member.name.split(' ').map(n => n[0]).join('')}</span>
            </div>
            <h3 className="team-name">{member.name}</h3>
            <p className="team-id">{member.id}</p>
            <span className="team-role">{member.role}</span>
          </div>
        ))}
      </section>
    </div>
  );
}
