"""
Unit Test: Kiểm tra hoạt động của Excel MCP Server và AI Tutor Agent qua giao thức MCP.
"""

import sys
import os
import unittest
from unittest.mock import patch

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.excel_mcp.server import (
    excel_get_cell_rect,
    excel_get_active_state,
    mouse_get_telemetry,
    pedagogy_evaluate_step,
    excel_write_cell
)
from src.excel_mcp.agent_client import AITutorMCPAgent


class TestMCPSystem(unittest.TestCase):
    def test_mcp_tool_get_cell_rect(self):
        """Kiểm tra MCP tool excel_get_cell_rect trả về định dạng chuẩn."""
        # Không dựa vào tọa độ fallback hard-code: tool chỉ báo success khi lấy
        # được tọa độ live từ ExcelMonitor.
        with patch(
            "src.excel_mcp.server.excel_monitor.get_cell_rect_by_address",
            return_value=(467, 697, 119, 41),
        ):
            res = excel_get_cell_rect("c8")
        self.assertTrue(res["success"])
        self.assertEqual(res["cell_address"], "C8")
        self.assertIn("x", res)
        self.assertIn("y", res)
        self.assertGreater(res["width"], 0)
        self.assertGreater(res["height"], 0)

    def test_mcp_tool_mouse_telemetry(self):
        """Kiểm tra MCP tool mouse_get_telemetry trả về trạng thái hợp lệ."""
        res = mouse_get_telemetry()
        self.assertIn("speed", res)
        self.assertIn("state_code", res)
        self.assertIn("state_label", res)

    def test_mcp_tool_pedagogy_evaluation(self):
        """Kiểm tra MCP tool pedagogy_evaluate_step bắt lỗi đảo ngược '8B'."""
        eval_res = pedagogy_evaluate_step(
            exercise_id="BAI_07",
            cell_address="C8",
            cell_value="8B"
        )
        self.assertFalse(eval_res["is_correct"])
        self.assertEqual(eval_res["error_type"], "REVERSED_ADDRESS")
        self.assertIn("Tên Cột", eval_res["hint_level_1"])

    def test_mcp_tool_write_cell(self):
        """Kiểm tra MCP tool excel_write_cell cấu trúc trả về chuẩn."""
        res = excel_write_cell("C8", "B8")
        self.assertIn("success", res)
        self.assertEqual(res["cell_address"], "C8")
        if res["success"]:
            self.assertEqual(res["written_value"], "B8")


if __name__ == "__main__":
    unittest.main()
