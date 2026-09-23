import React, { useState } from 'react';
import { Play, Sparkles, Clock, AlertCircle, Edit3, MousePointer, CheckCircle } from 'lucide-react';
import { simulateEvent } from '../api';

export default function LiveSimulator({ sessionId, onEventSimulated }) {
  const [loading, setLoading] = useState(false);
  const [toast, setToast] = useState(null);

  const handleSimulate = async (type, cell, step, metadata) => {
    if (!sessionId) return;
    setLoading(true);
    try {
      const res = await simulateEvent(sessionId, type, cell, step, metadata);
      setToast({
        type: 'success',
        msg: `Đã ghi nhận sự kiện ${type} vào MySQL thành công!`,
      });
      setTimeout(() => setToast(null), 3500);
      if (onEventSimulated) {
        onEventSimulated();
      }
    } catch (err) {
      setToast({
        type: 'error',
        msg: `Lỗi mô phỏng: ${err.message}`,
      });
      setTimeout(() => setToast(null), 4000);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ marginBottom: '16px' }}>
      <div className="sim-toolbar">
        <div className="sim-toolbar-title">
          <Sparkles size={16} />
          <span>Mô phỏng phát sự kiện Telemetry trực tiếp vào MySQL:</span>
        </div>

        <button
          className="btn-action btn-amber"
          style={{ padding: '6px 12px', fontSize: '0.78rem' }}
          disabled={loading || !sessionId}
          onClick={() =>
            handleSimulate('MOUSE_HESITATION_START', 'D5', 2, {
              hesitation_duration_sec: 4.8,
              status: 'PROLONGED_IDLE',
              mouse_coords: [540, 380],
            })
          }
          title="Ghi nhận sự kiện học viên dừng chuột 4.8s suy nghĩ vào MySQL"
        >
          <Clock size={14} /> Ngập ngừng 4.8s
        </button>

        <button
          className="btn-action btn-secondary"
          style={{ padding: '6px 12px', fontSize: '0.78rem', color: 'var(--accent-rose)' }}
          disabled={loading || !sessionId}
          onClick={() =>
            handleSimulate('FORMULA_ENTRY', 'E5', 2, {
              formula: '=VLOOKUP(A5, DanhMuc!A1:B10, 5, 0)',
              error_type: '#REF!',
              is_valid: false,
            })
          }
          title="Ghi nhận lỗi gõ sai chỉ số cột VLOOKUP vào MySQL"
        >
          <AlertCircle size={14} /> Lỗi công thức (#REF!)
        </button>

        <button
          className="btn-action btn-secondary"
          style={{ padding: '6px 12px', fontSize: '0.78rem', color: 'var(--accent-cyan)' }}
          disabled={loading || !sessionId}
          onClick={() =>
            handleSimulate('CELL_SELECTION', 'C5', 2, {
              previous_cell: 'B5',
              range_address: 'C5:C5',
            })
          }
          title="Ghi nhận di chuyển chuột chọn ô C5"
        >
          <MousePointer size={14} /> Chọn ô C5
        </button>

        <button
          className="btn-action btn-secondary"
          style={{ padding: '6px 12px', fontSize: '0.78rem', color: 'var(--primary)' }}
          disabled={loading || !sessionId}
          onClick={() =>
            handleSimulate('CELL_VALUE_CHANGE', 'C5', 2, {
              old_value: '',
              new_value: '1500000',
              data_type: 'number',
            })
          }
          title="Ghi nhận gõ giá trị 1500000 vào ô C5"
        >
          <Edit3 size={14} /> Nhập số 1,500,000
        </button>
      </div>

      {toast && (
        <div
          style={{
            padding: '8px 16px',
            borderRadius: '6px',
            fontSize: '0.8rem',
            background: toast.type === 'success' ? 'rgba(16, 185, 129, 0.2)' : 'rgba(244, 63, 94, 0.2)',
            color: toast.type === 'success' ? 'var(--primary)' : 'var(--accent-rose)',
            border: `1px solid ${toast.type === 'success' ? 'var(--border-highlight)' : 'var(--border-rose)'}`,
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
          }}
        >
          <CheckCircle size={15} />
          <span>{toast.msg}</span>
        </div>
      )}
    </div>
  );
}
