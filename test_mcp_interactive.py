"""
Interactive MCP Tester: Khung tùy chọn kiểm tra tương tác hai chiều với Excel qua giao thức MCP (Model Context Protocol).
Cung cấp:
1. Đọc và hiển thị tọa độ pixel màn hình (X, Y, Width, Height) thời gian thực của ô đang chọn trên Excel.
2. Vẽ khung viền hướng dẫn màu đỏ nhấp nháy phát sáng (Overlay) bám dính trực tiếp vào ô đang chọn theo đúng chỉ số tọa độ (x:y:w:h).
3. Form nhập địa chỉ ô và nội dung để ghi trực tiếp vào Excel qua MCP Tool.
"""

import sys
import os
import time
import re
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QTextEdit, QFrame, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QColor

# Đảm bảo đường dẫn import
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__))))

from src.excel_mcp.server import (
    excel_write_cell,
    excel_get_active_state,
    excel_get_cell_rect
)
from src.core.excel_monitor import ExcelMonitor
from src.gui.overlay_window import OverlayWindow


class MCPInteractiveTestWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.excel_monitor = ExcelMonitor()
        self.last_active_cell = ""
        self.last_selection_address = ""
        self.current_active_cell = ""
        self.overlay_enabled = True
        # Khi người dùng nhập/chọn một địa chỉ, giữ khung ở địa chỉ đó. Nếu không
        # có mục tiêu ghim, overlay tiếp tục bám ô đang chọn như trước.
        self.pinned_target_cell = None

        # 1. Khởi tạo Lớp phủ trong suốt vẽ khung hướng dẫn màu đỏ Always-On-Top
        self.overlay = OverlayWindow()
        self.overlay.show()

        self.init_ui()

        # Timer chu kỳ nhanh (150ms) để bám dính realtime khi người dùng click trên Excel
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self.poll_excel_active_state)
        self.status_timer.start(150)
        self.poll_excel_active_state()

    def init_ui(self):
        self.setWindowTitle("🛠️ BỘ TEST TƯƠNG TÁC & VẼ KHUNG ĐỎ THEO TỌA ĐỘ Ô (MCP)")
        self.setFixedSize(560, 740)
        # Always-On-Top để luôn nổi trên Excel
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint)

        self.setStyleSheet("""
            QWidget {
                background-color: #0f172a;
                color: #f8fafc;
                font-family: 'Segoe UI', system-ui, sans-serif;
            }
            QLabel {
                font-size: 13px;
                font-weight: 500;
            }
            QLineEdit {
                background-color: #1e293b;
                border: 1.5px solid #334155;
                border-radius: 8px;
                padding: 9px 12px;
                color: #f8fafc;
                font-size: 13px;
                font-weight: bold;
            }
            QLineEdit:focus {
                border: 1.5px solid #38bdf8;
                background-color: #0f172a;
            }
            QPushButton {
                font-weight: bold;
                border-radius: 8px;
                padding: 10px 14px;
                font-size: 12px;
                border: none;
            }
            QTextEdit {
                background-color: #020617;
                border: 1px solid #1e293b;
                border-radius: 8px;
                color: #a5f3fc;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 12px;
                padding: 8px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        # 1. Header & Tiêu đề
        title_lbl = QLabel("⚡ GIÁM SÁT & VẼ KHUNG ĐỎ THEO TỌA ĐỘ Ô (MCP)")
        title_lbl.setStyleSheet("color: #38bdf8; font-size: 15px; font-weight: 800; letter-spacing: 0.5px;")
        layout.addWidget(title_lbl)

        # Trạng thái kết nối
        self.conn_badge = QLabel("⏳ Đang kết nối Excel...")
        self.conn_badge.setStyleSheet("""
            background-color: #1e293b;
            color: #f59e0b;
            border-radius: 6px;
            padding: 5px 10px;
            font-size: 11px;
            font-weight: bold;
        """)
        layout.addWidget(self.conn_badge)

        # 2. KHUNG HIỂN THỊ TỌA ĐỘ Ô ĐANG CHỌN (REALTIME ACTIVE CELL COORDINATES)
        active_box = QFrame()
        active_box.setStyleSheet("""
            QFrame {
                background-color: #1e293b;
                border: 1.5px solid #0284c7;
                border-radius: 8px;
                padding: 8px;
            }
        """)
        active_layout = QVBoxLayout(active_box)
        active_layout.setSpacing(7)
        active_layout.setContentsMargins(10, 8, 10, 8)

        # Hàng 1: Ô đang chọn
        row1 = QHBoxLayout()
        self.active_selection_title_lbl = QLabel("🎯 Ô BẠN ĐANG CHỌN:")
        self.active_selection_title_lbl.setStyleSheet("color: #38bdf8; font-weight: bold; font-size: 12px;")
        self.active_cell_name_lbl = QLabel("--")
        self.active_cell_name_lbl.setStyleSheet("color: #facc15; font-size: 18px; font-weight: 900;")
        row1.addWidget(self.active_selection_title_lbl)
        row1.addWidget(self.active_cell_name_lbl)
        row1.addStretch()

        self.use_active_btn = QPushButton("📋 Chép vào ô nhập")
        self.use_active_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.use_active_btn.setStyleSheet("""
            QPushButton {
                background-color: #0f766e;
                color: white;
                padding: 5px 10px;
                font-size: 11px;
                border-radius: 5px;
            }
            QPushButton:hover { background-color: #0d9488; }
        """)
        self.use_active_btn.clicked.connect(self.on_use_active_cell)
        row1.addWidget(self.use_active_btn)
        active_layout.addLayout(row1)

        # Hàng 2: Tọa độ pixel màn hình (X, Y, Width, Height)
        row2 = QHBoxLayout()
        self.coord_title_lbl = QLabel("📍 TỌA ĐỘ MÀN HÌNH (X:Y:W:H):")
        self.coord_title_lbl.setStyleSheet("color: #cbd5e1; font-size: 11px; font-weight: bold;")
        self.active_cell_coord_input = QLineEdit()
        self.active_cell_coord_input.setReadOnly(True)
        self.active_cell_coord_input.setStyleSheet("""
            QLineEdit {
                background-color: #020617;
                color: #34d399;
                font-family: 'Consolas', monospace;
                font-size: 13px;
                font-weight: bold;
                border: 1.5px solid #059669;
                padding: 6px 10px;
            }
        """)
        row2.addWidget(self.coord_title_lbl)
        row2.addWidget(self.active_cell_coord_input, 1)
        active_layout.addLayout(row2)

        # Hàng 3: Điều khiển Khung Hướng Dẫn Đỏ (Overlay Toggle)
        row3 = QHBoxLayout()
        self.overlay_toggle_btn = QPushButton("🔴 KHUNG HƯỚNG DẪN ĐỎ: ĐANG BẬT")
        self.overlay_toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.overlay_toggle_btn.setStyleSheet("""
            QPushButton {
                background-color: #991b1b;
                color: #fef2f2;
                font-weight: bold;
                padding: 6px 12px;
                border: 1px solid #ef4444;
                border-radius: 6px;
                font-size: 11px;
            }
            QPushButton:hover { background-color: #b91c1c; }
        """)
        self.overlay_toggle_btn.clicked.connect(self.toggle_overlay)
        row3.addWidget(self.overlay_toggle_btn)

        self.active_cell_val_lbl = QLabel("(Trống)")
        self.active_cell_val_lbl.setStyleSheet("color: #94a3b8; font-size: 11px; font-style: italic;")
        row3.addStretch()
        row3.addWidget(QLabel("Giá trị:"))
        row3.addWidget(self.active_cell_val_lbl)
        active_layout.addLayout(row3)

        layout.addWidget(active_box)

        # Divider
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #334155;")
        layout.addWidget(line)

        # 3. FORM GHI DỮ LIỆU VÀO EXCEL QUA MCP
        form_title = QLabel("✍️ THIẾT LẬP THAO TÁC GHI VÀO EXCEL QUA MCP TOOL")
        form_title.setStyleSheet("color: #f8fafc; font-size: 12px; font-weight: bold;")
        layout.addWidget(form_title)

        inputs_layout = QHBoxLayout()
        inputs_layout.setSpacing(10)

        # Cột trái: Địa chỉ ô
        addr_col = QVBoxLayout()
        addr_col.setSpacing(3)
        addr_lbl = QLabel("1. Địa chỉ ô (VD: C8, B8, D7):")
        addr_lbl.setStyleSheet("color: #cbd5e1; font-size: 11px; font-weight: bold;")
        self.cell_input = QLineEdit()
        self.cell_input.setText("C8")
        self.cell_input.setPlaceholderText("VD: C8")
        addr_col.addWidget(addr_lbl)
        addr_col.addWidget(self.cell_input)
        inputs_layout.addLayout(addr_col, 1)

        # Cột phải: Nội dung ghi
        val_col = QVBoxLayout()
        val_col.setSpacing(3)
        val_lbl = QLabel("2. Nội dung cần ghi:")
        val_lbl.setStyleSheet("color: #cbd5e1; font-size: 11px; font-weight: bold;")
        self.val_input = QLineEdit()
        self.val_input.setText("B8")
        self.val_input.setPlaceholderText("VD: B8, 1988...")
        val_col.addWidget(val_lbl)
        val_col.addWidget(self.val_input)
        inputs_layout.addLayout(val_col, 1)

        layout.addLayout(inputs_layout)

        # Hàng nút bấm hành động
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self.write_btn = QPushButton("🚀 GHI VÀO EXCEL (MCP)")
        self.write_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.write_btn.setStyleSheet("""
            QPushButton {
                background-color: #0284c7;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #0369a1; }
            QPushButton:pressed { background-color: #075985; }
        """)
        self.write_btn.clicked.connect(self.on_click_write)

        self.snap_input_btn = QPushButton("🎯 Khoanh vùng ô này")
        self.snap_input_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.snap_input_btn.setStyleSheet("""
            QPushButton {
                background-color: #334155;
                color: #38bdf8;
                border: 1px solid #0284c7;
            }
            QPushButton:hover { background-color: #475569; }
        """)
        self.snap_input_btn.clicked.connect(self.on_snap_target_cell)

        self.clear_btn = QPushButton("🧹 Xóa ô")
        self.clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #27272a;
                color: #e4e4e7;
                border: 1px solid #3f3f46;
            }
            QPushButton:hover { background-color: #3f3f46; }
        """)
        self.clear_btn.clicked.connect(self.on_click_clear)

        btn_layout.addWidget(self.write_btn, 2)
        btn_layout.addWidget(self.snap_input_btn, 1)
        btn_layout.addWidget(self.clear_btn, 1)
        layout.addLayout(btn_layout)

        # Nhập địa chỉ sẽ tự khoanh sau một khoảng debounce ngắn; Enter tại ô địa
        # chỉ chỉ khoanh vùng, Enter tại ô nội dung mới thực hiện ghi.
        self.snap_debounce_timer = QTimer(self)
        self.snap_debounce_timer.setSingleShot(True)
        self.snap_debounce_timer.setInterval(250)
        self.snap_debounce_timer.timeout.connect(self.on_snap_target_cell_silent)
        self.cell_input.textEdited.connect(self.on_cell_address_edited)
        self.cell_input.returnPressed.connect(self.on_snap_target_cell)
        self.val_input.returnPressed.connect(self.on_click_write)

        # 4. Khung Log hiển thị payload MCP
        log_title = QLabel("📜 NHẬT KÝ GIAO THỨC MCP (PAYLOAD & RESPONSE):")
        log_title.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: bold; margin-top: 4px;")
        layout.addWidget(log_title)

        self.log_console = QTextEdit()
        self.log_console.setReadOnly(True)
        layout.addWidget(self.log_console)

        self.log("🚀 Sẵn sàng. Khung viền đỏ nhấp nháy phát sáng đang bám dính theo ô bạn chọn trên Excel!")

    def log(self, text: str):
        t_str = time.strftime("%H:%M:%S")
        self.log_console.append(f"[{t_str}] {text}")
        sb = self.log_console.verticalScrollBar()
        if sb:
            sb.setValue(sb.maximum())

    def toggle_overlay(self):
        """Bật hoặc tắt lớp phủ khoanh vùng màu đỏ."""
        self.overlay_enabled = not self.overlay_enabled
        if self.overlay_enabled:
            self.overlay_toggle_btn.setText("🔴 KHUNG HƯỚNG DẪN ĐỎ: ĐANG BẬT")
            self.overlay_toggle_btn.setStyleSheet("""
                QPushButton {
                    background-color: #991b1b;
                    color: #fef2f2;
                    font-weight: bold;
                    padding: 6px 12px;
                    border: 1px solid #ef4444;
                    border-radius: 6px;
                    font-size: 11px;
                }
                QPushButton:hover { background-color: #b91c1c; }
            """)
            self.log("🔴 Đã bật Khung hướng dẫn đỏ.")
            self.poll_excel_active_state()
        else:
            self.overlay_toggle_btn.setText("⚪ KHUNG HƯỚNG DẪN ĐỎ: ĐÃ TẮT")
            self.overlay_toggle_btn.setStyleSheet("""
                QPushButton {
                    background-color: #334155;
                    color: #94a3b8;
                    font-weight: bold;
                    padding: 6px 12px;
                    border: 1px solid #475569;
                    border-radius: 6px;
                    font-size: 11px;
                }
                QPushButton:hover { background-color: #475569; }
            """)
            self.overlay.clear_target()
            self.log("⚪ Đã ẩn Khung hướng dẫn đỏ.")

    def poll_excel_active_state(self):
        """Vòng lặp lấy trạng thái, tọa độ và vẽ khung đỏ theo đúng x:y:w:h."""
        state = excel_get_active_state()
        if state.get("connected"):
            wb_name = state.get("workbook", "Unknown")
            sheet_name = state.get("sheet", "")
            active_c = state.get("active_cell", "--")
            val = state.get("cell_value", "")
            rect = state.get("cell_rect")
            selection_address = state.get("selection_address") or active_c
            selection_rect = state.get("selection_rect") or rect
            selection_rows = max(1, int(state.get("selection_rows", 1)))
            selection_columns = max(1, int(state.get("selection_columns", 1)))
            is_range_selection = bool(state.get("is_range_selection", False))

            self.conn_badge.setText(f"🟢 EXCEL LIVE: {wb_name} | Sheet: {sheet_name}")
            self.conn_badge.setStyleSheet("""
                background-color: #064e3b;
                color: #34d399;
                border-radius: 6px;
                padding: 5px 10px;
                font-size: 11px;
                font-weight: bold;
                border: 1px solid #059669;
            """)

            # Cập nhật ô/vùng đang chọn. Giá trị vẫn là giá trị ActiveCell neo.
            self.current_active_cell = active_c
            self.active_selection_title_lbl.setText(
                "🎯 VÙNG BẠN ĐANG CHỌN:" if is_range_selection
                else "🎯 Ô BẠN ĐANG CHỌN:"
            )
            self.active_cell_name_lbl.setText(selection_address)
            self.active_cell_val_lbl.setText(f"'{val}'" if val else "(Trống)")

            # Địa chỉ nhập tay chỉ được ghim cho đến khi người dùng chủ động chọn
            # một ô Excel khác. Khi đó ưu tiên thao tác mới và chuyển overlay sang
            # ô vừa chọn, kể cả sau khi đã cuộn worksheet.
            if self.should_release_pinned_target(
                self.last_active_cell,
                active_c,
                self.pinned_target_cell,
                self.last_selection_address,
                selection_address,
            ):
                old_target = self.pinned_target_cell
                self.pinned_target_cell = None
                self.log(
                    f"🖱️ Đã chuyển khung từ ô ghim {old_target} sang ô vừa chọn {active_c}."
                )

            overlay_cell = self.pinned_target_cell or selection_address or active_c
            overlay_rect = selection_rect
            if self.pinned_target_cell:
                target_res = excel_get_cell_rect(self.pinned_target_cell, sheet_name)
                overlay_rect = (
                    (
                        target_res["x"], target_res["y"],
                        target_res["width"], target_res["height"]
                    )
                    if target_res.get("success") else None
                )

            if overlay_rect:
                x, y, w, h = overlay_rect
                log_x, log_y = int(round(x)), int(round(y))
                log_w, log_h = int(round(w)), int(round(h))
                if self.pinned_target_cell:
                    self.coord_title_lbl.setText(f"📍 MỤC TIÊU {overlay_cell} (X:Y:W:H):")
                elif is_range_selection:
                    self.coord_title_lbl.setText("📍 TỌA ĐỘ TOÀN VÙNG (X:Y:W:H):")
                else:
                    self.coord_title_lbl.setText("📍 TỌA ĐỘ MÀN HÌNH (X:Y:W:H):")
                self.active_cell_coord_input.setText(f"X: {log_x} | Y: {log_y} | W: {log_w} | H: {log_h}")

                if self.overlay_enabled:
                    if self.pinned_target_cell:
                        badge = f"👉 MỤC TIÊU: {overlay_cell} ({log_w}x{log_h} px)"
                    elif is_range_selection:
                        badge = (
                            f"👉 VÙNG ĐANG CHỌN: {overlay_cell} "
                            f"({selection_columns} cột × {selection_rows} dòng)"
                        )
                    else:
                        badge = f"👉 Ô ĐANG CHỌN: {overlay_cell} ({log_w}x{log_h} px)"
                    self.overlay.set_target_rect((x, y, w, h), is_physical_pixels=True, badge_text=badge)
            else:
                self.active_cell_coord_input.setText("Ô mục tiêu không nằm trong vùng nhìn thấy")
                if self.overlay_enabled:
                    self.overlay.clear_target()

            # Nếu người dùng vừa click sang ô mới trên Excel -> Ghi log
            if active_c and active_c != self.last_active_cell:
                if self.last_active_cell != "":
                    r_str = f"X={rect[0]}, Y={rect[1]}, W={rect[2]}, H={rect[3]}" if rect else "N/A"
                    self.log(f"🖱️ [CLICK EXCEL] Chuyển sang ô {active_c} -> Khung đỏ bám dính tại: {r_str}")
                self.last_active_cell = active_c
            if (
                is_range_selection
                and self.last_selection_address
                and selection_address != self.last_selection_address
            ):
                self.log(
                    f"🖱️ [CHỌN VÙNG EXCEL] {selection_address} -> "
                    f"Khung đỏ bao {selection_columns} cột × {selection_rows} dòng."
                )
            self.last_selection_address = selection_address
        else:
            self.conn_badge.setText("🔴 CHƯA KẾT NỐI EXCEL (Vui lòng mở file Excel)")
            self.conn_badge.setStyleSheet("""
                background-color: #450a0a;
                color: #f87171;
                border-radius: 6px;
                padding: 5px 10px;
                font-size: 11px;
                font-weight: bold;
                border: 1px solid #dc2626;
            """)
            self.active_cell_coord_input.setText("Chưa kết nối")
            if self.overlay_enabled:
                self.overlay.clear_target()

    @staticmethod
    def should_release_pinned_target(
        last_active: str,
        active: str,
        pinned: str,
        last_selection: str = "",
        selection: str = "",
    ) -> bool:
        """Ô được click mới luôn được ưu tiên hơn mục tiêu nhập tay trước đó."""
        active_cell_changed = bool(
            last_active
            and active
            and pinned
            and active != last_active
            and active != pinned
        )
        selected_range_changed = bool(
            pinned
            and last_selection
            and selection
            and selection != last_selection
            and selection != pinned
        )
        return active_cell_changed or selected_range_changed

    def on_use_active_cell(self):
        """Sao chép địa chỉ ô đang chọn trên Excel vào ô nhập liệu."""
        act = self.current_active_cell.strip()
        if act and act != "--":
            self.cell_input.setText(act)
            self._snap_target_cell(log_result=False)
            self.log(f"📋 Đã chọn ô {act} vào mục tiêu ghi.")

    def on_cell_address_edited(self, _text: str):
        """Debounce để không gọi COM ở từng phím nhưng vẫn khoanh gần như tức thì."""
        self.snap_debounce_timer.start()

    def on_snap_target_cell_silent(self):
        self._snap_target_cell(log_result=False)

    def on_snap_target_cell(self):
        """Khoanh vùng đỏ ngay vào ô đang điền trong form nhập liệu."""
        self._snap_target_cell(log_result=True)

    def _snap_target_cell(self, log_result: bool = True):
        cell_addr = self.cell_input.text().strip().replace("$", "").upper()
        if not cell_addr:
            self.pinned_target_cell = None
            return

        if not re.fullmatch(r"[A-Z]{1,3}[1-9][0-9]{0,6}", cell_addr):
            if log_result:
                self.log(f"⚠️ Địa chỉ '{cell_addr}' không hợp lệ. Ví dụ đúng: C8, AA12.")
            return

        # Ghim ngay cả khi ô tạm thời ngoài màn hình. Vòng poll sẽ không quay về
        # ô active và sẽ tự vẽ lại đúng mục tiêu khi người dùng cuộn nó vào view.
        self.pinned_target_cell = cell_addr
        res = excel_get_cell_rect(cell_addr)
        if res.get("success"):
            x, y, w, h = res["x"], res["y"], res["width"], res["height"]
            log_x, log_y = int(round(x)), int(round(y))
            log_w, log_h = int(round(w)), int(round(h))
            if log_result:
                self.log(f"🎯 [MCP OVERLAY] Đã ghim khung đỏ vào ô {cell_addr} tại: X={log_x}, Y={log_y}, W={log_w}, H={log_h}")
            if self.overlay_enabled:
                self.overlay.set_target_rect((x, y, w, h), is_physical_pixels=True, badge_text=f"👉 MỤC TIÊU: {cell_addr} ({log_w}x{log_h} px)")
        else:
            if log_result:
                self.log(f"⚠️ [MCP TOOL] {res.get('error', f'Không tìm thấy tọa độ ô {cell_addr}')}")

    def on_click_write(self):
        """Gửi lệnh ghi dữ liệu qua MCP Tool."""
        cell_addr = self.cell_input.text().strip().upper()
        val = self.val_input.text().strip()

        if not cell_addr:
            QMessageBox.warning(self, "Thiếu thông tin", "Vui lòng nhập địa chỉ ô (VD: C8)")
            return

        self.log(f"📡 [MCP REQUEST] Gửi Tool: excel_write_cell(cell_address='{cell_addr}', value='{val}')")

        # Gọi MCP Tool
        res = excel_write_cell(cell_address=cell_addr, value=val)

        if res.get("success"):
            self.pinned_target_cell = cell_addr
            self.log(f"✅ [MCP RESPONSE] {res.get('message')}")
            # Lấy tọa độ và khoanh vùng đỏ xác nhận
            rect_res = excel_get_cell_rect(cell_addr)
            if rect_res.get("success") and self.overlay_enabled:
                rx, ry, rw, rh = rect_res["x"], rect_res["y"], rect_res["width"], rect_res["height"]
                self.overlay.set_target_rect((rx, ry, rw, rh), is_physical_pixels=True, badge_text=f"✅ ĐÃ GHI VÀO Ô {cell_addr}")
            self.verify_cell_value(cell_addr)
        else:
            self.log(f"❌ [MCP ERROR] {res.get('error')}")

    def on_click_clear(self):
        """Xóa giá trị trong ô."""
        cell_addr = self.cell_input.text().strip().upper()
        if not cell_addr:
            return
        self.log(f"📡 [MCP REQUEST] Xóa ô: excel_write_cell(cell_address='{cell_addr}', value='')")
        res = excel_write_cell(cell_address=cell_addr, value="")
        if res.get("success"):
            self.log(f"🧹 Đã xóa trắng dữ liệu trong ô {cell_addr} trên Excel.")
            self.verify_cell_value(cell_addr)

    def verify_cell_value(self, cell_addr: str):
        """Truy vấn giá trị ô thực tế từ Excel để đối chứng."""
        try:
            if not self.excel_monitor.excel_app:
                self.excel_monitor.connect()
            ws = self.excel_monitor.excel_app.ActiveSheet
            cell = ws.Range(cell_addr)
            val = cell.Value
            fmt = str(cell.NumberFormat)
            self.log(f"🔍 [EXCEL LIVE] Ô {cell_addr} hiện có giá trị: {repr(val)} | Định dạng: {fmt}")
        except Exception as e:
            self.log(f"⚠️ Không thể đọc ô {cell_addr}: {e}")

    def closeEvent(self, event):
        """Đóng cả lớp phủ khi thoát."""
        self.overlay.close()
        event.accept()


def main():
    app = QApplication(sys.argv)
    window = MCPInteractiveTestWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
