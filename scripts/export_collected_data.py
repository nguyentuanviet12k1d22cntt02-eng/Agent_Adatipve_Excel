"""
Export Collected Data: Xuất toàn bộ dữ liệu thực hành đã thu thập từ MySQL
ra định dạng CSV, JSON và sinh sẵn file SQL chuẩn bị nạp trực tiếp vào SUPABASE CLOUD.
"""

import os
import sys
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import csv
import json
import time
from datetime import datetime
import pymysql

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT_DIR)

from src.config.db_config import (
    MYSQL_HOST,
    MYSQL_PORT,
    MYSQL_USER,
    MYSQL_PASSWORD,
    MYSQL_DATABASE,
)


def export_all():
    export_dir = os.path.join(ROOT_DIR, "data", "exports")
    os.makedirs(export_dir, exist_ok=True)

    print("=" * 80)
    print("📦 XUẤT DỮ LIỆU THỰC HÀNH TỪ MYSQL ĐỂ CHUẨN BỊ NẠP VÀO SUPABASE")
    print(f"   Thư mục xuất file: {export_dir}")
    print("=" * 80)

    try:
        conn = pymysql.connect(
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            database=MYSQL_DATABASE,
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
        )
    except Exception as e:
        print(f"❌ Không thể kết nối MySQL: {e}")
        return

    tables = ["students", "sessions", "events", "features", "labels", "predictions", "feedback"]
    summary_report = {}

    with conn.cursor() as cur:
        # 1. Xuất CSV & JSON cho từng bảng
        for table in tables:
            cur.execute(f"SELECT * FROM {table};")
            rows = cur.fetchall()
            summary_report[table] = len(rows)

            # JSON export
            json_file = os.path.join(export_dir, f"{table}.json")
            # Convert datetime to isoformat
            clean_rows = []
            for r in rows:
                c = {}
                for k, v in r.items():
                    if isinstance(v, (datetime, time.struct_time)):
                        c[k] = v.isoformat() if hasattr(v, "isoformat") else str(v)
                    else:
                        c[k] = v
                clean_rows.append(c)

            with open(json_file, "w", encoding="utf-8") as f:
                json.dump(clean_rows, f, ensure_ascii=False, indent=2)

            # CSV export
            if rows:
                csv_file = os.path.join(export_dir, f"{table}.csv")
                headers = list(rows[0].keys())
                with open(csv_file, "w", newline="", encoding="utf-8-sig") as f:
                    writer = csv.DictWriter(f, fieldnames=headers)
                    writer.writeheader()
                    for r in rows:
                        row_copy = dict(r)
                        for k, v in row_copy.items():
                            if isinstance(v, (dict, list)):
                                row_copy[k] = json.dumps(v, ensure_ascii=False)
                        writer.writerow(row_copy)

            print(f"✅ Bảng {table:<15}: Đã xuất {len(rows):>4} bản ghi -> CSV & JSON")

        # 2. Tạo file PostgreSQL Schema tương thích 100% với Supabase
        supabase_sql_path = os.path.join(export_dir, "supabase_schema_and_seed.sql")
        with open(supabase_sql_path, "w", encoding="utf-8") as f:
            f.write("-- =============================================================\n")
            f.write("-- SUPABASE POSTGRESQL SCHEMA & REALTIME CONFIGURATION\n")
            f.write("-- Tự động sinh từ dữ liệu thu thập offline tại trung tâm\n")
            f.write("-- =============================================================\n\n")

            f.write("""
-- 1. Bảng Students
CREATE TABLE IF NOT EXISTS public.students (
    student_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Bảng Sessions
CREATE TABLE IF NOT EXISTS public.sessions (
    session_id TEXT PRIMARY KEY,
    student_id TEXT NOT NULL REFERENCES public.students(student_id) ON DELETE CASCADE,
    lesson_id TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    ended_at TIMESTAMPTZ,
    status TEXT DEFAULT 'IN_PROGRESS',
    total_steps INT DEFAULT 0,
    completed_steps INT DEFAULT 0
);

-- 3. Bảng Events (Telemetry Stream)
CREATE TABLE IF NOT EXISTS public.events (
    id BIGSERIAL PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES public.sessions(session_id) ON DELETE CASCADE,
    timestamp DOUBLE PRECISION NOT NULL,
    iso_time TEXT NOT NULL,
    event_type TEXT NOT NULL,
    lesson_id TEXT,
    step_index INT DEFAULT 0,
    cell TEXT,
    metadata JSONB
);

-- 4. Bảng Features (Feature Store)
CREATE TABLE IF NOT EXISTS public.features (
    feature_id BIGSERIAL PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES public.sessions(session_id) ON DELETE CASCADE,
    step_index INT DEFAULT 0,
    time_on_task DOUBLE PRECISION DEFAULT 0.0,
    mouse_idle_avg DOUBLE PRECISION DEFAULT 0.0,
    mouse_idle_max DOUBLE PRECISION DEFAULT 0.0,
    mouse_speed_mean DOUBLE PRECISION DEFAULT 0.0,
    wrong_attempts INT DEFAULT 0,
    formula_errors INT DEFAULT 0,
    undo_count INT DEFAULT 0,
    retry_count INT DEFAULT 0,
    selection_changes INT DEFAULT 0,
    hint_requests INT DEFAULT 0,
    completion_rate DOUBLE PRECISION DEFAULT 0.0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 5. Bảng Labels (Cognitive Labels)
CREATE TABLE IF NOT EXISTS public.labels (
    label_id BIGSERIAL PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES public.sessions(session_id) ON DELETE CASCADE,
    step_index INT DEFAULT 0,
    label TEXT NOT NULL,
    source TEXT DEFAULT 'RULE_HEURISTIC',
    annotated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 6. Bảng Predictions (ML Predictions)
CREATE TABLE IF NOT EXISTS public.predictions (
    prediction_id BIGSERIAL PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES public.sessions(session_id) ON DELETE CASCADE,
    timestamp DOUBLE PRECISION NOT NULL,
    state TEXT NOT NULL,
    confidence DOUBLE PRECISION NOT NULL,
    model_version TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 7. Bảng Feedback (Adaptive Interventions)
CREATE TABLE IF NOT EXISTS public.feedback (
    feedback_id BIGSERIAL PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES public.sessions(session_id) ON DELETE CASCADE,
    timestamp DOUBLE PRECISION NOT NULL,
    intervention_type TEXT NOT NULL,
    message TEXT NOT NULL,
    adaptation_strategy TEXT,
    student_accepted BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- BẬT SUPABASE REALTIME ĐỂ GIAO DIỆN WEB TỰ NHẢY SỰ KIỆN TRỰC TIẾP
ALTER PUBLICATION supabase_realtime ADD TABLE public.sessions;
ALTER PUBLICATION supabase_realtime ADD TABLE public.events;
ALTER PUBLICATION supabase_realtime ADD TABLE public.features;
ALTER PUBLICATION supabase_realtime ADD TABLE public.predictions;
ALTER PUBLICATION supabase_realtime ADD TABLE public.feedback;
""")

        print(f"\n✨ Đã sinh file cấu hình Supabase sẵn sàng 100%: {supabase_sql_path}")
        print("=" * 80)
        print("TỔNG KẾT:")
        for t, cnt in summary_report.items():
            print(f"  - {t:<15}: {cnt} records")
        print("=" * 80)

    conn.close()


if __name__ == "__main__":
    export_all()
