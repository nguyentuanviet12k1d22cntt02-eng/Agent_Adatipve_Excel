"""
Unit Test: Kiểm thử các thành phần của Kiến trúc Kỹ thuật Zero-Lag Realtime
(GeometryCache, ExcelEventsHandler, Lazy Ribbon Sensing, Decoupled Worker).
"""

import os
import sys
import time
import unittest
from unittest.mock import MagicMock, patch

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.core.excel_monitor import GeometryCache, ExcelEventsHandler, ExcelMonitor
from src.core.realtime_teaching_agent import RealtimeTeachingAgent
from src.core.lesson_models import SessionStatus, ProcedureActionKind, ProcedureAction


class TestZeroLagArchitecture(unittest.TestCase):
    def test_geometry_cache_basic_and_ttl(self):
        """Kiểm tra lưu trữ, truy xuất và hết hạn TTL của GeometryCache."""
        cache = GeometryCache(ttl=0.1)
        key = (12345, "Sheet1", "C8", 1, 1, 100.0)
        rect = (100, 200, 80, 25)

        # Ban đầu chưa có
        self.assertIsNone(cache.get(key))

        # Lưu và lấy
        cache.set(key, rect)
        self.assertEqual(cache.get(key), rect)

        # Chờ TTL hết hạn
        time.sleep(0.12)
        self.assertIsNone(cache.get(key))

    def test_geometry_cache_clear(self):
        """Kiểm tra dọn dẹp cache."""
        cache = GeometryCache(ttl=10.0)
        cache.set(("k1",), (10, 20, 30, 40))
        self.assertIsNotNone(cache.get(("k1",)))
        cache.clear()
        self.assertIsNone(cache.get(("k1",)))

    def test_excel_events_handler_dispatch(self):
        """Kiểm tra bộ gom sự kiện ExcelEventsHandler thông báo chính xác tới các callback."""
        handler = ExcelEventsHandler()
        events_received = []

        def sample_cb(event_name, *args):
            events_received.append((event_name, args))

        handler.add_callback(sample_cb)

        # Giả lập Excel COM bắn sự kiện
        mock_sheet = MagicMock()
        mock_target = MagicMock()
        handler.OnSheetSelectionChange(mock_sheet, mock_target)
        handler.OnSheetChange(mock_sheet, mock_target)
        handler.OnWorkbookActivate(mock_sheet)
        handler.OnSheetActivate(mock_sheet)

        self.assertEqual(len(events_received), 4)
        self.assertEqual(events_received[0][0], "SheetSelectionChange")
        self.assertEqual(events_received[1][0], "SheetChange")
        self.assertEqual(events_received[2][0], "WorkbookActivate")
        self.assertEqual(events_received[3][0], "SheetActivate")

    def test_needs_ribbon_sensing_lazy_activation(self):
        """Kiểm tra RealtimeTeachingAgent chỉ bật needs_ribbon_sensing khi ở đúng vi-bước Ribbon."""
        agent = RealtimeTeachingAgent(
            range_reader=lambda s, r: {},
            rect_resolver=lambda r, s: None,
        )
        agent.start_lesson("BAI_07")

        # Ở trạng thái ban đầu WAITING_FOR_EXCEL -> needs_ribbon_sensing phải là False
        self.assertFalse(agent.needs_ribbon_sensing)

        # Chuyển sang trạng thái OBSERVING
        agent.session.status = SessionStatus.OBSERVING

        # Bước 1 của BAI_07 là SELECT_RANGE (không có thao tác Ribbon)
        self.assertFalse(agent.needs_ribbon_sensing)

        # Giả lập một bước có ProcedureActionKind.RIBBON_TAB
        step = agent.current_step
        if step:
            mock_action = ProcedureAction(
                id="test_ribbon",
                title="Bấm thẻ Home",
                instruction="Bấm Home",
                kind=ProcedureActionKind.RIBBON_TAB,
            )
            with patch.object(agent, "_actions_for_step", return_value=(mock_action,)):
                self.assertTrue(agent.needs_ribbon_sensing)

    def test_excel_monitor_get_state_lazy_ribbon(self):
        """Kiểm tra get_state(needs_ribbon=False) bỏ qua ribbon observer."""
        monitor = ExcelMonitor()
        monitor._ribbon_observer = MagicMock()

        # Mock connect để bài test độc lập với việc Excel ngoài máy tính có đang mở hay không
        with patch.object(monitor, "connect", return_value=False):
            state = monitor.get_state(needs_ribbon=False)
            self.assertFalse(state["connected"])
            self.assertFalse(state["ribbon_available"])
            monitor._ribbon_observer.get_state.assert_not_called()


if __name__ == "__main__":
    unittest.main()
