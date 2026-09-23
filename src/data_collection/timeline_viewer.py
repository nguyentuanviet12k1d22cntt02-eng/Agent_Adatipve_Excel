"""
Event Timeline Viewer: Công cụ trực quan hóa dòng sự kiện thu thập được trong phiên học.
Hỗ trợ kiểm chứng và gán nhãn dữ liệu hành vi.
"""

import json
from typing import List, Optional
from src.data_collection.db_manager import DatabaseManager


class TimelineViewer:
    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db = db_manager or DatabaseManager()

    def list_recent_sessions(self, limit: int = 10) -> List[dict]:
        """Liệt kê các phiên học gần nhất."""
        if self.db.mysql_available:
            try:
                conn = self.db.get_mysql_connection()
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT session_id, student_id, lesson_id, started_at, status, completed_steps, total_steps
                        FROM sessions
                        ORDER BY started_at DESC
                        LIMIT %s;
                        """,
                        (limit,),
                    )
                    rows = cursor.fetchall()
                conn.close()
                return [dict(r) for r in rows]
            except Exception as e:
                print(f"[TimelineViewer] Lỗi MySQL: {e}")

        with self.db.get_sqlite_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT session_id, student_id, lesson_id, started_at, status, completed_steps, total_steps
                FROM sessions
                ORDER BY started_at DESC
                LIMIT ?;
                """,
                (limit,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_session_events(self, session_id: str) -> List[dict]:
        """Lấy toàn bộ dòng sự kiện của một session."""
        if self.db.mysql_available:
            try:
                conn = self.db.get_mysql_connection()
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT id, timestamp, iso_time, event_type, lesson_id, step_index, cell, metadata
                        FROM events
                        WHERE session_id = %s
                        ORDER BY id ASC;
                        """,
                        (session_id,),
                    )
                    raw_rows = cursor.fetchall()
                conn.close()
                rows = []
                for r in raw_rows:
                    d = dict(r)
                    if isinstance(d.get("metadata"), str):
                        try:
                            d["metadata"] = json.loads(d["metadata"])
                        except Exception:
                            pass
                    rows.append(d)
                return rows
            except Exception as e:
                print(f"[TimelineViewer] Lỗi MySQL: {e}")

        with self.db.get_sqlite_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, timestamp, iso_time, event_type, lesson_id, step_index, cell, metadata
                FROM events
                WHERE session_id = ?
                ORDER BY id ASC;
                """,
                (session_id,),
            )
            rows = []
            for r in cursor.fetchall():
                d = dict(r)
                if isinstance(d.get("metadata"), str):
                    try:
                        d["metadata"] = json.loads(d["metadata"])
                    except Exception:
                        pass
                rows.append(d)
            return rows

    def print_timeline(self, session_id: str):
        """In bảng dòng thời gian sự kiện trực quan ra console."""
        events = self.get_session_events(session_id)
        if not events:
            print(f"Không tìm thấy sự kiện nào cho session: {session_id}")
            return

        print("=" * 80)
        print(f"🕒 EVENT TIMELINE FOR SESSION: {session_id} (Tổng: {len(events)} sự kiện)")
        print("=" * 80)
        print(f"{'TIME':<12} | {'EVENT TYPE':<26} | {'CELL':<8} | {'DETAILS'}")
        print("-" * 80)

        for e in events:
            iso = e.get("iso_time", "").split("T")[-1][:8]
            etype = e.get("event_type", "")
            cell = e.get("cell", "")
            meta = e.get("metadata", {})
            meta_str = ", ".join(f"{k}={v}" for k, v in meta.items() if k not in {"sheet", "workbook"})
            print(f"{iso:<12} | {etype:<26} | {cell:<8} | {meta_str}")

        print("=" * 80)


if __name__ == "__main__":
    viewer = TimelineViewer()
    sessions = viewer.list_recent_sessions(5)
    print("Các phiên học gần nhất:")
    for s in sessions:
        print(s)
    if sessions:
        viewer.print_timeline(sessions[0]["session_id"])
