"""
Event Logger: Bộ ghi nhận sự kiện bất đồng bộ (Non-blocking Asynchronous Logger).
Đảm bảo thu thập dữ liệu hành vi với độ trễ 0ms, không ảnh hưởng tới GUI hay COM loop.
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
    - Flush xuống SQLite theo đợt (batching) mỗi 0.5s hoặc khi đạt dung lượng
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
        """Khởi tạo phiên học mới trong CSDL."""
        try:
            with self.db_manager.get_connection() as conn:
                # Đảm bảo student tồn tại
                conn.execute(
                    "INSERT OR IGNORE INTO students (student_id, name, created_at) VALUES (?, ?, ?);",
                    (student_id, f"Student {student_id}", time.time()),
                )
                conn.execute(
                    """
                    INSERT OR REPLACE INTO sessions (session_id, student_id, lesson_id, started_at, status)
                    VALUES (?, ?, ?, ?, 'IN_PROGRESS');
                    """,
                    (session_id, student_id, lesson_id, time.time()),
                )
                conn.commit()
        except Exception as e:
            print(f"[EventLogger] Lỗi khởi tạo session: {e}")

    def end_session(self, session_id: str, status: str = "COMPLETED", total_steps: int = 0, completed_steps: int = 0):
        """Cập nhật kết thúc phiên học."""
        self.flush()
        try:
            with self.db_manager.get_connection() as conn:
                conn.execute(
                    """
                    UPDATE sessions
                    SET ended_at = ?, status = ?, total_steps = ?, completed_steps = ?
                    WHERE session_id = ?;
                    """,
                    (time.time(), status, total_steps, completed_steps, session_id),
                )
                conn.commit()
        except Exception as e:
            print(f"[EventLogger] Lỗi cập nhật session kết thúc: {e}")

    def flush(self):
        """Ghi cưỡng bức toàn bộ sự kiện còn lại trong hàng đợi xuống đĩa."""
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
                # Chờ lấy sự kiện với timeout ngắn
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

        # Flush lần cuối khi dừng
        if buffer:
            try:
                self.db_manager.insert_events_batch(buffer)
            except Exception:
                pass
