"""Render nhanh giao diện mascot/overlay để kiểm tra bằng mắt ở chế độ offscreen."""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image, ImageDraw
from PyQt6.QtWidgets import QApplication

from src.gui.companion_widget import CompanionWidget
from src.gui.overlay_window import _ScreenOverlay


def main() -> None:
    app = QApplication.instance() or QApplication([])
    output_dir = Path("artifacts")
    output_dir.mkdir(exist_ok=True)

    companion = CompanionWidget()
    companion.update_tutor_ui(
        {
            "agent_status": "observing",
            "mode_badge": "MỨC 3 · KHOANH VÙNG TRỰC QUAN",
            "hint_level": 3,
            "step_title": "Chọn đúng toàn bộ vùng dữ liệu",
            "hint_text": "Hãy kéo chuột từ ô D8 đến ô H15. Khung đỏ đang bao trọn vùng cần thao tác.",
            "lesson_title": "Bài 08 · Nhập dữ liệu chuẩn",
            "step_position": "Bước 2/5",
            "progress_percent": 40,
            "can_request_hint": False,
            "can_continue": False,
            "procedure_active": True,
            "action_position": "2/4",
            "action_title": "Mở thẻ Home",
            "action_kind": "ribbon_tab",
            "action_instruction": "Trên thanh Ribbon, bấm thẻ Home. Gia sư sẽ tự nhận biết và chuyển bước.",
            "procedure_actions": [
                {"number": 1, "title": "Chọn chính xác F7:F10", "status": "done"},
                {"number": 2, "title": "Mở thẻ Home", "status": "current"},
                {"number": 3, "title": "Mở danh sách Number Format", "status": "pending"},
                {"number": 4, "title": "Chọn Text", "status": "pending"},
            ],
            "verification_state": "waiting",
            "verification_message": "Đang chờ bạn mở đúng thẻ Home trên Ribbon.",
            "next_action_preview": "Mở danh sách Number Format",
            "can_advance_action": True,
        }
    )
    companion.show()
    app.processEvents()
    companion.grab().save(str(output_dir / "companion-mascot-preview.png"))

    surface = _ScreenOverlay(app.primaryScreen())
    surface.setGeometry(0, 0, 1100, 480)
    surface.set_local_target(
        (138, 210, 720, 155),
        "THAO TÁC TẠI: D8:H15",
        "teaching",
    )
    surface.show()
    app.processEvents()
    transparent_path = output_dir / "overlay-transparent-preview.png"
    surface.grab().save(str(transparent_path))

    # Ghép lên một nền bảng tính giả lập để đánh giá độ che phủ thực tế.
    base = Image.new("RGB", (1100, 480), "#FAFAFA")
    draw = ImageDraw.Draw(base)
    for x in range(4, 1100, 45):
        draw.line((x, 0, x, 480), fill="#D9DDE3", width=1)
    for y in range(6, 480, 26):
        draw.line((0, y, 1100, y), fill="#D9DDE3", width=1)
    overlay = Image.open(transparent_path).convert("RGBA")
    base.paste(overlay, (0, 0), overlay)
    base.save(output_dir / "overlay-mascot-preview.png")

    surface.close()
    companion.close()


if __name__ == "__main__":
    main()
