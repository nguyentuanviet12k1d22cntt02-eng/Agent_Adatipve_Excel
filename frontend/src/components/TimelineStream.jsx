import React, { useState } from 'react';
import { 
  MousePointer, 
  Edit3, 
  HelpCircle, 
  CheckCircle2, 
  AlertTriangle, 
  Clock, 
  Code2, 
  ChevronRight, 
  ChevronDown 
} from 'lucide-react';

export default function TimelineStream({ events, activeFilter, onFilterChange }) {
  const [expandedEventId, setExpandedEventId] = useState(null);

  const filters = [
    { key: 'ALL', label: 'Tất cả sự kiện' },
    { key: 'CELL_SELECTION', label: 'Chọn ô (Selection)' },
    { key: 'CELL_VALUE_CHANGE', label: 'Nhập dữ liệu (Value)' },
    { key: 'FORMULA_ENTRY', label: 'Công thức (Formula)' },
    { key: 'MOUSE_HESITATION_START', label: 'Ngập ngừng chuột (Hesitation)' },
    { key: 'ERRATIC_MOUSE_MOVEMENT', label: 'Di chuột hỗn loạn (Erratic)' },
  ];

  const getEventBadgeMeta = (type) => {
    switch (type) {
      case 'CELL_SELECTION':
      case 'RANGE_SELECTION':
        return {
          icon: <MousePointer size={16} />,
          color: 'var(--accent-cyan)',
          bg: 'rgba(6, 182, 212, 0.15)',
          title: 'Chọn ô / Vùng dữ liệu',
        };
      case 'CELL_VALUE_CHANGE':
        return {
          icon: <Edit3 size={16} />,
          color: 'var(--primary)',
          bg: 'rgba(16, 185, 129, 0.15)',
          title: 'Thay đổi giá trị ô',
        };
      case 'FORMULA_ENTRY':
        return {
          icon: <Code2 size={16} />,
          color: 'var(--accent-indigo)',
          bg: 'rgba(99, 102, 241, 0.15)',
          title: 'Nhập công thức hàm Excel',
        };
      case 'MOUSE_HESITATION_START':
      case 'MOUSE_HESITATION_END':
        return {
          icon: <Clock size={16} />,
          color: 'var(--accent-amber)',
          bg: 'rgba(245, 158, 11, 0.15)',
          title: 'Phát hiện ngập ngừng / Dừng thao tác',
        };
      case 'ERRATIC_MOUSE_MOVEMENT':
        return {
          icon: <AlertTriangle size={16} />,
          color: 'var(--accent-rose)',
          bg: 'rgba(244, 63, 94, 0.15)',
          title: 'Di chuột bất thường / Bối rối',
        };
      case 'STEP_STARTED':
      case 'STEP_FINISHED':
        return {
          icon: <CheckCircle2 size={16} />,
          color: '#38bdf8',
          bg: 'rgba(56, 189, 248, 0.15)',
          title: 'Tiến độ bước thực hành',
        };
      default:
        return {
          icon: <HelpCircle size={16} />,
          color: 'var(--text-muted)',
          bg: 'rgba(255, 255, 255, 0.08)',
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
          <Clock size={18} style={{ color: 'var(--accent-cyan)' }} />
          <span>Dòng sự kiện tương tác thời gian thực (Telemetry Stream) - {events.length} sự kiện</span>
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
          <div style={{ padding: '32px', textAlign: 'center', color: 'var(--text-muted)' }}>
            Không có sự kiện nào khớp với bộ lọc hiện tại.
          </div>
        ) : (
          events.map((evt) => {
            const meta = getEventBadgeMeta(evt.event_type);
            const isExpanded = expandedEventId === evt.id;
            const timeStr = evt.iso_time 
              ? evt.iso_time.split('T')[1]?.substring(0, 8) 
              : new Date(evt.timestamp * 1000).toLocaleTimeString();

            return (
              <div key={evt.id} className="event-row">
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
                      {evt.step_index !== undefined && (
                        <span style={{ fontSize: '0.72rem', color: 'var(--text-subtle)' }}>
                          Bước {evt.step_index}
                        </span>
                      )}
                    </div>
                    <span className="event-time">{timeStr}</span>
                  </div>

                  <div style={{ fontSize: '0.8rem', color: '#cbd5e1', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <span>
                      Sự kiện: <code style={{ color: meta.color }}>{evt.event_type}</code>
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
                        fontSize: '0.72rem',
                      }}
                    >
                      {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                      {isExpanded ? 'Ẩn Metadata' : 'Xem chi tiết'}
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
