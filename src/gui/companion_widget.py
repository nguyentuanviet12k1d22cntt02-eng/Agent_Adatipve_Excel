"""
Companion Widget: Giao diện Gia sư AI dạng thẻ nổi (Floating Card)
Thiết kế hiện đại, sang trọng theo phong cách Glassmorphism / Dark Mode.
Cho phép học viên tương tác, xem gợi ý phân cấp và đối thoại phản biện với AI.
"""

from PyQt6.QtCore import Qt, QPoint, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QCursor, QPixmap
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QLineEdit,
    QFrame,
    QGraphicsDropShadowEffect,
    QProgressBar,
)

from src.gui.mascot_assets import (
    mascot_asset_path,
    mascot_style,
    visual_state_for_guidance,
)


class CompanionWidget(QWidget):
    # Các tín hiệu tương tác
    open_exercise_signal = pyqtSignal(str)
    request_hint_signal = pyqtSignal()
    repeat_instruction_signal = pyqtSignal()
    toggle_pause_signal = pyqtSignal()
    continue_step_signal = pyqtSignal()
    submit_reflection_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()

        # Thiết lập cửa sổ nổi Always-On-Top, không bị Excel che khuất
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        self.drag_position = QPoint()
        self._init_ui()

    def _init_ui(self):
        self.resize(390, 540)

        # Layout ngoài cùng
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # Khung nền chính dạng thẻ Glassmorphism
        self.card_frame = QFrame(self)
        self.card_frame.setStyleSheet("""
            QFrame {
                background-color: rgba(17, 24, 39, 0.95);
                border: 1px solid rgba(75, 85, 99, 0.4);
                border-radius: 16px;
            }
        """)

        # Hiệu ứng đổ bóng (Drop Shadow)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(25)
        shadow.setColor(QColor(0, 0, 0, 180))
        shadow.setOffset(0, 8)
        self.card_frame.setGraphicsEffect(shadow)

        # Layout bên trong thẻ
        card_layout = QVBoxLayout(self.card_frame)
        card_layout.setContentsMargins(18, 16, 18, 16)
        card_layout.setSpacing(12)

        # 1. HEADER (Thanh tiêu đề có thể kéo thả)
        header_layout = QHBoxLayout()
        
        # Avatar & Tiêu đề
        self.title_label = QLabel("GIA SƯ EXCEL", self.card_frame)
        self.title_label.setStyleSheet("color: #F3F4F6; font-size: 13px; font-weight: bold; letter-spacing: 0.5px;")

        # Nút trạng thái (Status pill)
        self.status_pill = QLabel("Realtime", self.card_frame)
        self.status_pill.setFixedWidth(100)
        self.status_pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_pill.setStyleSheet("""
            background-color: rgba(16, 185, 129, 0.15);
            color: #34D399;
            font-size: 10px;
            font-weight: 600;
            padding: 3px 8px;
            border-radius: 10px;
            border: 1px solid rgba(16, 185, 129, 0.3);
        """)

        self.pause_btn = QPushButton("Ⅱ", self.card_frame)
        self.pause_btn.setFixedSize(28, 22)
        self.pause_btn.setToolTip("Tạm dừng hoặc tiếp tục Teaching Agent")
        self.pause_btn.setAccessibleName("Tạm dừng Teaching Agent")
        self.pause_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(55, 65, 81, 0.75);
                color: #D1D5DB;
                border: 1px solid rgba(107, 114, 128, 0.45);
                border-radius: 6px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #4B5563; color: white; }
        """)
        self.pause_btn.clicked.connect(self.toggle_pause_signal.emit)

        # Nút thu nhỏ / đóng
        self.close_btn = QPushButton("✕", self.card_frame)
        self.close_btn.setFixedSize(22, 22)
        self.close_btn.setAccessibleName("Đóng Gia sư Excel")
        self.close_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #9CA3AF;
                border: none;
                font-weight: bold;
                border-radius: 11px;
            }
            QPushButton:hover {
                background-color: rgba(239, 68, 68, 0.2);
                color: #EF4444;
            }
        """)
        self.close_btn.clicked.connect(self.close)

        header_layout.addWidget(self.title_label)
        header_layout.addStretch()
        header_layout.addWidget(self.status_pill)
        header_layout.addWidget(self.pause_btn)
        header_layout.addWidget(self.close_btn)
        card_layout.addLayout(header_layout)

        # 2. THANH CHỌN BÀI TẬP NHANH (Exercise Quick Selector)
        exercise_layout = QHBoxLayout()
        self.btn_open_07 = QPushButton("Bài 07", self.card_frame)
        self.btn_open_08 = QPushButton("Bài 08", self.card_frame)

        btn_style = """
            QPushButton {
                background-color: rgba(31, 41, 55, 0.8);
                color: #E5E7EB;
                font-size: 11px;
                font-weight: 600;
                padding: 6px 10px;
                border: 1px solid rgba(75, 85, 99, 0.6);
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #374151;
                border-color: #60A5FA;
                color: #60A5FA;
            }
        """
        self.btn_open_07.setStyleSheet(btn_style)
        self.btn_open_08.setStyleSheet(btn_style)

        self.btn_open_07.clicked.connect(lambda: self.open_exercise_signal.emit("07"))
        self.btn_open_08.clicked.connect(lambda: self.open_exercise_signal.emit("08"))

        exercise_layout.addWidget(self.btn_open_07)
        exercise_layout.addWidget(self.btn_open_08)
        card_layout.addLayout(exercise_layout)

        # Đường kẻ phân cách
        sep = QFrame(self.card_frame)
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("border: none; background-color: rgba(75, 85, 99, 0.3); height: 1px;")
        card_layout.addWidget(sep)

        # 3. TIẾN ĐỘ BÀI HỌC REALTIME
        progress_header = QHBoxLayout()
        self.lesson_label = QLabel("Chưa chọn bài học", self.card_frame)
        self.lesson_label.setStyleSheet("color: #CBD5E1; font-size: 10px; font-weight: 600;")
        self.lesson_label.setFixedWidth(230)
        self.lesson_label.setWordWrap(True)
        self.progress_label = QLabel("Bước 0/0", self.card_frame)
        self.progress_label.setStyleSheet("color: #93C5FD; font-size: 10px; font-weight: 700;")
        progress_header.addWidget(self.lesson_label, 1)
        progress_header.addWidget(self.progress_label)
        card_layout.addLayout(progress_header)

        self.lesson_progress = QProgressBar(self.card_frame)
        self.lesson_progress.setRange(0, 100)
        self.lesson_progress.setValue(0)
        self.lesson_progress.setTextVisible(False)
        self.lesson_progress.setFixedHeight(7)
        self.lesson_progress.setAccessibleName("Tiến độ bài học")
        self.lesson_progress.setStyleSheet("""
            QProgressBar {
                background-color: rgba(55, 65, 81, 0.7);
                border: none;
                border-radius: 3px;
            }
            QProgressBar::chunk {
                background-color: #3B82F6;
                border-radius: 3px;
            }
        """)
        card_layout.addWidget(self.lesson_progress)

        # 4. HỘP HIỂN THỊ GỢI Ý SƯ PHẠM (Graduated Hint Box)
        self.badge_label = QLabel("MỨC 1: ĐỊNH HƯỚNG TƯ DUY", self.card_frame)
        self.badge_label.setStyleSheet("""
            color: #60A5FA;
            font-size: 10px;
            font-weight: 700;
            letter-spacing: 0.8px;
        """)
        card_layout.addWidget(self.badge_label)

        # Tiêu đề bước
        self.step_label = QLabel("Đang lắng nghe thao tác...", self.card_frame)
        self.step_label.setStyleSheet("color: #F9FAFB; font-size: 12px; font-weight: 600;")
        self.step_label.setWordWrap(True)
        card_layout.addWidget(self.step_label)

        # Checklist vi-bước: luôn cho biết đang làm gì, đã xong gì và bước kế.
        self.procedure_frame = QFrame(self.card_frame)
        self.procedure_frame.setStyleSheet("""
            QFrame {
                background-color: rgba(30, 41, 59, 0.72);
                border: 1px solid rgba(96, 165, 250, 0.30);
                border-radius: 9px;
            }
        """)
        procedure_layout = QVBoxLayout(self.procedure_frame)
        procedure_layout.setContentsMargins(10, 8, 10, 8)
        procedure_layout.setSpacing(4)

        self.procedure_steps_label = QLabel(self.procedure_frame)
        self.procedure_steps_label.setWordWrap(True)
        self.procedure_steps_label.setTextFormat(Qt.TextFormat.RichText)
        self.procedure_steps_label.setStyleSheet(
            "border: none; background: transparent; color: #CBD5E1; font-size: 11px;"
        )
        self.verification_label = QLabel(self.procedure_frame)
        self.verification_label.setWordWrap(True)
        self.verification_label.setStyleSheet(
            "border: none; background: transparent; color: #FBBF24; font-size: 11px; font-weight: 600;"
        )
        self.next_action_label = QLabel(self.procedure_frame)
        self.next_action_label.setWordWrap(True)
        self.next_action_label.setStyleSheet(
            "border: none; background: transparent; color: #94A3B8; font-size: 10px;"
        )
        procedure_layout.addWidget(self.procedure_steps_label)
        procedure_layout.addWidget(self.verification_label)
        procedure_layout.addWidget(self.next_action_label)
        card_layout.addWidget(self.procedure_frame)
        self.procedure_frame.setVisible(False)

        # Nội dung gợi ý chi tiết + pose phản hồi theo trạng thái của Agent
        hint_content_layout = QHBoxLayout()
        hint_content_layout.setSpacing(10)

        self.mascot_label = QLabel(self.card_frame)
        self.mascot_label.setFixedSize(82, 118)
        self.mascot_label.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom)
        self.mascot_label.setAccessibleName("Trạng thái trực quan của Gia sư Excel")

        self.hint_text_area = QTextEdit(self.card_frame)
        self.hint_text_area.setReadOnly(True)
        self.hint_text_area.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.hint_text_area.setMinimumHeight(126)
        self.hint_text_area.setStyleSheet("""
            QTextEdit {
                background-color: rgba(31, 41, 55, 0.5);
                color: #D1D5DB;
                font-size: 12px;
                line-height: 1.5;
                border: 1px solid rgba(75, 85, 99, 0.4);
                border-radius: 8px;
                padding: 8px;
            }
        """)
        self.hint_text_area.setText("Xin chào! Hãy mở file Bài 07 hoặc Bài 08 để bắt đầu buổi luyện tập. Mình sẽ đồng hành và hỗ trợ bạn khi gặp khó khăn!")
        hint_content_layout.addWidget(self.mascot_label, 0, Qt.AlignmentFlag.AlignBottom)
        hint_content_layout.addWidget(self.hint_text_area, 1)
        card_layout.addLayout(hint_content_layout)
        self._set_mascot_state("welcome")

        # 5. THANH HÀNH ĐỘNG GỢI Ý (Action Buttons)
        action_layout = QHBoxLayout()
        self.btn_next_hint = QPushButton("Gợi ý", self.card_frame)
        self.btn_next_hint.setStyleSheet("""
            QPushButton {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3B82F6, stop:1 #2563EB);
                color: white;
                font-size: 11px;
                font-weight: bold;
                padding: 7px 12px;
                border: none;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #1D4ED8;
            }
        """)
        self.btn_next_hint.clicked.connect(self.request_hint_signal.emit)

        self.btn_repeat = QPushButton("Nhắc lại", self.card_frame)
        self.btn_repeat.setStyleSheet("""
            QPushButton {
                background-color: rgba(55, 65, 81, 0.8);
                color: #D1D5DB;
                font-size: 11px;
                font-weight: 600;
                padding: 7px 9px;
                border: 1px solid rgba(75, 85, 99, 0.6);
                border-radius: 8px;
            }
            QPushButton:hover { background-color: #4B5563; color: white; }
        """)
        self.btn_repeat.clicked.connect(self.repeat_instruction_signal.emit)

        self.btn_understood = QPushButton("Tiếp tục", self.card_frame)
        self.btn_understood.setStyleSheet("""
            QPushButton {
                background-color: rgba(55, 65, 81, 0.8);
                color: #9CA3AF;
                font-size: 11px;
                font-weight: 600;
                padding: 7px 12px;
                border: 1px solid rgba(75, 85, 99, 0.5);
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #4B5563;
                color: #F3F4F6;
            }
        """)
        self.btn_understood.clicked.connect(self.continue_step_signal.emit)
        self.btn_understood.setEnabled(False)
        action_layout.addWidget(self.btn_next_hint)
        action_layout.addWidget(self.btn_repeat)
        action_layout.addWidget(self.btn_understood)
        card_layout.addLayout(action_layout)

        # 6. KHUNG TRẢ LỜI PHẢN BIỆN (Teachable Agent Response Input)
        self.reflection_frame = QFrame(self.card_frame)
        self.reflection_frame.setStyleSheet("border: none;")
        refl_layout = QVBoxLayout(self.reflection_frame)
        refl_layout.setContentsMargins(0, 4, 0, 0)
        refl_layout.setSpacing(6)

        refl_input_layout = QHBoxLayout()
        self.refl_input = QLineEdit(self.reflection_frame)
        self.refl_input.setPlaceholderText("Gõ câu trả lời giải thích cho AI...")
        self.refl_input.setStyleSheet("""
            QLineEdit {
                background-color: rgba(31, 41, 55, 0.8);
                color: #F9FAFB;
                border: 1px solid rgba(75, 85, 99, 0.6);
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 11px;
            }
            QLineEdit:focus {
                border-color: #8B5CF6;
            }
        """)

        self.btn_submit_refl = QPushButton("Gửi", self.reflection_frame)
        self.btn_submit_refl.setStyleSheet("""
            QPushButton {
                background-color: #8B5CF6;
                color: white;
                font-size: 11px;
                font-weight: bold;
                padding: 6px 12px;
                border: none;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #7C3AED;
            }
        """)
        self.btn_submit_refl.clicked.connect(self._on_submit_reflection)
        self.refl_input.returnPressed.connect(self._on_submit_reflection)

        refl_input_layout.addWidget(self.refl_input)
        refl_input_layout.addWidget(self.btn_submit_refl)
        refl_layout.addLayout(refl_input_layout)
        card_layout.addWidget(self.reflection_frame)
        self.reflection_frame.setVisible(False)

        main_layout.addWidget(self.card_frame)
        self.resize(max(390, self.minimumSizeHint().width()), 540)

        # Đặt vị trí mặc định ở góc dưới bên phải màn hình hiển thị
        from PyQt6.QtWidgets import QApplication
        screen = QApplication.primaryScreen()
        if screen:
            avail = screen.availableGeometry()
            pos_x = max(10, avail.right() - self.width() - 10)
            pos_y = max(10, avail.bottom() - self.height() - 10)
            self.move(pos_x, pos_y)
        else:
            self.move(950, 250)

    def _on_submit_reflection(self):
        text = self.refl_input.text().strip()
        if text:
            self.submit_reflection_signal.emit(text)
            self.refl_input.clear()

    def update_tutor_ui(self, info: dict):
        """Cập nhật nội dung hiển thị từ PromptingEngine."""
        self._set_mascot_state(visual_state_for_guidance(info))
        procedure_active = bool(info.get("procedure_active", False))
        if procedure_active:
            self.badge_label.setText(f"THAO TÁC {info.get('action_position', '')}")
            self.step_label.setText(info.get("action_title", ""))
            self.step_label.setStyleSheet(
                "color: #F9FAFB; font-size: 15px; font-weight: 700;"
            )
            self._update_procedure_ui(info)
        else:
            self.badge_label.setText(info.get("mode_badge", ""))
            self.step_label.setText(info.get("step_title", ""))
            self.step_label.setStyleSheet(
                "color: #F9FAFB; font-size: 12px; font-weight: 600;"
            )
            self.procedure_frame.setVisible(False)
        hint_text = info.get("hint_text", "")
        if self.hint_text_area.toPlainText() != hint_text:
            self.hint_text_area.setText(hint_text)

        self.lesson_label.setText(info.get("lesson_title", "Chưa chọn bài học"))
        self.progress_label.setText(info.get("step_position", "Bước 0/0"))
        self.lesson_progress.setValue(int(round(info.get("progress_percent", 0))))
        self.lesson_progress.setAccessibleDescription(
            info.get("step_position", "Chưa bắt đầu")
        )

        agent_status = info.get("agent_status", "observing")
        is_paused = bool(info.get("is_paused", False))
        can_continue = bool(info.get("can_continue", False))
        can_advance_action = bool(info.get("can_advance_action", False))
        self.pause_btn.setText("▶" if is_paused else "Ⅱ")
        self.pause_btn.setAccessibleName("Tiếp tục Teaching Agent" if is_paused else "Tạm dừng Teaching Agent")
        self.btn_next_hint.setEnabled(bool(info.get("can_request_hint", False)))
        self.btn_repeat.setEnabled(agent_status not in {"idle", "completed"})
        self.btn_understood.setEnabled(can_continue or can_advance_action)
        if can_advance_action:
            action_kind = info.get("action_kind", "")
            if action_kind == "ribbon_tab":
                self.btn_understood.setText("Đã mở Home")
                self.btn_understood.setAccessibleName("Xác nhận đã mở thẻ Home")
                self.btn_understood.setToolTip(
                    "Dùng khi Gia sư chưa tự nhận diện được thẻ Home"
                )
            elif action_kind == "ribbon_control":
                self.btn_understood.setText("Đã mở danh sách")
                self.btn_understood.setAccessibleName(
                    "Xác nhận đã mở danh sách Number Format"
                )
                self.btn_understood.setToolTip(
                    "Dùng khi Gia sư chưa tự nhận diện được Number Format"
                )
            else:
                self.btn_understood.setText("Bước tiếp theo")
                self.btn_understood.setAccessibleName("Bước tiếp theo")
                self.btn_understood.setToolTip("")
            self.btn_understood.setStyleSheet("""
                QPushButton {
                    background-color: #2563EB;
                    color: white;
                    font-size: 11px;
                    font-weight: 700;
                    padding: 7px 10px;
                    border: 1px solid #60A5FA;
                    border-radius: 8px;
                }
                QPushButton:hover { background-color: #1D4ED8; }
                QPushButton:pressed { background-color: #1E40AF; }
                QPushButton:focus { border: 2px solid #BFDBFE; }
            """)
        elif can_continue:
            self.btn_understood.setText("Tiếp tục")
            self.btn_understood.setAccessibleName("Tiếp tục bài học")
            self.btn_understood.setToolTip("")
            self.btn_understood.setStyleSheet("""
                QPushButton {
                    background-color: #059669;
                    color: white;
                    font-size: 11px;
                    font-weight: 700;
                    padding: 7px 12px;
                    border: 1px solid #34D399;
                    border-radius: 8px;
                }
                QPushButton:hover { background-color: #047857; }
                QPushButton:focus { border: 2px solid #A7F3D0; }
            """)
        else:
            self.btn_understood.setText("Đang kiểm tra")
            self.btn_understood.setAccessibleName("Đang kiểm tra thao tác")
            self.btn_understood.setToolTip("")
            self.btn_understood.setStyleSheet("""
                QPushButton {
                    background-color: rgba(55, 65, 81, 0.55);
                    color: #64748B;
                    font-size: 11px;
                    font-weight: 600;
                    padding: 7px 12px;
                    border: 1px solid rgba(75, 85, 99, 0.35);
                    border-radius: 8px;
                }
            """)

        # Nội dung thao tác có thể làm thay đổi sizeHint sau khi widget đã neo
        # cạnh phải màn hình. Clamp lại ở event-loop kế để không bị cắt khỏi màn
        # hình trên laptop/màn hình phụ có chiều rộng nhỏ.
        QTimer.singleShot(0, self._keep_inside_available_screen)

        # Đổi màu badge tùy theo mức gợi ý
        level = info.get("hint_level", 1)
        teachable = info.get("teachable_active", False)
        is_correct = info.get("is_correct", False)
        self.reflection_frame.setVisible(bool(teachable))

        if agent_status == "paused":
            self.badge_label.setStyleSheet("color: #CBD5E1; font-size: 10px; font-weight: 700; letter-spacing: 0.8px;")
            self.status_pill.setText("Tạm dừng")
            self.status_pill.setStyleSheet("background-color: rgba(100, 116, 139, 0.18); color: #CBD5E1; font-size: 10px; font-weight: 600; padding: 3px 8px; border-radius: 10px; border: 1px solid rgba(148, 163, 184, 0.35);")
        elif agent_status in {"waiting_for_excel", "waiting_for_workbook", "waiting_for_sheet"}:
            self.badge_label.setStyleSheet("color: #FBBF24; font-size: 10px; font-weight: 700; letter-spacing: 0.8px;")
            self.status_pill.setText("Đang chờ")
            self.status_pill.setStyleSheet("background-color: rgba(251, 191, 36, 0.15); color: #FBBF24; font-size: 10px; font-weight: 600; padding: 3px 8px; border-radius: 10px; border: 1px solid rgba(251, 191, 36, 0.3);")
        elif agent_status == "completed":
            self.badge_label.setStyleSheet("color: #34D399; font-size: 10px; font-weight: 700; letter-spacing: 0.8px;")
            self.status_pill.setText("Hoàn thành")
            self.status_pill.setStyleSheet("background-color: rgba(16, 185, 129, 0.15); color: #34D399; font-size: 10px; font-weight: 600; padding: 3px 8px; border-radius: 10px; border: 1px solid rgba(16, 185, 129, 0.3);")

        elif teachable:
            self.badge_label.setStyleSheet("color: #C084FC; font-size: 10px; font-weight: 700; letter-spacing: 0.8px;")
            self.status_pill.setText("Củng cố")
            self.status_pill.setStyleSheet("background-color: rgba(192, 132, 252, 0.15); color: #C084FC; font-size: 10px; font-weight: 600; padding: 3px 8px; border-radius: 10px; border: 1px solid rgba(192, 132, 252, 0.3);")
        elif is_correct:
            self.badge_label.setStyleSheet("color: #34D399; font-size: 10px; font-weight: 700; letter-spacing: 0.8px;")
            self.status_pill.setText("Chính xác")
            self.status_pill.setStyleSheet("background-color: rgba(16, 185, 129, 0.15); color: #34D399; font-size: 10px; font-weight: 600; padding: 3px 8px; border-radius: 10px; border: 1px solid rgba(16, 185, 129, 0.3);")
        elif level == 1:
            self.badge_label.setStyleSheet("color: #60A5FA; font-size: 10px; font-weight: 700; letter-spacing: 0.8px;")
            self.status_pill.setText("Định hướng")
            self.status_pill.setStyleSheet("background-color: rgba(96, 165, 250, 0.15); color: #60A5FA; font-size: 10px; font-weight: 600; padding: 3px 8px; border-radius: 10px; border: 1px solid rgba(96, 165, 250, 0.3);")
        elif level == 2:
            self.badge_label.setStyleSheet("color: #FBBF24; font-size: 10px; font-weight: 700; letter-spacing: 0.8px;")
            self.status_pill.setText("Công cụ")
            self.status_pill.setStyleSheet("background-color: rgba(251, 191, 36, 0.15); color: #FBBF24; font-size: 10px; font-weight: 600; padding: 3px 8px; border-radius: 10px; border: 1px solid rgba(251, 191, 36, 0.3);")
        elif level == 3:
            self.badge_label.setStyleSheet("color: #F87171; font-size: 10px; font-weight: 700; letter-spacing: 0.8px;")
            self.status_pill.setText("Khoanh vùng")
            self.status_pill.setStyleSheet("background-color: rgba(248, 113, 113, 0.15); color: #F87171; font-size: 10px; font-weight: 600; padding: 3px 8px; border-radius: 10px; border: 1px solid rgba(248, 113, 113, 0.3);")

        if procedure_active and agent_status == "observing":
            self.status_pill.setText(f"Thao tác {info.get('action_position', '')}")
            self.status_pill.setStyleSheet(
                "background-color: rgba(96, 165, 250, 0.15); color: #93C5FD; "
                "font-size: 10px; font-weight: 600; padding: 3px 8px; "
                "border-radius: 10px; border: 1px solid rgba(96, 165, 250, 0.35);"
            )

    def _update_procedure_ui(self, info: dict):
        self.procedure_frame.setVisible(True)
        rows = []
        for action in info.get("procedure_actions", []):
            status = action.get("status")
            number = action.get("number")
            title = action.get("title", "")
            if status == "done":
                color, state_text = "#34D399", "Đã xong"
            elif status == "inferred":
                color, state_text = "#FBBF24", "Đạt theo kết quả"
            elif status == "current":
                color, state_text = "#93C5FD", "Đang làm"
            else:
                color, state_text = "#64748B", "Tiếp theo"
            rows.append(
                f'<span style="color:{color}; font-weight:600;">'
                f'{number}. {title}</span> '
                f'<span style="color:{color};">— {state_text}</span>'
            )
        self.procedure_steps_label.setText("<br>".join(rows))

        verification_state = info.get("verification_state", "waiting")
        verification_color = {
            "correct": "#34D399",
            "wrong": "#F87171",
            "waiting": "#FBBF24",
        }.get(verification_state, "#CBD5E1")
        self.verification_label.setStyleSheet(
            "border: none; background: transparent; "
            f"color: {verification_color}; font-size: 11px; font-weight: 600;"
        )
        self.verification_label.setText(info.get("verification_message", ""))
        next_action = info.get("next_action_preview", "")
        self.next_action_label.setText(
            f"Tiếp theo: {next_action}" if next_action else ""
        )
        self.next_action_label.setVisible(bool(next_action))

    def _keep_inside_available_screen(self):
        """Giữ toàn bộ card trong vùng làm việc khi nội dung động đổi kích thước."""
        from PyQt6.QtWidgets import QApplication

        screen = QApplication.screenAt(self.frameGeometry().center())
        if screen is None:
            screen = QApplication.primaryScreen()
        if screen is None:
            return
        available = screen.availableGeometry()
        margin = 10
        max_x = max(available.left() + margin, available.right() - self.width() - margin + 1)
        max_y = max(available.top() + margin, available.bottom() - self.height() - margin + 1)
        next_x = min(max(self.x(), available.left() + margin), max_x)
        next_y = min(max(self.y(), available.top() + margin), max_y)
        if next_x != self.x() or next_y != self.y():
            self.move(next_x, next_y)

    def _set_mascot_state(self, state: str):
        """Hiện pose phù hợp mà không làm thay đổi vị trí các nút điều khiển."""
        style = mascot_style(state)
        pixmap = QPixmap(str(mascot_asset_path(state)))
        if pixmap.isNull():
            self.mascot_label.clear()
            self.mascot_label.hide()
            return

        self.mascot_label.show()
        self.mascot_label.setToolTip(style.title.title())
        self.mascot_label.setStyleSheet("background: transparent; border: none; padding: 0;")
        self.mascot_label.setPixmap(
            pixmap.scaled(
                80,
                112,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    # Xử lý kéo thả cửa sổ tự do
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()
