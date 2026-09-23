import React from 'react';
import { Clock, CheckCircle2, AlertOctagon, User, BookOpen } from 'lucide-react';

export default function SessionList({ sessions, selectedSessionId, onSelectSession }) {
  return (
    <div className="panel-card">
      <div className="panel-header">
        <div className="panel-title">
          <BookOpen size={18} style={{ color: 'var(--primary)' }} />
          <span>Phiên thực hành ({sessions.length})</span>
        </div>
      </div>

      <div className="session-list">
        {sessions.map((s) => {
          const isSelected = s.session_id === selectedSessionId;
          const isCompleted = s.status === 'COMPLETED';
          const isStuck = s.session_id.includes('STUCK');
          const progressPercent = s.total_steps > 0 
            ? Math.round((s.completed_steps / s.total_steps) * 100) 
            : 0;

          return (
            <div
              key={s.session_id}
              className={`session-item ${isSelected ? 'active' : ''}`}
              onClick={() => onSelectSession(s.session_id)}
            >
              <div className="session-item-header">
                <span className="session-id-text">{s.session_id}</span>
                {isCompleted ? (
                  <span className="badge badge-completed">
                    <CheckCircle2 size={12} /> Hoàn thành
                  </span>
                ) : isStuck ? (
                  <span className="badge badge-stuck">
                    <AlertOctagon size={12} /> Cần can thiệp
                  </span>
                ) : (
                  <span className="badge badge-in-progress">
                    <Clock size={12} /> Đang làm
                  </span>
                )}
              </div>

              <div className="session-meta-sub">
                <span style={{ display: 'flex', alignItems: 'center', gap: '4px', color: '#cbd5e1' }}>
                  <User size={13} /> {s.student_name || s.student_id}
                </span>
                <span>Bài: <strong>{s.lesson_id}</strong></span>
              </div>

              <div className="session-meta-sub" style={{ marginTop: '8px' }}>
                <span>Tiến độ bước: {s.completed_steps}/{s.total_steps} ({progressPercent}%)</span>
                <span>{s.event_count || 0} events</span>
              </div>

              <div className="progress-track">
                <div
                  className="progress-fill"
                  style={{
                    width: `${progressPercent}%`,
                    background: isStuck ? 'var(--accent-rose)' : undefined,
                  }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
