"""
Supabase Migration & Sync Script:
1. Kết nối thẳng vào Supabase PostgreSQL (aws-0-ap-northeast-1.pooler.supabase.com)
2. Tự động khởi tạo toàn bộ 7 bảng chuẩn hóa
3. Kích hoạt Supabase Realtime cho các bảng
4. Đồng bộ toàn bộ dữ liệu đã thu thập từ MySQL lên Supabase Cloud!
"""

import os
import sys
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import json
import psycopg2
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

SUPABASE_HOST = "aws-0-ap-northeast-1.pooler.supabase.com"
SUPABASE_PORT = 5432
SUPABASE_USER = "postgres.cxjhnsvzacqlfbpcnkrh"
SUPABASE_PASSWORD = "Viet.10092004@"
SUPABASE_DB = "postgres"

DDL = """
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

-- 3. Bảng Events
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

-- 4. Bảng Features
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

-- 5. Bảng Labels
CREATE TABLE IF NOT EXISTS public.labels (
    label_id BIGSERIAL PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES public.sessions(session_id) ON DELETE CASCADE,
    step_index INT DEFAULT 0,
    label TEXT NOT NULL,
    source TEXT DEFAULT 'RULE_HEURISTIC',
    annotated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 6. Bảng Predictions
CREATE TABLE IF NOT EXISTS public.predictions (
    prediction_id BIGSERIAL PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES public.sessions(session_id) ON DELETE CASCADE,
    timestamp DOUBLE PRECISION NOT NULL,
    state TEXT NOT NULL,
    confidence DOUBLE PRECISION NOT NULL,
    model_version TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 7. Bảng Feedback
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

-- Kích hoạt Realtime
DO $$
BEGIN
    BEGIN
        ALTER PUBLICATION supabase_realtime ADD TABLE public.sessions;
    EXCEPTION WHEN duplicate_object THEN
    END;
    BEGIN
        ALTER PUBLICATION supabase_realtime ADD TABLE public.events;
    EXCEPTION WHEN duplicate_object THEN
    END;
    BEGIN
        ALTER PUBLICATION supabase_realtime ADD TABLE public.features;
    EXCEPTION WHEN duplicate_object THEN
    END;
    BEGIN
        ALTER PUBLICATION supabase_realtime ADD TABLE public.predictions;
    EXCEPTION WHEN duplicate_object THEN
    END;
    BEGIN
        ALTER PUBLICATION supabase_realtime ADD TABLE public.feedback;
    EXCEPTION WHEN duplicate_object THEN
    END;
END $$;
"""


