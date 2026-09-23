"""
Database Manager: Quản trị kết nối cơ sở dữ liệu MySQL (chính) và SQLite (dự phòng).
Hỗ trợ ghi nhận dòng sự kiện tương tác, phiên học, nhãn và đặc trưng hành vi người học.
"""

import json
import os
import sqlite3
import time
from typing import Any, Dict, List, Optional
import pymysql

from src.config.db_config import (
    MYSQL_HOST,
    MYSQL_PORT,
    MYSQL_USER,
    MYSQL_PASSWORD,
    MYSQL_DATABASE,
    SQLITE_DB_PATH,
)


class DatabaseManager:
    def __init__(self, use_mysql: bool = True, db_path: Optional[str] = None):
        self.use_mysql = use_mysql
        self.sqlite_path = db_path or SQLITE_DB_PATH
        os.makedirs(os.path.dirname(self.sqlite_path), exist_ok=True)

        # Kiểm tra kết nối MySQL
        self.mysql_available = False
        if self.use_mysql:
            try:
                conn = self.get_mysql_connection()
                conn.close()
                self.mysql_available = True
            except Exception as e:
                print(f"[DatabaseManager] Không thể kết nối MySQL ({e}). Tự động fallback sang SQLite.")
                self.mysql_available = False

        if not self.mysql_available:
            self._init_sqlite()

    def get_mysql_connection(self):
        """Tạo kết nối tới máy chủ MySQL."""
        return pymysql.connect(
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            database=MYSQL_DATABASE,
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=True,
            connect_timeout=3,
        )

    def get_sqlite_connection(self) -> sqlite3.Connection:
        """Tạo kết nối SQLite an toàn với WAL mode."""
        conn = sqlite3.connect(self.sqlite_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def get_connection(self):
        """Trả về kết nối khả dụng (Ưu tiên MySQL, fallback SQLite)."""
        if self.mysql_available:
            try:
                return self.get_mysql_connection()
            except Exception:
                pass
        return self.get_sqlite_connection()

    def _init_sqlite(self):
        """Khởi tạo cấu trúc các bảng cho SQLite khi ở chế độ fallback."""
        with self.get_sqlite_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS students (
                    student_id TEXT PRIMARY KEY,
                    name TEXT,
                    email TEXT,
                    created_at REAL
                );
                """
            )
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
                    completed_steps INTEGER DEFAULT 0
                );
                """
            )
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
                    metadata TEXT
                );
                """
            )
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_session ON events(session_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);")
            conn.commit()

    def insert_events_batch(self, events: List[Dict[str, Any]]):
        """Ghi hàng loạt sự kiện vào MySQL hoặc SQLite."""
        if not events:
            return

        if self.mysql_available:
            try:
                conn = self.get_mysql_connection()
                with conn.cursor() as cursor:
                    rows = [
                        (
                            e.get("session_id", ""),
                            float(e.get("timestamp", time.time())),
                            str(e.get("iso_time", "")),
                            str(e.get("event_type", "")),
                            str(e.get("lesson_id", "")),
                            int(e.get("step_index", 0)),
                            str(e.get("cell", "")),
                            json.dumps(e.get("metadata", {}), ensure_ascii=False),
                        )
                        for e in events
                    ]
                    cursor.executemany(
                        """
                        INSERT INTO events (session_id, timestamp, iso_time, event_type, lesson_id, step_index, cell, metadata)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
                        """,
                        rows,
                    )
                conn.close()
                return
            except Exception as e:
                print(f"[DatabaseManager] Lỗi ghi MySQL ({e}). Ghi tạm vào SQLite.")

        # Fallback SQLite
        with self.get_sqlite_connection() as conn:
            cursor = conn.cursor()
            rows = [
                (
                    e.get("session_id", ""),
                    float(e.get("timestamp", time.time())),
                    str(e.get("iso_time", "")),
                    str(e.get("event_type", "")),
                    str(e.get("lesson_id", "")),
                    int(e.get("step_index", 0)),
                    str(e.get("cell", "")),
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
