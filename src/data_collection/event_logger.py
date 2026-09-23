"""
Event Logger: Bộ ghi nhận sự kiện bất đồng bộ (Non-blocking Asynchronous Logger).
Đảm bảo thu thập dữ liệu hành vi với độ trễ 0ms, không ảnh hưởng tới GUI hay COM loop.
Đồng bộ trực tiếp cả Supabase Cloud và MySQL cục bộ.
"""

import queue
import threading
import time
from typing import Any, Dict, List, Optional
from src.sensors.base_sensor import RawEvent
from src.data_collection.db_manager import DatabaseManager


class EventLogger:
    """
    Logger chạy luồng ngầm (Background Worker Thread):
    - Đẩy sự kiện vào hàng đợi FIFO thread-safe
    - Flush xuống Supabase Cloud & MySQL theo đợt (batching) mỗi 0.25s hoặc khi đạt dung lượng
    """

    def __init__(self, db_manager: Optional[DatabaseManager] = None, batch_size: int = 20, flush_interval: float = 0.5):
        self.db_manager = db_manager or DatabaseManager()
        self.batch_size = batch_size
        self.flush_interval = flush_interval

        self._queue: queue.Queue = queue.Queue()
        self._running = True
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True, name="EventLoggerThread")
        self._worker_thread.start()

    def log_event(self, event: RawEvent):
        """Đưa một RawEvent vào hàng đợi ghi log."""
        if self._running:
            self._queue.put(event.to_dict())

    def log_events(self, events: List[RawEvent]):
        """Đưa một danh sách RawEvent vào hàng đợi."""
        if self._running:
            for e in events:
                self._queue.put(e.to_dict())

    def start_session(self, session_id: str, student_id: str = "DEFAULT_STUDENT", lesson_id: str = ""):
        """Khởi tạo phiên học mới trong CSDL (cả Supabase và MySQL)."""
        now = time.time()
        now_dt = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now))
        clean_lesson = (lesson_id or "Chua_Mo_File")[:250]

        # 1. Ghi nhận vào Supabase Cloud
        if self.db_manager.supabase_available:
            try:
                conn = self.db_manager.get_supabase_connection()
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO public.students (student_id, name, created_at)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (student_id) DO UPDATE SET name = EXCLUDED.name;
                        """,
                        (student_id, f"Student {student_id}", now_dt),
                    )
                    cursor.execute(
                        """
                        INSERT INTO public.sessions (session_id, student_id, lesson_id, started_at, status)
                        VALUES (%s, %s, %s, %s, 'IN_PROGRESS')
                        ON CONFLICT (session_id) DO UPDATE SET status = 'IN_PROGRESS', lesson_id = EXCLUDED.lesson_id;
                        """,
                        (session_id, student_id, clean_lesson, now_dt),
                    )
                conn.close()
            except Exception as e:
                print(f"[EventLogger] Lỗi Supabase start_session: {e}")

        # 2. Ghi nhận vào MySQL cục bộ
        if self.db_manager.mysql_available:
            try:
                conn = self.db_manager.get_mysql_connection()
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO students (student_id, name, created_at)
                        VALUES (%s, %s, %s)
                        ON DUPLICATE KEY UPDATE name=VALUES(name);
                        """,
                        (student_id, f"Student {student_id}", now_dt),
                    )
                    cursor.execute(
                        """
                        INSERT INTO sessions (session_id, student_id, lesson_id, started_at, status)
                        VALUES (%s, %s, %s, %s, 'IN_PROGRESS')
                        ON DUPLICATE KEY UPDATE status='IN_PROGRESS', lesson_id=VALUES(lesson_id);
                        """,
                        (session_id, student_id, clean_lesson, now_dt),
                    )
                conn.close()
            except Exception as e:
                print(f"[EventLogger] Lỗi MySQL start_session: {e}")

        # 3. Fallback SQLite
        try:
            with self.db_manager.get_sqlite_connection() as conn:
                conn.execute(
                    "INSERT OR IGNORE INTO students (student_id, name, created_at) VALUES (?, ?, ?);",
                    (student_id, f"Student {student_id}", now),
                )
                conn.execute(
                    """
                    INSERT OR REPLACE INTO sessions (session_id, student_id, lesson_id, started_at, status)
                    VALUES (?, ?, ?, ?, 'IN_PROGRESS');
                    """,
                    (session_id, student_id, clean_lesson, now),
                )
                conn.commit()
        except Exception as e:
            print(f"[EventLogger] Lỗi SQLite start_session: {e}")

    def update_session_lesson(self, session_id: str, lesson_id: str):
        """Cập nhật tên file bài tập khi học viên mở file mới."""
        clean_lesson = (lesson_id or "")[:250]
        if self.db_manager.supabase_available:
            try:
                conn = self.db_manager.get_supabase_connection()
                with conn.cursor() as cursor:
                    cursor.execute(
                        "UPDATE public.sessions SET lesson_id = %s WHERE session_id = %s;",
                        (clean_lesson, session_id),
                    )
                conn.close()
            except Exception:
                pass

        if self.db_manager.mysql_available:
            try:
                conn = self.db_manager.get_mysql_connection()
                with conn.cursor() as cursor:
                    cursor.execute(
                        "UPDATE sessions SET lesson_id = %s WHERE session_id = %s;",
                        (clean_lesson, session_id),
                    )
                conn.close()
            except Exception:
                pass

    def end_session(self, session_id: str, status: str = "COMPLETED", total_steps: int = 0, completed_steps: int = 0):
        """Cập nhật kết thúc phiên học (cả Supabase và MySQL)."""
        self.flush()
        now = time.time()
        now_dt = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now))

        if self.db_manager.supabase_available:
            try:
                conn = self.db_manager.get_supabase_connection()
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        UPDATE public.sessions
                        SET ended_at = %s, status = %s, total_steps = %s, completed_steps = %s
                        WHERE session_id = %s;
                        """,
                        (now_dt, status, total_steps, completed_steps, session_id),
                    )
                conn.close()
            except Exception as e:
                print(f"[EventLogger] Lỗi Supabase end_session: {e}")

        if self.db_manager.mysql_available:
            try:
                conn = self.db_manager.get_mysql_connection()
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        UPDATE sessions
                        SET ended_at = %s, status = %s, total_steps = %s, completed_steps = %s
                        WHERE session_id = %s;
                        """,
                        (now_dt, status, total_steps, completed_steps, session_id),
                    )
                conn.close()
            except Exception as e:
                print(f"[EventLogger] Lỗi MySQL end_session: {e}")

        try:
            with self.db_manager.get_sqlite_connection() as conn:
                conn.execute(
                    """
                    UPDATE sessions
                    SET ended_at = ?, status = ?, total_steps = ?, completed_steps = ?
                    WHERE session_id = ?;
                    """,
                    (now, status, total_steps, completed_steps, session_id),
                )
                conn.commit()
        except Exception as e:
            print(f"[EventLogger] Lỗi SQLite end_session: {e}")

    def flush(self):
        """Ghi cưỡng bức toàn bộ sự kiện còn lại trong hàng đợi."""
        pending = []
        while not self._queue.empty():
            try:
                pending.append(self._queue.get_nowait())
            except queue.Empty:
                break
        if pending:
            self.db_manager.insert_events_batch(pending)

    def close(self):
        """Đóng logger an toàn."""
        self._running = False
        self.flush()
        if self._worker_thread.is_alive():
            self._worker_thread.join(timeout=1.0)

    def _worker_loop(self):
        """Vòng lặp tiêu thụ hàng đợi ngầm."""
        buffer: List[Dict[str, Any]] = []
        last_flush = time.monotonic()

        while self._running or not self._queue.empty():
            try:
                item = self._queue.get(timeout=0.1)
                buffer.append(item)
            except queue.Empty:
                pass

            now = time.monotonic()
            should_flush = len(buffer) >= self.batch_size or (buffer and (now - last_flush) >= self.flush_interval)

            if should_flush:
                try:
                    self.db_manager.insert_events_batch(buffer)
                except Exception as e:
                    print(f"[EventLogger] Lỗi ghi batch events: {e}")
                buffer = []
                last_flush = now

        if buffer:
            try:
                self.db_manager.insert_events_batch(buffer)
            except Exception:
                pass
