import React from 'react';
import { Users, BookOpen, Cpu, AlertTriangle, AlertCircle } from 'lucide-react';

export default function KpiMetrics({ stats }) {
  if (!stats) return null;

  return (
    <div className="kpi-grid">
      {/* 1. Học viên */}
      <div className="kpi-card">
        <div className="kpi-icon-container" style={{ background: 'rgba(6, 182, 212, 0.12)', color: 'var(--accent-cyan)' }}>
          <Users size={24} />
        </div>
        <div>
          <div className="kpi-value">{stats.total_students ?? 0}</div>
          <div className="kpi-label">Học viên ghi danh</div>
        </div>
      </div>

      {/* 2. Phiên học */}
      <div className="kpi-card">
        <div className="kpi-icon-container" style={{ background: 'rgba(16, 185, 129, 0.12)', color: 'var(--primary)' }}>
          <BookOpen size={24} />
        </div>
        <div>
          <div className="kpi-value">
            {stats.total_sessions ?? 0}
            <span style={{ fontSize: '0.9rem', color: 'var(--text-muted)', marginLeft: '6px' }}>
              ({stats.active_sessions ?? 0} đang chạy)
            </span>
          </div>
          <div className="kpi-label">Tổng phiên thực hành</div>
        </div>
      </div>

      {/* 3. Sự kiện Telemetry */}
      <div className="kpi-card">
        <div className="kpi-icon-container" style={{ background: 'rgba(99, 102, 241, 0.12)', color: 'var(--accent-indigo)' }}>
          <Cpu size={24} />
        </div>
        <div>
          <div className="kpi-value">{stats.total_events ?? 0}</div>
          <div className="kpi-label">Sự kiện hành vi ghi nhận</div>
        </div>
      </div>

      {/* 4. Cảnh báo Ngập ngừng */}
      <div className="kpi-card">
        <div className="kpi-icon-container" style={{ background: 'rgba(245, 158, 11, 0.12)', color: 'var(--accent-amber)' }}>
          <AlertTriangle size={24} />
        </div>
        <div>
          <div className="kpi-value">{stats.hesitation_events ?? 0}</div>
          <div className="kpi-label">Nhận diện ngập ngừng (Pause)</div>
        </div>
      </div>

      {/* 5. Lỗi công thức */}
      <div className="kpi-card">
        <div className="kpi-icon-container" style={{ background: 'rgba(244, 63, 94, 0.12)', color: 'var(--accent-rose)' }}>
          <AlertCircle size={24} />
        </div>
        <div>
          <div className="kpi-value">{stats.formula_errors ?? 0}</div>
          <div className="kpi-label">Lỗi công thức / định dạng</div>
        </div>
      </div>
    </div>
  );
}
