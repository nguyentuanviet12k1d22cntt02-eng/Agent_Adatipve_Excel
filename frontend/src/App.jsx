import React, { useState, useEffect, useCallback, useRef } from 'react';
import './styles/theme.css';
import './styles/dashboard.css';

import {
  supabase,
  getSessionsFromSupabase,
  getSessionEventsFromSupabase,
  getSessionFeaturesFromSupabase,
  getSessionPredictionsFromSupabase,
  getSessionFeedbackFromSupabase,
  getStatsFromSupabase,
  formatActionDescription,
} from './supabase';

import Header from './components/Header';
import KpiMetrics from './components/KpiMetrics';
import ExcelRadar from './components/ExcelRadar';
import LiveSimulator from './components/LiveSimulator';
import SessionList from './components/SessionList';
import SessionHero from './components/SessionHero';
import TimelineStream from './components/TimelineStream';
import FeatureViewer from './components/FeatureViewer';
import CognitiveAiTab from './components/CognitiveAiTab';

import { Clock, Activity, BrainCircuit } from 'lucide-react';

export default function App() {
  // Realtime & System State
  const [isRealtimeConnected, setIsRealtimeConnected] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [stats, setStats] = useState(null);
  const [sessions, setSessions] = useState([]);
  const [selectedSessionId, setSelectedSessionId] = useState(null);
  const [selectedSession, setSelectedSession] = useState(null);

  // Active Session Details
  const [events, setEvents] = useState([]);
  const [features, setFeatures] = useState([]);
  const [predictions, setPredictions] = useState([]);
  const [feedback, setFeedback] = useState([]);

  // Radar Live State (Thao tác Excel thời gian thực)
  const [activeCell, setActiveCell] = useState('J10');
  const [activeTool, setActiveTool] = useState('Chọn ô');
  const [activeStudent, setActiveStudent] = useState('Đang chờ...');
  const [activeWorkbook, setActiveWorkbook] = useState('Chưa mở file');
  const [activeSheet, setActiveSheet] = useState('Sheet1');
  const [lastAction, setLastAction] = useState('Hệ thống sẵn sàng lắng nghe thao tác Excel...');
  const [latestEventId, setLatestEventId] = useState(null);

  // Tab & Filters
  const [activeFilter, setActiveFilter] = useState('ALL');
  const [activeTab, setActiveTab] = useState('timeline'); // 'timeline' | 'features' | 'cognitive'

  // Ref để truy cập selectedSessionId mới nhất bên trong WebSocket callback
  const selectedSessionIdRef = useRef(selectedSessionId);
  useEffect(() => {
    selectedSessionIdRef.current = selectedSessionId;
  }, [selectedSessionId]);

  // 1. Tải toàn bộ thống kê & danh sách phiên từ Supabase
  const loadOverview = useCallback(async () => {
    try {
      const [sData, sesList] = await Promise.all([
        getStatsFromSupabase(),
        getSessionsFromSupabase(),
      ]);
      setStats(sData);
      setSessions(sesList);

      // Nếu chưa chọn phiên nào hoặc phiên hiện tại không còn tồn tại -> chọn phiên mới nhất
      if (sesList.length > 0) {
        if (!selectedSessionIdRef.current || !sesList.some(s => s.session_id === selectedSessionIdRef.current)) {
          const first = sesList[0];
          setSelectedSessionId(first.session_id);
          setSelectedSession(first);
          setActiveStudent(first.student_name || first.student_id);
          setActiveWorkbook(first.lesson_id || 'Bảng tính Excel');
        }
      }
    } catch (err) {
      console.error('Lỗi tải tổng quan từ Supabase:', err);
    }
  }, []);

  // 2. Tải chi tiết phiên được chọn từ Supabase
  const loadSessionDetails = useCallback(async (sessionId, filter = activeFilter) => {
    if (!sessionId) return;
    try {
      const [evts, feats, preds, fbacks] = await Promise.all([
        getSessionEventsFromSupabase(sessionId, filter),
        getSessionFeaturesFromSupabase(sessionId),
        getSessionPredictionsFromSupabase(sessionId),
        getSessionFeedbackFromSupabase(sessionId),
      ]);
      setEvents(evts);
      setFeatures(feats);
      setPredictions(preds);
      setFeedback(fbacks);

      // Cập nhật Radar từ sự kiện gần nhất của session này
      if (evts.length > 0) {
        const newest = evts[0];
        if (newest.cell) setActiveCell(newest.cell);
        const desc = formatActionDescription(newest);
        setLastAction(`${desc} (${new Date(newest.timestamp || Date.now()).toLocaleTimeString()})`);

        let meta = newest.metadata;
        if (typeof meta === 'string') {
          try { meta = JSON.parse(meta); } catch (e) { meta = {}; }
        }
        meta = meta || {};
        if (meta.workbook) setActiveWorkbook(meta.workbook);
        if (meta.sheet) setActiveSheet(meta.sheet);
      }
    } catch (err) {
      console.error(`Lỗi tải chi tiết phiên ${sessionId}:`, err);
    }
  }, [activeFilter]);

  // Khởi động lần đầu
  useEffect(() => {
    loadOverview();
  }, [loadOverview]);

  // Khi selectedSessionId thay đổi
  useEffect(() => {
    if (selectedSessionId) {
      const found = sessions.find((s) => s.session_id === selectedSessionId);
      if (found) {
        setSelectedSession(found);
        setActiveStudent(found.student_name || found.student_id);
        setActiveWorkbook(found.lesson_id || 'Bảng tính');
      }
      loadSessionDetails(selectedSessionId, activeFilter);
    }
  }, [selectedSessionId, activeFilter, sessions, loadSessionDetails]);

  // 3. KẾT NỐI WEBSOCKET REALTIME TRỰC TIẾP VỚI SUPABASE
  useEffect(() => {
    console.log('📡 Đang kết nối Supabase Realtime WebSockets...');

    // Kênh nhận sự kiện thao tác Excel (events)
    const eventsChannel = supabase
      .channel('realtime:events-live')
      .on(
        'postgres_changes',
        { event: 'INSERT', schema: 'public', table: 'events' },
        (payload) => {
          const newEvt = payload.new;
          console.log('⚡ [SUPABASE REALTIME EVENT]:', newEvt);

          // Cập nhật Radar ngay lập tức
          setLatestEventId(newEvt.id);
          if (newEvt.cell) {
            setActiveCell(newEvt.cell);
          }

          const desc = formatActionDescription(newEvt);
          const timeString = new Date(newEvt.timestamp || Date.now()).toLocaleTimeString();
          setLastAction(`${desc} (${timeString})`);

          let meta = newEvt.metadata;
          if (typeof meta === 'string') {
            try { meta = JSON.parse(meta); } catch (e) { meta = {}; }
          }
          meta = meta || {};
          if (meta.workbook) setActiveWorkbook(meta.workbook);
          if (meta.sheet) setActiveSheet(meta.sheet);
          if (meta.student_name) setActiveStudent(meta.student_name);

          // Cập nhật công cụ hoặc nội dung đã dùng
          if (newEvt.event_type === 'EXCEL_TOOL_USED') {
            setActiveTool(meta.tool_name || meta.tool || 'Định dạng');
          } else if (newEvt.event_type === 'FORMULA_ENTRY') {
            setActiveTool(meta.formula ? `Hàm: ${meta.formula}` : 'Gõ công thức hàm');
          } else if (newEvt.event_type === 'CELL_VALUE_CHANGE') {
            setActiveTool(meta.value !== undefined && meta.value !== '' ? `Nhập: "${meta.value}"` : 'Nhập dữ liệu');
          } else if (newEvt.event_type === 'CELL_SELECTION') {
            setActiveTool('Chọn địa chỉ ô');
          } else if (newEvt.event_type === 'STUDENT_PAUSE') {
            setActiveTool('Tạm dừng suy nghĩ');
          }

          // Nếu sự kiện thuộc phiên đang xem -> Chèn vào đầu danh sách sự kiện
          if (newEvt.session_id === selectedSessionIdRef.current) {
            setEvents((prev) => [newEvt, ...prev.filter(e => e.id !== newEvt.id)]);
          }

          // Tăng KPI tổng số sự kiện
          setStats((prev) => {
            if (!prev) return prev;
            const isHesitation = (newEvt.event_type || '').includes('HESITATION') || (newEvt.event_type || '').includes('ERRATIC');
            const isFormulaErr = newEvt.event_type === 'FORMULA_ENTRY' && JSON.stringify(newEvt.metadata || '').includes('error');
            return {
              ...prev,
              total_events: (prev.total_events || 0) + 1,
              hesitation_events: isHesitation ? (prev.hesitation_events || 0) + 1 : prev.hesitation_events,
              formula_errors: isFormulaErr ? (prev.formula_errors || 0) + 1 : prev.formula_errors,
            };
          });
        }
      )
      .subscribe((status) => {
        console.log('Supabase Channel Status:', status);
        if (status === 'SUBSCRIBED') {
          setIsRealtimeConnected(true);
        } else if (status === 'CLOSED' || status === 'CHANNEL_ERROR') {
          setIsRealtimeConnected(false);
        }
      });

    // Kênh cập nhật phiên thực hành (sessions)
    const sessionsChannel = supabase
      .channel('realtime:sessions-live')
      .on(
        'postgres_changes',
        { event: '*', schema: 'public', table: 'sessions' },
        async (payload) => {
          console.log('⚡ [SUPABASE REALTIME SESSION UPDATE]:', payload);
          try {
            const updated = await getSessionsFromSupabase();
            setSessions(updated);
          } catch (e) {
            console.error('Lỗi làm mới sessions sau Realtime event:', e);
          }
        }
      )
      .subscribe();

    return () => {
      supabase.removeChannel(eventsChannel);
      supabase.removeChannel(sessionsChannel);
    };
  }, []);

  // Handler Làm mới toàn bộ thủ công
  const handleRefreshAll = async () => {
    setIsRefreshing(true);
    await loadOverview();
    if (selectedSessionId) {
      await loadSessionDetails(selectedSessionId, activeFilter);
    }
    setIsRefreshing(false);
  };

  const handleSelectSession = (id) => {
    setSelectedSessionId(id);
  };

  const handleFilterChange = (filter) => {
    setActiveFilter(filter);
    if (selectedSessionId) {
      loadSessionDetails(selectedSessionId, filter);
    }
  };

  return (
    <div className="dashboard-container">
      {/* 1. Header SaaS Sáng & Hiện đại */}
      <Header
        isRealtimeConnected={isRealtimeConnected}
        isRefreshing={isRefreshing}
        onRefresh={handleRefreshAll}
      />

      {/* 2. Nội dung chính */}
      <main className="dashboard-content">
        {/* KPI Metrics */}
        <KpiMetrics stats={stats} />

        {/* Live Excel Action Radar (Theo dõi thời gian thực) */}
        <ExcelRadar
          activeStudent={activeStudent}
          activeWorkbook={activeWorkbook}
          activeSheet={activeSheet}
          activeCell={activeCell}
          activeTool={activeTool}
          lastAction={lastAction}
          isRealtimeConnected={isRealtimeConnected}
        />

        {/* Live Simulator Toolbar */}
        <LiveSimulator
          sessionId={selectedSessionId}
          onEventSimulated={handleRefreshAll}
        />

        {/* Main Grid: Danh sách phiên (Trái) + Chi tiết phiên & Dòng Telemetry (Phải) */}
        <div className="main-view-grid">
          {/* Cột trái: Danh sách phiên học */}
          <SessionList
            sessions={sessions}
            selectedSessionId={selectedSessionId}
            onSelectSession={handleSelectSession}
          />

          {/* Cột phải: Chi tiết phiên & Dòng telemetry */}
          <div className="detail-workspace">
            {selectedSession ? (
              <>
                {/* Hero Banner Thông tin Phiên */}
                <SessionHero session={selectedSession} />

                {/* Tabs điều hướng */}
                <div className="tabs-bar">
                  <button
                    className={`tab-btn ${activeTab === 'timeline' ? 'active' : ''}`}
                    onClick={() => setActiveTab('timeline')}
                  >
                    <Clock size={16} />
                    <span>Dòng sự kiện Telemetry ({events.length})</span>
                  </button>

                  <button
                    className={`tab-btn ${activeTab === 'features' ? 'active' : ''}`}
                    onClick={() => setActiveTab('features')}
                  >
                    <Activity size={16} />
                    <span>Vector đặc trưng hành vi ({features.length})</span>
                  </button>

                  <button
                    className={`tab-btn ${activeTab === 'cognitive' ? 'active' : ''}`}
                    onClick={() => setActiveTab('cognitive')}
                  >
                    <BrainCircuit size={16} />
                    <span>Nhận thức & Can thiệp AI ({predictions.length})</span>
                  </button>
                </div>

                {/* Nội dung Tab */}
                {activeTab === 'timeline' && (
                  <TimelineStream
                    events={events}
                    activeFilter={activeFilter}
                    onFilterChange={handleFilterChange}
                    latestEventId={latestEventId}
                  />
                )}

                {activeTab === 'features' && <FeatureViewer features={features} />}

                {activeTab === 'cognitive' && (
                  <CognitiveAiTab predictions={predictions} feedback={feedback} />
                )}
              </>
            ) : (
              <div
                className="panel-card"
                style={{ padding: '64px', textAlign: 'center', color: 'var(--text-muted)' }}
              >
                Vui lòng chọn một phiên thực hành bên danh sách để xem dữ liệu telemetry chi tiết.
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
