"""
Mouse Speed Telemetry HUD: Cửa sổ nổi hiển thị vận tốc chuột thời gian thực (Real-time Speedometer),
đồ thị sóng vận tốc và ngữ cảnh ô tính trong Microsoft Excel.
"""

import sys
import os
from typing import Optional
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QProgressBar, QFrame, QPushButton
)
from PyQt6.QtCore import Qt, QTimer, QPoint
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QLinearGradient, QFont, QPainterPath

# Đảm bảo đường dẫn import
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.core.mouse_tracker import MouseSpeedTracker
from src.core.excel_monitor import ExcelMonitor


class SparklineGraphWidget(QWidget):
    """Widget vẽ đồ thị sóng vận tốc thời gian thực dạng dải sóng công nghệ cao (Sparkline)."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.history = [0.0] * 60
        self.max_val = 1500.0
        self.setFixedHeight(75)
        self.setStyleSheet("background-color: #0b1120; border-radius: 8px; border: 1px solid #1e293b;")

    def update_data(self, history, max_val=1500.0):
        self.history = history
        self.max_val = max(800.0, max(history) * 1.1)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        if len(self.history) < 2:
            return

        # Tạo đường đi Path
        points = []
        step_x = w / (len(self.history) - 1)
        for i, val in enumerate(self.history):
            clamped = min(val, self.max_val)
            normalized_y = h - (clamped / self.max_val) * (h - 12) - 6
            points.append((i * step_x, normalized_y))

        # 1. Vẽ vùng Gradient dưới đường sóng
        fill_path = QPainterPath()
        fill_path.moveTo(0, h)
        for x, y in points:
            fill_path.lineTo(x, y)
        fill_path.lineTo(w, h)
        fill_path.closeSubpath()

        grad = QLinearGradient(0, 0, 0, h)
        grad.setColorAt(0.0, QColor(14, 165, 233, 120))   # Sky Blue mờ
        grad.setColorAt(1.0, QColor(14, 165, 233, 10))
        painter.fillPath(fill_path, QBrush(grad))

        # 2. Vẽ đường sóng chính
        stroke_path = QPainterPath()
        stroke_path.moveTo(points[0][0], points[0][1])
        for x, y in points[1:]:
            stroke_path.lineTo(x, y)

        pen = QPen(QColor(56, 189, 248), 2.2)  # Bright Cyan Neon
        painter.setPen(pen)
        painter.drawPath(stroke_path)

        # 3. Vẽ điểm phát sáng tại vị trí mới nhất
        last_x, last_y = points[-1]
        painter.setBrush(QBrush(QColor(244, 63, 94)))  # Điểm đỏ neon
        painter.setPen(QPen(QColor(255, 255, 255), 1.5))
        painter.drawEllipse(QPoint(int(last_x), int(last_y)), 4, 4)


class MouseSpeedHUD(QWidget):
    """
    Cửa sổ HUD nổi Always-On-Top theo dõi tốc độ chuột realtime và ngữ cảnh ô tính Excel.
    """
    def __init__(self, excel_monitor: Optional[ExcelMonitor] = None):
        super().__init__()
        self.excel_monitor = excel_monitor or ExcelMonitor()
        self.tracker = MouseSpeedTracker(excel_monitor=self.excel_monitor)

        self.drag_position = QPoint()
        self.init_ui()

        # Timer lấy mẫu tốc độ 30 FPS (mỗi 33ms)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.on_tick)
        self.timer.start(33)

    def init_ui(self):
        # Thiết lập cửa sổ nổi Always on Top, không viền hệ điều hành (Frameless)
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(380, 430)

        # Container giao diện chính phong cách Glassmorphism / Cyber Fintech
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        self.card = QFrame()
        self.card.setStyleSheet("""
            QFrame {
                background-color: #0f172a;
                border: 2px solid #334155;
                border-radius: 16px;
            }
        """)
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(18, 14, 18, 16)
        card_layout.setSpacing(10)

        # 1. Header: Tiêu đề + Nút Đóng
        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(2)

        title_lbl = QLabel("⚡ EXCEL MOUSE TELEMETRY")
        title_lbl.setStyleSheet("color: #38bdf8; font-size: 13px; font-weight: 800; letter-spacing: 1px;")
        sub_title = QLabel("Theo Dõi Tốc Độ Chuột Realtime")
        sub_title.setStyleSheet("color: #94a3b8; font-size: 11px;")
        title_box.addWidget(title_lbl)
        title_box.addWidget(sub_title)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(26, 26)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #cbd5e1;
                border: 1px solid #475569;
                border-radius: 13px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #ef4444;
                color: white;
            }
        """)
        close_btn.clicked.connect(self.close)

        header.addLayout(title_box)
        header.addStretch()
        header.addWidget(close_btn)
        card_layout.addLayout(header)

        # 2. Đồng hồ tốc độ lớn (Digital Speed Display)
        speed_box = QHBoxLayout()
        self.speed_number = QLabel("0.0")
        self.speed_number.setStyleSheet("color: #10b981; font-size: 38px; font-weight: 900; font-family: 'Consolas', 'Courier New', monospace;")

        unit_box = QVBoxLayout()
        unit_lbl = QLabel("pixels/s")
        unit_lbl.setStyleSheet("color: #64748b; font-size: 13px; font-weight: bold;")
        self.max_speed_lbl = QLabel("Max: 0 px/s")
        self.max_speed_lbl.setStyleSheet("color: #475569; font-size: 10px;")
        unit_box.addWidget(unit_lbl)
        unit_box.addWidget(self.max_speed_lbl)

        speed_box.addWidget(self.speed_number)
        speed_box.addLayout(unit_box)
        speed_box.addStretch()
        card_layout.addLayout(speed_box)

        # 3. Thanh đo vận tốc (Gauge Progress Bar)
        self.speed_bar = QProgressBar()
        self.speed_bar.setRange(0, 1500)
        self.speed_bar.setValue(0)
        self.speed_bar.setTextVisible(False)
        self.speed_bar.setFixedHeight(8)
        self.speed_bar.setStyleSheet("""
            QProgressBar {
                background-color: #1e293b;
                border-radius: 4px;
                border: none;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #10b981, stop:0.5 #3b82f6, stop:1 #f59e0b);
                border-radius: 4px;
            }
        """)
        card_layout.addWidget(self.speed_bar)

        # 4. Huy hiệu nhận thức hành vi (Cognitive State Badge)
        self.badge = QLabel("⏸️ TĨNH (CHUẨN BỊ THAO TÁC)")
        self.badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.badge.setFixedHeight(28)
        self.badge.setStyleSheet("""
            background-color: rgba(16, 185, 129, 0.15);
            color: #10b981;
            border: 1px solid #10b981;
            border-radius: 14px;
            font-size: 11px;
            font-weight: 700;
        """)
        card_layout.addWidget(self.badge)

        # 5. Đồ thị sóng Sparkline vận tốc
        self.graph = SparklineGraphWidget()
        card_layout.addWidget(self.graph)

        # 6. Ngữ cảnh Excel & Vị trí chuột
        ctx_box = QFrame()
        ctx_box.setStyleSheet("background-color: #1e293b; border-radius: 10px; border: 1px solid #334155;")
        ctx_layout = QVBoxLayout(ctx_box)
        ctx_layout.setContentsMargins(12, 10, 12, 10)
        ctx_layout.setSpacing(4)

        # Vị trí màn hình
        self.pos_lbl = QLabel("📍 Tọa độ chuột: X: 0 | Y: 0")
        self.pos_lbl.setStyleSheet("color: #94a3b8; font-size: 11px;")

        # Trạng thái cửa sổ Excel
        self.excel_status_lbl = QLabel("🏢 Cửa sổ: Đang kiểm tra...")
        self.excel_status_lbl.setStyleSheet("color: #cbd5e1; font-size: 11px;")

        # Ô tính dưới con trỏ
        self.cell_lbl = QLabel("🎯 Ô đang hover: [ Ngoài bảng tính ]")
        self.cell_lbl.setStyleSheet("color: #38bdf8; font-size: 12px; font-weight: bold;")

        ctx_layout.addWidget(self.pos_lbl)
        ctx_layout.addWidget(self.excel_status_lbl)
        ctx_layout.addWidget(self.cell_lbl)
        card_layout.addWidget(ctx_box)

        # 7. Nút hành động nhanh
        actions_layout = QHBoxLayout()
        self.open_excel_btn = QPushButton("📁 Mở Bài Tập 07 Để Test")
        self.open_excel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.open_excel_btn.setStyleSheet("""
            QPushButton {
                background-color: #0f766e;
                color: white;
                font-weight: bold;
                font-size: 11px;
                border-radius: 6px;
                padding: 6px 12px;
                border: none;
            }
            QPushButton:hover {
                background-color: #0d9488;
            }
        """)
        self.open_excel_btn.clicked.connect(self.on_open_exercise)
        actions_layout.addWidget(self.open_excel_btn)

        card_layout.addLayout(actions_layout)
        main_layout.addWidget(self.card)

    def on_open_exercise(self):
        """Mở file Bài 07 để người dùng trải nghiệm ngay lập tức."""
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "bài tập"))
        file_path = os.path.join(base_dir, "Bài 07. Các thao tác cơ bản với địa chỉ ô.xlsx")
        self.excel_monitor.launch_exercise(file_path)

    def on_tick(self):
        """Vòng lặp cập nhật tốc độ chuột mỗi 33ms."""
        data = self.tracker.update()

        # 1. Cập nhật số tốc độ
        speed = data["speed"]
        self.speed_number.setText(f"{speed:.1f}")

        # Đổi màu số hiển thị linh hoạt theo tốc độ
        color = data["state_color"]
        self.speed_number.setStyleSheet(f"color: {color}; font-size: 38px; font-weight: 900; font-family: 'Consolas', monospace;")
        self.max_speed_lbl.setText(f"Max: {data['max_speed']:.0f} px/s")

        # 2. Cập nhật thanh Gauge
        self.speed_bar.setValue(int(min(speed, 1500)))

        # 3. Cập nhật Huy hiệu trạng thái
        self.badge.setText(f"● {data['state_label']}")
        self.badge.setStyleSheet(f"""
            background-color: {color}22;
            color: {color};
            border: 1px solid {color};
            border-radius: 14px;
            font-size: 11px;
            font-weight: 700;
        """)

        # 4. Cập nhật Đồ thị sóng Sparkline
        self.graph.update_data(data["speed_history"])

        # 5. Cập nhật thông tin vị trí và Excel
        self.pos_lbl.setText(f"📍 Tọa độ chuột: X: {data['x']} | Y: {data['y']} (Gia tốc: {data['acceleration']:+.0f} px/s²)")

        if data["is_inside_excel"]:
            title_short = data["excel_title"][:30] + "..." if len(data["excel_title"]) > 30 else data["excel_title"]
            self.excel_status_lbl.setText(f"🏢 Trong Excel: {title_short}")
            self.excel_status_lbl.setStyleSheet("color: #10b981; font-size: 11px; font-weight: bold;")
        else:
            self.excel_status_lbl.setText("🏢 Cửa sổ: Ngoài Excel")
            self.excel_status_lbl.setStyleSheet("color: #94a3b8; font-size: 11px;")

        # Cập nhật ô tính đang hover
        hover_cell = data["hovered_cell"]
        if hover_cell and hover_cell not in ["OUTSIDE_GRID", "EXCEL_BUSY", "SHAPE/OBJECT"]:
            val_str = f" | Giá trị: {data['cell_value']}" if data['cell_value'] is not None else ""
            self.cell_lbl.setText(f"🎯 Ô đang trỏ: [ {hover_cell} ]{val_str}")
            self.cell_lbl.setStyleSheet("color: #38bdf8; font-size: 12px; font-weight: bold;")
        elif hover_cell == "EXCEL_BUSY":
            self.cell_lbl.setText("🎯 Excel đang nhập dữ liệu (Edit Mode)")
            self.cell_lbl.setStyleSheet("color: #f59e0b; font-size: 11px; font-style: italic;")
        else:
            self.cell_lbl.setText("🎯 Vùng chuột: Thanh công cụ / Ngoài bảng")
            self.cell_lbl.setStyleSheet("color: #64748b; font-size: 11px;")

    # Hỗ trợ kéo thả di chuyển cửa sổ HUD bằng chuột
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()


def main():
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    app = QApplication(sys.argv)
    hud = MouseSpeedHUD()
    hud.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
