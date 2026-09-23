import React from 'react';
import { BrainCircuit, Bot, AlertTriangle, CheckCircle2, Lightbulb } from 'lucide-react';

export default function CognitiveAiTab({ predictions, feedback }) {
  const latestPrediction = predictions && predictions.length > 0 
    ? predictions[predictions.length - 1] 
    : null;

  const isStuck = latestPrediction?.state === 'STUCK';
  const isHesitating = latestPrediction?.state === 'HESITATING';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* 1. ML State Card */}
      {latestPrediction ? (
        <div className={`cognitive-status-card ${isStuck ? 'stuck' : isHesitating ? 'hesitating' : ''}`}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <div
              style={{
                width: '48px',
                height: '48px',
                borderRadius: '12px',
                background: isStuck ? 'rgba(244, 63, 94, 0.2)' : 'rgba(16, 185, 129, 0.2)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: isStuck ? 'var(--accent-rose)' : 'var(--primary)',
              }}
            >
              <BrainCircuit size={26} />
            </div>
            <div>
              <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                Trạng thái nhận thức người học (ML Prediction)
              </div>
              <div style={{ fontSize: '1.4rem', fontWeight: 700, color: '#fff', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span>{latestPrediction.state}</span>
                <span
                  style={{
                    fontSize: '0.75rem',
                    padding: '2px 8px',
                    borderRadius: '999px',
                    background: 'rgba(255, 255, 255, 0.1)',
                    color: '#e2e8f0',
                  }}
                >
                  Độ tin cậy: {Math.round(latestPrediction.confidence * 100)}%
                </span>
              </div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-subtle)', marginTop: '2px' }}>
                Mô hình: {latestPrediction.model_version} • Cập nhật lúc {new Date(latestPrediction.timestamp * 1000).toLocaleTimeString()}
              </div>
            </div>
          </div>

          <div>
            {isStuck ? (
              <span className="badge badge-stuck" style={{ padding: '6px 12px', fontSize: '0.8rem' }}>
                <AlertTriangle size={14} /> Cần AI hỗ trợ ngay
              </span>
            ) : (
              <span className="badge badge-completed" style={{ padding: '6px 12px', fontSize: '0.8rem' }}>
                <CheckCircle2 size={14} /> Thao tác bình thường
              </span>
            )}
          </div>
        </div>
      ) : (
        <div className="panel-card" style={{ padding: '24px', textAlign: 'center', color: 'var(--text-muted)' }}>
          Chưa có dự đoán ML nào được ghi nhận cho phiên này.
        </div>
      )}

      {/* 2. Adaptive AI Feedback History */}
      <div className="panel-card">
        <div className="panel-header">
          <div className="panel-title">
            <Bot size={18} style={{ color: 'var(--accent-indigo)' }} />
            <span>Nhật ký can thiệp & Trợ giúp từ AI Agent ({feedback.length})</span>
          </div>
        </div>

        <div style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '14px' }}>
          {feedback.length === 0 ? (
            <div style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '24px' }}>
              Người học thao tác thuận lợi, chưa cần kích hoạt phản hồi can thiệp.
            </div>
          ) : (
            feedback.map((item) => (
              <div
                key={item.feedback_id}
                style={{
                  background: 'rgba(30, 41, 59, 0.5)',
                  border: '1px solid rgba(99, 102, 241, 0.25)',
                  borderRadius: '10px',
                  padding: '16px',
                  display: 'flex',
                  gap: '14px',
                }}
              >
                <div
                  style={{
                    width: '36px',
                    height: '36px',
                    borderRadius: '8px',
                    background: 'rgba(99, 102, 241, 0.15)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: 'var(--accent-indigo)',
                    flexShrink: 0,
                  }}
                >
                  <Lightbulb size={20} />
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
                    <div style={{ fontSize: '0.85rem', fontWeight: 600, color: '#e2e8f0' }}>
                      Hình thức can thiệp: <span style={{ color: 'var(--accent-cyan)' }}>{item.intervention_type}</span>
                    </div>
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-subtle)', fontFamily: 'var(--font-mono)' }}>
                      {new Date(item.timestamp * 1000).toLocaleTimeString()}
                    </span>
                  </div>
                  <div style={{ fontSize: '0.85rem', color: '#cbd5e1', lineHeight: '1.5' }}>
                    "{item.message}"
                  </div>
                  <div style={{ marginTop: '8px', fontSize: '0.72rem', color: 'var(--text-subtle)' }}>
                    Chiến lược: {item.adaptation_strategy} • Học viên chấp nhận: {item.student_accepted ? 'Có' : 'Chưa'}
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
