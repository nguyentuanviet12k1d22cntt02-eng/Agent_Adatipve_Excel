"""
Unit Test: Kiểm thử toàn diện Hệ thống Thu thập Dữ liệu & Cảm biến (Phase 1 Data Collection).
Bao gồm: SelectionSensor, CellValueSensor, MouseSensor, TimingSensor, SensorManager, DatabaseManager, EventLogger, TimelineViewer.
"""

import os
import sys
import tempfile
import time
import unittest

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.sensors.base_sensor import RawEvent
from src.sensors.selection_sensor import SelectionSensor
from src.sensors.cell_value_sensor import CellValueSensor
from src.sensors.mouse_sensor import MouseSensor
from src.sensors.timing_sensor import TimingSensor
from src.sensors.sensor_manager import SensorManager
from src.data_collection.db_manager import DatabaseManager
from src.data_collection.event_logger import EventLogger
from src.data_collection.timeline_viewer import TimelineViewer


class TestPhase1DataCollection(unittest.TestCase):
    def test_selection_sensor(self):
        """Kiểm tra SelectionSensor bắt đúng chọn ô và quét vùng."""
        sensor = SelectionSensor()
        ctx = {"session_id": "TEST_S01", "lesson_id": "BAI_07", "step_index": 0}

        # 1. Chọn ô C8
        state1 = {"connected": True, "cell_clean_address": "C8", "selection_address": "C8", "is_range_selection": False}
        events = sensor.detect(state1, {}, ctx)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event_type, "CELL_SELECTION")
        self.assertEqual(events[0].cell, "C8")

        # 2. Không đổi ô -> không sinh event thừa
        events = sensor.detect(state1, {}, ctx)
        self.assertEqual(len(events), 0)

        # 3. Quét vùng F7:F10
        state2 = {
            "connected": True,
            "cell_clean_address": "F7",
            "selection_address": "F7:F10",
            "is_range_selection": True,
            "selection_rows": 4,
            "selection_columns": 1,
            "selection_area_count": 1,
        }
        events = sensor.detect(state2, {}, ctx)
        self.assertTrue(any(e.event_type == "RANGE_SELECTION" for e in events))

    def test_cell_value_sensor_and_errors(self):
        """Kiểm tra CellValueSensor phát hiện sửa giá trị, công thức và lỗi."""
        sensor = CellValueSensor()
        ctx = {"session_id": "TEST_S01", "lesson_id": "BAI_08", "step_index": 1}

        # Khởi tạo ô F7
        state1 = {"connected": True, "cell_clean_address": "F7", "cell_value": None, "cell_format": "General"}
        sensor.detect(state1, {}, ctx)

        # Gõ giá trị số điện thoại
        state2 = {"connected": True, "cell_clean_address": "F7", "cell_value": "0901234567", "cell_format": "General"}
        events = sensor.detect(state2, {}, ctx)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event_type, "CELL_VALUE_CHANGE")
        self.assertEqual(events[0].metadata["new_value"], "0901234567")

        # Gõ công thức bị lỗi #NAME?
        state3 = {"connected": True, "cell_clean_address": "F7", "cell_value": "=#NAME?", "cell_format": "General"}
        events = sensor.detect(state3, {}, ctx)
        types = [e.event_type for e in events]
        self.assertIn("FORMULA_ENTRY", types)
        self.assertIn("FORMULA_ERROR", types)

    def test_mouse_sensor_hesitation_and_erratic(self):
        """Kiểm tra MouseSensor nhận diện ngập ngừng và lúng túng."""
        sensor = MouseSensor()
        ctx = {"session_id": "TEST_S01"}

        # Chuột bình thường
        mouse1 = {"is_hesitating": False, "state_code": "NORMAL", "speed": 400.0, "idle_duration": 0.0}
        events = sensor.detect({"connected": True, "cell_clean_address": "C8"}, mouse1, ctx)
        self.assertEqual(len(events), 0)

        # Chuột rơi vào ngập ngừng (>2s)
        mouse2 = {"is_hesitating": True, "state_code": "IDLE", "speed": 0.0, "idle_duration": 2.5}
        events = sensor.detect({"connected": True, "cell_clean_address": "C8"}, mouse2, ctx)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event_type, "MOUSE_HESITATION_START")

        # Lắc chuột mạnh / bối rối (ERRATIC)
        mouse3 = {"is_hesitating": False, "state_code": "ERRATIC", "instant_speed": 2100.0, "max_speed": 2100.0}
        events = sensor.detect({"connected": True, "cell_clean_address": "C8"}, mouse3, ctx)
        types = [e.event_type for e in events]
        self.assertIn("ERRATIC_MOUSE_MOVEMENT", types)
        self.assertIn("MOUSE_HESITATION_END", types)

    def test_timing_sensor(self):
        """Kiểm tra TimingSensor ghi nhận bước học."""
        sensor = TimingSensor()
        ctx1 = {"session_id": "TEST_S01", "lesson_id": "BAI_07", "step_index": 0, "step_title": "Chọn ô B8"}
        events1 = sensor.detect({"cell_clean_address": "B8"}, {}, ctx1)
        self.assertEqual(events1[0].event_type, "STEP_STARTED")

        # Chuyển sang bước 1
        ctx2 = {"session_id": "TEST_S01", "lesson_id": "BAI_07", "step_index": 1, "step_title": "Nhập công thức"}
        events2 = sensor.detect({"cell_clean_address": "B8"}, {}, ctx2)
        types = [e.event_type for e in events2]
        self.assertIn("STEP_FINISHED", types)
        self.assertIn("STEP_STARTED", types)

    def test_database_and_event_logger_lifecycle(self):
        """Kiểm tra lưu trữ SQLite và bộ ghi log EventLogger bất đồng bộ."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
            temp_db_path = tf.name

        try:
            db_mgr = DatabaseManager(db_path=temp_db_path)
            logger = EventLogger(db_manager=db_mgr, batch_size=5, flush_interval=0.1)

            session_id = "SES_TEST_999"
            logger.start_session(session_id=session_id, student_id="ST_01", lesson_id="BAI_07")

            # Ghi một số sự kiện
            for i in range(10):
                ev = RawEvent(
                    event_type="CELL_SELECTION",
                    session_id=session_id,
                    lesson_id="BAI_07",
                    step_index=0,
                    cell=f"A{i+1}",
                    metadata={"index": i},
                )
                logger.log_event(ev)

            # Chờ worker loop flush hoặc flush thủ công
            logger.flush()
            logger.end_session(session_id=session_id, status="COMPLETED", total_steps=7, completed_steps=7)
            logger.close()

            # Kiểm tra dữ liệu trong SQLite qua TimelineViewer
            viewer = TimelineViewer(db_manager=db_mgr)
            sessions = viewer.list_recent_sessions(5)
            self.assertEqual(len(sessions), 1)
            self.assertEqual(sessions[0]["session_id"], session_id)
            self.assertEqual(sessions[0]["status"], "COMPLETED")

            events = viewer.get_session_events(session_id)
            self.assertEqual(len(events), 10)
            self.assertEqual(events[0]["cell"], "A1")
            self.assertEqual(events[9]["cell"], "A10")
        finally:
            if os.path.exists(temp_db_path):
                try:
                    os.remove(temp_db_path)
                except Exception:
                    pass


if __name__ == "__main__":
    unittest.main()
