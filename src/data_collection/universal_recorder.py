"""
Universal Excel Telemetry Recorder: Bộ ghi nhận thao tác Excel chuyên sâu chạy ngầm.
Dành cho phòng máy học tập & Nghiên cứu hành vi:
- Chỉ bắt đầu ghi nhận KHI VÀ CHỈ KHI người học MỞ FILE EXCEL.
- KHÔNG bắt tín hiệu chuột liên tiếp hay làm rác luồng sự kiện.
- Ghi nhận chính xác LỊCH SỬ THAO TÁC:
  + Địa chỉ ô được chọn (CELL_SELECTION: ví dụ J10, C9, A1:B10)
  + Nhập liệu giá trị (CELL_VALUE_CHANGE: chuỗi văn bản, số liệu)
  + Gõ công thức hàm (FORMULA_ENTRY: =IF(...), =VLOOKUP(...), =SUM(...))
  + Tên công cụ / Định dạng đã sử dụng (EXCEL_TOOL_USED: Đổi Font, Cỡ chữ, Tô màu nền, In đậm, Căn lề, Định dạng số...)
  + Mở bảng tính / Đổi Sheet (WORKBOOK_OPEN, SHEET_ACTIVATE)
  + Tạm dừng suy nghĩ kéo dài tại ô (STUDENT_PAUSE: khi dừng > 10s tại một ô)
- Đồng bộ tức thì trực tiếp vào Supabase Cloud (WebSockets Realtime) & MySQL.
"""

import os
import sys
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import time
import socket
import threading
from typing import Any, Dict, Optional

# Thiết lập đường dẫn thư mục gốc
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT_DIR)

import pythoncom
import win32com.client
from src.data_collection.db_manager import DatabaseManager
from src.data_collection.event_logger import EventLogger
from src.sensors.base_sensor import RawEvent


