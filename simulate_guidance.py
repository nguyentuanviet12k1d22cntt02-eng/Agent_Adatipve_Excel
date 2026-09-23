"""
Guidance Simulator: Bộ giả lập quy trình Hướng dẫn Sư phạm Phân cấp (Graduated Prompting)
và Tác tử Học tập Phản biện (Teachable Agent).
Tự động định vị ô tính chính xác 100% trên Excel và luôn hiển thị nổi Always-On-Top.
"""

import sys
import os
import time
from typing import Optional, Tuple
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QComboBox, QTextBrowser, QProgressBar
)
from PyQt6.QtCore import Qt, QTimer, QPoint
from PyQt6.QtGui import QColor, QFont

# Đảm bảo đường dẫn import
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.gui.companion_widget import CompanionWidget
from src.gui.overlay_window import OverlayWindow
from src.ai.tutor_agent import TutorAgent
from src.core.excel_monitor import ExcelMonitor


class GuidanceSimulatorControl(QWidget):
    """
    Bảng điều khiển Giả lập kịch bản Hướng dẫn Sư phạm với khả năng bắt tọa độ Excel động.
    """
    def __init__(self, companion_widget: CompanionWidget, overlay_window: OverlayWindow):
        super().__init__()
        self.companion = companion_widget
        self.overlay = overlay_window
        self.tutor_agent = TutorAgent()
        self.excel_monitor = ExcelMonitor()
        self.excel_monitor.connect()

        self.current_scenario = "BAI_07"
        self.current_step_idx = 0
        self.auto_timer = QTimer(self)
        self.auto_timer.timeout.connect(self._auto_step_tick)

        # Timer liên tục cập nhật lại tọa độ ô nếu người dùng cuộn chuột hoặc đổi kích thước Excel
        self.sync_timer = QTimer(self)
        self.sync_timer.timeout.connect(self._sync_active_overlay)
        self.sync_timer.start(200)

        # Định nghĩa các kịch bản sư phạm giả lập
        self._init_scenarios()
        self.init_ui()

        # Áp dụng bước đầu tiên
        self.apply_step(0)

    def _init_scenarios(self):
        """Kịch bản các bước hướng dẫn cụ thể theo tiến trình học viên."""
        self.scenarios = {
            "BAI_07": {
                "title": "Bài 07: Thao tác với Địa chỉ ô (Cell Address)",
                "exercise_file": "Bài 07. Các thao tác cơ bản với địa chỉ ô.xlsx",
                "steps": [
                    {
                        "name": "Bước 1: Giới thiệu & Quan sát ô mẫu (Bắt đầu bài học)",
                        "speed_sim": 350.0,
                        "idle_sim": 0.0,
                        "pedagogy": "Học viên vừa mở bài. AI hướng dẫn quan sát dòng 7 mẫu để nhận diện quy luật trước khi tự làm.",
                        "target_cell": None,
                        "badge_text": "",
                        "prompt_info": {
                            "mode_badge": "ĐANG LẮNG NGHE THAO TÁC",
                            "hint_level": 1,
                            "step_title": "Bài 07: Xác định Địa chỉ ô cho 'Rồng'",
                            "hint_text": "📖 HƯỚNG DẪN BẮT ĐẦU:\n1. Quan sát dòng số 7 đã làm mẫu: Ô B7 chứa '1988' -> Địa chỉ là 'B7', Cột 'B', Dòng '7'.\n2. Bây giờ đến lượt bạn làm dòng 8: Ô B8 đang chứa chữ 'Rồng'.\n👉 Mục tiêu: Điền địa chỉ của ô chứa chữ 'Rồng' vào ô C8!",
                            "is_correct": False,
                            "teachable_active": False,
                        }
                    },
                    {
                        "name": "Bước 2: Chuột đứng yên 4.2s (Ngập ngừng / Hesitation)",
                        "speed_sim": 0.0,
                        "idle_sim": 4.2,
                        "pedagogy": "Phát hiện chuột dừng quá 3.5s. Kích hoạt Mức 1: Đặt câu hỏi kích hoạt tư duy, không làm hộ.",
                        "target_cell": None,
                        "badge_text": "",
                        "prompt_info": {
                            "mode_badge": "MỨC 1: ĐỊNH HƯỚNG TƯ DUY",
                            "hint_level": 1,
                            "step_title": "Định hướng xác định ô C8",
                            "hint_text": "🤔 Câu hỏi tư duy:\nĐể ghép thành địa chỉ của một ô trong Excel, ta viết Tên Cột (Chữ cái) hay Số Dòng (Con số) đứng trước bạn nhỉ?",
                            "is_correct": False,
                            "teachable_active": False,
                        }
                    },
                    {
                        "name": "Bước 3: Ngập ngừng kéo dài thêm (Chỉ dẫn công cụ Mức 2)",
                        "speed_sim": 12.0,
                        "idle_sim": 7.5,
                        "pedagogy": "Học viên vẫn chưa thao tác. Tự động nâng cấp lên Mức 2: Chỉ rõ công thức ghép tọa độ.",
                        "target_cell": None,
                        "badge_text": "",
                        "prompt_info": {
                            "mode_badge": "MỨC 2: CHỈ DẪN CÔNG CỤ",
                            "hint_level": 2,
                            "step_title": "Quy ước ghép tọa độ ô",
                            "hint_text": "💡 Quy ước chuẩn của Excel:\nĐịa chỉ ô = [Tên Cột][Số Dòng].\nÔ chứa chữ 'Rồng' nằm ở Cột B và Dòng 8, vậy ghép lại là 'B8'.",
                            "is_correct": False,
                            "teachable_active": False,
                        }
                    },
                    {
                        "name": "Bước 4: Bế tắc > 10s (Khoanh vùng ô C8 bằng khung đỏ nhấp nháy)",
                        "speed_sim": 0.0,
                        "idle_sim": 11.0,
                        "pedagogy": "Học viên bế tắc. Lớp phủ Overlay khoanh vùng đỏ phát sáng ĐÚNG Ô C8 (ngay bên cạnh chữ 'Rồng').",
                        "target_cell": "C8",
                        "target_sheet": "Bài 01",
                        "badge_text": "👉 ĐIỀN 'B8' VÀO Ô C8 NÀY",
                        "prompt_info": {
                            "mode_badge": "MỨC 3: KHOANH VÙNG TRỰC QUAN",
                            "hint_level": 3,
                            "step_title": "Khoanh vùng vị trí cần nhập",
                            "hint_text": "🎯 HÃY NHÌN VÀO KHUNG ĐỎ NHẤP NHÁY TRÊN EXCEL:\n1. Bấm chuột vào ô C8 (được khoanh viền đỏ cạnh chữ 'Rồng')\n2. Gõ chữ 'B8' rồi nhấn phím Enter.",
                            "is_correct": False,
                            "teachable_active": False,
                        }
                    },
                    {
                        "name": "Bước 5: Thao tác sai cú pháp '8B' (Buggy State)",
                        "speed_sim": 280.0,
                        "idle_sim": 0.5,
                        "pedagogy": "Học viên gõ ngược '8B'. AI chấn chỉnh ngay nguyên nhân gốc rễ và duy trì khoanh vùng ô C8.",
                        "target_cell": "C8",
                        "target_sheet": "Bài 01",
                        "badge_text": "⚠️ SỬA THÀNH 'B8' (CHỮ TRƯỚC SỐ SAU)",
                        "prompt_info": {
                            "mode_badge": "CHẤN CHỈNH QUY ƯỚC Ô",
                            "hint_level": 2,
                            "step_title": "Lỗi: Đảo ngược quy ước địa chỉ",
                            "hint_text": "⚠️ Bạn vừa gõ '8B'.\nTrong Excel, nếu viết số trước chữ ('8B') thì hệ thống chỉ coi là văn bản thông thường chứ không nhận diện được địa chỉ ô!\n👉 Hãy chọn lại ô C8 và sửa thành chữ 'B' viết hoa trước, số '8' sau: 'B8'.",
                            "is_correct": False,
                            "teachable_active": False,
                        }
                    },
                    {
                        "name": "Bước 6: Nhập đúng 'B8' -> Kích hoạt Teachable Agent",
                        "speed_sim": 80.0,
                        "idle_sim": 1.0,
                        "pedagogy": "Học viên sửa đúng. Tắt khoanh vùng, AI đổi vai thành học trò chất vấn để học viên tự giải thích bản chất.",
                        "target_cell": None,
                        "badge_text": "",
                        "prompt_info": {
                            "mode_badge": "HỌC TRÒ HỎI (TEACHABLE AGENT)",
                            "hint_level": 1,
                            "step_title": "Xuất sắc! Đã điền đúng ô C8 = B8",
                            "hint_text": "🌟 Tuyệt vời! Bạn đã hoàn thành đúng ô C8 = B8.\n\n🤖 AI hỏi lại bạn:\n\"Tại sao ô chứa chữ 'Rồng' lại có địa chỉ là B8 mà không phải là 8B hay địa chỉ nào khác?\"\n(Hãy gõ câu trả lời vào ô bên dưới và bấm Gửi)",
                            "is_correct": True,
                            "teachable_active": True,
                        }
                    }
                ]
            },
            "BAI_08": {
                "title": "Bài 08: Kỹ năng nhập liệu & Giữ số 0 ở đầu (Text vs Number)",
                "exercise_file": "Bài 08. Các bước cần thực hiện trước khi nhập dữ liệu 10092026 (1).xlsx",
                "steps": [
                    {
                        "name": "Bước 1: Chuột dừng tại Cột F (Số điện thoại)",
                        "speed_sim": 20.0,
                        "idle_sim": 3.8,
                        "pedagogy": "Chuột ngập ngừng ở ô SĐT trước khi gõ. AI chủ động gợi ý phòng ngừa trước khi học viên mắc lỗi.",
                        "target_cell": None,
                        "badge_text": "",
                        "prompt_info": {
                            "mode_badge": "MỨC 1: ĐỊNH HƯỚNG TƯ DUY",
                            "hint_level": 1,
                            "step_title": "Quy tắc nhập Số điện thoại / CCCD",
                            "hint_text": "🤔 Trước khi gõ số điện thoại vào ô này, bạn cần thực hiện thao tác quan trọng gì trên thanh công cụ để số 0 không bị mất?",
                            "is_correct": False,
                            "teachable_active": False,
                        }
                    },
                    {
                        "name": "Bước 2: Gõ khi chưa định dạng -> Mất số 0 (Lỗi điển hình)",
                        "speed_sim": 310.0,
                        "idle_sim": 0.8,
                        "pedagogy": "Học viên gõ '0908123456' nhưng Excel hiển thị '908123456'. AI bắt lỗi MISSING_LEADING_ZERO.",
                        "target_cell": None,
                        "badge_text": "",
                        "prompt_info": {
                            "mode_badge": "MỨC 2: CHỈ DẪN CÔNG CỤ",
                            "hint_level": 2,
                            "step_title": "Lỗi: Mất số 0 ở đầu số điện thoại",
                            "hint_text": "⚠️ Hãy nhìn kỹ số vừa gõ: Số 0 ở đầu đã biến mất!\nExcel đang hiểu đây là con số toán học (Number) nên tự bỏ số 0 vô nghĩa. Cần chuyển sang định dạng 'Text' trước.",
                            "is_correct": False,
                            "teachable_active": False,
                        }
                    },
                    {
                        "name": "Bước 3: Khoanh vùng ô F7 trên bảng tính (Mức 3)",
                        "speed_sim": 0.0,
                        "idle_sim": 6.5,
                        "pedagogy": "Khoanh vùng trực quan ô F7 và chỉ dẫn 3 bước đổi định dạng sang Text.",
                        "target_cell": "F7",
                        "target_sheet": "1. Thuc_Hanh_Tung_Buoc",
                        "badge_text": "👉 CHỌN ĐỊNH DẠNG TEXT CHO Ô NÀY",
                        "prompt_info": {
                            "mode_badge": "MỨC 3: KHOANH VÙNG TRỰC QUAN",
                            "hint_level": 3,
                            "step_title": "Khoanh vùng ô cần định dạng",
                            "hint_text": "🎯 Các bước sửa lỗi:\n1. Chọn ô F7 (đang khoanh vùng)\n2. Trên thanh Ribbon (Thẻ Home -> Hộp General), chọn định dạng 'Text'\n3. Gõ lại số điện thoại có số 0 ở đầu.",
                            "is_correct": False,
                            "teachable_active": False,
                        }
                    },
                    {
                        "name": "Bước 4: Nhập chuẩn '0908...' -> Teachable Agent chất vấn",
                        "speed_sim": 150.0,
                        "idle_sim": 1.2,
                        "pedagogy": "Đã sửa thành công. AI đặt câu hỏi phản biện về bản chất toán học vs dữ liệu văn bản.",
                        "target_cell": None,
                        "badge_text": "",
                        "prompt_info": {
                            "mode_badge": "HỌC TRÒ HỎI (TEACHABLE AGENT)",
                            "hint_level": 1,
                            "step_title": "Hoàn tất định dạng Text chuẩn!",
                            "hint_text": "🌟 Số điện thoại đã giữ nguyên số 0 và căn lề trái chuẩn Text!\n\n🤖 AI hỏi lại bạn:\n\"Tại sao trong toán học số 0 ở đầu lại vô nghĩa, nhưng trong số điện thoại và CCCD thì số 0 lại bắt buộc phải giữ?\"",
                            "is_correct": True,
                            "teachable_active": True,
                        }
                    }
                ]
            }
        }

    def init_ui(self):
        self.setWindowTitle("🎮 AI GUIDANCE SIMULATOR")
        # Luôn nổi trên cùng Always-On-Top để không bị Excel che khuất
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setFixedSize(400, 560)
        self.setStyleSheet("""
            QWidget {
                background-color: #0f172a;
                color: #f8fafc;
                font-family: 'Segoe UI', system-ui, sans-serif;
            }
        """)

        # Đặt cửa sổ ở cạnh trái màn hình để không che Excel
        screen = QApplication.primaryScreen()
        if screen:
            avail = screen.availableGeometry()
            self.move(avail.left() + 15, avail.top() + 35)
        else:
            self.move(15, 35)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        # 1. Header
        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(1)
        main_title = QLabel("🧪 AI GUIDANCE SIMULATOR")
        main_title.setStyleSheet("color: #38bdf8; font-size: 13px; font-weight: 900; letter-spacing: 0.5px;")
        sub_title = QLabel("Giả lập phản ứng sư phạm phân cấp")
        sub_title.setStyleSheet("color: #94a3b8; font-size: 10px;")
        title_box.addWidget(main_title)
        title_box.addWidget(sub_title)
        header.addLayout(title_box)
        header.addStretch()

        # Chọn kịch bản bài tập
        self.scenario_combo = QComboBox()
        self.scenario_combo.addItem("Bài 07 (Địa chỉ)", "BAI_07")
        self.scenario_combo.addItem("Bài 08 (Số 0 SĐT)", "BAI_08")
        self.scenario_combo.setStyleSheet("""
            QComboBox {
                background-color: #1e293b;
                color: #38bdf8;
                border: 1px solid #475569;
                border-radius: 6px;
                padding: 4px 8px;
                font-weight: bold;
                font-size: 11px;
            }
        """)
        self.scenario_combo.currentIndexChanged.connect(self._on_scenario_changed)
        header.addWidget(self.scenario_combo)
        layout.addLayout(header)

        # 2. Thanh tiến trình bước (Progress Bar)
        prog_box = QVBoxLayout()
        prog_box.setSpacing(2)
        self.step_counter_lbl = QLabel("Bước 1 / 6")
        self.step_counter_lbl.setStyleSheet("color: #cbd5e1; font-size: 11px; font-weight: bold;")
        self.step_progress = QProgressBar()
        self.step_progress.setRange(0, 100)
        self.step_progress.setValue(16)
        self.step_progress.setTextVisible(False)
        self.step_progress.setFixedHeight(4)
        self.step_progress.setStyleSheet("""
            QProgressBar {
                background-color: #1e293b;
                border-radius: 2px;
                border: none;
            }
            QProgressBar::chunk {
                background-color: #38bdf8;
                border-radius: 2px;
            }
        """)
        prog_box.addWidget(self.step_counter_lbl)
        prog_box.addWidget(self.step_progress)
        layout.addLayout(prog_box)

        # 3. Khung hiển thị Tên bước & Phân tích sư phạm
        info_card = QFrame()
        info_card.setStyleSheet("background-color: #1e293b; border-radius: 8px; border: 1px solid #334155; padding: 8px;")
        info_layout = QVBoxLayout(info_card)
        info_layout.setSpacing(4)

        self.cur_step_title = QLabel("Tên bước giả lập")
        self.cur_step_title.setStyleSheet("color: #f1f5f9; font-size: 11px; font-weight: 800;")
        self.cur_step_title.setWordWrap(True)

        self.telemetry_badge = QLabel("📊 Tốc độ: 0 px/s | Ngập ngừng: 0.0s")
        self.telemetry_badge.setStyleSheet("color: #10b981; font-size: 10px; font-weight: bold;")

        self.tracking_status_lbl = QLabel("🎯 Bắt tọa độ: Đang kiểm tra Excel...")
        self.tracking_status_lbl.setStyleSheet("color: #94a3b8; font-size: 10px;")

        self.pedagogy_desc = QLabel("Mô tả ý đồ sư phạm...")
        self.pedagogy_desc.setStyleSheet("color: #cbd5e1; font-size: 10px; line-height: 1.3;")
        self.pedagogy_desc.setWordWrap(True)

        info_layout.addWidget(self.cur_step_title)
        info_layout.addWidget(self.telemetry_badge)
        info_layout.addWidget(self.tracking_status_lbl)
        info_layout.addWidget(self.pedagogy_desc)
        layout.addWidget(info_card)

        # 4. Danh sách nút nhảy nhanh từng bước
        quick_title = QLabel("BẤM ĐỂ CHỌN NHANH BƯỚC GIẢ LẬP:")
        quick_title.setStyleSheet("color: #64748b; font-size: 9px; font-weight: bold;")
        layout.addWidget(quick_title)

        self.quick_btn_layout = QVBoxLayout()
        self.quick_btn_layout.setSpacing(3)
        layout.addLayout(self.quick_btn_layout)
        self._rebuild_quick_buttons()

        # 5. Thanh điều hướng chính (Previous, Play Auto, Next)
        nav_layout = QHBoxLayout()
        nav_layout.setSpacing(6)

        self.prev_btn = QPushButton("◀ Trước")
        self.prev_btn.setStyleSheet("""
            QPushButton {
                background-color: #334155;
                color: #f1f5f9;
                font-weight: bold;
                padding: 7px 10px;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover { background-color: #475569; }
        """)
        self.prev_btn.clicked.connect(self.on_prev_step)

        self.auto_btn = QPushButton("▶ Chạy Tự Động")
        self.auto_btn.setStyleSheet("""
            QPushButton {
                background-color: #0284c7;
                color: white;
                font-weight: bold;
                padding: 7px 10px;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover { background-color: #0369a1; }
        """)
        self.auto_btn.clicked.connect(self.toggle_auto_play)

        self.next_btn = QPushButton("Tiếp Theo ▶")
        self.next_btn.setStyleSheet("""
            QPushButton {
                background-color: #0f766e;
                color: white;
                font-weight: bold;
                padding: 7px 10px;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover { background-color: #0d9488; }
        """)
        self.next_btn.clicked.connect(self.on_next_step)

        nav_layout.addWidget(self.prev_btn)
        nav_layout.addWidget(self.auto_btn)
        nav_layout.addWidget(self.next_btn)
        layout.addLayout(nav_layout)

    def _rebuild_quick_buttons(self):
        """Tạo danh sách các nút bấm từng bước."""
        while self.quick_btn_layout.count():
            item = self.quick_btn_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        steps = self.scenarios[self.current_scenario]["steps"]
        self.quick_buttons = []
        for i, s in enumerate(steps):
            btn = QPushButton(f"{i+1}. {s['name']}")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #1e293b;
                    color: #94a3b8;
                    text-align: left;
                    padding: 5px 8px;
                    border-radius: 5px;
                    border: 1px solid #334155;
                    font-size: 10px;
                }
                QPushButton:hover {
                    background-color: #334155;
                    color: #f8fafc;
                }
            """)
            btn.clicked.connect(lambda checked, idx=i: self.apply_step(idx))
            self.quick_btn_layout.addWidget(btn)
            self.quick_buttons.append(btn)

    def _on_scenario_changed(self, idx):
        self.current_scenario = self.scenario_combo.currentData()
        self.current_step_idx = 0
        self._rebuild_quick_buttons()
        self.apply_step(0)

    def _resolve_target_rect(self, target_cell: Optional[str], target_sheet: str = "") -> Tuple[Optional[Tuple[int, int, int, int]], bool]:
        """
        Bắt tọa độ pixel thực tế của ô tính từ Excel đang mở.
        Trả về: (rect, is_from_excel)
        """
        if not target_cell:
            return None, False

        # 1. Thử lấy trực tiếp từ Excel bằng COM / AccessibleObject
        rect = self.excel_monitor.get_cell_rect_by_address(target_cell, target_sheet)
        if rect:
            return rect, True

        # 2. Fallback: Nếu Excel chưa cấp quyền hoặc đang bận,
        # Sử dụng tọa độ đo đạc thực tế chính xác trên màn hình 1366x768 với Excel mở toàn màn hình
        screen = QApplication.primaryScreen()
        scr_w = screen.geometry().width() if screen else 1366
        scr_h = screen.geometry().height() if screen else 768

        # Trong Bài 07:
        # Cột C (Địa chỉ ô) nằm ở x = 118 đến 205 (bên phải chữ 'Rồng' ở cột B)
        # Dòng 8 (chứa chữ 'Rồng') nằm ở y = 675 đến 715 (ngay dưới dòng 7)
        if target_cell == "C8":
            # Tọa độ ô C8 chính xác ngay bên cạnh chữ 'Rồng'
            return (117, 557, 70, 24), False
        elif target_cell == "F7":
            # Cột F, dòng 7 trong Bài 08
            return (480, 520, 95, 32), False

        return (117, 557, 70, 24), False

    def _sync_active_overlay(self):
        """Đồng bộ lại tọa độ ô tính nếu Excel thay đổi trạng thái cuộn / kích thước."""
        steps = self.scenarios[self.current_scenario]["steps"]
        step = steps[self.current_step_idx]
        target_cell = step.get("target_cell")

        if target_cell:
            rect, is_from_excel = self._resolve_target_rect(target_cell, step.get("target_sheet", ""))
            if rect:
                badge = step.get("badge_text", "👉 THAO TÁC Ở ĐÂY")
                self.overlay.set_target_rect(rect, is_physical_pixels=True, badge_text=badge)
                if is_from_excel:
                    self.tracking_status_lbl.setText(f"🎯 Bắt dính ô {target_cell} từ Excel: ({rect[0]}, {rect[1]})")
                    self.tracking_status_lbl.setStyleSheet("color: #10b981; font-size: 10px; font-weight: bold;")
                else:
                    self.tracking_status_lbl.setText(f"🎯 Đang định vị ô {target_cell} (cạnh chữ 'Rồng')")
                    self.tracking_status_lbl.setStyleSheet("color: #38bdf8; font-size: 10px;")

    def apply_step(self, step_idx: int):
        """Kích hoạt và cập nhật giao diện tương ứng với bước giả lập."""
        steps = self.scenarios[self.current_scenario]["steps"]
        if step_idx < 0 or step_idx >= len(steps):
            return

        self.current_step_idx = step_idx
        step = steps[step_idx]

        # 1. Cập nhật tiến trình
        pct = int(((step_idx + 1) / len(steps)) * 100)
        self.step_progress.setValue(pct)
        self.step_counter_lbl.setText(f"Bước {step_idx + 1} / {len(steps)}")
        self.cur_step_title.setText(step["name"])

        # 2. Cập nhật telemetry
        speed = step["speed_sim"]
        idle = step["idle_sim"]
        if idle > 2.0:
            status_text = f"⏸️ DỪNG CHUỘT NGẬP NGỪNG: {idle:.1f}s ({speed} px/s)"
            color = "#f59e0b"
        elif speed < 50:
            status_text = f"🎯 RÊ CHUỘT CHẬM CHÍNH XÁC: {speed} px/s"
            color = "#3b82f6"
        else:
            status_text = f"⚡ DI CHUYỂN BÌNH THƯỜNG: {speed} px/s"
            color = "#10b981"

        self.telemetry_badge.setText(f"📊 {status_text}")
        self.telemetry_badge.setStyleSheet(f"color: {color}; font-size: 10px; font-weight: bold;")
        self.pedagogy_desc.setText(step["pedagogy"])

        # Đổi highlight nút
        for i, b in enumerate(self.quick_buttons):
            if i == step_idx:
                b.setStyleSheet("""
                    background-color: #0f766e;
                    color: white;
                    text-align: left;
                    padding: 5px 8px;
                    border-radius: 5px;
                    border: 1px solid #14b8a6;
                    font-weight: bold;
                    font-size: 10px;
                """)
            else:
                b.setStyleSheet("""
                    background-color: #1e293b;
                    color: #94a3b8;
                    text-align: left;
                    padding: 5px 8px;
                    border-radius: 5px;
                    border: 1px solid #334155;
                    font-size: 10px;
                """)

        # 3. Cập nhật Companion Widget
        p_info = dict(step["prompt_info"])
        self.companion.update_tutor_ui(p_info)

        # 4. Cập nhật Overlay Window với tọa độ thực tế và nhãn cụ thể
        target_cell = step.get("target_cell")
        if target_cell:
            rect, is_from_excel = self._resolve_target_rect(target_cell, step.get("target_sheet", ""))
            if rect:
                badge = step.get("badge_text", "👉 THAO TÁC Ở ĐÂY")
                self.overlay.set_target_rect(rect, is_physical_pixels=True, badge_text=badge)
                if is_from_excel:
                    self.tracking_status_lbl.setText(f"🎯 Bắt dính ô {target_cell} từ Excel: ({rect[0]}, {rect[1]})")
                    self.tracking_status_lbl.setStyleSheet("color: #10b981; font-size: 10px; font-weight: bold;")
                else:
                    self.tracking_status_lbl.setText(f"🎯 Đang định vị ô {target_cell} (cạnh chữ 'Rồng')")
                    self.tracking_status_lbl.setStyleSheet("color: #38bdf8; font-size: 10px;")
        else:
            self.overlay.clear_target()
            self.tracking_status_lbl.setText("🎯 Chưa cần khoanh vùng ô tính ở bước này.")
            self.tracking_status_lbl.setStyleSheet("color: #94a3b8; font-size: 10px;")

    def on_next_step(self):
        steps = self.scenarios[self.current_scenario]["steps"]
        next_idx = (self.current_step_idx + 1) % len(steps)
        self.apply_step(next_idx)

    def on_prev_step(self):
        steps = self.scenarios[self.current_scenario]["steps"]
        prev_idx = (self.current_step_idx - 1 + len(steps)) % len(steps)
        self.apply_step(prev_idx)

    def toggle_auto_play(self):
        if self.auto_timer.isActive():
            self.auto_timer.stop()
            self.auto_btn.setText("▶ Chạy Tự Động")
            self.auto_btn.setStyleSheet("""
                QPushButton {
                    background-color: #0284c7;
                    color: white;
                    font-weight: bold;
                    padding: 7px 10px;
                    border-radius: 6px;
                    border: none;
                }
                QPushButton:hover { background-color: #0369a1; }
            """)
        else:
            self.auto_timer.start(4000)
            self.auto_btn.setText("⏸ Tạm Dừng")
            self.auto_btn.setStyleSheet("""
                QPushButton {
                    background-color: #dc2626;
                    color: white;
                    font-weight: bold;
                    padding: 7px 10px;
                    border-radius: 6px;
                    border: none;
                }
                QPushButton:hover { background-color: #b91c1c; }
            """)

    def _auto_step_tick(self):
        steps = self.scenarios[self.current_scenario]["steps"]
        next_idx = self.current_step_idx + 1
        if next_idx >= len(steps):
            next_idx = 0
        self.apply_step(next_idx)


def main():
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    app = QApplication(sys.argv)

    # 1. Khởi tạo Cửa sổ Lớp phủ Overlay
    overlay = OverlayWindow()
    overlay.show()

    # 2. Khởi tạo Thẻ nổi Gia Sư AI (Always On Top)
    companion = CompanionWidget()
    companion.show()

    # Kết nối phản hồi Teachable Agent khi người dùng gõ câu trả lời
    tutor_agent = TutorAgent()
    def handle_reflection(text):
        q = companion.hint_text_area.toPlainText()
        feedback = tutor_agent.evaluate_reflection(q, text)
        companion.hint_text_area.setText(
            f"🗣️ Bạn giải thích: \"{text}\"\n\n🤖 Gia Sư AI nhận xét:\n{feedback}"
        )
    companion.submit_reflection_signal.connect(handle_reflection)

    # 3. Khởi tạo Bảng Điều Khiển Giả Lập Kịch Bản (Always On Top)
    sim_ctrl = GuidanceSimulatorControl(companion, overlay)
    sim_ctrl.show()

    print("=" * 65)
    print("✨ BỘ GIẢ LẬP HƯỚNG DẪN ĐÃ ĐƯỢC CẢI TIẾN HOÀN CHỈNH!")
    print("   1. Cả 2 cửa sổ đều ALWAYS-ON-TOP (không bị Excel che khuất)")
    print("   2. Ô khoanh vùng đỏ nhấp nháy ĐÚNG Ô C8 (ngay cạnh chữ 'Rồng')")
    print("   3. Nhãn hướng dẫn hiển thị cụ thể: '👉 ĐIỀN B8 VÀO Ô C8 NÀY'")
    print("=" * 65)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
