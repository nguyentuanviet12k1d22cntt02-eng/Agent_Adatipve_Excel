import React, { useState } from 'react';
import { 
  MousePointer, 
  Edit3, 
  HelpCircle, 
  CheckCircle2, 
  AlertTriangle, 
  Clock, 
  Code2, 
  FileSpreadsheet,
  ChevronRight, 
  ChevronDown 
} from 'lucide-react';

export default function TimelineStream({ events, activeFilter, onFilterChange, latestEventId }) {
  const [expandedEventId, setExpandedEventId] = useState(null);

  const filters = [
    { key: 'ALL', label: 'Tất cả' },
    { key: 'CELL_SELECTION', label: 'Chọn ô (Selection)' },
    { key: 'CELL_VALUE_CHANGE', label: 'Nhập số/chữ (Value)' },
    { key: 'FORMULA_ENTRY', label: 'Gõ công thức (Formula)' },
    { key: 'MOUSE_HESITATION_START', label: 'Ngập ngừng chuột' },
    { key: 'WORKBOOK_OPEN', label: 'Mở file Excel' },
  ];

  const getEventBadgeMeta = (type) => {
    switch (type) {
      case 'CELL_SELECTION':
      case 'RANGE_SELECTION':
        return {
          icon: <MousePointer size={16} />,
          color: 'var(--accent-sky)',
          bg: 'var(--accent-sky-light)',
          rowClass: 'type-selection',
          title: 'Chọn ô / Vùng dữ liệu',
        };
      case 'CELL_VALUE_CHANGE':
        return {
          icon: <Edit3 size={16} />,
          color: 'var(--primary)',
          bg: 'var(--primary-light)',
          rowClass: 'type-value',
          title: 'Nhập giá trị vào ô',
        };
      case 'FORMULA_ENTRY':
        return {
          icon: <Code2 size={16} />,
          color: 'var(--accent-indigo)',
          bg: 'var(--accent-indigo-light)',
          rowClass: 'type-formula',
          title: 'Gõ công thức hàm',
        };
      case 'MOUSE_HESITATION_START':
      case 'MOUSE_HESITATION_END':
        return {
          icon: <Clock size={16} />,
          color: 'var(--accent-amber)',
          bg: 'var(--accent-amber-light)',
          rowClass: 'type-hesitation',
          title: 'Dừng thao tác (Ngập ngừng)',
        };
      case 'WORKBOOK_OPEN':
        return {
          icon: <FileSpreadsheet size={16} />,
          color: '#059669',
          bg: '#ecfdf5',
          rowClass: 'type-value',
          title: 'Mở file Excel',
        };
      case 'ERRATIC_MOUSE_MOVEMENT':
        return {
          icon: <AlertTriangle size={16} />,
          color: 'var(--accent-rose)',
          bg: 'var(--accent-rose-light)',
          rowClass: 'type-error',
          title: 'Di chuột bối rối',
        };
      default:
        return {
          icon: <HelpCircle size={16} />,
          color: 'var(--text-muted)',
          bg: '#f1f5f9',
          rowClass: '',
          title: type,
        };
    }
  };

  const toggleExpand = (id) => {
    setExpandedEventId(expandedEventId === id ? null : id);
  };

  return (
    <div className="panel-card">
      <div className="panel-header">
        <div className="panel-title">
          <Clock size={18} style={{ color: 'var(--primary)' }} />
          <span>Dòng thao tác trực tiếp (Live Telemetry Stream) - {events.length} sự kiện</span>
        </div>
      </div>

      {/* Filter Chips */}
      <div className="filter-bar">
        {filters.map((f) => (
          <button
            key={f.key}
            className={`filter-chip ${activeFilter === f.key ? 'active' : ''}`}
            onClick={() => onFilterChange(f.key)}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* Events Timeline */}
      <div className="timeline-stream">
        {events.length === 0 ? (
          <div style={{ padding: '36px', textAlign: 'center', color: 'var(--text-muted)' }}>
            Chưa có sự kiện nào cho phiên này hoặc chưa khớp bộ lọc.
          </div>
        ) : (
          events.map((evt) => {
            const meta = getEventBadgeMeta(evt.event_type);
            const isExpanded = expandedEventId === evt.id;
            const isLatest = evt.id === latestEventId;
            
            let timeStr = 'N/A';
            try {
              if (evt.iso_time) {
                timeStr = evt.iso_time.split('T')[1]?.substring(0, 8);
              } else if (typeof evt.timestamp === 'number') {
                const ms = evt.timestamp > 1e11 ? evt.timestamp : evt.timestamp * 1000;
                timeStr = new Date(ms).toLocaleTimeString();
              } else if (typeof evt.timestamp === 'string') {
                timeStr = new Date(evt.timestamp).toLocaleTimeString();
              }
            } catch (e) {
              timeStr = 'N/A';
            }

            // Trích xuất an toàn metadata
            let metaData = evt.metadata;
            if (typeof metaData === 'string') {
              try { metaData = JSON.parse(metaData); } catch (e) { metaData = {}; }
            }
            metaData = metaData || {};

            let previewText = '';
            if (metaData.formula) previewText = `Công thức: ${metaData.formula}`;
            else if (metaData.value !== undefined) previewText = `Giá trị: ${metaData.value}`;
            else if (metaData.workbook || metaData.workbook_name) previewText = `File: ${metaData.workbook || metaData.workbook_name}`;
            else if (metaData.hesitation_duration_sec) previewText = `Dừng: ${Number(metaData.hesitation_duration_sec).toFixed(1)}s`;
            else if (metaData.idle_duration) previewText = `Dừng: ${Number(metaData.idle_duration).toFixed(1)}s`;

            return (
              <div key={evt.id} className={`event-row ${meta.rowClass} ${isLatest ? 'new-realtime-event' : ''}`}>
                <div
                  className="event-icon-badge"
                  style={{ background: meta.bg, color: meta.color }}
                >
                  {meta.icon}
                </div>

                <div className="event-content-body">
                  <div className="event-headline">
                    <div className="event-type-title">
                      <span>{meta.title}</span>
                      {evt.cell && <span className="event-cell-tag">[{evt.cell}]</span>}
                    </div>
                    <span className="event-time">{timeStr}</span>
                  </div>

                  <div style={{ fontSize: '0.82rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <span>
                      {previewText ? (
                        <strong style={{ color: 'var(--text-main)', fontFamily: 'var(--font-mono)' }}>{previewText}</strong>
                      ) : (
                        <code>{evt.event_type}</code>
                      )}
                    </span>
                    <button
                      onClick={() => toggleExpand(evt.id)}
                      style={{
                        background: 'transparent',
                        border: 'none',
                        color: 'var(--text-muted)',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '2px',
                        fontSize: '0.75rem',
                        fontWeight: 600,
                      }}
                    >
                      {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                      {isExpanded ? 'Ẩn chi tiết' : 'Chi tiết'}
                    </button>
                  </div>

                  {isExpanded && evt.metadata && (
                    <pre className="event-meta-json">
                      {typeof evt.metadata === 'object'
                        ? JSON.stringify(evt.metadata, null, 2)
                        : evt.metadata}
                    </pre>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
