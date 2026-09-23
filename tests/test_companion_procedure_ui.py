"""Regression test cho CTA xác nhận thao tác Ribbon."""

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from src.gui.companion_widget import CompanionWidget


class CompanionProcedureUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_ribbon_fallback_button_is_clearly_enabled_and_clickable(self):
        widget = CompanionWidget()
        emitted = []
        widget.continue_step_signal.connect(lambda: emitted.append(True))
        widget.update_tutor_ui(
            {
                "procedure_active": True,
                "procedure_actions": [
                    {
                        "number": 1,
                        "title": "Chọn chính xác F7:F10",
                        "status": "done",
                    },
                    {"number": 2, "title": "Mở thẻ Home", "status": "current"},
                ],
                "action_position": "2/4",
                "action_title": "Mở thẻ Home",
                "action_kind": "ribbon_tab",
                "verification_state": "waiting",
                "verification_message": "Đang chờ bạn mở đúng thẻ Home trên Ribbon.",
                "next_action_preview": "Mở danh sách Number Format",
                "hint_text": "Trên thanh Ribbon, bấm thẻ Home.",
                "lesson_title": "Các bước cần thực hiện trước khi nhập dữ liệu",
                "step_position": "Bước 2/10",
                "progress_percent": 15,
                "agent_status": "observing",
                "hint_level": 1,
                "can_request_hint": True,
                "can_advance_action": True,
            }
        )

        self.assertTrue(widget.btn_understood.isEnabled())
        self.assertEqual(widget.btn_understood.text(), "Đã mở Home")
        self.assertEqual(
            widget.btn_understood.accessibleName(),
            "Xác nhận đã mở thẻ Home",
        )
        self.assertIn("#2563EB", widget.btn_understood.styleSheet())
        widget.btn_understood.click()
        self.app.processEvents()
        self.assertEqual(emitted, [True])
        widget.close()


if __name__ == "__main__":
    unittest.main()
