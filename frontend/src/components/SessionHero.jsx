import React from 'react';
import { User, Calendar, CheckCircle2, Clock, AlertTriangle } from 'lucide-react';

export default function SessionHero({ session }) {
  if (!session) return null;

  const isCompleted = session.status === 'COMPLETED';
  const isStuck = session.session_id.includes('STUCK');

  return (
    <div className="session-hero-banner">
      <div className="hero-left">
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '4px' }}>
          <h2>{session.session_id}</h2>
          {isCompleted ? (
            <span className="badge badge-completed">COMPLETED</span>
          ) : isStuck ? (
            <span className="badge badge-stuck">COGNITIVE STUCK DETECTED</span>
          ) : (
            <span className="badge badge-in-progress">IN PROGRESS</span>
          )}
        </div>
        <p style={{ display: 'flex', alignItems: 'center', gap: '16px', flexWrap: 'wrap' }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <User size={14} /> Học viên: <strong>{session.student_name} ({session.student_id})</strong>
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <Calendar size={14} /> Bài tập: <strong>{session.lesson_id}</strong>
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <Clock size={14} /> Bắt đầu: {session.started_at ? new Date(session.started_at).toLocaleTimeString() : 'N/A'}
          </span>
        </p>
      </div>

      <div className="hero-stats-group">
        <div className="hero-stat-box">
          <div className="val" style={{ color: 'var(--primary)' }}>
            {session.completed_steps} / {session.total_steps}
          </div>
          <div className="lbl">Số bước hoàn thành</div>
        </div>
        <div className="hero-stat-box">
          <div className="val" style={{ color: 'var(--accent-cyan)' }}>
            {session.total_steps > 0 ? Math.round((session.completed_steps / session.total_steps) * 100) : 0}%
          </div>
          <div className="lbl">Tỷ lệ hoàn thành</div>
        </div>
      </div>
    </div>
  );
}
