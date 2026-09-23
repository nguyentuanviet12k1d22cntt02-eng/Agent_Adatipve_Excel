"""
Universal Excel Telemetry Recorder: Bộ ghi nhận thao tác Excel toàn năng chạy ngầm.
Dành cho phòng máy trung tâm:
- Học viên CHỈ CẦN NHẤP ĐÚP CHUỘT LÀ CHẠY, không cần chọn bài trước.
- Tự động gắn kết (hook) vào bất kỳ tiến trình Excel nào đang mở hoặc sắp mở.
- Học viên mở file Excel bất kỳ, tạo file mới, mở bài tập cũ... đều tự động ghi lại:
  + Chọn ô / vùng dữ liệu (CELL_SELECTION)
  + Nhập liệu / Gõ công thức hàm (CELL_VALUE_CHANGE, FORMULA_ENTRY)
  + Chuyển đổi Sheet / Mở file (WORKBOOK_OPEN, SHEET_ACTIVATE)
  + Ngập ngừng chuột, dừng thao tác (MOUSE_HESITATION_START/END)
- Đẩy dữ liệu trực tiếp vào Supabase Cloud & MySQL mà KHÔNG cần phân tích làm phiền học viên.
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
from src.sensors.mouse_sensor import MouseSensor
from src.core.mouse_tracker import MouseSpeedTracker


class ExcelAppEvents:
    """Bắt các sự kiện cấp ứng dụng của Excel (Application-level Events)."""

    def __init__(self):
        self.recorder = None

    def set_recorder(self, recorder):
        self.recorder = recorder

    def OnSheetSelectionChange(self, Sh, Target):
        """Bắt sự kiện chọn ô bất kỳ trên bất kỳ sheet nào."""
        if not self.recorder:
            return
        try:
            cell_address = Target.Address(False, False)
            sheet_name = Sh.Name
            wb_name = Sh.Parent.Name
            self.recorder.record_selection(wb_name, sheet_name, cell_address)
        except Exception:
            pass

    def OnSheetChange(self, Sh, Target):
        """Bắt sự kiện nhập dữ liệu hoặc gõ công thức trên bất kỳ ô nào."""
        if not self.recorder:
            return
        try:
            cell_address = Target.Address(False, False)
            sheet_name = Sh.Name
            wb_name = Sh.Parent.Name
            val = Target.Value
            formula = Target.Formula

            self.recorder.record_cell_change(wb_name, sheet_name, cell_address, val, formula)
        except Exception:
            pass

    def OnWorkbookOpen(self, Wb):
        """Bắt sự kiện khi học viên mở một file Excel bất kỳ."""
        if not self.recorder:
            return
        try:
            wb_name = Wb.Name
            wb_path = Wb.FullName
            self.recorder.record_workbook_open(wb_name, wb_path)
        except Exception:
            pass

    def OnWorkbookActivate(self, Wb):
        """Bắt sự kiện khi học viên chuyển đổi giữa các file Excel."""
        if not self.recorder:
            return
        try:
            wb_name = Wb.Name
            self.recorder.set_active_workbook(wb_name)
        except Exception:
            pass


class UniversalExcelRecorder:
    def __init__(self, student_id: Optional[str] = None, student_name: Optional[str] = None):
        self.station_name = os.environ.get("COMPUTERNAME", socket.gethostname())
        self.student_id = student_id or f"HS_{self.station_name}"
        self.student_name = student_name or f"Học viên {self.student_id}"

        self.db_manager = DatabaseManager()
        self.event_logger = EventLogger(db_manager=self.db_manager, batch_size=5, flush_interval=0.25)
        self.mouse_tracker = MouseSpeedTracker()
        self.mouse_sensor = MouseSensor()

        self.current_session_id = f"SES_AUTO_{self.student_id}_{int(time.time())}"
        self.current_workbook = "Chua_Mo_File"
        self.current_sheet = "Sheet1"
        self.current_cell = ""

        self._running = False
        self._excel_hooked = False
        self._com_thread = None

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
        print("🟢 BỘ GHI NHẬN EXCEL TỰ ĐỘNG (UNIVERSAL RECORDER) ĐÃ BẬT!")
        print(f"   - Mã máy/Học viên: {self.student_id} ({self.student_name})")
        print(f"   - Phiên học: {self.current_session_id}")
        print("   - Trạng thái: Đang theo dõi Excel ngầm...")
        print("   👉 Học viên CỨ MỞ BẤT KỲ FILE EXCEL NÀO VÀ LÀM BÀI BÌNH THƯỜNG!")
        print("   - Không cần chọn bài, không hiển thị gợi ý làm phiền.")
        print("   - Toàn bộ thao tác chọn ô, nhập dữ liệu, gõ hàm đều được ghi vào Database.")
        print("=" * 80)

        # Khởi động luồng COM quan sát Excel
        self._com_thread = threading.Thread(target=self._com_monitor_loop, daemon=True)
        self._com_thread.start()

        # Khởi động luồng theo dõi chuột (đo ngập ngừng)
        self._mouse_thread = threading.Thread(target=self._mouse_monitor_loop, daemon=True)
        self._mouse_thread.start()

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
                print(f"[Recorder] Lỗi đăng ký học viên: {e}")

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

    def _com_monitor_loop(self):
        """Vòng lặp liên tục kiểm tra và hook vào Excel bất cứ khi nào nó được bật."""
        pythoncom.CoInitialize()
        excel_app = None
        event_handler = None

        while self._running:
            if not self._excel_hooked:
                try:
                    # Cố gắng gắn kết vào tiến trình Excel đang mở
                    excel_app = win32com.client.GetActiveObject("Excel.Application")
                    if excel_app:
                        event_handler = win32com.client.DispatchWithEvents(excel_app, ExcelAppEvents)
                        event_handler.set_recorder(self)
                        self._excel_hooked = True
                        print(f"\n⚡ ĐÃ KẾT NỐI VÀO TIẾN TRÌNH EXCEL! (Bắt đầu ghi nhận thao tác)")

                        # Lấy tên workbook đang mở hiện tại nếu có
                        try:
                            if excel_app.ActiveWorkbook:
                                self.record_workbook_open(
                                    excel_app.ActiveWorkbook.Name,
                                    excel_app.ActiveWorkbook.FullName,
                                )
                        except Exception:
                            pass
                except Exception:
                    # Excel chưa bật, đợi 1 giây rồi thử lại
                    self._excel_hooked = False
                    excel_app = None

            if self._excel_hooked:
                try:
                    pythoncom.PumpWaitingMessages()
                except Exception:
                    # Người dùng có thể vừa tắt Excel
                    self._excel_hooked = False
                    excel_app = None
                    print("\n💤 Excel đã đóng. Đang chờ học viên mở lại...")

            time.sleep(0.05)

        pythoncom.CoUninitialize()

    def _mouse_monitor_loop(self):
        """Theo dõi chuyển động chuột để phát hiện ngập ngừng."""
        while self._running:
            try:
                mouse_state = self.mouse_tracker.update()
                # Nếu chuột đứng yên >= 3.5s -> đánh dấu ngập ngừng
                idle_dur = mouse_state.get("idle_duration", 0.0)
                if idle_dur >= 3.5:
                    mouse_state["is_hesitating"] = True

                events = self.mouse_sensor._do_detect(
                    excel_state={"cell_clean_address": self.current_cell},
                    mouse_state=mouse_state,
                    context={
                        "session_id": self.current_session_id,
                        "lesson_id": self.current_workbook,
                        "step_index": 0,
                    },
                )
                for ev in events:
                    self.event_logger.log_event(ev)
            except Exception:
                pass
            time.sleep(0.1)

    # =========================================================================
    # CÁC HÀM GHI NHẬN SỰ KIỆN TỪ EXCEL
    # =========================================================================

    def record_workbook_open(self, wb_name: str, wb_path: str):
        self.current_workbook = wb_name
        print(f"📂 [EXCEL MỞ FILE]: {wb_name}")
        self.event_logger.update_session_lesson(self.current_session_id, wb_name)
        ev = RawEvent(
            event_type="WORKBOOK_OPEN",
            session_id=self.current_session_id,
            lesson_id=wb_name,
            cell="",
            metadata={"workbook_name": wb_name, "file_path": wb_path},
        )
        self.event_logger.log_event(ev)

    def set_active_workbook(self, wb_name: str):
        self.current_workbook = wb_name

    def record_selection(self, wb_name: str, sheet_name: str, cell_address: str):
        self.current_workbook = wb_name
        self.current_sheet = sheet_name
        self.current_cell = cell_address
        print(f"👉 [CHỌN Ô]: [{cell_address}] (Sheet: {sheet_name}, File: {wb_name})")
        ev = RawEvent(
            event_type="CELL_SELECTION",
            session_id=self.current_session_id,
            lesson_id=wb_name,
            cell=cell_address,
            metadata={"sheet": sheet_name, "workbook": wb_name},
        )
        self.event_logger.log_event(ev)

    def record_cell_change(self, wb_name: str, sheet_name: str, cell_address: str, val: Any, formula: Any):
        self.current_workbook = wb_name
        self.current_sheet = sheet_name
        self.current_cell = cell_address

        is_formula = isinstance(formula, str) and formula.startswith("=")
        event_type = "FORMULA_ENTRY" if is_formula else "CELL_VALUE_CHANGE"

        display_val = str(formula) if is_formula else str(val)
        print(f"✍️ [{'CÔNG THỨC' if is_formula else 'NHẬP LIỆU'}]: [{cell_address}] = {display_val}")

        # Kiểm tra lỗi công thức nếu có
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
            },
        )
        self.event_logger.log_event(ev)

    def stop(self):
        """Dừng bộ ghi nhận an toàn."""
        self._running = False
        print("\n🛑 Đang lưu toàn bộ sự kiện vào CSDL...")
        self.event_logger.end_session(self.current_session_id, status="COMPLETED")
        self.event_logger.close()
        print("✅ Đã kết thúc và lưu trữ an toàn!")


if __name__ == "__main__":
    recorder = UniversalExcelRecorder()
    recorder.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        recorder.stop()
