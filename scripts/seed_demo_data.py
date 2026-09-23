"""
Seed Demo Data: Nạp dữ liệu mẫu thực tế vào cơ sở dữ liệu MySQL (excel_adaptive_tutor)
phục vụ kiểm tra trực quan giao diện ReactJS Dashboard và kiểm thử ML pipeline.
"""

import os
import sys
sys.stdout.reconfigure(encoding="utf-8")
import json
import time
from datetime import datetime, timedelta
import pymysql

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.config.db_config import (
    MYSQL_HOST,
    MYSQL_PORT,
    MYSQL_USER,
    MYSQL_PASSWORD,
    MYSQL_DATABASE,
)


def seed_database():
    conn = pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DATABASE,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )

    now = datetime.now()

    try:
        with conn.cursor() as cursor:
            print("🌱 Đang làm sạch và nạp dữ liệu mẫu vào MySQL...")

            # 1. Nạp học viên (Students)
            students = [
                ("ST001", "Nguyễn Tuấn Việt", "tuanvietdev@gmail.com", now - timedelta(days=2)),
                ("ST002", "Trần Minh Hoàng", "hoangtm@student.edu.vn", now - timedelta(days=1)),
                ("ST003", "Lê Thị Mai", "maile@student.edu.vn", now - timedelta(hours=5)),
            ]
            cursor.executemany(
                """
                INSERT INTO students (student_id, name, email, created_at)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE name=VALUES(name), email=VALUES(email);
                """,
                students,
            )

            # 2. Nạp phiên thực hành (Sessions)
            sessions = [
                # Phiên 1: Bài 07 - Hoàn thành xuất sắc
                (
                    "SES_BAI07_001",
                    "ST001",
                    "BAI_07",
                    now - timedelta(minutes=45),
                    now - timedelta(minutes=42),
                    "COMPLETED",
                    7,
                    7,
                ),
                # Phiên 2: Bài 08 - Hoàn thành chuẩn
                (
                    "SES_BAI08_001",
                    "ST001",
                    "BAI_08",
                    now - timedelta(minutes=30),
                    now - timedelta(minutes=22),
                    "COMPLETED",
                    10,
                    10,
                ),
                # Phiên 3: Bài 08 - Học viên gặp khó khăn và bị kẹt (STUCK) ở bước định dạng Text
                (
                    "SES_BAI08_STUCK_002",
                    "ST002",
                    "BAI_08",
                    now - timedelta(minutes=10),
                    None,
                    "IN_PROGRESS",
                    10,
                    2,
                ),
            ]
            cursor.executemany(
                """
                INSERT INTO sessions (session_id, student_id, lesson_id, started_at, ended_at, status, total_steps, completed_steps)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE status=VALUES(status), completed_steps=VALUES(completed_steps);
                """,
                sessions,
            )

            # 3. Nạp sự kiện thô (Events Stream) cho SES_BAI08_STUCK_002 (mô phỏng tình huống ngập ngừng & lỗi)
            base_t = (now - timedelta(minutes=10)).timestamp()
            events = [
                ("SES_BAI08_STUCK_002", base_t + 1, "STEP_STARTED", "BAI_08", 0, "F7", {"step_title": "Quan sát mất số 0"}),
                ("SES_BAI08_STUCK_002", base_t + 3, "CELL_SELECTION", "BAI_08", 0, "F7", {"previous_cell": "A1"}),
                ("SES_BAI08_STUCK_002", base_t + 7, "CELL_VALUE_CHANGE", "BAI_08", 0, "F7", {"new_value": "908123456", "previous_value": ""}),
                ("SES_BAI08_STUCK_002", base_t + 8, "STEP_FINISHED", "BAI_08", 0, "F7", {"time_on_step": 7.0}),
                ("SES_BAI08_STUCK_002", base_t + 9, "STEP_STARTED", "BAI_08", 1, "F7:F10", {"step_title": "Định dạng F7:F10 thành Text"}),
                ("SES_BAI08_STUCK_002", base_t + 14, "RANGE_SELECTION", "BAI_08", 1, "F7:F10", {"rows": 4, "columns": 1}),
                ("SES_BAI08_STUCK_002", base_t + 20, "MOUSE_HESITATION_START", "BAI_08", 1, "F7", {"idle_duration": 4.8, "hovered_cell": "F7"}),
                ("SES_BAI08_STUCK_002", base_t + 25, "ERRATIC_MOUSE_MOVEMENT", "BAI_08", 1, "F7", {"instant_speed": 1950.0, "max_speed": 2100.0}),
                ("SES_BAI08_STUCK_002", base_t + 32, "CELL_VALUE_CHANGE", "BAI_08", 1, "F7", {"new_value": "0908123456", "previous_value": "908123456"}),
                ("SES_BAI08_STUCK_002", base_t + 34, "FORMULA_ERROR", "BAI_08", 1, "F7", {"error_type": "MISSING_LEADING_ZERO", "note": "Chưa định dạng Text nên số 0 bị mất"}),
                ("SES_BAI08_STUCK_002", base_t + 45, "MOUSE_HESITATION_START", "BAI_08", 1, "F7", {"idle_duration": 6.2, "note": "Học viên dừng lại lúng túng"}),
            ]
            for ev in events:
                sess_id, ts, etype, lid, sidx, cell, meta = ev
                iso_str = datetime.fromtimestamp(ts).isoformat()
                cursor.execute(
                    """
                    INSERT INTO events (session_id, timestamp, iso_time, event_type, lesson_id, step_index, cell, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
                    """,
                    (sess_id, ts, iso_str, etype, lid, sidx, cell, json.dumps(meta, ensure_ascii=False)),
                )

            # 4. Nạp Features Vector phục vụ huấn luyện Machine Learning
            features = [
                # Session 1 - Bước 1
                ("SES_BAI07_001", 0, 12.5, 0.8, 1.5, 520.0, 0, 0, 0, 0, 2, 0, 1.0),
                # Session 1 - Bước 2
                ("SES_BAI07_001", 1, 18.2, 1.1, 2.0, 480.0, 0, 0, 0, 0, 3, 0, 1.0),
                # Session 3 - Bước 2 (Lúng túng & STUCK)
                ("SES_BAI08_STUCK_002", 1, 65.4, 4.5, 6.2, 120.0, 3, 2, 1, 3, 9, 1, 0.2),
            ]
            cursor.executemany(
                """
                INSERT INTO features (session_id, step_index, time_on_task, mouse_idle_avg, mouse_idle_max, mouse_speed_mean,
                                     wrong_attempts, formula_errors, undo_count, retry_count, selection_changes, hint_requests, completion_rate)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                """,
                features,
            )

            # 5. Nạp Labels & Predictions
            labels = [
                ("SES_BAI07_001", 0, "MASTERED", "OUTCOME"),
                ("SES_BAI07_001", 1, "NORMAL", "OUTCOME"),
                ("SES_BAI08_STUCK_002", 1, "STUCK", "TEACHER"),
            ]
            cursor.executemany(
                """
                INSERT INTO labels (session_id, step_index, label, source)
                VALUES (%s, %s, %s, %s);
                """,
                labels,
            )

            predictions = [
                ("SES_BAI07_001", base_t, "NORMAL", 0.94, "RandomForest-v1.0"),
                ("SES_BAI08_STUCK_002", base_t + 40, "STUCK", 0.89, "RandomForest-v1.0"),
            ]
            cursor.executemany(
                """
                INSERT INTO predictions (session_id, timestamp, state, confidence, model_version)
                VALUES (%s, %s, %s, %s, %s);
                """,
                predictions,
            )

            # 6. Nạp Feedback tương ứng từ AI Agent
            feedback = [
                ("SES_BAI08_STUCK_002", 1, 2, "Trên thanh Ribbon (Thẻ Home), chọn định dạng Text trước khi gõ số 0 nhé!"),
                ("SES_BAI08_STUCK_002", 1, 3, "Gia sư đã khoanh vùng đỏ: Nhấn vào ô F7, mở dropdown Number Format và chọn Text."),
            ]
            cursor.executemany(
                """
                INSERT INTO feedback (session_id, step_index, hint_level, message)
                VALUES (%s, %s, %s, %s);
                """,
                feedback,
            )

            conn.commit()
            print("✅ Đã nạp thành công toàn bộ dữ liệu mẫu vào MySQL (excel_adaptive_tutor)!")

    finally:
        conn.close()


if __name__ == "__main__":
    seed_database()