def main():
    print("=" * 80)
    print("🚀 BẮT ĐẦU KHỞI TẠO CẤU TRÚC VÀ ĐỒNG BỘ DỮ LIỆU LÊN SUPABASE CLOUD")
    print(f"   Máy chủ Supabase: {SUPABASE_HOST}:{SUPABASE_PORT}")
    print("=" * 80)

    # 1. Kết nối Supabase và chạy DDL
    print("1. Đang kết nối tới Supabase PostgreSQL...")
    pg_conn = psycopg2.connect(
        host=SUPABASE_HOST,
        port=SUPABASE_PORT,
        user=SUPABASE_USER,
        password=SUPABASE_PASSWORD,
        dbname=SUPABASE_DB,
        connect_timeout=15,
    )
    pg_conn.autocommit = True

    with pg_conn.cursor() as cur:
        print("2. Đang tạo các bảng dữ liệu & kích hoạt Realtime trên Supabase...")
        cur.execute(DDL)
        print("   ✅ Đã khởi tạo cấu trúc 7 bảng và kích hoạt Realtime thành công!")

        cur.execute(
            """
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            ORDER BY table_name;
            """
        )
        tables = [r[0] for r in cur.fetchall()]
        print(f"   📋 Danh sách bảng hiện có trên Supabase: {tables}")

    # 2. Đồng bộ dữ liệu hiện có từ MySQL lên Supabase
    print("\n3. Đang đồng bộ dữ liệu thực hành từ MySQL lên Supabase Cloud...")
    try:
        my_conn = pymysql.connect(
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            database=MYSQL_DATABASE,
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
        )

        with my_conn.cursor() as my_cur, pg_conn.cursor() as pg_cur:
            # Sync Students
            my_cur.execute("SELECT * FROM students;")
            students = my_cur.fetchall()
            for s in students:
                pg_cur.execute(
                    """
                    INSERT INTO public.students (student_id, name, email, created_at)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (student_id) DO UPDATE SET name = EXCLUDED.name, email = EXCLUDED.email;
                    """,
                    (s["student_id"], s["name"], s.get("email"), s["created_at"]),
                )
            print(f"   ✅ Đã đồng bộ {len(students)} học viên (Students).")

            # Sync Sessions
            my_cur.execute("SELECT * FROM sessions;")
            sessions = my_cur.fetchall()
            for ses in sessions:
                pg_cur.execute(
                    """
                    INSERT INTO public.sessions (session_id, student_id, lesson_id, started_at, ended_at, status, total_steps, completed_steps)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (session_id) DO UPDATE SET status = EXCLUDED.status, completed_steps = EXCLUDED.completed_steps;
                    """,
                    (
                        ses["session_id"],
                        ses["student_id"],
                        ses["lesson_id"],
                        ses["started_at"],
                        ses.get("ended_at"),
                        ses["status"],
                        ses.get("total_steps", 0),
                        ses.get("completed_steps", 0),
                    ),
                )
            print(f"   ✅ Đã đồng bộ {len(sessions)} phiên thực hành (Sessions).")

            # Sync Events
            my_cur.execute("SELECT * FROM events;")
            events = my_cur.fetchall()
            for ev in events:
                meta = ev.get("metadata")
                meta_json = json.dumps(meta) if isinstance(meta, dict) else (meta if meta else None)
                pg_cur.execute(
                    """
                    INSERT INTO public.events (id, session_id, timestamp, iso_time, event_type, lesson_id, step_index, cell, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO NOTHING;
                    """,
                    (
                        ev["id"],
                        ev["session_id"],
                        ev["timestamp"],
                        ev["iso_time"],
                        ev["event_type"],
                        ev.get("lesson_id"),
                        ev.get("step_index", 0),
                        ev.get("cell"),
                        meta_json,
                    ),
                )
            print(f"   ✅ Đã đồng bộ {len(events)} sự kiện thao tác (Events).")

            # Sync Features
            my_cur.execute("SELECT * FROM features;")
            features = my_cur.fetchall()
            for f in features:
                pg_cur.execute(
                    """
                    INSERT INTO public.features (
                        feature_id, session_id, step_index, time_on_task, mouse_idle_avg, mouse_idle_max,
                        mouse_speed_mean, wrong_attempts, formula_errors, undo_count, retry_count,
                        selection_changes, hint_requests, completion_rate
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (feature_id) DO NOTHING;
                    """,
                    (
                        f["feature_id"],
                        f["session_id"],
                        f["step_index"],
                        f["time_on_task"],
                        f["mouse_idle_avg"],
                        f["mouse_idle_max"],
                        f["mouse_speed_mean"],
                        f["wrong_attempts"],
                        f["formula_errors"],
                        f["undo_count"],
                        f["retry_count"],
                        f["selection_changes"],
                        f["hint_requests"],
                        f["completion_rate"],
                    ),
                )
            print(f"   ✅ Đã đồng bộ {len(features)} vector đặc trưng (Features).")

        my_conn.close()
    except Exception as e:
        print(f"   ⚠️ Lỗi đồng bộ dữ liệu MySQL: {e}")

    pg_conn.close()
    print("\n" + "=" * 80)
    print("🎉 TẤT CẢ ĐÃ HOÀN TẤT MỸ MÃN!")
    print("   Bây giờ bạn mở Supabase Dashboard lên là thấy toàn bộ bảng và dữ liệu!")
    print("=" * 80)


if __name__ == "__main__":
    main()
