"""
Main Entry Point: Khởi chạy Hệ thống Gia Sư AI Thực hành Excel (Zero-Lag Architecture)
Kiến trúc Tác tử bất đồng bộ (Decoupled QThread Worker + Push Event-Driven COM).
"""

import sys
import os
from PyQt6.QtWidgets import QApplication

# Đảm bảo đường dẫn import
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.core.excel_worker import ExcelObserverWorker
from src.gui.overlay_window import OverlayWindow
from src.gui.companion_widget import CompanionWidget
from src.gui.mascot_assets import visual_state_for_guidance


class AITutorApp:
    def __init__(self):
        # 1. Khởi tạo Giao diện Trực quan (Hoàn toàn chạy trên Main GUI Thread 60 FPS)
        self.overlay_window = OverlayWindow()
        self.companion_widget = CompanionWidget()

        # 2. Khởi tạo Worker Thread chạy độc lập chuyên trách COM STA & Tác tử MCP
        self.worker = ExcelObserverWorker(hesitation_threshold=3.5, poll_interval_ms=50)

        # 3. Kết nối các tín hiệu từ Companion Widget tới Worker Thread qua hàng đợi Thread-Safe
        self.companion_widget.open_exercise_signal.connect(self.on_open_exercise)
        self.companion_widget.request_hint_signal.connect(self.worker.post_request_hint)
        self.companion_widget.repeat_instruction_signal.connect(self.worker.post_repeat_instruction)
        self.companion_widget.toggle_pause_signal.connect(self.worker.post_toggle_pause)
        self.companion_widget.continue_step_signal.connect(self.worker.post_continue_step)
        self.companion_widget.submit_reflection_signal.connect(self.on_submit_reflection)

        # 4. Nhận dữ liệu đẩy từ Worker Thread về Main GUI Thread
        self.worker.guidance_ready.connect(self.apply_guidance)
        self.worker.exercise_launched.connect(self.on_exercise_launched)
        self.worker.worker_error.connect(self.on_worker_error)

        # Lưu lại câu hỏi phản biện hiện tại
        self.current_teachable_question = ""

        # Hiển thị các cửa sổ giao diện
        self.overlay_window.show()
        self.companion_widget.show()

        # 5. Khởi động luồng quan sát COM bất đồng bộ
        self.worker.start()

    def on_open_exercise(self, exercise_code: str):
        """Học viên chọn bài tập -> Gửi yêu cầu sang luồng Worker."""
        self.companion_widget.step_label.setText(f"Đang mở Bài {exercise_code} qua Excel COM...")
        self.overlay_window.clear_target()
        self.worker.post_open_exercise(exercise_code)

    def on_exercise_launched(self, res: dict):
        """Nhận kết quả mở bài tập từ Worker Thread."""
        exercise_code = res.get("exercise_code", "")
        if res.get("success"):
            self.companion_widget.step_label.setText(f"Đã mở Bài {exercise_code}. Agent đang chờ Excel sẵn sàng.")
            self.overlay_window.clear_target()
        else:
            self.companion_widget.step_label.setText(f"Lỗi: {res.get('error', 'Không thể mở Excel')}")

    def on_worker_error(self, err_msg: str):
        print(f"[AITutorApp] Cảnh báo Worker: {err_msg}")

    def on_submit_reflection(self, answer_text: str):
        """Học viên trả lời câu hỏi phản biện của Teachable Agent."""
        self.worker.post_submit_reflection(self.current_teachable_question, answer_text)

    def apply_guidance(self, guidance: dict):
        """Đồng bộ một quyết định của Agent lên thẻ hướng dẫn và overlay (Chạy thuần trên GUI)."""
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

    def cleanup(self):
        """Dừng worker thread trước khi đóng ứng dụng."""
        if hasattr(self, "worker") and self.worker.isRunning():
            self.worker.stop()


def main():
    # Kích hoạt High DPI scaling
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"

    app = QApplication(sys.argv)
    tutor_app = AITutorApp()
    app.aboutToQuit.connect(tutor_app.cleanup)

    print("=" * 70)
    print("🚀 HỆ THỐNG GIA SƯ AI EXCEL (ZERO-LAG REALTIME ARCHITECTURE) ĐÃ KHỞI CHẠY!")
    print("   - Giao thức: Model Context Protocol (MCP 2.x)")
    print("   - Kiến trúc luồng: Decoupled QThread Worker + STA COM Apartment")
    print("   - Cơ chế bắt sự kiện: Push Event Sink (< 5ms phản hồi)")
    print("   - Tối ưu hóa: Geometry Viewport Cache + Lazy Ribbon Sensing")
    print("=" * 70)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
