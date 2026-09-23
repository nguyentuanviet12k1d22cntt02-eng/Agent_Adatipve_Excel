"""
Feature Extractor: Trích xuất vector đặc trưng hành vi người học từ dòng sự kiện Telemetry thô (Events).
Căn cứ: Mục tiêu Phase 1 & Phase 2 trong Ke_hoach_Excel_AI_Tutor_ML_Agent.docx.
Tính toán 4 nhóm đặc trưng: Thời gian, Động lực học chuột, Lỗi thao tác, Hiệu suất.
"""

import json
import time
from typing import Any, Dict, List, Optional
from src.data_collection.db_manager import DatabaseManager


class FeatureExtractor:
    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db = db_manager or DatabaseManager()

    def extract_features_from_events(self, events: List[Dict[str, Any]], session_meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Trích xuất vector 4 nhóm đặc trưng từ danh sách sự kiện thô của một bước hoặc một phiên.
        """
        if not events:
            return {
                "time_on_task": 0.0,
                "mouse_idle_avg": 0.0,
                "mouse_idle_max": 0.0,
                "mouse_speed_mean": 0.0,
                "wrong_attempts": 0,
                "formula_errors": 0,
                "undo_count": 0,
                "retry_count": 0,
                "selection_changes": 0,
                "hint_requests": 0,
                "completion_rate": 0.0,
            }

        timestamps = [e.get("timestamp", 0.0) for e in events if e.get("timestamp")]
        start_ts = min(timestamps) if timestamps else 0.0
        end_ts = max(timestamps) if timestamps else 0.0
        time_on_task = max(0.0, end_ts - start_ts)

        # 1. Đặc trưng ngập ngừng & chuột
        hesitation_durations = []
        mouse_speeds = []
        selection_changes = 0
        formula_errors = 0
        wrong_attempts = 0
        undo_count = 0
        retry_count = 0
        hint_requests = 0

        cell_edit_history: Dict[str, int] = {}

        for e in events:
            etype = e.get("event_type", "")
            meta = e.get("metadata", {})
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except Exception:
                    meta = {}

            if "HESITATION" in etype:
                duration = float(meta.get("hesitation_duration_sec", 0.0))
                if duration > 0:
                    hesitation_durations.append(duration)

            if "speed" in meta:
                try:
                    mouse_speeds.append(float(meta["speed"]))
                except (ValueError, TypeError):
                    pass

            if etype in ("CELL_SELECTION", "RANGE_SELECTION"):
                selection_changes += 1

            if etype == "FORMULA_ENTRY":
                cell = e.get("cell", "")
                if cell:
                    cell_edit_history[cell] = cell_edit_history.get(cell, 0) + 1
                    if cell_edit_history[cell] > 1:
                        retry_count += 1

                # Kiểm tra lỗi công thức
                has_error = (
                    not meta.get("is_valid", True)
                    or "error" in str(meta).lower()
                    or any(err in str(meta) for err in ("#NAME?", "#VALUE!", "#REF!", "#N/A", "#DIV/0!"))
                )
                if has_error:
                    formula_errors += 1
                    wrong_attempts += 1

            if "UNDO" in etype:
                undo_count += 1

            if "HINT" in etype:
                hint_requests += 1

        mouse_idle_avg = sum(hesitation_durations) / len(hesitation_durations) if hesitation_durations else 0.0
        mouse_idle_max = max(hesitation_durations) if hesitation_durations else 0.0
        mouse_speed_mean = sum(mouse_speeds) / len(mouse_speeds) if mouse_speeds else 0.0

        # Tỷ lệ hoàn thành
        completion_rate = 0.0
        if session_meta:
            total_steps = session_meta.get("total_steps", 0)
            completed_steps = session_meta.get("completed_steps", 0)
            if total_steps > 0:
                completion_rate = min(1.0, completed_steps / total_steps)

        return {
            "time_on_task": round(time_on_task, 2),
            "mouse_idle_avg": round(mouse_idle_avg, 2),
            "mouse_idle_max": round(mouse_idle_max, 2),
            "mouse_speed_mean": round(mouse_speed_mean, 2),
            "wrong_attempts": wrong_attempts,
            "formula_errors": formula_errors,
            "undo_count": undo_count,
            "retry_count": retry_count,
            "selection_changes": selection_changes,
            "hint_requests": hint_requests,
            "completion_rate": round(completion_rate, 2),
        }

    def compute_and_save_session_features(self, session_id: str, step_index: int = 0) -> Dict[str, Any]:
        """
        Đọc các events của session từ MySQL, tính toán vector đặc trưng và lưu vào bảng features.
        """
        events = []
        session_meta = None

        if self.db.mysql_available:
            try:
                conn = self.db.get_mysql_connection()
                with conn.cursor() as cur:
                    cur.execute("SELECT * FROM sessions WHERE session_id = %s;", (session_id,))
                    session_meta = cur.fetchone()

                    cur.execute(
                        "SELECT * FROM events WHERE session_id = %s ORDER BY id ASC;",
                        (session_id,),
                    )
                    events = cur.fetchall()

                conn.close()
            except Exception as e:
                print(f"[FeatureExtractor] Lỗi đọc MySQL: {e}")

        if not events:
            # Fallback SQLite
            with self.db.get_sqlite_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT * FROM sessions WHERE session_id = ?;", (session_id,))
                srow = cur.fetchone()
                if srow:
                    session_meta = dict(srow)

                cur.execute("SELECT * FROM events WHERE session_id = ? ORDER BY id ASC;", (session_id,))
                events = [dict(r) for r in cur.fetchall()]

        features = self.extract_features_from_events(events, session_meta)

        # Lưu vào bảng features
        self.save_features(session_id, step_index, features)
        return features

    def save_features(self, session_id: str, step_index: int, feat: Dict[str, Any]):
        """Lưu bản ghi đặc trưng vào MySQL hoặc SQLite."""
        if self.db.mysql_available:
            try:
                conn = self.db.get_mysql_connection()
                with conn.cursor() as cur:
                    sql = """
                    INSERT INTO features (
                        session_id, step_index, time_on_task, mouse_idle_avg, mouse_idle_max,
                        mouse_speed_mean, wrong_attempts, formula_errors, undo_count,
                        retry_count, selection_changes, hint_requests, completion_rate
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                    """
                    cur.execute(
                        sql,
                        (
                            session_id,
                            step_index,
                            feat.get("time_on_task", 0.0),
                            feat.get("mouse_idle_avg", 0.0),
                            feat.get("mouse_idle_max", 0.0),
                            feat.get("mouse_speed_mean", 0.0),
                            feat.get("wrong_attempts", 0),
                            feat.get("formula_errors", 0),
                            feat.get("undo_count", 0),
                            feat.get("retry_count", 0),
                            feat.get("selection_changes", 0),
                            feat.get("hint_requests", 0),
                            feat.get("completion_rate", 0.0),
                        ),
                    )
                conn.close()
                return
            except Exception as e:
                print(f"[FeatureExtractor] Lỗi ghi MySQL: {e}")

        # Fallback SQLite
        try:
            with self.db.get_sqlite_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO features (
                        session_id, step_index, time_on_task, mouse_idle_avg, mouse_idle_max,
                        mouse_speed_mean, wrong_attempts, formula_errors, undo_count,
                        retry_count, selection_changes, hint_requests, completion_rate
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        session_id,
                        step_index,
                        feat.get("time_on_task", 0.0),
                        feat.get("mouse_idle_avg", 0.0),
                        feat.get("mouse_idle_max", 0.0),
                        feat.get("mouse_speed_mean", 0.0),
                        feat.get("wrong_attempts", 0),
                        feat.get("formula_errors", 0),
                        feat.get("undo_count", 0),
                        feat.get("retry_count", 0),
                        feat.get("selection_changes", 0),
                        feat.get("hint_requests", 0),
                        feat.get("completion_rate", 0.0),
                    ),
                )
                conn.commit()
        except Exception as e:
            print(f"[FeatureExtractor] Lỗi ghi SQLite: {e}")
