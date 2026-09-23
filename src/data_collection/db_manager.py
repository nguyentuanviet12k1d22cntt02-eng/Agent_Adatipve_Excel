"""
Database Manager: Quản trị kết nối cơ sở dữ liệu Supabase Cloud (chính), MySQL (nội bộ) và SQLite (dự phòng).
Hỗ trợ ghi nhận dòng sự kiện tương tác, phiên học, nhãn và đặc trưng hành vi người học.
"""

import json
import os
import sqlite3
import time
from typing import Any, Dict, List, Optional
import pymysql
import psycopg2

from src.config.db_config import (
    SUPABASE_HOST,
    SUPABASE_PORT,
    SUPABASE_USER,
    SUPABASE_PASSWORD,
    SUPABASE_DATABASE,
    USE_SUPABASE,
    MYSQL_HOST,
    MYSQL_PORT,
    MYSQL_USER,
    MYSQL_PASSWORD,
    MYSQL_DATABASE,
    SQLITE_DB_PATH,
)


class DatabaseManager:
    def __init__(self, use_supabase: bool = True, use_mysql: bool = True, db_path: Optional[str] = None):
        self.use_supabase = use_supabase and USE_SUPABASE
        self.use_mysql = use_mysql
        self.sqlite_path = db_path or SQLITE_DB_PATH
        os.makedirs(os.path.dirname(self.sqlite_path), exist_ok=True)

        # 1. Kiểm tra kết nối Supabase Cloud
        self.supabase_available = False
        if self.use_supabase:
            try:
                conn = self.get_supabase_connection()
                conn.close()
                self.supabase_available = True
            except Exception as e:
                print(f"[DatabaseManager] Supabase Cloud chưa sẵn sàng ({e}).")
                self.supabase_available = False

        # 2. Kiểm tra kết nối MySQL
        self.mysql_available = False
        if self.use_mysql:
            try:
                conn = self.get_mysql_connection()
                conn.close()
                self.mysql_available = True
            except Exception as e:
                print(f"[DatabaseManager] Không thể kết nối MySQL ({e}). Tự động fallback sang SQLite.")
                self.mysql_available = False

        if not self.mysql_available and not self.supabase_available or db_path is not None:
            self._init_sqlite()

    def get_supabase_connection(self):
        """Tạo kết nối tới máy chủ Supabase PostgreSQL."""
        conn = psycopg2.connect(
            host=SUPABASE_HOST,
            port=SUPABASE_PORT,
            user=SUPABASE_USER,
            password=SUPABASE_PASSWORD,
            dbname=SUPABASE_DATABASE,
            connect_timeout=5,
        )
        conn.autocommit = True
        return conn

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
        """Trả về kết nối khả dụng (Ưu tiên Supabase, MySQL, fallback SQLite)."""
        if self.supabase_available:
            try:
                return self.get_supabase_connection()
            except Exception:
                pass
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
        """Ghi hàng loạt sự kiện vào Supabase Cloud và MySQL / SQLite."""
        if not events:
            return

        # 1. Ghi vào Supabase Cloud (Nếu có mạng)
        if self.supabase_available:
            try:
                conn = self.get_supabase_connection()
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
                    sql = """
                    INSERT INTO public.events (session_id, timestamp, iso_time, event_type, lesson_id, step_index, cell, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
                    """
                    cursor.executemany(sql, rows)
                conn.close()
            except Exception as e:
                print(f"[DatabaseManager] Gửi Supabase Cloud lỗi: {e}")

        # 2. Ghi vào MySQL cục bộ
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

        # 3. Fallback SQLite
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
