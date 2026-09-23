import React, { useState } from 'react';
import { Play, Sparkles, Clock, AlertCircle, Edit3, MousePointer, CheckCircle, Radio, Wrench, Palette, Type } from 'lucide-react';
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
        // Local MySQL sync
      }

      setToast({
        type: 'success',
        msg: `⚡ Đã phát sự kiện [${type}] vào Supabase: ${metadata.tool_name || metadata.formula || metadata.value || cell}!`,
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
          <span>Mô phỏng thao tác Excel (Địa chỉ ô & Công cụ):</span>
        </div>

        {/* 1. Chọn ô J10 */}
        <button
          className="btn-action btn-secondary"
          style={{ padding: '6px 12px', fontSize: '0.78rem', color: 'var(--accent-sky)' }}
          disabled={loading || !sessionId}
          onClick={() =>
            handleSimulate('CELL_SELECTION', 'J10', 1, {
              sheet: 'Sheet1',
              tool: 'Select Cell',
            })
          }
          title="Chọn ô J10 trong bảng tính"
        >
          <MousePointer size={14} /> Chọn ô J10
        </button>

        {/* 2. Nhập 'xin chào' vào ô C9 */}
        <button
          className="btn-action btn-secondary"
          style={{ padding: '6px 12px', fontSize: '0.78rem', color: 'var(--primary)' }}
          disabled={loading || !sessionId}
          onClick={() =>
            handleSimulate('CELL_VALUE_CHANGE', 'C9', 1, {
              sheet: 'Sheet1',
              value: 'xin chào',
              tool: 'Edit Cell',
            })
          }
          title="Nhập giá trị 'xin chào' vào ô C9"
        >
          <Edit3 size={14} /> Nhập "xin chào" (C9)
        </button>

        {/* 3. Gõ hàm =IF(...) */}
        <button
          className="btn-action btn-secondary"
          style={{ padding: '6px 12px', fontSize: '0.78rem', color: 'var(--accent-indigo)' }}
          disabled={loading || !sessionId}
          onClick={() =>
            handleSimulate('FORMULA_ENTRY', 'D9', 1, {
              sheet: 'Sheet1',
              formula: '=IF(C8<5, "Trực nhật", "Thưởng 1 cuốn vở")',
              has_error: false,
              tool: 'Formula Bar',
            })
          }
          title="Gõ hàm =IF(...) tại ô D9"
        >
          <Sparkles size={14} /> Gõ hàm =IF(...) (D9)
        </button>

        {/* 4. Dùng công cụ: Tô màu nền vàng */}
        <button
          className="btn-action btn-secondary"
          style={{ padding: '6px 12px', fontSize: '0.78rem', color: '#9333ea' }}
          disabled={loading || !sessionId}
          onClick={() =>
            handleSimulate('EXCEL_TOOL_USED', 'C9', 1, {
              sheet: 'Sheet1',
              tool_name: 'Tô màu nền (Fill Color)',
              tool: 'Tô màu nền (Fill Color)',
              color: '#FFFF00',
            })
          }
          title="Sử dụng công cụ Tô màu vàng cho ô C9"
        >
          <Palette size={14} /> Tô màu nền ô (C9)
        </button>

        {/* 5. Dùng công cụ: Đổi Font Times New Roman */}
        <button
          className="btn-action btn-secondary"
          style={{ padding: '6px 12px', fontSize: '0.78rem', color: '#0284c7' }}
          disabled={loading || !sessionId}
          onClick={() =>
            handleSimulate('EXCEL_TOOL_USED', 'J10', 1, {
              sheet: 'Sheet1',
              tool_name: 'Đổi Font: Times New Roman 12pt',
              tool: 'Đổi Font: Times New Roman 12pt',
              font_size: 12,
            })
          }
          title="Sử dụng công cụ đổi phông chữ Times New Roman"
        >
          <Type size={14} /> Đổi Font Times New Roman
        </button>

        {/* 6. Tạm dừng suy nghĩ */}
        <button
          className="btn-action btn-amber"
          style={{ padding: '6px 12px', fontSize: '0.78rem' }}
          disabled={loading || !sessionId}
          onClick={() =>
            handleSimulate('STUDENT_PAUSE', 'J10', 1, {
              sheet: 'Sheet1',
              pause_duration_sec: 12.5,
              tool: 'Student Pause',
            })
          }
          title="Tạm dừng suy nghĩ 12.5 giây tại ô J10"
        >
          <Clock size={14} /> Dừng suy nghĩ 12.5s (J10)
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
