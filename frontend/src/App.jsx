import React, { useState, useEffect, useCallback } from 'react';
import './styles/theme.css';
import './styles/dashboard.css';

import {
  fetchHealth,
  fetchStats,
  fetchSessions,
  fetchSessionDetail,
  fetchSessionEvents,
  fetchSessionFeatures,
  fetchSessionPredictions,
  fetchSessionFeedback,
} from './api';

import Header from './components/Header';
import KpiMetrics from './components/KpiMetrics';
import SessionList from './components/SessionList';
import SessionHero from './components/SessionHero';
import TimelineStream from './components/TimelineStream';
import FeatureViewer from './components/FeatureViewer';
import CognitiveAiTab from './components/CognitiveAiTab';
import LiveSimulator from './components/LiveSimulator';

import { Clock, Activity, BrainCircuit } from 'lucide-react';

export default function App() {
  const [health, setHealth] = useState(null);
  const [stats, setStats] = useState(null);
  const [sessions, setSessions] = useState([]);
  const [selectedSessionId, setSelectedSessionId] = useState(null);
  const [selectedSession, setSelectedSession] = useState(null);

  const [events, setEvents] = useState([]);
  const [features, setFeatures] = useState([]);
  const [predictions, setPredictions] = useState([]);
  const [feedback, setFeedback] = useState([]);

  const [activeFilter, setActiveFilter] = useState('ALL');
  const [activeTab, setActiveTab] = useState('timeline'); // 'timeline' | 'features' | 'cognitive'
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);

  // 1. Tải thông số hệ thống và danh sách phiên
  const loadSystemOverview = useCallback(async () => {
    try {
      const [hData, sData, sesData] = await Promise.all([
        fetchHealth(),
        fetchStats(),
        fetchSessions(),
      ]);
      setHealth(hData);
      setStats(sData);
      setSessions(sesData);

      // Nếu chưa chọn session nào, mặc định chọn session đầu tiên hoặc session bị STUCK để demo
      if (!selectedSessionId && sesData.length > 0) {
        const stuckSes = sesData.find((s) => s.session_id.includes('STUCK'));
        setSelectedSessionId(stuckSes ? stuckSes.session_id : sesData[0].session_id);
      }
    } catch (err) {
      console.error('Lỗi khi tải dữ liệu tổng quan:', err);
    }
  }, [selectedSessionId]);

  // 2. Tải dữ liệu chi tiết của session đang chọn
  const loadSessionDetails = useCallback(async (sessionId, filter = activeFilter) => {
    if (!sessionId) return;
    try {
      const [detail, evts, feats, preds, fbacks] = await Promise.all([
        fetchSessionDetail(sessionId),
        fetchSessionEvents(sessionId, filter),
        fetchSessionFeatures(sessionId),
        fetchSessionPredictions(sessionId),
        fetchSessionFeedback(sessionId),
      ]);
      setSelectedSession(detail);
      setEvents(evts);
      setFeatures(feats);
      setPredictions(preds);
      setFeedback(fbacks);
    } catch (err) {
      console.error(`Lỗi khi tải dữ liệu session ${sessionId}:`, err);
    }
  }, [activeFilter]);

  // Khởi động lần đầu
  useEffect(() => {
    loadSystemOverview();
  }, [loadSystemOverview]);

  // Khi selectedSessionId đổi -> tải chi tiết
  useEffect(() => {
    if (selectedSessionId) {
      loadSessionDetails(selectedSessionId, activeFilter);
    }
  }, [selectedSessionId, activeFilter, loadSessionDetails]);

  // Cơ chế Auto-Polling (Live cập nhật từ MySQL)
  useEffect(() => {
    if (!autoRefresh) return;
    const interval = setInterval(() => {
      loadSystemOverview();
      if (selectedSessionId) {
        loadSessionDetails(selectedSessionId, activeFilter);
      }
    }, 3000);
    return () => clearInterval(interval);
  }, [autoRefresh, selectedSessionId, activeFilter, loadSystemOverview, loadSessionDetails]);

  // Handler Refresh thủ công
  const handleManualRefresh = async () => {
    setIsRefreshing(true);
    await loadSystemOverview();
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
      {/* 1. Header */}
      <Header
        health={health}
        isRefreshing={isRefreshing}
        onRefresh={handleManualRefresh}
        autoRefresh={autoRefresh}
        setAutoRefresh={setAutoRefresh}
      />

      {/* 2. Main Content */}
      <main className="dashboard-content">
        {/* KPI Metrics Summary */}
        <KpiMetrics stats={stats} />

        {/* Live Simulator Toolbar */}
        <LiveSimulator
          sessionId={selectedSessionId}
          onEventSimulated={handleManualRefresh}
        />

        {/* Main Grid: Session List (Left) + Detail Workspace (Right) */}
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
                {/* Hero Banner */}
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
