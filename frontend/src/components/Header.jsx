import React from 'react';
import { Database, Activity, RefreshCw, Layers, ShieldCheck } from 'lucide-react';

export default function Header({ health, isRefreshing, onRefresh, autoRefresh, setAutoRefresh }) {
  const isOnline = health?.status === 'online';

  return (
    <header className="top-header">
      <div className="brand-section">
        <div className="brand-icon-wrapper">
          <Layers size={24} />
        </div>
        <div>
          <div className="brand-title">
            Adaptive AI Excel Tutor
            <span className="brand-badge">Phase 1: Telemetry & Sensing</span>
          </div>
          <div className="brand-subtitle">
            Hệ thống thu thập dữ liệu hành vi người học & Phân tích nhận thức thời gian thực
          </div>
        </div>
      </div>

      <div className="header-actions">
        {/* MySQL Health Indicator */}
        <div className="db-status-chip">
          <span className={`status-dot ${isOnline ? 'online' : 'offline'}`} />
          <Database size={15} style={{ color: isOnline ? 'var(--primary)' : 'var(--accent-rose)' }} />
          <span>
            {isOnline ? (
              <>
                <strong>MySQL 9.4</strong> Connected ({health.database_name})
              </>
            ) : (
              <>Đang kết nối lại MySQL...</>
            )}
          </span>
        </div>

        {/* Auto Refresh Toggle */}
        <button
          className={`btn-action ${autoRefresh ? 'btn-primary' : 'btn-secondary'}`}
          onClick={() => setAutoRefresh(!autoRefresh)}
          title="Tự động cập nhật mỗi 3 giây"
        >
          <Activity size={16} />
          <span>{autoRefresh ? 'Live Polling: BẬT' : 'Live Polling: TẮT'}</span>
        </button>

        {/* Manual Refresh */}
        <button
          className="btn-action btn-secondary"
          onClick={onRefresh}
          disabled={isRefreshing}
          title="Làm mới dữ liệu từ MySQL"
        >
          <RefreshCw size={16} className={isRefreshing ? 'animate-spin' : ''} />
          <span>Làm mới</span>
        </button>
      </div>
    </header>
  );
}
