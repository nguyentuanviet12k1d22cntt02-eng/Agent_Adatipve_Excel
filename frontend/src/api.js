/**
 * API Service: Kết nối tới FastAPI Backend (http://localhost:8000)
 * Giao tiếp trực tiếp với cơ sở dữ liệu MySQL (excel_adaptive_tutor)
 */

const API_BASE_URL = 'http://localhost:8000/api';

export async function fetchHealth() {
  const res = await fetch(`${API_BASE_URL}/health`);
  if (!res.ok) throw new Error('Không thể kết nối máy chủ API');
  return res.json();
}

export async function fetchStats() {
  const res = await fetch(`${API_BASE_URL}/stats`);
  if (!res.ok) throw new Error('Lỗi tải thống kê');
  return res.json();
}

export async function fetchSessions() {
  const res = await fetch(`${API_BASE_URL}/sessions`);
  if (!res.ok) throw new Error('Lỗi tải danh sách phiên học');
  return res.json();
}

export async function fetchSessionDetail(sessionId) {
  const res = await fetch(`${API_BASE_URL}/sessions/${sessionId}`);
  if (!res.ok) throw new Error('Lỗi tải chi tiết phiên học');
  return res.json();
}

export async function fetchSessionEvents(sessionId, eventType = null) {
  let url = `${API_BASE_URL}/sessions/${sessionId}/events?limit=300`;
  if (eventType && eventType !== 'ALL') {
    url += `&event_type=${encodeURIComponent(eventType)}`;
  }
  const res = await fetch(url);
  if (!res.ok) throw new Error('Lỗi tải dòng sự kiện');
  return res.json();
}

export async function fetchSessionFeatures(sessionId) {
  const res = await fetch(`${API_BASE_URL}/sessions/${sessionId}/features`);
  if (!res.ok) throw new Error('Lỗi tải vector đặc trưng');
  return res.json();
}

export async function fetchSessionPredictions(sessionId) {
  const res = await fetch(`${API_BASE_URL}/sessions/${sessionId}/predictions`);
  if (!res.ok) throw new Error('Lỗi tải dự đoán nhận thức');
  return res.json();
}

export async function fetchSessionFeedback(sessionId) {
  const res = await fetch(`${API_BASE_URL}/sessions/${sessionId}/feedback`);
  if (!res.ok) throw new Error('Lỗi tải phản hồi thích ứng');
  return res.json();
}

export async function simulateEvent(sessionId, eventType, cell = 'C5', stepIndex = 1, metadata = {}) {
  const res = await fetch(`${API_BASE_URL}/sessions/${sessionId}/simulate-event`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      event_type: eventType,
      cell,
      step_index: stepIndex,
      metadata,
    }),
  });
  if (!res.ok) throw new Error('Lỗi gửi sự kiện mô phỏng');
  return res.json();
}
