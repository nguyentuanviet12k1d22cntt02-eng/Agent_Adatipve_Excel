import React, { useState } from 'react';
import { 
  MousePointer, 
  Edit3, 
  HelpCircle, 
  Clock, 
  Code2, 
  FileSpreadsheet,
  ChevronRight, 
  ChevronDown,
  Wrench,
  Layers
} from 'lucide-react';

export default function TimelineStream({ events, activeFilter, onFilterChange, latestEventId }) {
  const [expandedEventId, setExpandedEventId] = useState(null);

  const filters = [
    { key: 'ALL', label: 'Tất cả thao tác' },
    { key: 'CELL_SELECTION', label: '🎯 Địa chỉ ô (Cells)' },
    { key: 'EXCEL_TOOL_USED', label: '🛠️ Công cụ Excel (Tools)' },
    { key: 'FORMULA_ENTRY', label: '⚡ Gõ công thức (Formula)' },
    { key: 'CELL_VALUE_CHANGE', label: '✍️ Nhập dữ liệu (Value)' },
    { key: 'STUDENT_PAUSE', label: '⏱️ Tạm dừng suy nghĩ' },
    { key: 'WORKBOOK_OPEN', label: '📂 Mở file / Sheet' },
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
          title: 'Chọn địa chỉ ô',
        };
      case 'EXCEL_TOOL_USED':
        return {
          icon: <Wrench size={16} />,
          color: '#9333ea',
          bg: '#faf5ff',
          rowClass: 'type-tool',
          title: 'Công cụ Excel đã dùng',
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
      case 'STUDENT_PAUSE':
      case 'MOUSE_HESITATION_START':
      case 'MOUSE_HESITATION_END':
        return {
          icon: <Clock size={16} />,
          color: 'var(--accent-amber)',
          bg: 'var(--accent-amber-light)',
          rowClass: 'type-hesitation',
          title: 'Tạm dừng suy nghĩ tại ô',
        };
      case 'WORKBOOK_OPEN':
        return {
          icon: <FileSpreadsheet size={16} />,
          color: '#059669',
          bg: '#ecfdf5',
          rowClass: 'type-value',
          title: 'Mở file Excel',
        };
      case 'SHEET_ACTIVATE':
        return {
          icon: <Layers size={16} />,
          color: '#0284c7',
          bg: '#f0f9ff',
          rowClass: 'type-selection',
          title: 'Chuyển đổi Sheet',
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
          <span>Lịch sử thao tác thực hành Excel ({events.length} sự kiện)</span>
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
            Chưa có thao tác nào khớp với bộ lọc hiện tại.
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
            if (evt.event_type === 'CELL_VALUE_CHANGE') {
              previewText = metaData.value !== undefined && metaData.value !== ''
                ? `Nhập nội dung: "${metaData.value}"`
                : 'Xóa nội dung ô';
            } else if (evt.event_type === 'FORMULA_ENTRY') {
              previewText = `Công thức: ${metaData.formula || metaData.raw || ''}`;
            } else if (evt.event_type === 'EXCEL_TOOL_USED') {
              previewText = `Công cụ: ${metaData.tool_name || metaData.tool || 'Định dạng'}`;
            } else if (evt.event_type === 'CELL_SELECTION' || evt.event_type === 'RANGE_SELECTION') {
              previewText = `Vị trí ô: [${evt.cell || metaData.cell || ''}]`;
            } else if (evt.event_type === 'STUDENT_PAUSE') {
              previewText = `Dừng suy nghĩ: ${Number(metaData.pause_duration_sec || 0).toFixed(1)}s`;
            } else if (evt.event_type === 'WORKBOOK_OPEN') {
              previewText = `Mở bảng tính: ${metaData.workbook_name || metaData.workbook || ''}`;
            } else if (evt.event_type === 'SHEET_ACTIVATE') {
              previewText = `Sheet: ${metaData.sheet || ''}`;
            } else if (metaData.tool_name || metaData.tool) {
              previewText = `Công cụ: ${metaData.tool_name || metaData.tool}`;
            }

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
                      {evt.cell && (
                        <span className="event-cell-tag" style={{ background: '#e0f2fe', color: '#0369a1', fontWeight: 800 }}>
                          [{evt.cell}]
                        </span>
                      )}
                    </div>
                    <span className="event-time">{timeStr}</span>
                  </div>

                  <div style={{ fontSize: '0.84rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
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

                  {/* Chi tiết Payload JSON mở rộng */}
                  {isExpanded && (
                    <div className="event-meta-json">
                      <pre>{JSON.stringify(metaData, null, 2)}</pre>
                    </div>
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
