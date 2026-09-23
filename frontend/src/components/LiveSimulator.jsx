import React, { useState } from 'react';
import { Play, Sparkles, Clock, AlertCircle, Edit3, MousePointer, CheckCircle, Radio } from 'lucide-react';
import { simulateEvent } from '../api';
import { insertEventToSupabase } from '../supabase';

export default function LiveSimulator({ sessionId, onEventSimulated }) {
  const [loading, setLoading] = useState(false);
  const [toast, setToast] = useState(null);

  const handleSimulate = async (type, cell, step, metadata) => {
    if (!sessionId) return;
    setLoading(true);
    try {
      // 1. Ghi trực tiếp vào Supabase Cloud để kích hoạt WebSocket Realtime
      await insertEventToSupabase({
        session_id: sessionId,
        event_type: type,
        cell: cell,
        step_index: step,
        metadata: metadata,
      });

      // 2. Đồng thời ghi vào MySQL (nếu API local đang chạy)
      try {
        await simulateEvent(sessionId, type, cell, step, metadata);
      } catch (e) {
        console.warn('MySQL Local sync skipped:', e.message);
      }

      setToast({
        type: 'success',
        msg: `⚡ Đã phát sự kiện [${type}] vào Supabase Realtime!`,
      });
      setTimeout(() => setToast(null), 3000);
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
    <div style={{ marginBottom: '20px' }}>
      <div className="sim-toolbar">
        <div className="sim-toolbar-title">
          <Radio size={16} className="text-emerald-600 animate-pulse" />
          <span>Mô phỏng phát sự kiện Telemetry (Supabase Realtime):</span>
        </div>

        <button
          className="btn-action btn-amber"
          style={{ padding: '6px 14px', fontSize: '0.8rem' }}
          disabled={loading || !sessionId}
          onClick={() =>
            handleSimulate('MOUSE_HESITATION_START', 'D5', 2, {
              hesitation_duration_sec: 4.8,
              status: 'PROLONGED_IDLE',
              mouse_coords: [540, 380],
            })
          }
          title="Ghi nhận sự kiện học viên dừng chuột 4.8s suy nghĩ vào Supabase"
        >
          <Clock size={14} /> Ngập ngừng 4.8s (D5)
        </button>

        <button
          className="btn-action btn-secondary"
          style={{ padding: '6px 14px', fontSize: '0.8rem', color: 'var(--accent-rose)' }}
          disabled={loading || !sessionId}
          onClick={() =>
            handleSimulate('FORMULA_ENTRY', 'E5', 2, {
              formula: '=VLOOKUP(A5, DanhMuc!A1:B10, 5, 0)',
              error_type: '#REF!',
              is_valid: false,
            })
          }
          title="Ghi nhận lỗi gõ sai chỉ số cột VLOOKUP vào Supabase"
        >
          <AlertCircle size={14} /> Lỗi công thức (#REF!)
        </button>

        <button
          className="btn-action btn-secondary"
          style={{ padding: '6px 14px', fontSize: '0.8rem', color: 'var(--accent-sky)' }}
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
          style={{ padding: '6px 14px', fontSize: '0.8rem', color: 'var(--primary)' }}
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
            padding: '10px 16px',
            borderRadius: '8px',
            fontSize: '0.82rem',
            background: toast.type === 'success' ? '#ecfdf5' : '#fff1f2',
            color: toast.type === 'success' ? '#065f46' : '#9f1239',
            border: `1px solid ${toast.type === 'success' ? '#a7f3d0' : '#fecdd3'}`,
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            fontWeight: 500,
          }}
        >
          <CheckCircle size={16} />
          <span>{toast.msg}</span>
        </div>
      )}
    </div>
  );
}
