import React from 'react';
import { Radio, FileSpreadsheet, Layers, User, Zap } from 'lucide-react';

export default function ExcelRadar({ activeStudent, activeWorkbook, activeSheet, activeCell, lastAction, isRealtimeConnected }) {
  return (
    <div className="radar-card">
      <div className="radar-left">
        <div className="radar-badge-row">
          <span className="radar-live-tag">
            <span className={`status-dot ${isRealtimeConnected ? 'online' : 'offline'}`} />
            {isRealtimeConnected ? 'Supabase Realtime Live' : 'Kết nối lại...'}
          </span>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-subtle)', display: 'flex', alignItems: 'center', gap: '4px' }}>
            <Radio size={14} className="text-emerald-500 animate-pulse" />
            Đang bắt thao tác trực tiếp từ Excel
          </span>
        </div>

        <div className="radar-title">
          {lastAction ? (
            <span style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Zap size={20} style={{ color: 'var(--primary)' }} />
              {lastAction}
            </span>
          ) : (
            'Đang chờ học viên thao tác trên Excel...'
          )}
        </div>

        <div className="radar-meta-row">
          <div className="radar-meta-item">
            <User size={15} style={{ color: 'var(--text-muted)' }} />
            <span>Học viên: <strong>{activeStudent || 'Chưa có'}</strong></span>
          </div>

          <div className="radar-meta-item">
            <FileSpreadsheet size={15} style={{ color: 'var(--primary)' }} />
            <span>File: <strong>{activeWorkbook || 'Chưa mở file'}</strong></span>
          </div>

          <div className="radar-meta-item">
            <Layers size={15} style={{ color: 'var(--accent-sky)' }} />
            <span>Sheet: <strong>{activeSheet || 'Sheet1'}</strong></span>
          </div>
        </div>
      </div>

      <div className="radar-right">
        <div className="current-cell-box">
          <div className="current-cell-lbl">Ô Excel Hiện Tại</div>
          <div className="current-cell-val">
            {activeCell ? `[ ${activeCell} ]` : '[ -- ]'}
          </div>
        </div>
      </div>
    </div>
  );
}
