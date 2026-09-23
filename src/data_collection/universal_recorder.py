"""
Universal Excel Telemetry Recorder: Bộ ghi nhận thao tác Excel chuyên sâu chạy ngầm.
Dành cho phòng máy học tập & Nghiên cứu hành vi:
- Chỉ bắt đầu ghi nhận KHI VÀ CHỈ KHI người học MỞ FILE EXCEL.
- KHÔNG bắt tín hiệu chuột liên tiếp hay làm rác luồng sự kiện.
- Ghi nhận chính xác LỊCH SỬ THAO TÁC:
  + Địa chỉ ô được chọn (CELL_SELECTION: ví dụ C8, J10, A1:B10)
  + Nhập liệu giá trị (CELL_VALUE_CHANGE: "Hello", "xin chào", số liệu...)
  + Gõ công thức hàm (FORMULA_ENTRY: =IF(...), =VLOOKUP(...), =SUM(...))
  + Tên công cụ / Ribbon / Định dạng (EXCEL_TOOL_USED: Tab Home, Tab Insert, Bold, Tô màu, Đổi Font...)
  + Mở bảng tính / Đổi Sheet (WORKBOOK_OPEN, SHEET_ACTIVATE)
  + Tạm dừng suy nghĩ kéo dài tại ô (STUDENT_PAUSE: khi dừng > 8s tại một ô)
- Tự động xuất mọi lỗi phát sinh ra log file và màn hình console.
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
import ctypes
import ctypes.wintypes
from typing import Any, Dict, Optional, Set

# Thiết lập đường dẫn thư mục gốc
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT_DIR)

import pythoncom
import win32com.client
from src.data_collection.db_manager import DatabaseManager
from src.data_collection.event_logger import EventLogger
from src.sensors.base_sensor import RawEvent

try:
    import uiautomation as auto
except Exception:
    auto = None

# Ctypes Windows Accessibility & Mouse Hook Constants
user32 = ctypes.windll.user32
oleacc = ctypes.windll.oleacc

EVENT_OBJECT_FOCUS = 0x8005
EVENT_OBJECT_SELECTION = 0x8006
EVENT_OBJECT_STATECHANGE = 0x800A
EVENT_OBJECT_NAMECHANGE = 0x800C
EVENT_OBJECT_INVOKED = 0x8013
WINEVENT_OUTOFCONTEXT = 0

WH_MOUSE_LL = 14
WM_LBUTTONUP = 0x0202

class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("pt", POINT),
        ("mouseData", ctypes.wintypes.DWORD),
        ("flags", ctypes.wintypes.DWORD),
        ("time", ctypes.wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_ulonglong),
    ]

WinEventProcType = ctypes.WINFUNCTYPE(
    None,
    ctypes.wintypes.HANDLE,
    ctypes.wintypes.DWORD,
    ctypes.wintypes.HWND,
    ctypes.wintypes.LONG,
    ctypes.wintypes.LONG,
    ctypes.wintypes.DWORD,
    ctypes.wintypes.DWORD
)

LowLevelMouseProc = ctypes.WINFUNCTYPE(
    ctypes.c_long,
    ctypes.c_int,
    ctypes.wintypes.WPARAM,
    ctypes.wintypes.LPARAM
)


def clean_address(raw_obj) -> str:
    """Trích xuất địa chỉ ô an toàn tuyệt đối từ COM Range / ActiveCell."""
    if raw_obj is None:
        return ""
    try:
        addr = getattr(raw_obj, "Address", raw_obj)
        if callable(addr):
            addr = addr()
        return str(addr).replace("$", "").strip()
    except Exception:
        try:
            return str(raw_obj).replace("$", "").strip()
        except Exception:
            return ""


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
        self._hook_thread = None

        # Bộ nhớ đệm lưu trạng thái để so khớp thay đổi
        self._last_sel = None
        self._last_wb_sel = None
        self._last_sheet_sel = None
        self._last_wb = None
        self._last_sheet = None
        self._last_cell_addr = ""
        self._editing_cell = None
        self._is_editing = False

        self._cell_values = {}      # key: (wb, sheet, cell) -> (val_str, formula_str)
        self._cell_formats = {}     # key: (wb, sheet, cell) -> tuple of format properties
        self._last_action_time = time.time()
        self._pause_logged_for_cell = None

        # Bộ lọc chống trùng sự kiện Ribbon trong thời gian ngắn
        self._last_ribbon_tool = ""
        self._last_ribbon_time = 0

        # Lưu giữ con trỏ callback để tránh bị Garbage Collector thu hồi
        self._win_event_proc = None
        self._win_event_hook = None
        self._mouse_proc = None
        self._mouse_hook = None

    def log_error(self, message: str, exc: Optional[Exception] = None):
        """Ghi nhận lỗi chi tiết ra màn hình console và file recorder_error.log."""
        if exc:
            err_str = str(exc).lower()
            if "rejected" in err_str or "-2147418111" in err_str:
                return  # Trạng thái bình thường khi người dùng đang gõ phím bên trong ô
            err_detail = f"{message}: {exc}"
        else:
            err_detail = message

        print(f"⚠️ [LOG LỖI]: {err_detail}")
        try:
            log_file = os.path.join(ROOT_DIR, "recorder_error.log")
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {err_detail}\n")
        except Exception:
            pass

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
        print(f"   👤 Học viên  : {self.student_name} ({self.student_id})")
        print(f"   🆔 Phiên ID  : {self.current_session_id}")
        print("   ⏸️  Trạng thái: Đang chờ người dùng mở file Excel...")
        print("   💡 Hệ thống sẽ TỰ ĐỘNG BẬT GHI NHẬN ngay khi bạn mở file Excel!")
        print("   📝 Tự động bắt địa chỉ ô, nội dung gõ, công thức hàm, công cụ Ribbon.")
        print("   ⚠️  Mọi lỗi kỹ thuật sẽ được tự động xuất ra recorder_error.log")
        print("=" * 80)

        # 1. Luồng giám sát COM & Trạng thái ô tính (Selection, Value, Formula, Format)
        self._com_thread = threading.Thread(target=self._excel_monitor_loop, daemon=True)
        self._com_thread.start()

        # 2. Luồng móc nối sự kiện Ribbon / Thanh công cụ qua Windows Accessibility & Mouse Hook
        self._hook_thread = threading.Thread(target=self._ribbon_hook_loop, daemon=True)
        self._hook_thread.start()

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
                self.log_error("Lỗi đăng ký học viên MySQL", e)

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
                self.log_error("Lỗi đăng ký học viên Supabase", e)

    def _excel_monitor_loop(self):
        """Vòng lặp giám sát Excel độ chính xác cao: chỉ ghi nhận khi Excel mở."""
        pythoncom.CoInitialize()
        excel_app = None

        while self._running:
            try:
                # 1. Tìm hoặc kiểm tra kết nối với Excel
                if excel_app is None:
                    try:
                        excel_app = win32com.client.GetActiveObject("Excel.Application")
                    except Exception:
                        excel_app = None

                # 2. Nếu Excel đang mở
                if excel_app is not None:
                    wb_count = 0
                    try:
                        wb_count = excel_app.Workbooks.Count
                    except Exception as e:
                        err_str = str(e).lower()
                        if "rejected" in err_str or "-2147418111" in err_str:
                            wb_count = 1  # Đang gõ phím bên trong ô
                            self._is_editing = True
                        else:
                            excel_app = None
                            wb_count = 0

                    if wb_count > 0:
                        if not self._excel_active:
                            self._excel_active = True
                            print("\n🟢 [EXCEL ĐÃ MỞ]: Bắt đầu ghi nhận thao tác người học!")

                        # Quét trạng thái chi tiết của Workbook, Sheet, Ô hiện tại
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
                self.log_error("Lỗi vòng lặp giám sát Excel", e)

            time.sleep(0.12)  # Quét cực nhạy 120ms

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
                except Exception as e:
                    wb_path = wb_name
                    self.log_error("Không lấy được FullName của file Excel", e)
                self.record_workbook_open(wb_name, wb_path)

            # 2. Kiểm tra chuyển sheet
            if sheet_name != self._last_sheet:
                self._last_sheet = sheet_name
                self.record_sheet_activate(wb_name, sheet_name)

            # 3. Lấy thông tin ô và vùng chọn hiện tại
            active_cell = None
            try:
                active_cell = excel_app.ActiveCell
            except Exception as e:
                err_str = str(e).lower()
                if "rejected" in err_str or "-2147418111" in err_str:
                    self._is_editing = True
                    if self._last_cell_addr:
                        self._editing_cell = self._last_cell_addr
                else:
                    self.log_error("Lỗi đọc ActiveCell", e)
                return

            if not active_cell:
                return

            cell_addr = clean_address(active_cell)
            if not cell_addr:
                return

            sel_range = None
            try:
                sel_range = excel_app.Selection
            except Exception as e:
                self.log_error("Lỗi đọc Selection", e)

            sel_addr = clean_address(sel_range) or cell_addr

            # 4. Kiểm tra chọn ô / chọn vùng dữ liệu (CELL_SELECTION)
            if sel_addr and (sel_addr != self._last_sel or wb_name != self._last_wb_sel or sheet_name != self._last_sheet_sel):
                self._last_sel = sel_addr
                self._last_wb_sel = wb_name
                self._last_sheet_sel = sheet_name
                self._last_action_time = time.time()
                self._pause_logged_for_cell = None
                self.record_selection(wb_name, sheet_name, sel_addr)

            # 5. KIỂM TRA NỘI DUNG Ô & CÔNG THỨC HÀM (CELL_VALUE_CHANGE / FORMULA_ENTRY)
            # Rà soát triệt để: ô vừa gõ xong (previous cell), ô đang chỉnh sửa, và ô hiện tại
            pending_cells: Set[str] = set()
            if self._last_cell_addr and self._last_cell_addr != cell_addr:
                pending_cells.add(self._last_cell_addr)
            if self._editing_cell:
                pending_cells.add(self._editing_cell)
                self._editing_cell = None
            pending_cells.add(cell_addr)

            # Nếu người dùng dán hoặc fill nhiều ô, rà soát vùng chọn (tối đa 50 ô để không lag)
            try:
                if sel_range is not None:
                    cnt = getattr(sel_range, "Count", 1)
                    if 1 < cnt <= 50:
                        for sc in sel_range:
                            sc_addr = clean_address(sc)
                            if sc_addr:
                                pending_cells.add(sc_addr)
            except Exception:
                pass

            for target_addr in pending_cells:
                try:
                    target_cell = active_sheet.Range(target_addr)
                    cur_val = target_cell.Value
                    cur_formula = target_cell.Formula

                    val_str = str(cur_val).strip() if cur_val is not None else ""
                    formula_str = str(cur_formula).strip() if cur_formula is not None else ""

                    cell_key = (wb_name, sheet_name, target_addr)
                    old_data = self._cell_values.get(cell_key)

                    if old_data is not None:
                        old_val, old_formula = old_data
                        if val_str != old_val or formula_str != old_formula:
                            self._last_action_time = time.time()
                            self._pause_logged_for_cell = None
                            self.record_cell_change(wb_name, sheet_name, target_addr, cur_val, cur_formula)
                            self._cell_values[cell_key] = (val_str, formula_str)
                    else:
                        self._cell_values[cell_key] = (val_str, formula_str)
                        # Nếu ô trước đó vừa được gõ dữ liệu mới lần đầu tiên
                        if target_addr != cell_addr and (val_str != "" or formula_str != ""):
                            self._last_action_time = time.time()
                            self._pause_logged_for_cell = None
                            self.record_cell_change(wb_name, sheet_name, target_addr, cur_val, cur_formula)

                except Exception as e:
                    err_str = str(e).lower()
                    if "rejected" in err_str or "-2147418111" in err_str:
                        self._is_editing = True
                        self._editing_cell = target_addr
                    else:
                        self.log_error(f"Lỗi đọc nội dung ô [{target_addr}]", e)

            # Cập nhật địa chỉ ô cuối cùng
            self._last_cell_addr = cell_addr

            # 6. KIỂM TRA CÔNG CỤ & ĐỊNH DẠNG ĐÃ DÙNG (EXCEL_TOOL_USED)
            try:
                f = active_cell.Font
                font_name = str(f.Name) if hasattr(f, 'Name') and f.Name else ""
                font_size = float(f.Size) if hasattr(f, 'Size') and f.Size else 0.0
                font_bold = bool(f.Bold) if hasattr(f, 'Bold') and f.Bold is not None else False
                font_italic = bool(f.Italic) if hasattr(f, 'Italic') and f.Italic is not None else False
                font_underline = int(f.Underline) if hasattr(f, 'Underline') and f.Underline is not None else -4142
                font_color = int(f.Color) if hasattr(f, 'Color') and f.Color is not None else 0

                interior = active_cell.Interior
                interior_color = int(interior.Color) if hasattr(interior, 'Color') and interior.Color is not None else 0
                interior_index = int(interior.ColorIndex) if hasattr(interior, 'ColorIndex') and interior.ColorIndex is not None else -4142

                num_format = str(active_cell.NumberFormat) if hasattr(active_cell, 'NumberFormat') else ""
                h_align = int(active_cell.HorizontalAlignment) if hasattr(active_cell, 'HorizontalAlignment') and active_cell.HorizontalAlignment is not None else 0
                v_align = int(active_cell.VerticalAlignment) if hasattr(active_cell, 'VerticalAlignment') and active_cell.VerticalAlignment is not None else 0
                wrap_text = bool(active_cell.WrapText) if hasattr(active_cell, 'WrapText') and active_cell.WrapText is not None else False
                merge_cells = bool(active_cell.MergeCells) if hasattr(active_cell, 'MergeCells') and active_cell.MergeCells is not None else False

                has_borders = False
                try:
                    has_borders = bool(active_cell.Borders.LineStyle != -4142)
                except Exception:
                    pass

                cur_fmt = (
                    font_name, font_size, font_bold, font_italic, font_underline, font_color,
                    interior_color, interior_index, num_format, h_align, v_align, wrap_text, merge_cells, has_borders
                )
                cell_fmt_key = (wb_name, sheet_name, cell_addr)
                old_fmt = self._cell_formats.get(cell_fmt_key)

                if old_fmt is not None and old_fmt != cur_fmt:
                    (
                        old_fn, old_fs, old_b, old_it, old_u, old_fc,
                        old_ic, old_ii, old_nf, old_ha, old_va, old_wt, old_mc, old_bd
                    ) = old_fmt
                    self._last_action_time = time.time()

                    if font_bold != old_b and font_bold:
                        self.record_tool_used(wb_name, sheet_name, cell_addr, "In đậm chữ (Bold)", {"tool": "Bold", "value": True})
                    if font_italic != old_it and font_italic:
                        self.record_tool_used(wb_name, sheet_name, cell_addr, "In nghiêng (Italic)", {"tool": "Italic", "value": True})
                    if font_underline != old_u and font_underline != -4142:
                        self.record_tool_used(wb_name, sheet_name, cell_addr, "Gạch chân (Underline)", {"tool": "Underline", "value": True})
                    if font_name != old_fn and font_name and old_fn:
                        self.record_tool_used(wb_name, sheet_name, cell_addr, f"Đổi Phông chữ: {font_name}", {"tool": "FontName", "value": font_name})
                    if font_size != old_fs and font_size > 0 and old_fs > 0:
                        self.record_tool_used(wb_name, sheet_name, cell_addr, f"Đổi Cỡ chữ: {font_size}pt", {"tool": "FontSize", "value": font_size})
                    if font_color != old_fc and font_color > 0 and old_fc > 0:
                        self.record_tool_used(wb_name, sheet_name, cell_addr, "Đổi Màu chữ (Font Color)", {"tool": "FontColor", "color_code": font_color})
                    if interior_index != old_ii and interior_index != -4142:
                        self.record_tool_used(wb_name, sheet_name, cell_addr, "Tô màu nền ô (Fill Color)", {"tool": "FillColor", "color_code": interior_color})
                    if num_format != old_nf and num_format not in ("General", "@", "") and old_nf:
                        self.record_tool_used(wb_name, sheet_name, cell_addr, f"Định dạng số: {num_format}", {"tool": "NumberFormat", "format": num_format})
                    if h_align != old_ha and old_ha != 0:
                        align_names = {-4108: "Căn giữa (Center)", -4131: "Căn trái (Align Left)", -4152: "Căn phải (Align Right)", -4130: "Căn đều (Justify)"}
                        lbl = align_names.get(h_align, f"Căn lề ngang: {h_align}")
                        self.record_tool_used(wb_name, sheet_name, cell_addr, lbl, {"tool": "HorizontalAlignment", "value": h_align})
                    if v_align != old_va and old_va != 0:
                        valign_names = {-4108: "Căn giữa dọc (Middle Align)", -4160: "Căn trên cùng (Top Align)", -4107: "Căn dưới đáy (Bottom Align)"}
                        lbl = valign_names.get(v_align, f"Căn lề dọc: {v_align}")
                        self.record_tool_used(wb_name, sheet_name, cell_addr, lbl, {"tool": "VerticalAlignment", "value": v_align})
                    if wrap_text != old_wt and wrap_text:
                        self.record_tool_used(wb_name, sheet_name, cell_addr, "Ngắt dòng tự động (Wrap Text)", {"tool": "WrapText", "value": True})
                    if merge_cells != old_mc and merge_cells:
                        self.record_tool_used(wb_name, sheet_name, cell_addr, "Gộp & Căn giữa ô (Merge & Center)", {"tool": "MergeCells", "value": True})
                    if has_borders != old_bd and has_borders:
                        self.record_tool_used(wb_name, sheet_name, cell_addr, "Kẻ viền khung bảng (Borders)", {"tool": "Borders", "value": True})

                self._cell_formats[cell_fmt_key] = cur_fmt
            except Exception as e:
                err_str = str(e).lower()
                if "rejected" not in err_str and "-2147418111" not in err_str:
                    self.log_error(f"Lỗi kiểm tra định dạng ô [{cell_addr}]", e)

            # 7. Nhận diện Ngập ngừng / Tạm dừng suy nghĩ (> 8s không thao tác tại ô)
            idle_sec = time.time() - self._last_action_time
            if idle_sec >= 8.0 and self._pause_logged_for_cell != cell_addr:
                self._pause_logged_for_cell = cell_addr
                self.record_pause(wb_name, sheet_name, cell_addr, idle_sec)

        except Exception as e:
            err_str = str(e).lower()
            if "rejected" not in err_str and "-2147418111" not in err_str:
                self.log_error("Lỗi trong chu kỳ quét Excel", e)

    def _inspect_ribbon_element_at(self, x: int, y: int):
        """Trích xuất tên công cụ chính xác khi người dùng nhấp chuột trên thanh Ribbon."""
        try:
            if not auto:
                return
            ctrl = auto.ControlFromPoint(x, y)
            if ctrl and ctrl.Name:
                tool_name = ctrl.Name.strip()
                if tool_name and len(tool_name) < 60:
                    ignore_names = {"ribbon", "lower ribbon", "ribbon tabs", "ribbon bar", "desktop", "excel"}
                    if tool_name.lower() not in ignore_names:
                        now = time.time()
                        if tool_name != self._last_ribbon_tool or (now - self._last_ribbon_time) > 1.0:
                            self._last_ribbon_tool = tool_name
                            self._last_ribbon_time = now
                            self.record_tool_used(
                                self.current_workbook,
                                self.current_sheet,
                                self.current_cell,
                                f"Chọn công cụ: {tool_name}",
                                {"tool_name": tool_name, "source": "RibbonClick", "control_type": getattr(ctrl, "ControlTypeName", "Button")}
                            )
        except Exception as e:
            self.log_error(f"Lỗi kiểm tra phần tử Ribbon tại tọa độ ({x}, {y})", e)

    def _ribbon_hook_loop(self):
        """Lắng nghe sự kiện click trên thanh Ribbon / Menu của Excel qua Windows Accessibility & Mouse Hook."""
        pythoncom.CoInitialize()

        def win_event_callback(hWinEventHook, event, hwnd, idObject, idChild, dwEventThread, dwmsEventTime):
            if not self._excel_active:
                return
            try:
                cls_buff = ctypes.create_unicode_buffer(256)
                user32.GetClassNameW(hwnd, cls_buff, 256)
                cls_name = cls_buff.value.lower()

                # Kiểm tra cửa sổ liên quan tới Ribbon Excel
                if any(k in cls_name for k in ("netui", "mso", "ribbon", "excel")):
                    p_acc = ctypes.c_void_p()
                    var_child = (ctypes.c_byte * 32)()  # 32 bytes an toàn tuyệt đối cho VARIANT trên 64-bit Windows
                    res = oleacc.AccessibleObjectFromEvent(
                        hwnd, idObject, idChild,
                        ctypes.byref(p_acc), ctypes.byref(var_child)
                    )
                    if res == 0 and p_acc.value:
                        acc = win32com.client.Dispatch(p_acc.value)
                        tool_name = acc.accName(idChild) if hasattr(acc, 'accName') else ""
                        if tool_name and len(tool_name) < 60:
                            ignore_names = {"ribbon", "lower ribbon", "ribbon tabs", "ribbon bar", "excel"}
                            if tool_name.lower() not in ignore_names:
                                now = time.time()
                                if tool_name != self._last_ribbon_tool or (now - self._last_ribbon_time) > 1.0:
                                    self._last_ribbon_tool = tool_name
                                    self._last_ribbon_time = now
                                    self.record_tool_used(
                                        self.current_workbook,
                                        self.current_sheet,
                                        self.current_cell,
                                        f"Chọn công cụ: {tool_name}",
                                        {"tool_name": tool_name, "source": "WinEventHook"}
                                    )
            except Exception as e:
                self.log_error("Lỗi callback WinEventHook", e)

        self._win_event_proc = WinEventProcType(win_event_callback)
        self._win_event_hook = user32.SetWinEventHook(
            EVENT_OBJECT_FOCUS,
            EVENT_OBJECT_INVOKED,
            0,
            self._win_event_proc,
            0,
            0,
            WINEVENT_OUTOFCONTEXT
        )

        # Cài đặt low-level mouse hook chỉ bắt WM_LBUTTONUP trên thanh Ribbon
        def mouse_callback(nCode, wParam, lParam):
            if nCode >= 0 and wParam == WM_LBUTTONUP and self._excel_active:
                try:
                    info = ctypes.cast(lParam, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
                    hwnd = user32.WindowFromPoint(info.pt)
                    if hwnd:
                        cls_buff = ctypes.create_unicode_buffer(256)
                        user32.GetClassNameW(hwnd, cls_buff, 256)
                        cls_name = cls_buff.value.lower()
                        if any(k in cls_name for k in ("netui", "ribbon", "mso")):
                            threading.Thread(
                                target=self._inspect_ribbon_element_at,
                                args=(info.pt.x, info.pt.y),
                                daemon=True
                            ).start()
                except Exception as e:
                    self.log_error("Lỗi mouse hook", e)
            return user32.CallNextHookEx(None, nCode, wParam, lParam)

        self._mouse_proc = LowLevelMouseProc(mouse_callback)
        self._mouse_hook = user32.SetWindowsHookExW(
            WH_MOUSE_LL,
            self._mouse_proc,
            None,
            0
        )

        msg = ctypes.wintypes.MSG()
        while self._running:
            if user32.PeekMessageW(ctypes.byref(msg), 0, 0, 0, 1):
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
            time.sleep(0.02)

        if self._win_event_hook:
            user32.UnhookWinEvent(self._win_event_hook)
        if self._mouse_hook:
            user32.UnhookWindowsHookEx(self._mouse_hook)
        pythoncom.CoUninitialize()

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
            metadata={"workbook_name": wb_name, "workbook": wb_name, "file_path": wb_path, "tool": "Open File"},
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
            metadata={"sheet": sheet_name, "workbook": wb_name, "cell": cell_address, "tool": "Select Cell"},
        )
        self.event_logger.log_event(ev)

    def record_cell_change(self, wb_name: str, sheet_name: str, cell_address: str, val: Any, formula: Any):
        self.current_workbook = wb_name
        self.current_sheet = sheet_name
        self.current_cell = cell_address

        is_formula = isinstance(formula, str) and formula.startswith("=")
        event_type = "FORMULA_ENTRY" if is_formula else "CELL_VALUE_CHANGE"

        display_val = str(formula) if is_formula else str(val)
        if is_formula:
            print(f"⚡ [GÕ CÔNG THỨC]: Ô [{cell_address}] = {display_val}")
        else:
            print(f"✍️ [NHẬP NỘI DUNG]: Ô [{cell_address}] = \"{display_val}\"")

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
        print(f"⏱️ [TẠM DỪNG / SUY NGHĨ]: Dừng {duration:.1f}s tại ô [{cell_address}]")
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
        if self._win_event_hook:
            try:
                user32.UnhookWinEvent(self._win_event_hook)
            except Exception:
                pass
        if self._mouse_hook:
            try:
                user32.UnhookWindowsHookEx(self._mouse_hook)
            except Exception:
                pass

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
