"""
Database Manager: Quản trị kết nối cơ sở dữ liệu SQLite cục bộ phục vụ thu thập dữ liệu học tập.
Bật chế độ WAL (Write-Ahead Logging) để hỗ trợ đọc/ghi đồng thời với hiệu năng tối đa.
"""

import json
import os
import sqlite3
from typing import Any, Dict, List, Optional


class DatabaseManager:
    DEFAULT_DB_PATH = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "data",
        "excel_tutor.db",
    )

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or self.DEFAULT_DB_PATH
        # Đảm bảo thư mục cha tồn tại
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_database()

    def get_connection(self) -> sqlite3.Connection:
        """Tạo kết nối SQLite an toàn với WAL mode."""
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def _init_database(self):
        """Khởi tạo cấu trúc các bảng theo tài liệu thiết kế."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # 1. Bảng học viên (Students)
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS students (
                    student_id TEXT PRIMARY KEY,
                    name TEXT,
                    created_at REAL
                );
                """
            )

            # 2. Bảng phiên học (Sessions)
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    student_id TEXT,
                    lesson_id TEXT,
                    started_at REAL,
                    ended_at REAL,
                    status TEXT,
                    total_steps INTEGER DEFAULT 0,
                    completed_steps INTEGER DEFAULT 0,
                    FOREIGN KEY(student_id) REFERENCES students(student_id)
                );
                """
            )

            # 3. Bảng dòng sự kiện thô (Events)
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    timestamp REAL,
                    iso_time TEXT,
                    event_type TEXT,
                    lesson_id TEXT,
                    step_index INTEGER,
                    cell TEXT,
                    metadata TEXT,
                    FOREIGN KEY(session_id) REFERENCES sessions(session_id)
                );
                """
            )
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_session ON events(session_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);")

            # 4. Bảng dự đoán trạng thái của ML (Predictions)
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS predictions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    timestamp REAL,
                    state TEXT,
                    confidence REAL,
                    model_version TEXT,
                    FOREIGN KEY(session_id) REFERENCES sessions(session_id)
                );
                """
            )

            conn.commit()

    def insert_events_batch(self, events: List[Dict[str, Any]]):
        """Ghi hàng loạt sự kiện vào database theo batch tối ưu I/O."""
        if not events:
            return

        with self.get_connection() as conn:
            cursor = conn.cursor()
            rows = [
                (
                    e.get("session_id", ""),
                    e.get("timestamp", 0.0),
                    e.get("iso_time", ""),
                    e.get("event_type", ""),
                    e.get("lesson_id", ""),
                    e.get("step_index", 0),
                    e.get("cell", ""),
                    json.dumps(e.get("metadata", {}), ensure_ascii=False),
                )
                for e in events
            ]
            cursor.executemany(
                """
                INSERT INTO events (session_id, timestamp, iso_time, event_type, lesson_id, step_index, cell, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """,
                rows,
            )
            conn.commit()
