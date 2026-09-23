import React, { useState } from 'react';
import { BookOpen, CheckCircle2, Clock, AlertOctagon, User, Search } from 'lucide-react';

export default function SessionList({ sessions, selectedSessionId, onSelectSession }) {
  const [searchTerm, setSearchTerm] = useState('');

  const filteredSessions = sessions.filter(s => {
    const q = searchTerm.toLowerCase();
    const id = (s.session_id || '').toLowerCase();
    const student = (s.student_name || s.student_id || '').toLowerCase();
    const lesson = (s.lesson_id || '').toLowerCase();
    return id.includes(q) || student.includes(q) || lesson.includes(q);
  });

  return (
    <div className="panel-card">
      <div className="panel-header">
        <div className="panel-title">
          <BookOpen size={18} style={{ color: 'var(--primary)' }} />
          <span>Phiên thực hành ({sessions.length})</span>
        </div>
      </div>

      {/* Search Input */}
      <div style={{ padding: '10px 16px', borderBottom: '1px solid #f1f5f9', background: '#f8fafc' }}>
        <div style={{ position: 'relative' }}>
          <Search size={15} style={{ position: 'absolute', left: '10px', top: '9px', color: 'var(--text-subtle)' }} />
          <input
            type="text"
            placeholder="Tìm theo tên học viên, bài tập..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            style={{
              width: '100%',
              padding: '6px 12px 6px 32px',
              borderRadius: '6px',
              border: '1px solid #e2e8f0',
              fontSize: '0.8rem',
              outline: 'none',
              background: '#ffffff',
            }}
          />
        </div>
      </div>

      <div className="session-list">
        {filteredSessions.length === 0 ? (
          <div style={{ padding: '24px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
            Không tìm thấy phiên thực hành nào.
          </div>
        ) : (
          filteredSessions.map((s) => {
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
                  <span className="session-id-text" title={s.session_id}>
                    {s.session_id.length > 28 ? s.session_id.substring(0, 26) + '...' : s.session_id}
                  </span>
                  {isCompleted ? (
                    <span className="badge badge-completed">
                      <CheckCircle2 size={11} /> Xong
                    </span>
                  ) : isStuck ? (
                    <span className="badge badge-stuck">
                      <AlertOctagon size={11} /> Cần trợ giúp
                    </span>
                  ) : (
                    <span className="badge badge-in-progress">
                      <Clock size={11} /> Đang làm
                    </span>
                  )}
                </div>

                <div className="session-meta-sub">
                  <span style={{ display: 'flex', alignItems: 'center', gap: '4px', fontWeight: 600, color: 'var(--text-main)' }}>
                    <User size={13} style={{ color: 'var(--text-muted)' }} /> {s.student_name || s.student_id}
                  </span>
                  <span>{s.event_count || 0} thao tác</span>
                </div>

                <div className="session-meta-sub" style={{ marginTop: '4px', fontSize: '0.78rem' }}>
                  <span title={s.lesson_id} style={{ maxWidth: '100%', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    Bài: <strong>{s.lesson_id || 'Chưa mở file'}</strong>
                  </span>
                </div>

                <div className="progress-track">
                  <div
                    className="progress-fill"
                    style={{
                      width: `${progressPercent > 0 ? progressPercent : (s.event_count > 0 ? Math.min(100, s.event_count * 5) : 0)}%`,
                      background: isStuck ? 'var(--accent-rose)' : undefined,
                    }}
                  />
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
