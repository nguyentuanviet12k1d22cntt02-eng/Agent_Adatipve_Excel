import React from 'react';
import { Activity, Clock, MousePointer2, AlertOctagon, Target } from 'lucide-react';

export default function FeatureViewer({ features }) {
  if (!features || features.length === 0) {
    return (
      <div className="panel-card" style={{ padding: '32px', textAlign: 'center', color: 'var(--text-muted)' }}>
        Chưa có vector đặc trưng nào được tính toán cho phiên này.
      </div>
    );
  }

  // Lấy bản ghi đặc trưng gần nhất
  const latest = features[features.length - 1];

  return (
    <div className="panel-card">
      <div className="panel-header">
        <div className="panel-title">
          <Activity size={18} style={{ color: 'var(--accent-indigo)' }} />
          <span>Vector đặc trưng hành vi người học (Feature Store - Bước {latest.step_index})</span>
        </div>
      </div>

      <div className="feature-cards-grid">
        {/* 1. Nhóm Thời gian (Timing) */}
        <div className="feature-box">
          <div className="feature-box-title">
            <Clock size={16} style={{ color: 'var(--accent-cyan)' }} />
            <span>1. Đặc trưng Thời gian (Timing)</span>
          </div>
          <div className="feature-row">
            <span className="f-name">Thời gian thực hiện (time_on_task):</span>
            <span className="f-val" style={{ color: 'var(--accent-cyan)' }}>
              {Number(latest.time_on_task).toFixed(1)}s
            </span>
          </div>
          <div className="feature-row">
            <span className="f-name">Khoảng ngập ngừng TB (mouse_idle_avg):</span>
            <span className="f-val">
              {Number(latest.mouse_idle_avg).toFixed(2)}s
            </span>
          </div>
          <div className="feature-row">
            <span className="f-name">Khoảng ngập ngừng lớn nhất (mouse_idle_max):</span>
            <span className="f-val" style={{ color: latest.mouse_idle_max > 4 ? 'var(--accent-amber)' : '#fff' }}>
              {Number(latest.mouse_idle_max).toFixed(2)}s
            </span>
          </div>
        </div>

        {/* 2. Động lực học chuột (Mouse Dynamics) */}
        <div className="feature-box">
          <div className="feature-box-title">
            <MousePointer2 size={16} style={{ color: 'var(--primary)' }} />
            <span>2. Động lực học chuột (Mouse)</span>
          </div>
          <div className="feature-row">
            <span className="f-name">Tốc độ di chuột TB (mouse_speed_mean):</span>
            <span className="f-val" style={{ color: 'var(--primary)' }}>
              {Number(latest.mouse_speed_mean).toFixed(1)} px/s
            </span>
          </div>
          <div className="feature-row">
            <span className="f-name">Số lần đổi chọn ô (selection_changes):</span>
            <span className="f-val">
              {latest.selection_changes} lần
            </span>
          </div>
          <div className="feature-row">
            <span className="f-name">Đánh giá chuyển động:</span>
            <span className="f-val" style={{ color: latest.mouse_speed_mean > 250 ? 'var(--accent-rose)' : 'var(--primary)' }}>
              {latest.mouse_speed_mean > 250 ? 'Di chuột hỗn loạn' : 'Chuyển động ổn định'}
            </span>
          </div>
        </div>

        {/* 3. Lỗi thao tác & Công thức */}
        <div className="feature-box">
          <div className="feature-box-title">
            <AlertOctagon size={16} style={{ color: 'var(--accent-rose)' }} />
            <span>3. Lỗi thao tác (Errors & Mistakes)</span>
          </div>
          <div className="feature-row">
            <span className="f-name">Lỗi công thức (formula_errors):</span>
            <span className="f-val" style={{ color: latest.formula_errors > 0 ? 'var(--accent-rose)' : '#fff' }}>
              {latest.formula_errors}
            </span>
          </div>
          <div className="feature-row">
            <span className="f-name">Số lần thử sai (wrong_attempts):</span>
            <span className="f-val" style={{ color: latest.wrong_attempts > 0 ? 'var(--accent-rose)' : '#fff' }}>
              {latest.wrong_attempts}
            </span>
          </div>
          <div className="feature-row">
            <span className="f-name">Số lần Undo / Rollback (undo_count):</span>
            <span className="f-val">{latest.undo_count}</span>
          </div>
          <div className="feature-row">
            <span className="f-name">Số lần làm lại (retry_count):</span>
            <span className="f-val">{latest.retry_count}</span>
          </div>
        </div>

        {/* 4. Tiến độ & Yêu cầu trợ giúp */}
        <div className="feature-box">
          <div className="feature-box-title">
            <Target size={16} style={{ color: '#38bdf8' }} />
            <span>4. Tiến độ & Hỗ trợ (Performance)</span>
          </div>
          <div className="feature-row">
            <span className="f-name">Tỷ lệ hoàn thành (completion_rate):</span>
            <span className="f-val" style={{ color: '#38bdf8' }}>
              {Math.round((latest.completion_rate || 0) * 100)}%
            </span>
          </div>
          <div className="feature-row">
            <span className="f-name">Số lần xin gợi ý (hint_requests):</span>
            <span className="f-val">{latest.hint_requests}</span>
          </div>
          <div className="feature-row">
            <span className="f-name">Dữ liệu ghi nhận lúc:</span>
            <span className="f-val" style={{ fontSize: '0.75rem', color: 'var(--text-subtle)' }}>
              {latest.created_at ? new Date(latest.created_at).toLocaleTimeString() : 'Vừa xong'}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
