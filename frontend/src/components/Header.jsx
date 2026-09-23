import React from 'react';
import { Cloud, Database, RefreshCw, FileSpreadsheet } from 'lucide-react';

export default function Header({ isRealtimeConnected, isRefreshing, onRefresh }) {
  return (
    <header className="top-header">
      <div className="brand-section">
        <div className="brand-icon-wrapper">
          <FileSpreadsheet size={24} />
        </div>
        <div>
          <div className="brand-title">
            Excel Adaptive AI Tutor
            <span className="brand-badge">Realtime Telemetry Dashboard</span>
          </div>
          <div className="brand-subtitle">
            Hệ thống giám sát thao tác Excel trực tiếp qua Supabase Cloud & Machine Learning
          </div>
        </div>
      </div>

      <div className="header-actions">
        {/* Supabase Status Chip */}
        <div className="db-status-chip supabase">
          <span className={`status-dot ${isRealtimeConnected ? 'online' : 'offline'}`} />
          <Cloud size={16} />
          <span>
            <strong>Supabase Cloud</strong> Realtime Active
          </span>
        </div>

        {/* MySQL Status Chip */}
        <div className="db-status-chip">
          <Database size={15} style={{ color: 'var(--primary)' }} />
          <span>MySQL Local Synced</span>
        </div>

        {/* Manual Refresh */}
        <button
          className="btn-action btn-secondary"
          onClick={onRefresh}
          disabled={isRefreshing}
          title="Tải lại dữ liệu mới nhất"
        >
          <RefreshCw size={15} className={isRefreshing ? 'animate-spin' : ''} />
          <span>Làm mới</span>
        </button>
      </div>
    </header>
  );
}
