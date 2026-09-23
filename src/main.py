"""
Main Entry Point: Khởi chạy Hệ thống Gia Sư AI Thực hành Excel
Kiến trúc Tác tử kết nối qua Giao thức Model Context Protocol (MCP).
"""

import sys
import os
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer

# Đảm bảo đường dẫn import
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.excel_mcp.agent_client import AITutorMCPAgent
from src.gui.overlay_window import OverlayWindow
from src.gui.companion_widget import CompanionWidget
from src.gui.mascot_assets import visual_state_for_guidance


class AITutorApp:
    def __init__(self):
        # 1. Khởi tạo Tác tử Gia sư AI kết nối qua MCP
        self.agent = AITutorMCPAgent(hesitation_threshold=3.5)

        # 2. Khởi tạo Giao diện Trực quan
        self.overlay_window = OverlayWindow()
        self.companion_widget = CompanionWidget()

        # 3. Kết nối các tín hiệu tương tác từ Companion Widget
        self.companion_widget.open_exercise_signal.connect(self.on_open_exercise)
        self.companion_widget.request_hint_signal.connect(self.on_request_hint)
        self.companion_widget.repeat_instruction_signal.connect(self.on_repeat_instruction)
        self.companion_widget.toggle_pause_signal.connect(self.on_toggle_pause)
        self.companion_widget.continue_step_signal.connect(self.on_continue_step)
        self.companion_widget.submit_reflection_signal.connect(self.on_submit_reflection)

        # 4. Timer vòng lặp nhận thức & hành động của Tác tử MCP (chu kỳ 300ms)
        self.agent_timer = QTimer()
        self.agent_timer.timeout.connect(self.on_agent_tick)
        self.agent_timer.start(300)

        # Lưu lại câu hỏi phản biện hiện tại
        self.current_teachable_question = ""

        # Hiển thị các cửa sổ giao diện
        self.overlay_window.show()
        self.companion_widget.show()

    def on_open_exercise(self, exercise_code: str):
        """Học viên chọn bài tập -> Agent gọi MCP tool khởi chạy file."""
        res = self.agent.set_exercise(exercise_code)
        guidance = res.get("guidance", {})
        if guidance:
            self.apply_guidance(guidance)
        if res.get("success"):
            self.companion_widget.step_label.setText(f"Đã mở Bài {exercise_code}. Agent đang chờ Excel sẵn sàng.")
            self.overlay_window.clear_target()
        else:
            self.companion_widget.step_label.setText(f"Lỗi: {res.get('error', 'Không thể mở Excel')}")

    def on_request_hint(self):
        """Học viên chủ động yêu cầu nâng cấp gợi ý."""
        guidance = self.agent.request_next_hint()
        if guidance:
            self.apply_guidance(guidance)

    def on_repeat_instruction(self):
        self.apply_guidance(self.agent.repeat_instruction())

    def on_toggle_pause(self):
        self.apply_guidance(self.agent.toggle_pause())

    def on_continue_step(self):
        self.apply_guidance(self.agent.continue_lesson())

    def on_submit_reflection(self, answer_text: str):
        """Học viên trả lời câu hỏi phản biện của Teachable Agent."""
        self.agent.evaluate_student_reflection(
            question=self.current_teachable_question,
            answer=answer_text
        )
        guidance = self.agent.runtime.last_guidance
        if guidance:
            self.apply_guidance(guidance)

    def on_agent_tick(self):
        """Vòng lặp chu kỳ nhận thức của Tác tử MCP mỗi 300ms."""
        # Tác tử thực hiện 1 bước nhận thức & suy luận qua MCP
        guidance = self.agent.step()

        self.apply_guidance(guidance)

    def apply_guidance(self, guidance: dict):
        """Đồng bộ một quyết định của Agent lên thẻ hướng dẫn và overlay."""

        # Lưu câu hỏi phản biện nếu đang ở chế độ Teachable Agent
        if guidance.get("teachable_active"):
            self.current_teachable_question = guidance.get("reflection_question", "")

        # Cập nhật Thẻ Gia Sư Nổi
        self.companion_widget.update_tutor_ui(guidance)

        # Cập nhật Lớp phủ Overlay Khoanh Vùng Trực Quan (Mức 3)
        target_rect = guidance.get("target_rect")
        if target_rect:
            badge_text = guidance.get("badge_text", "👉 THAO TÁC Ở ĐÂY")
            self.overlay_window.set_target_rect(
                rect=target_rect,
                is_physical_pixels=True,
                badge_text=badge_text,
                visual_state=visual_state_for_guidance(guidance),
            )
        else:
            self.overlay_window.clear_target()


def main():
    # Kích hoạt High DPI scaling
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"

    app = QApplication(sys.argv)
    tutor_app = AITutorApp()
    print("=" * 65)
    print("🚀 HỆ THỐNG GIA SƯ AI EXCEL (KIẾN TRÚC MCP 2.X) ĐÃ KHỞI CHẠY!")
    print("   - Giao thức: Model Context Protocol (MCP)")
    print("   - Tầng Tác tử: AITutorMCPAgent (stdio/tools)")
    print("   - Tầng Giám sát: Excel MCP Server (Dynamic COM + Mouse Telemetry)")
    print("=" * 65)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
