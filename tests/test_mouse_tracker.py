"""
Unit Test: Kiểm thử chức năng đo tốc độ chuột và phân tích hành vi trong MouseSpeedTracker.
"""

import os
import sys
import unittest
import time

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.core.mouse_tracker import MouseSpeedTracker


class TestMouseSpeedTracker(unittest.TestCase):
    def setUp(self):
        self.tracker = MouseSpeedTracker(excel_monitor=None, smoothing_alpha=0.5)

    def test_idle_state(self):
        """Kiểm tra nhận diện trạng thái tĩnh và ngập ngừng."""
        # Khởi tạo vị trí ban đầu
        self.tracker.update(custom_pos=(100, 100))
        time.sleep(0.05)
        # Giữ nguyên tại (100, 100) trong 10 chu kỳ tiếp theo
        for _ in range(15):
            res = self.tracker.update(custom_pos=(100, 100))
            time.sleep(0.02)
        
        self.assertLess(res["speed"], 10.0)
        self.assertIn(res["state_code"], ["IDLE", "HESITATING"])

    def test_precision_movement(self):
        """Kiểm tra dải tốc độ điều hướng chính xác (20 - 350 px/s)."""
        x, y = 100, 100
        for _ in range(15):
            x += 5
            y += 2
            res = self.tracker.update(custom_pos=(x, y))
            time.sleep(0.04)

        self.assertGreater(res["speed"], 20.0)
        self.assertLess(res["speed"], 400.0)
        self.assertEqual(res["state_code"], "PRECISION")

    def test_speed_history_sparkline(self):
        """Kiểm tra bộ đệm lịch sử tốc độ cho đồ thị sóng."""
        for i in range(70):
            self.tracker.update(custom_pos=(100 + i, 100))
        
        self.assertEqual(len(self.tracker.speed_history), 60)


if __name__ == "__main__":
    unittest.main()
