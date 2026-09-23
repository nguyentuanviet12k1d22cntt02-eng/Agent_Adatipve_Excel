-- ==============================================================================
-- CƠ SỞ DỮ LIỆU: HỆ THỐNG TRỢ GIẢNG EXCEL THÍCH ỨNG (ML + AI AGENT)
-- Thiết kế chuẩn hóa theo tài liệu nghiên cứu: Ke_hoach_Excel_AI_Tutor_ML_Agent.docx
-- ==============================================================================

CREATE DATABASE IF NOT EXISTS excel_adaptive_tutor
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;

USE excel_adaptive_tutor;

-- 1. Bảng học viên (Students)
CREATE TABLE IF NOT EXISTS students (
    student_id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- 2. Bảng phiên thực hành (Sessions)
CREATE TABLE IF NOT EXISTS sessions (
    session_id VARCHAR(100) PRIMARY KEY,
    student_id VARCHAR(50) NOT NULL,
    lesson_id VARCHAR(50) NOT NULL,
    started_at DATETIME NOT NULL,
    ended_at DATETIME NULL,
    status VARCHAR(50) DEFAULT 'IN_PROGRESS',
    total_steps INT DEFAULT 0,
    completed_steps INT DEFAULT 0,
    INDEX idx_student (student_id),
    INDEX idx_lesson (lesson_id),
    INDEX idx_started (started_at),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- 3. Bảng dòng sự kiện thô (Events Stream)
CREATE TABLE IF NOT EXISTS events (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    session_id VARCHAR(100) NOT NULL,
    timestamp DOUBLE NOT NULL,
    iso_time VARCHAR(50) NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    lesson_id VARCHAR(50) NULL,
    step_index INT DEFAULT 0,
    cell VARCHAR(50) NULL,
    metadata JSON NULL,
    INDEX idx_session (session_id),
    INDEX idx_event_type (event_type),
    INDEX idx_timestamp (timestamp),
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- 4. Bảng vector đặc trưng hành vi (Features)
CREATE TABLE IF NOT EXISTS features (
    feature_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    session_id VARCHAR(100) NOT NULL,
    step_index INT DEFAULT 0,
    time_on_task DOUBLE DEFAULT 0.0,
    mouse_idle_avg DOUBLE DEFAULT 0.0,
    mouse_idle_max DOUBLE DEFAULT 0.0,
    mouse_speed_mean DOUBLE DEFAULT 0.0,
    wrong_attempts INT DEFAULT 0,
    formula_errors INT DEFAULT 0,
    undo_count INT DEFAULT 0,
    retry_count INT DEFAULT 0,
    selection_changes INT DEFAULT 0,
    hint_requests INT DEFAULT 0,
    completion_rate DOUBLE DEFAULT 0.0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_session_step (session_id, step_index),
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- 5. Bảng nhãn trạng thái học tập (Labels)
CREATE TABLE IF NOT EXISTS labels (
    label_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    session_id VARCHAR(100) NOT NULL,
    step_index INT DEFAULT 0,
    label VARCHAR(50) NOT NULL, -- NORMAL, HESITATING, CONFUSED, STUCK, MASTERED
    source VARCHAR(50) DEFAULT 'RULE_HEURISTIC', -- OUTCOME, RULE_HEURISTIC, TEACHER, SELF_REPORT
    annotated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_session_step_label (session_id, step_index),
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- 6. Bảng kết quả dự đoán của mô hình ML (Predictions)
CREATE TABLE IF NOT EXISTS predictions (
    prediction_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    session_id VARCHAR(100) NOT NULL,
    timestamp DOUBLE NOT NULL,
    state VARCHAR(50) NOT NULL, -- NORMAL, HESITATING, CONFUSED, STUCK, MASTERED
    confidence DOUBLE NOT NULL,
    model_version VARCHAR(50) NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_session_pred (session_id),
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- 7. Bảng phản hồi thích ứng từ AI Agent (Feedback)
CREATE TABLE IF NOT EXISTS feedback (
    feedback_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    session_id VARCHAR(100) NOT NULL,
    step_index INT DEFAULT 0,
    hint_level INT DEFAULT 1, -- 0 (None), 1 (Reflective), 2 (Tool hint), 3 (Step-by-step & Overlay)
    message TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_session_fb (session_id),
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- 8. Bảng quản lý phiên bản mô hình (Model Versions)
CREATE TABLE IF NOT EXISTS model_versions (
    version_id VARCHAR(50) PRIMARY KEY,
    model_name VARCHAR(100) NOT NULL,
    training_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    f1_score DOUBLE NULL,
    accuracy DOUBLE NULL,
    parameters JSON NULL
) ENGINE=InnoDB;