class UniversalExcelRecorder:
    def __init__(self, student_id: Optional[str] = None, student_name: Optional[str] = None):
        self.station_name = os.environ.get("COMPUTERNAME", socket.gethostname())
        self.student_id = student_id or f"HS_{self.station_name}"
        self.student_name = student_name or f"Học viên {self.student_id}"

        self.db_manager = DatabaseManager()
        self.event_logger = EventLogger(db_manager=self.db_manager, batch_size=5, flush_interval=0.25)

        self.current_session_id = f"SES_AUTO_{self.student_id}_{int(time.time())}"
        self.current_workbook = "Chua_Mo_File"
        self.current_sheet = "Sheet1"
        self.current_cell = ""
        self.current_tool = ""

        # Trạng thái theo dõi Excel
        self._running = False
        self._excel_active = False
        self._com_thread = None

        # Bộ nhớ đệm lưu trạng thái ô để phát hiện thay đổi
        self._last_sel = None
        self._last_wb = None
        self._last_sheet = None
        self._cell_values = {}      # key: (wb, sheet, cell) -> (val_str, formula_str)
        self._cell_formats = {}     # key: (wb, sheet, cell) -> (font_name, size, bold, italic, fcolor, icolor, numfmt, align)
        self._last_action_time = time.time()
        self._pause_logged_for_cell = None

    def start(self):
        """Bắt đầu tiến trình ghi nhận thao tác ngầm."""
        self._running = True

        # Đăng ký học viên vào CSDL
        self._register_student()

        # Tạo phiên ghi nhận tự động ban đầu
        self.event_logger.start_session(
            session_id=self.current_session_id,
            student_id=self.student_id,
            lesson_id=self.current_workbook,
        )

        print("=" * 80)
        print("🎯 BỘ GHI NHẬN THAO TÁC EXCEL CHUYÊN SÂU ĐÃ KHỞI ĐỘNG!")
        print(f"   👤 Học viên : {self.student_name} ({self.student_id})")
        print(f"   🆔 Phiên ID : {self.current_session_id}")
        print("   ⏸️  Trạng thái: Đang chờ người dùng mở file Excel...")
        print("   💡 Hệ thống sẽ TỰ ĐỘNG GHI NHẬN khi bạn mở file Excel!")
        print("   ❌ ĐÃ TẮT tín hiệu chuột liên tiếp. Chỉ ghi nhận địa chỉ ô & công cụ thực tế.")
        print("=" * 80)

        # Khởi động luồng giám sát Excel
        self._com_thread = threading.Thread(target=self._excel_monitor_loop, daemon=True)
        self._com_thread.start()

    def _register_student(self):
        now_dt = time.strftime("%Y-%m-%d %H:%M:%S")
        if self.db_manager.mysql_available:
            try:
                conn = self.db_manager.get_mysql_connection()
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO students (student_id, name, created_at)
                        VALUES (%s, %s, %s)
                        ON DUPLICATE KEY UPDATE name=VALUES(name);
                        """,
                        (self.student_id, self.student_name, now_dt),
                    )
                conn.close()
            except Exception as e:
                pass

        if self.db_manager.supabase_available:
            try:
                conn = self.db_manager.get_supabase_connection()
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO public.students (student_id, name, created_at)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (student_id) DO UPDATE SET name = EXCLUDED.name;
                        """,
                        (self.student_id, self.student_name, now_dt),
                    )
                conn.close()
            except Exception as e:
                pass

    def _excel_monitor_loop(self):
        """Vòng lặp giám sát Excel độ chính xác cao: chỉ ghi nhận khi Excel mở."""
        pythoncom.CoInitialize()
        excel_app = None

        while self._running:
            try:
                # 1. Kết nối hoặc kiểm tra kết nối với Excel
                if excel_app is None:
                    try:
                        excel_app = win32com.client.GetActiveObject("Excel.Application")
                    except Exception:
                        excel_app = None

                # 2. Nếu Excel đang mở
                if excel_app is not None:
                    try:
                        wb_count = excel_app.Workbooks.Count
                    except Exception:
                        wb_count = 0
                        excel_app = None

                    if wb_count > 0:
                        if not self._excel_active:
                            self._excel_active = True
                            print("\n🟢 [EXCEL ĐÃ MỞ]: Bắt đầu ghi nhận thao tác người học!")

                        # Đọc trạng thái Excel hiện tại
                        self._poll_excel_state(excel_app)
                    else:
                        if self._excel_active:
                            self._excel_active = False
                            print("\n💤 [EXCEL ĐÃ ĐÓNG TẤT CẢ FILE]: Tạm dừng ghi nhận...")
                else:
                    if self._excel_active:
                        self._excel_active = False
                        print("\n💤 [EXCEL CHƯA MỞ HOẶC ĐÃ ĐÓNG]: Đang chờ mở file...")

            except Exception as e:
                excel_app = None
                self._excel_active = False

            time.sleep(0.15)  # Chu kỳ quét 150ms cực nhạy và không tốn CPU

        pythoncom.CoUninitialize()

    def _poll_excel_state(self, excel_app):
        """Quét và so khớp trạng thái của Workbook, Sheet, Active Cell, Value, Formula và Tools."""
        try:
            active_wb = excel_app.ActiveWorkbook
            if not active_wb:
                return

            wb_name = active_wb.Name
            active_sheet = excel_app.ActiveSheet
            sheet_name = active_sheet.Name if active_sheet else "Sheet1"

            # 1. Kiểm tra mở file hoặc chuyển file
            if wb_name != self._last_wb:
                self._last_wb = wb_name
                try:
                    wb_path = active_wb.FullName
                except Exception:
                    wb_path = wb_name
                self.record_workbook_open(wb_name, wb_path)

            # 2. Kiểm tra chuyển sheet
            if sheet_name != self._last_sheet:
                self._last_sheet = sheet_name
                self.record_sheet_activate(wb_name, sheet_name)

            # 3. Lấy thông tin ô và vùng chọn hiện tại
            active_cell = excel_app.ActiveCell
            sel_range = excel_app.Selection

            if not active_cell:
                return

            try:
                cell_addr = active_cell.Address(False, False)
                sel_addr = sel_range.Address(False, False) if sel_range else cell_addr
            except Exception:
                return

            # 4. Kiểm tra chọn ô / chọn vùng dữ liệu (CELL_SELECTION)
            if sel_addr != self._last_sel:
                self._last_sel = sel_addr
                self._last_action_time = time.time()
                self._pause_logged_for_cell = None
                self.record_selection(wb_name, sheet_name, sel_addr)

            # 5. Kiểm tra Giá trị & Công thức hàm (CELL_VALUE_CHANGE / FORMULA_ENTRY)
            try:
                cur_val = active_cell.Value
                cur_formula = active_cell.Formula
            except Exception:
                cur_val = None
                cur_formula = None

            val_str = str(cur_val) if cur_val is not None else ""
            formula_str = str(cur_formula) if cur_formula is not None else ""

            cell_key = (wb_name, sheet_name, cell_addr)
            old_data = self._cell_values.get(cell_key)

            if old_data is not None:
                old_val, old_formula = old_data
                if val_str != old_val or formula_str != old_formula:
                    self._last_action_time = time.time()
                    self._pause_logged_for_cell = None
                    self.record_cell_change(wb_name, sheet_name, cell_addr, cur_val, cur_formula)
                    self._cell_values[cell_key] = (val_str, formula_str)
            else:
                self._cell_values[cell_key] = (val_str, formula_str)

            # 6. Kiểm tra Công cụ & Định dạng đã chọn (EXCEL_TOOL_USED)
            try:
                font_name = active_cell.Font.Name
                font_size = active_cell.Font.Size
                font_bold = active_cell.Font.Bold
                font_italic = active_cell.Font.Italic
                font_color = active_cell.Font.Color
                interior_color = active_cell.Interior.Color
                num_format = str(active_cell.NumberFormat)
                align = active_cell.HorizontalAlignment

                cur_fmt = (font_name, font_size, font_bold, font_italic, font_color, interior_color, num_format, align)
                old_fmt = self._cell_formats.get(cell_key)

                if old_fmt is not None and old_fmt != cur_fmt:
                    old_fn, old_fs, old_b, old_it, old_fc, old_ic, old_nf, old_al = old_fmt
                    self._last_action_time = time.time()

                    # Phân tích công cụ cụ thể người dùng vừa bấm
                    if font_bold != old_b and font_bold:
                        self.record_tool_used(wb_name, sheet_name, cell_addr, "In đậm chữ (Bold)", {"tool": "Bold", "value": True})
                    if font_italic != old_it and font_italic:
                        self.record_tool_used(wb_name, sheet_name, cell_addr, "In nghiêng (Italic)", {"tool": "Italic", "value": True})
                    if font_name != old_fn:
                        self.record_tool_used(wb_name, sheet_name, cell_addr, f"Đổi Phông chữ: {font_name}", {"tool": "FontName", "value": font_name})
                    if font_size != old_fs:
                        self.record_tool_used(wb_name, sheet_name, cell_addr, f"Đổi Cỡ chữ: {font_size}pt", {"tool": "FontSize", "value": font_size})
                    if interior_color != old_ic and interior_color not in (16777215, -4142):
                        self.record_tool_used(wb_name, sheet_name, cell_addr, "Tô màu nền ô (Fill Color)", {"tool": "FillColor", "color_code": interior_color})
                    if font_color != old_fc and font_color != 0:
                        self.record_tool_used(wb_name, sheet_name, cell_addr, "Đổi màu chữ (Font Color)", {"tool": "FontColor", "color_code": font_color})
                    if num_format != old_nf and num_format not in ("General", "@", ""):
                        self.record_tool_used(wb_name, sheet_name, cell_addr, f"Định dạng số: {num_format}", {"tool": "NumberFormat", "format": num_format})
                    if align != old_al and align != 1:
                        self.record_tool_used(wb_name, sheet_name, cell_addr, "Căn lề ô (Alignment)", {"tool": "Alignment", "align_code": align})

                self._cell_formats[cell_key] = cur_fmt
            except Exception:
                pass

            # 7. Nhận diện Ngập ngừng / Tạm dừng suy nghĩ (> 8s không thao tác tại ô)
            idle_sec = time.time() - self._last_action_time
            if idle_sec >= 8.0 and self._pause_logged_for_cell != cell_addr:
                self._pause_logged_for_cell = cell_addr
                self.record_pause(wb_name, sheet_name, cell_addr, idle_sec)

        except Exception as e:
            pass

    # =========================================================================
    # CÁC HÀM GHI NHẬN SỰ KIỆN CHUẨN XÁC
    # =========================================================================

    def record_workbook_open(self, wb_name: str, wb_path: str):
        self.current_workbook = wb_name
        print(f"📂 [MỞ BẢNG TÍNH]: {wb_name}")
        self.event_logger.update_session_lesson(self.current_session_id, wb_name)
        ev = RawEvent(
            event_type="WORKBOOK_OPEN",
            session_id=self.current_session_id,
            lesson_id=wb_name,
            cell="",
            metadata={"workbook_name": wb_name, "file_path": wb_path, "tool": "Open File"},
        )
        self.event_logger.log_event(ev)

    def record_sheet_activate(self, wb_name: str, sheet_name: str):
        self.current_sheet = sheet_name
        print(f"📑 [CHUYỂN SHEET]: {sheet_name} (File: {wb_name})")
        ev = RawEvent(
            event_type="SHEET_ACTIVATE",
            session_id=self.current_session_id,
            lesson_id=wb_name,
            cell="",
            metadata={"sheet": sheet_name, "workbook": wb_name, "tool": "Switch Sheet"},
        )
        self.event_logger.log_event(ev)

    def record_selection(self, wb_name: str, sheet_name: str, cell_address: str):
        self.current_workbook = wb_name
        self.current_sheet = sheet_name
        self.current_cell = cell_address
        print(f"🎯 [CHỌN ĐỊA CHỈ Ô]: [{cell_address}] (Sheet: {sheet_name})")
        ev = RawEvent(
            event_type="CELL_SELECTION",
            session_id=self.current_session_id,
            lesson_id=wb_name,
            cell=cell_address,
            metadata={"sheet": sheet_name, "workbook": wb_name, "tool": "Select Cell"},
        )
        self.event_logger.log_event(ev)

    def record_cell_change(self, wb_name: str, sheet_name: str, cell_address: str, val: Any, formula: Any):
        self.current_workbook = wb_name
        self.current_sheet = sheet_name
        self.current_cell = cell_address

        is_formula = isinstance(formula, str) and formula.startswith("=")
        event_type = "FORMULA_ENTRY" if is_formula else "CELL_VALUE_CHANGE"

        display_val = str(formula) if is_formula else str(val)
        print(f"✍️ [{'GÕ HÀM/CÔNG THỨC' if is_formula else 'NHẬP DỮ LIỆU'}]: [{cell_address}] = {display_val}")

        str_val = str(val) if val is not None else ""
        has_error = any(err in str_val for err in ("#NAME?", "#VALUE!", "#REF!", "#N/A", "#DIV/0!"))

        ev = RawEvent(
            event_type=event_type,
            session_id=self.current_session_id,
            lesson_id=wb_name,
            cell=cell_address,
            metadata={
                "sheet": sheet_name,
                "workbook": wb_name,
                "value": str_val,
                "formula": str(formula) if is_formula else None,
                "has_error": has_error,
                "tool": "Formula Bar" if is_formula else "Edit Cell",
            },
        )
        self.event_logger.log_event(ev)

    def record_tool_used(self, wb_name: str, sheet_name: str, cell_address: str, tool_name: str, tool_details: Dict[str, Any]):
        self.current_workbook = wb_name
        self.current_sheet = sheet_name
        self.current_cell = cell_address
        self.current_tool = tool_name
        print(f"🛠️ [CÔNG CỤ EXCEL]: {tool_name} tại ô [{cell_address}]")

        ev = RawEvent(
            event_type="EXCEL_TOOL_USED",
            session_id=self.current_session_id,
            lesson_id=wb_name,
            cell=cell_address,
            metadata={
                "sheet": sheet_name,
                "workbook": wb_name,
                "tool_name": tool_name,
                "tool": tool_name,
                **tool_details,
            },
        )
        self.event_logger.log_event(ev)

    def record_pause(self, wb_name: str, sheet_name: str, cell_address: str, duration: float):
        print(f"⏱️ [TẠM DỪNG / NGẬP NGỪNG]: Dừng {duration:.1f}s tại ô [{cell_address}]")
        ev = RawEvent(
            event_type="STUDENT_PAUSE",
            session_id=self.current_session_id,
            lesson_id=wb_name,
            cell=cell_address,
            metadata={
                "sheet": sheet_name,
                "workbook": wb_name,
                "pause_duration_sec": round(duration, 1),
                "tool": "Hesitation",
            },
        )
        self.event_logger.log_event(ev)

    def stop(self):
        """Dừng bộ ghi nhận an toàn."""
        self._running = False
        print("\n🛑 Đang lưu toàn bộ sự kiện vào CSDL...")
        self.event_logger.end_session(self.current_session_id, status="COMPLETED")
        self.event_logger.close()
        print("✅ Buổi thực hành đã kết thúc. Dữ liệu đã được lưu an toàn!")


if __name__ == "__main__":
    recorder = UniversalExcelRecorder()
    recorder.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        recorder.stop()
