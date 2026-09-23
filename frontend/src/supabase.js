/**
 * Supabase Client & Realtime Service
 * Kết nối trực tiếp tới Supabase Cloud để nhận dữ liệu thao tác Excel theo thời gian thực (WebSockets)
 */

import { createClient } from '@supabase/supabase-js';

export const SUPABASE_URL = 'https://cxjhnsvzacqlfbpcnkrh.supabase.co';
export const SUPABASE_ANON_KEY = 'sb_publishable_F_v1G9WDNfWUyL61P5j1HA_iB5pdERf';

export const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
  realtime: {
    params: {
      eventsPerSecond: 20,
    },
  },
});

// 1. Tải danh sách Học viên
export async function getStudentsFromSupabase() {
  const { data, error } = await supabase
    .from('students')
    .select('*')
    .order('created_at', { ascending: false });
  if (error) throw error;
  return data || [];
}

// 2. Tải danh sách Phiên thực hành (kèm đếm số events)
export async function getSessionsFromSupabase() {
  const { data: sessions, error } = await supabase
    .from('sessions')
    .select(`
      session_id,
      student_id,
      lesson_id,
      started_at,
      ended_at,
      status,
      total_steps,
      completed_steps,
      students (
        name,
        email
      )
    `)
    .order('started_at', { ascending: false });

  if (error) throw error;

  // Lấy thêm số lượng events cho mỗi session
  const { data: eventCounts } = await supabase
    .from('events')
    .select('session_id');

  const countMap = {};
  if (eventCounts) {
    eventCounts.forEach(e => {
      countMap[e.session_id] = (countMap[e.session_id] || 0) + 1;
    });
  }

  return (sessions || []).map(s => ({
    ...s,
    student_name: s.students?.name || s.student_id,
    student_email: s.students?.email || '',
    event_count: countMap[s.session_id] || 0,
  }));
}

// 3. Tải danh sách Sự kiện của một phiên
export async function getSessionEventsFromSupabase(sessionId, eventType = null) {
  let query = supabase
    .from('events')
    .select('*')
    .eq('session_id', sessionId)
    .order('id', { ascending: false })
    .limit(200);

  if (eventType && eventType !== 'ALL') {
    query = query.eq('event_type', eventType);
  }

  const { data, error } = await query;
  if (error) throw error;
  return data || [];
}

// 4. Tải Features của session
export async function getSessionFeaturesFromSupabase(sessionId) {
  const { data, error } = await supabase
    .from('features')
    .select('*')
    .eq('session_id', sessionId)
    .order('step_index', { ascending: true });
  if (error) return [];
  return data || [];
}

// 5. Tải Predictions của session
export async function getSessionPredictionsFromSupabase(sessionId) {
  const { data, error } = await supabase
    .from('predictions')
    .select('*')
    .eq('session_id', sessionId)
    .order('timestamp', { ascending: true });
  if (error) return [];
  return data || [];
}

// 6. Tải Feedback của session
export async function getSessionFeedbackFromSupabase(sessionId) {
  const { data, error } = await supabase
    .from('feedback')
    .select('*')
    .eq('session_id', sessionId)
    .order('created_at', { ascending: false });
  if (error) return [];
  return data || [];
}

// 7. Tải tổng hợp chỉ số thống kê (Stats)
export async function getStatsFromSupabase() {
  const [studentsRes, sessionsRes, eventsRes] = await Promise.all([
    supabase.from('students').select('*', { count: 'exact', head: true }),
    supabase.from('sessions').select('*'),
    supabase.from('events').select('event_type, metadata'),
  ]);

  const sessions = sessionsRes.data || [];
  const events = eventsRes.data || [];

  const activeSessions = sessions.filter(s => s.status === 'IN_PROGRESS').length;
  const completedSessions = sessions.filter(s => s.status === 'COMPLETED').length;

  const hesitationEvents = events.filter(e => 
    e.event_type.includes('HESITATION') || e.event_type.includes('ERRATIC')
  ).length;

  const formulaErrors = events.filter(e => {
    const meta = typeof e.metadata === 'object' ? JSON.stringify(e.metadata) : (e.metadata || '');
    return e.event_type === 'FORMULA_ENTRY' && (meta.includes('error') || meta.includes('#'));
  }).length;

  return {
    total_students: studentsRes.count || 0,
    total_sessions: sessions.length,
    total_events: events.length,
    active_sessions: activeSessions,
    completed_sessions: completedSessions,
    hesitation_events: hesitationEvents,
    formula_errors: formulaErrors,
  };
}

// 8. Chèn sự kiện mới trực tiếp vào Supabase (dùng cho Live Simulator & Đồng bộ)
export async function insertEventToSupabase({ session_id, event_type, cell, step_index, metadata }) {
  const { data, error } = await supabase
    .from('events')
    .insert([{
      session_id,
      event_type,
      cell: cell || 'C5',
      step_index: step_index || 1,
      metadata: metadata || {},
      timestamp: new Date().toISOString(),
    }])
    .select();
  if (error) throw error;
  return data ? data[0] : null;
}

// 9. Format mô tả hành vi người học trực quan, sinh động
export function formatActionDescription(event) {
  if (!event) return 'Đang chờ thao tác...';

  const cell = event.cell ? `[ ${event.cell} ]` : '';
  let meta = event.metadata;
  if (typeof meta === 'string') {
    try { meta = JSON.parse(meta); } catch (e) { meta = {}; }
  }
  meta = meta || {};

  switch (event.event_type) {
    case 'CELL_SELECTION':
      return `Đã chọn ô ${cell}`;
    case 'RANGE_SELECTION':
      return `Đã bôi đen vùng ô ${cell}`;
    case 'CELL_VALUE_CHANGE':
      return `Nhập giá trị: "${meta.value !== undefined ? meta.value : '...'}" vào ô ${cell}`;
    case 'FORMULA_ENTRY':
      return `Gõ công thức hàm: ${meta.formula || meta.raw || '=...'} tại ô ${cell}`;
    case 'MOUSE_HESITATION_START':
      return `Tạm dừng ngập ngừng chuột ${meta.hesitation_duration_sec ? meta.hesitation_duration_sec + 's' : ''} tại ô ${cell}`;
    case 'MOUSE_HESITATION_END':
      return `Đã tiếp tục thao tác tại ô ${cell}`;
    case 'WORKBOOK_OPEN':
      return `Mở file Excel: ${meta.workbook || meta.file || 'Bảng tính'}`;
    case 'ERRATIC_MOUSE':
      return `Di chuyển chuột hỗn loạn / bối rối quanh ô ${cell}`;
    default:
      return `${event.event_type} tại ô ${cell}`;
  }
}
