"""
Excel Monitor: Lắng nghe và trích xuất trạng thái thời gian thực từ Microsoft Excel
sử dụng pywin32 COM API.
"""

import ctypes
import os
import time
from ctypes import wintypes
from typing import Optional, Dict, Any, Tuple
import win32com.client
import win32gui
import win32process

from src.core.excel_ribbon_observer import ExcelRibbonObserver


class ExcelMonitor:
    POINTS_PER_INCH = 72.0
    DEFAULT_DPI = 96

    def __init__(self):
        self.excel_app = None
        self.last_connected_time = 0
        self.last_workbook_name = ""
        self.last_sheet_name = ""
        self.last_cell_address = ""
        # Cache phép hiệu chỉnh RangeFromPoint cho viewport hiện tại. Cache tự
        # hết hiệu lực khi scroll/zoom/di chuyển cửa sổ sang monitor khác.
        self._viewport_cache_key = None
        self._viewport_calibration = None
        self._exact_rect_cache_key = None
        self._exact_rect_cache = None
        self._ribbon_observer = ExcelRibbonObserver()

    def connect(self) -> bool:
        """Thử kết nối tới tiến trình Excel đang chạy."""
        # Cách 1: Qua ROT GetActiveObject (nhanh nhất nếu có đăng ký)
        try:
            app = win32com.client.GetActiveObject("Excel.Application")
            if app and app.Workbooks.Count > 0:
                self.excel_app = app
                return True
        except Exception:
            pass

        # Cách 2: Qua Windows Handle EXCEL7 và AccessibleObjectFromWindow
        try:
            import ctypes
            import pythoncom
            from ctypes import wintypes, byref, c_void_p

            u = ctypes.windll.user32
            u.OpenDesktopW.restype = wintypes.HANDLE
            u.OpenDesktopW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            u.SetThreadDesktop.restype = wintypes.BOOL
            u.SetThreadDesktop.argtypes = [wintypes.HANDLE]
            u.EnumDesktopWindows.restype = wintypes.BOOL
            u.EnumDesktopWindows.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.LPARAM]
            u.EnumChildWindows.restype = wintypes.BOOL
            u.EnumChildWindows.argtypes = [wintypes.HWND, ctypes.c_void_p, wintypes.LPARAM]

            # Đảm bảo gắn thread vào desktop Default nếu cần
            try:
                h_desk = u.OpenDesktopW("Default", 0, False, 0x0001 | 0x0040)
                if h_desk:
                    u.SetThreadDesktop(h_desk)
            except Exception:
                h_desk = None

            xl_windows = []
            def enum_desktop_cb(h, lparam):
                cls_buf = ctypes.create_unicode_buffer(256)
                u.GetClassNameW(h, cls_buf, 256)
                if cls_buf.value == "XLMAIN":
                    title_buf = ctypes.create_unicode_buffer(256)
                    u.GetWindowTextW(h, title_buf, 256)
                    vis = u.IsWindowVisible(h)
                    xl_windows.append((h, title_buf.value, vis))
                return True

            WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
            if h_desk:
                u.EnumDesktopWindows(h_desk, ctypes.cast(WNDENUMPROC(enum_desktop_cb), ctypes.c_void_p), 0)
            else:
                u.EnumWindows(ctypes.cast(WNDENUMPROC(enum_desktop_cb), ctypes.c_void_p), 0)

            # Ưu tiên cửa sổ đang hiển thị và có tên file bài tập trong tiêu đề
            xl_windows.sort(key=lambda x: (x[2], len(x[1]) > 0 and "Book" not in x[1]), reverse=True)

            OBJID_NATIVEOM = -16
            iid = bytes(pythoncom.IID_IDispatch)

            for hwnd_main, title, vis in xl_windows:
                excel7_list = []
                def enum_child(h, lparam):
                    cls_buf = ctypes.create_unicode_buffer(256)
                    u.GetClassNameW(h, cls_buf, 256)
                    if cls_buf.value == "EXCEL7":
                        excel7_list.append(h)
                    return True

                u.EnumChildWindows(hwnd_main, ctypes.cast(WNDENUMPROC(enum_child), ctypes.c_void_p), 0)
                for excel7 in excel7_list:
                    p_disp = c_void_p()
                    res = ctypes.oledll.oleacc.AccessibleObjectFromWindow(
                        excel7, OBJID_NATIVEOM, iid, byref(p_disp)
                    )
                    if res == 0 and p_disp.value:
                        disp = pythoncom.ObjectFromAddress(p_disp.value, pythoncom.IID_IDispatch)
                        excel_win = win32com.client.Dispatch(disp)
                        app = excel_win.Application
                        if app and app.Workbooks.Count > 0:
                            self.excel_app = app
                            return True
        except Exception:
            pass

        self.excel_app = None
        return False

    def get_cell_rect_by_address(self, cell_address: str, sheet_name: str = "") -> Optional[Tuple[int, int, int, int]]:
        """
        Truy vấn tọa độ pixel thực tế của ô tính (VD: 'C8') từ cửa sổ Excel đang mở.
        Tự động tái kết nối nếu phiên làm việc Excel bị ngắt quãng.
        """
        for attempt in range(2):
            if not self.excel_app:
                if not self.connect():
                    return None
            try:
                wb = self.excel_app.ActiveWorkbook
                if not wb:
                    self.excel_app = None
                    continue
                ws = wb.Sheets(sheet_name) if sheet_name else self.excel_app.ActiveSheet
                if not ws:
                    return None
                # Chỉ ActiveSheet mới có tọa độ trong ActiveWindow. Không được
                # chiếu cùng một địa chỉ của sheet ẩn/khác lên sheet đang xem.
                active_sheet = self.excel_app.ActiveSheet
                if not active_sheet or str(active_sheet.Name) != str(ws.Name):
                    return None
                cell = ws.Range(cell_address)
                try:
                    if int(cell.Rows.Count) > 1 or int(cell.Columns.Count) > 1:
                        return self.get_visible_range_screen_rect(cell)
                except Exception:
                    pass
                return self.get_cell_screen_rect(cell)
            except Exception:
                self.excel_app = None
        return None

    def launch_exercise(self, file_path: str) -> bool:
        """Mở file bài tập bằng Excel."""
        if not os.path.exists(file_path):
            return False
        try:
            if not self.excel_app:
                try:
                    self.excel_app = win32com.client.GetActiveObject("Excel.Application")
                except Exception:
                    self.excel_app = win32com.client.Dispatch("Excel.Application")
            
            self.excel_app.Visible = True
            abs_path = os.path.abspath(file_path)
            self.excel_app.Workbooks.Open(abs_path)
            return True
        except Exception as e:
            print(f"[ExcelMonitor] Lỗi khi mở bài tập: {e}")
            return False

    def is_excel_foreground(self) -> bool:
        """Kiểm tra xem cửa sổ Excel có đang được người dùng focus hay không."""
        if not self.excel_app:
            return False
        try:
            hwnd = win32gui.GetForegroundWindow()
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            # Kiểm tra xem pid này có phải Excel không
            win_title = win32gui.GetWindowText(hwnd)
            return "excel" in win_title.lower()
        except Exception:
            return False

    def get_cell_screen_rect(self, cell) -> Optional[Tuple[int, int, int, int]]:
        """
        Tính toán tọa độ pixel thực tế trên màn hình (x, y, width, height) của một ô tính.

        Excel trả ``Range.Left/Top/Width/Height`` theo point, không phải pixel. Ở
        màn hình có DPI scaling, việc truyền trực tiếp các giá trị này vào
        PointsToScreenPixelsX/Y làm độ lệch tăng dần theo hàng/cột. Vì vậy chỉ
        dùng PointsToScreenPixelsX/Y(0) làm mốc của vùng lưới, sau đó tự đổi
        point -> physical pixel bằng DPI của cửa sổ Excel và mức Zoom hiện tại.
        """
        try:
            win = self.excel_app.ActiveWindow
            if not win:
                return None

            # Nếu địa chỉ nằm trong một vùng merge, cần khoanh toàn bộ vùng merge.
            try:
                if bool(cell.MergeCells):
                    cell = cell.MergeArea
            except Exception:
                pass

            ws = cell.Worksheet
            anchor_left, anchor_top = self._get_view_anchor(win, ws, cell)

            # PointsToScreenPixelsX/Y có tính trạng thái scroll của document.
            # Sau khi cuộn, mốc 0 là vị trí của ô đầu worksheet (có thể đã nằm
            # ngoài màn hình), không còn là góc trên-trái của viewport. Dùng ô
            # đầu tiên đang hiển thị làm anchor để tránh bù scroll hai lần.
            origin_x = int(win.PointsToScreenPixelsX(int(round(anchor_left))))
            origin_y = int(win.PointsToScreenPixelsY(int(round(anchor_top))))
            dpi = self._get_window_dpi(int(self.excel_app.Hwnd))
            zoom = float(win.Zoom or 100)
            rect = self._excel_points_to_screen_rect(
                left=float(cell.Left),
                top=float(cell.Top),
                width=float(cell.Width),
                height=float(cell.Height),
                origin_x=origin_x,
                origin_y=origin_y,
                zoom=zoom,
                dpi=dpi,
                scroll_left=anchor_left,
                scroll_top=anchor_top,
            )

            # Fast path: công thức thường đúng khi chưa cuộn. Nếu Excel/Office
            # virtualize tọa độ khác đi sau scroll hoặc khi đổi monitor, dùng
            # RangeFromPoint để hiệu chỉnh lại bằng một cell đang hiển thị thật.
            refined = self._refine_range_rect(win, cell, rect)
            if refined:
                return refined
            if self._rect_matches_cell(win, cell, rect):
                return rect
            return self._get_calibrated_cell_rect(win, cell, dpi, zoom)
        except Exception:
            # Ô ẩn, ngoài màn hình hoặc Excel đang bận/Edit Mode.
            return None

    def get_visible_range_screen_rect(self, cell) -> Optional[Tuple[int, int, int, int]]:
        """Lấy phần hình chữ nhật đang nhìn thấy của một Range nhiều ô.

        Một vùng chọn có thể lớn hơn viewport hiện tại. Khoanh toàn bộ ``Width`` /
        ``Height`` của Range trong trường hợp đó sẽ làm khung đỏ tràn lên Ribbon
        hoặc ra ngoài màn hình, vì vậy chỉ vẽ phần giao với ``VisibleRange``.
        """
        try:
            win = self.excel_app.ActiveWindow
            if not win:
                return None

            visible_part = self.excel_app.Intersect(cell, win.VisibleRange)
            if visible_part is None:
                return None

            # Intersect thường trả một Area. Vẫn xử lý nhiều Area để không làm
            # mất khung ở workbook có split/frozen panes đặc biệt.
            try:
                areas = visible_part.Areas
                area_count = int(areas.Count)
            except Exception:
                areas = None
                area_count = 1

            if area_count <= 1:
                return self.get_cell_screen_rect(visible_part)

            rects = []
            for index in range(1, area_count + 1):
                area = areas.Item(index)
                rect = self.get_cell_screen_rect(area)
                if rect:
                    rects.append(rect)
            return self._union_rects(rects)
        except Exception:
            # Excel cũ có thể không cấp Intersect/VisibleRange trong Edit Mode.
            return self.get_cell_screen_rect(cell)

    @staticmethod
    def _union_rects(rects) -> Optional[Tuple[int, int, int, int]]:
        """Gộp các hình chữ nhật physical-pixel thành một khung bao."""
        valid = [tuple(rect) for rect in rects if rect and rect[2] > 0 and rect[3] > 0]
        if not valid:
            return None
        left = min(rect[0] for rect in valid)
        top = min(rect[1] for rect in valid)
        right = max(rect[0] + rect[2] for rect in valid)
        bottom = max(rect[1] + rect[3] for rect in valid)
        return left, top, right - left, bottom - top

    @classmethod
    def _excel_points_to_screen_rect(
        cls,
        *,
        left: float,
        top: float,
        width: float,
        height: float,
        origin_x: int,
        origin_y: int,
        zoom: float,
        dpi: int,
        scroll_left: float = 0.0,
        scroll_top: float = 0.0,
    ) -> Tuple[int, int, int, int]:
        """Đổi hình chữ nhật Excel (point) sang physical screen pixels."""
        scale = max(0.01, float(zoom) / 100.0) * max(1, int(dpi)) / cls.POINTS_PER_INCH
        x = int(round(origin_x + (left - scroll_left) * scale))
        y = int(round(origin_y + (top - scroll_top) * scale))
        right = int(round(origin_x + (left + width - scroll_left) * scale))
        bottom = int(round(origin_y + (top + height - scroll_top) * scale))
        w = max(0, right - x)
        h = max(0, bottom - y)
        return x, y, w, h

    @staticmethod
    def _get_window_dpi(hwnd: int) -> int:
        """Lấy DPI thật của đúng monitor chứa Excel, có fallback cho Windows cũ."""
        try:
            get_dpi = ctypes.windll.user32.GetDpiForWindow
            get_dpi.argtypes = [ctypes.c_void_p]
            get_dpi.restype = ctypes.c_uint
            dpi = int(get_dpi(hwnd))
            if dpi > 0:
                return dpi
        except Exception:
            pass

        hdc = None
        try:
            hdc = ctypes.windll.user32.GetDC(hwnd)
            if hdc:
                # LOGPIXELSX = 88
                dpi = int(ctypes.windll.gdi32.GetDeviceCaps(hdc, 88))
                if dpi > 0:
                    return dpi
        except Exception:
            pass
        finally:
            if hdc:
                try:
                    ctypes.windll.user32.ReleaseDC(hwnd, hdc)
                except Exception:
                    pass
        return ExcelMonitor.DEFAULT_DPI

    @staticmethod
    def _get_view_anchor(win, ws, cell) -> Tuple[float, float]:
        """Lấy mốc point của pane thực sự chứa ô mục tiêu sau khi cuộn."""
        scroll_row = max(1, int(win.ScrollRow or 1))
        scroll_col = max(1, int(win.ScrollColumn or 1))
        split_row = max(0, int(win.SplitRow or 0))
        split_col = max(0, int(win.SplitColumn or 0))
        freeze_panes = bool(win.FreezePanes)

        # Ô trong vùng frozen vẫn lấy gốc worksheet; ô trong pane cuộn lấy gốc
        # là cell đầu tiên đang hiển thị của pane đó.
        if freeze_panes and split_col > 0 and int(cell.Column) <= split_col:
            anchor_left = 0.0
        else:
            anchor_left = float(ws.Cells(1, scroll_col).Left)

        if freeze_panes and split_row > 0 and int(cell.Row) <= split_row:
            anchor_top = 0.0
        else:
            anchor_top = float(ws.Cells(scroll_row, 1).Top)

        return anchor_left, anchor_top

    @classmethod
    def _rect_matches_cell(cls, win, cell, rect: Tuple[int, int, int, int]) -> bool:
        """Xác nhận cả bốn góc, không chỉ tâm, trùng đúng biên Range."""
        x, y, w, h = rect
        if w <= 0 or h <= 0:
            return False
        try:
            first_row = int(cell.Row)
            first_col = int(cell.Column)
            last_row = first_row + int(cell.Rows.Count) - 1
            last_col = first_col + int(cell.Columns.Count) - 1
            inset_x = 1 if w > 2 else 0
            inset_y = 1 if h > 2 else 0
            probes = (
                (x + inset_x, y + inset_y, first_row, first_col),
                (x + w - 1 - inset_x, y + inset_y, first_row, last_col),
                (x + inset_x, y + h - 1 - inset_y, last_row, first_col),
                (x + w - 1 - inset_x, y + h - 1 - inset_y, last_row, last_col),
            )
            for probe_x, probe_y, expected_row, expected_col in probes:
                hit = cls._range_at_point(win, probe_x, probe_y)
                if hit is None:
                    return False
                if int(hit.Row) != expected_row or int(hit.Column) != expected_col:
                    return False
                try:
                    if str(hit.Worksheet.Name) != str(cell.Worksheet.Name):
                        return False
                except Exception:
                    pass
            return True
        except Exception:
            return False

    def _get_calibrated_cell_rect(self, win, cell, dpi: int, zoom: float):
        """
        Hiệu chỉnh viewport bằng RangeFromPoint.

        Phương pháp này không giả định vị trí Ribbon, thanh công thức, scroll hay
        monitor. Nó lấy một cell tham chiếu ngay trong EXCEL7, đo biên cell đó
        bằng tọa độ màn hình thật, rồi ánh xạ cell mục tiêu theo đơn vị point.
        """
        for grid_rect in self._get_excel_grid_rects():
            cache_key = self._viewport_key(win, cell, grid_rect)
            calibration = None
            if cache_key == self._viewport_cache_key:
                calibration = self._viewport_calibration

            if calibration:
                rect = self._rect_from_calibration(cell, calibration)
                refined = self._refine_range_rect(win, cell, rect)
                if refined:
                    return refined
                if self._rect_matches_cell(win, cell, rect):
                    return rect

            calibration = self._build_viewport_calibration(
                win, grid_rect, dpi=dpi, zoom=zoom
            )
            if not calibration:
                continue

            self._viewport_cache_key = cache_key
            self._viewport_calibration = calibration
            rect = self._rect_from_calibration(cell, calibration)
            refined = self._refine_range_rect(win, cell, rect)
            if refined:
                return refined
            if self._rect_matches_cell(win, cell, rect):
                return rect
        return None

    def _refine_range_rect(self, win, cell, candidate):
        """Đo lại chính xác bốn biên Range bằng RangeFromPoint.

        Công thức point→pixel chỉ dùng để tìm một điểm nằm bên trong. Sau đó
        exponential/binary search đo pixel đầu và pixel cuối thực sự thuộc
        Range, nên sai số scale/round không còn tích lũy theo hàng hoặc cột.
        """
        x, y, width, height = candidate
        if width <= 0 or height <= 0:
            return None

        for grid_rect in self._get_excel_grid_rects():
            left, top, right, bottom = grid_rect
            ix1 = max(x, left)
            iy1 = max(y, top)
            ix2 = min(x + width, right)
            iy2 = min(y + height, bottom)
            if ix2 <= ix1 or iy2 <= iy1:
                continue

            try:
                address = str(cell.Address).replace("$", "")
            except Exception:
                address = ""
            cache_key = self._viewport_key(win, cell, grid_rect) + (
                address,
                float(cell.Left),
                float(cell.Top),
                float(cell.Width),
                float(cell.Height),
            )
            if cache_key == self._exact_rect_cache_key and self._exact_rect_cache:
                return self._exact_rect_cache

            sample_x = (ix1 + ix2 - 1) // 2
            sample_y = (iy1 + iy2 - 1) // 2
            probes = (
                (sample_x, sample_y),
                (ix1 + 1, iy1 + 1),
                (ix2 - 2, iy1 + 1),
                (ix1 + 1, iy2 - 2),
                (ix2 - 2, iy2 - 2),
            )
            for probe_x, probe_y in probes:
                probe_x = min(max(ix1, probe_x), ix2 - 1)
                probe_y = min(max(iy1, probe_y), iy2 - 1)
                if not self._point_matches_range(win, cell, probe_x, probe_y):
                    continue
                bounds = self._measure_range_bounds(
                    win, cell, probe_x, probe_y, grid_rect
                )
                if not bounds:
                    continue
                exact_left, exact_top, exact_right, exact_bottom = bounds
                exact = (
                    exact_left,
                    exact_top,
                    exact_right - exact_left,
                    exact_bottom - exact_top,
                )
                if exact[2] > 0 and exact[3] > 0:
                    self._exact_rect_cache_key = cache_key
                    self._exact_rect_cache = exact
                    return exact
        return None

    def _get_excel_grid_rects(self):
        """Lấy physical rectangles của các child window EXCEL7 đang hiển thị."""
        try:
            hwnd_main = int(self.excel_app.Hwnd)
            candidates = []

            def collect(hwnd, _extra):
                try:
                    if win32gui.GetClassName(hwnd) == "EXCEL7" and win32gui.IsWindowVisible(hwnd):
                        rect = self._get_physical_window_rect(hwnd)
                        width = max(0, rect[2] - rect[0])
                        height = max(0, rect[3] - rect[1])
                        if width > 100 and height > 100:
                            candidates.append((width * height, rect))
                except Exception:
                    pass
                return True

            win32gui.EnumChildWindows(hwnd_main, collect, None)
            candidates.sort(key=lambda item: item[0], reverse=True)
            return [rect for _, rect in candidates]
        except Exception:
            return []

    @staticmethod
    def _get_physical_window_rect(
        hwnd: int,
        _user32=None,
        _get_rect=None,
    ) -> Tuple[int, int, int, int]:
        """Đọc ``GetWindowRect`` trong hệ tọa độ physical-pixel.

        Nếu tiến trình Python chưa được khai báo Per-Monitor DPI Aware, Windows
        sẽ ảo hóa ``GetWindowRect`` về 96 DPI, trong khi Excel
        ``PointsToScreenPixels*`` và ``RangeFromPoint`` vẫn dùng physical pixel.
        Hai hệ tọa độ lẫn nhau làm mất khung tại 125%/150% scaling. Chỉ nâng DPI
        awareness của thread trong đúng lúc đọc rectangle rồi khôi phục ngay.
        """
        user32 = _user32 or ctypes.windll.user32
        get_rect = _get_rect or win32gui.GetWindowRect
        set_context = getattr(user32, "SetThreadDpiAwarenessContext", None)
        previous_context = None
        context_changed = False
        if set_context is not None:
            try:
                set_context.argtypes = [ctypes.c_void_p]
                set_context.restype = ctypes.c_void_p
                # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = (HANDLE)-4
                previous_context = set_context(ctypes.c_void_p(-4))
                context_changed = previous_context is not None
            except Exception:
                previous_context = None
        try:
            rect = tuple(int(value) for value in get_rect(int(hwnd)))
        finally:
            if set_context is not None and context_changed:
                try:
                    set_context(ctypes.c_void_p(previous_context))
                except Exception:
                    pass

        if context_changed:
            return rect

        # Fallback nếu Windows từ chối đổi context: đổi từng điểm theo HWND,
        # an toàn cả với monitor có tọa độ âm/mixed-DPI (không nhân tỉ lệ global).
        convert_point = getattr(
            user32,
            "LogicalToPhysicalPointForPerMonitorDPI",
            None,
        )
        if convert_point is not None:
            try:
                convert_point.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
                convert_point.restype = wintypes.BOOL
                top_left = wintypes.POINT(rect[0], rect[1])
                bottom_right = wintypes.POINT(rect[2], rect[3])
                converted_left = bool(
                    convert_point(wintypes.HWND(int(hwnd)), ctypes.byref(top_left))
                )
                converted_right = bool(
                    convert_point(wintypes.HWND(int(hwnd)), ctypes.byref(bottom_right))
                )
                if converted_left and converted_right:
                    return (
                        int(top_left.x),
                        int(top_left.y),
                        int(bottom_right.x),
                        int(bottom_right.y),
                    )
            except Exception:
                pass
        return rect

    @staticmethod
    def _viewport_key(win, cell, grid_rect):
        try:
            sheet_name = str(cell.Worksheet.Name)
            workbook_name = str(cell.Worksheet.Parent.Name)
        except Exception:
            sheet_name = ""
            workbook_name = ""
        try:
            window_hwnd = int(win.Hwnd)
        except Exception:
            window_hwnd = 0
        return (
            window_hwnd,
            workbook_name,
            sheet_name,
            int(win.ScrollRow or 1),
            int(win.ScrollColumn or 1),
            int(win.SplitRow or 0),
            int(win.SplitColumn or 0),
            bool(win.FreezePanes),
            float(win.Zoom or 100),
            tuple(grid_rect),
        )

    def _build_viewport_calibration(self, win, grid_rect, dpi: int, zoom: float):
        left, top, right, bottom = grid_rect
        width = right - left
        height = bottom - top
        # Thử nhiều điểm ở vùng nội dung; tránh row/column headers và scrollbar.
        probes = (
            (0.50, 0.50), (0.35, 0.35), (0.65, 0.35),
            (0.35, 0.65), (0.65, 0.65), (0.20, 0.50),
        )
        base_scale = max(0.01, float(zoom) / 100.0) * max(1, int(dpi)) / self.POINTS_PER_INCH

        for fx, fy in probes:
            probe_x = int(round(left + width * fx))
            probe_y = int(round(top + height * fy))
            reference = self._range_at_point(win, probe_x, probe_y)
            if reference is None:
                continue
            try:
                if bool(reference.MergeCells):
                    reference = reference.MergeArea
            except Exception:
                pass

            bounds = self._measure_range_bounds(
                win, reference, probe_x, probe_y, grid_rect
            )
            if not bounds:
                continue
            ref_left_px, ref_top_px, ref_right_px, ref_bottom_px = bounds

            try:
                ref_width_pt = float(reference.Width)
                ref_height_pt = float(reference.Height)
                scale_x = (
                    (ref_right_px - ref_left_px) / ref_width_pt
                    if ref_width_pt > 0 else base_scale
                )
                scale_y = (
                    (ref_bottom_px - ref_top_px) / ref_height_pt
                    if ref_height_pt > 0 else base_scale
                )
                # Một số cell bị cắt ở mép viewport. Khi số đo bất thường, dùng
                # scale DPI*Zoom chuẩn thay vì đưa sai số vào toàn bộ worksheet.
                if not (base_scale * 0.65 <= scale_x <= base_scale * 1.35):
                    scale_x = base_scale
                if not (base_scale * 0.65 <= scale_y <= base_scale * 1.35):
                    scale_y = base_scale

                return {
                    "reference_left_pt": float(reference.Left),
                    "reference_top_pt": float(reference.Top),
                    "reference_left_px": ref_left_px,
                    "reference_top_px": ref_top_px,
                    "scale_x": scale_x,
                    "scale_y": scale_y,
                }
            except Exception:
                continue
        return None

    @staticmethod
    def _rect_from_calibration(cell, calibration):
        scale_x = float(calibration["scale_x"])
        scale_y = float(calibration["scale_y"])
        x = int(round(
            calibration["reference_left_px"]
            + (float(cell.Left) - calibration["reference_left_pt"]) * scale_x
        ))
        y = int(round(
            calibration["reference_top_px"]
            + (float(cell.Top) - calibration["reference_top_pt"]) * scale_y
        ))
        right = int(round(
            calibration["reference_left_px"]
            + (
                float(cell.Left)
                + float(cell.Width)
                - calibration["reference_left_pt"]
            ) * scale_x
        ))
        bottom = int(round(
            calibration["reference_top_px"]
            + (
                float(cell.Top)
                + float(cell.Height)
                - calibration["reference_top_pt"]
            ) * scale_y
        ))
        w = max(0, right - x)
        h = max(0, bottom - y)
        return x, y, w, h

    @staticmethod
    def _range_at_point(win, x: int, y: int):
        try:
            hit = win.RangeFromPoint(int(x), int(y))
            if hit is None:
                return None
            # Shape/Chart không có Row/Column như Range.
            _ = int(hit.Row)
            _ = int(hit.Column)
            return hit
        except Exception:
            return None

    @classmethod
    def _point_matches_range(cls, win, reference, x: int, y: int) -> bool:
        hit = cls._range_at_point(win, x, y)
        if hit is None:
            return False
        try:
            hit_row = int(hit.Row)
            hit_col = int(hit.Column)
            first_row = int(reference.Row)
            first_col = int(reference.Column)
            last_row = first_row + int(reference.Rows.Count) - 1
            last_col = first_col + int(reference.Columns.Count) - 1
            if not (first_row <= hit_row <= last_row and first_col <= hit_col <= last_col):
                return False
            try:
                return str(hit.Worksheet.Name) == str(reference.Worksheet.Name)
            except Exception:
                return True
        except Exception:
            return False

    @classmethod
    def _find_matching_edge(
        cls, win, reference, start: int, fixed: int, limit: int,
        direction: int, horizontal: bool
    ) -> int:
        """Tìm pixel đầu/cuối thuộc reference bằng exponential + binary search."""
        match_pos = int(start)
        step = 1

        def matches(position):
            x, y = (position, fixed) if horizontal else (fixed, position)
            return cls._point_matches_range(win, reference, x, y)

        while True:
            candidate = start + direction * step
            candidate = max(limit, candidate) if direction < 0 else min(limit, candidate)
            if matches(candidate):
                match_pos = candidate
                if candidate == limit:
                    return candidate if direction < 0 else candidate + 1
                step *= 2
                continue
            mismatch_pos = candidate
            break

        if direction < 0:
            low, high = mismatch_pos, match_pos  # mismatch, match
            while high - low > 1:
                middle = (low + high) // 2
                if matches(middle):
                    high = middle
                else:
                    low = middle
            return high

        low, high = match_pos, mismatch_pos  # match, mismatch
        while high - low > 1:
            middle = (low + high) // 2
            if matches(middle):
                low = middle
            else:
                high = middle
        return low + 1  # exclusive right/bottom edge

    @classmethod
    def _measure_range_bounds(cls, win, reference, x: int, y: int, grid_rect):
        if not cls._point_matches_range(win, reference, x, y):
            return None
        left, top, right, bottom = grid_rect
        try:
            range_left = cls._find_matching_edge(
                win, reference, x, y, left, -1, horizontal=True
            )
            range_right = cls._find_matching_edge(
                win, reference, x, y, right - 1, 1, horizontal=True
            )
            range_top = cls._find_matching_edge(
                win, reference, y, x, top, -1, horizontal=False
            )
            range_bottom = cls._find_matching_edge(
                win, reference, y, x, bottom - 1, 1, horizontal=False
            )
            if range_right <= range_left or range_bottom <= range_top:
                return None
            return range_left, range_top, range_right, range_bottom
        except Exception:
            return None

    def get_state(self) -> Dict[str, Any]:
        """
        Trích xuất toàn bộ trạng thái hiện tại của Excel:
        - workbook: Tên file đang mở
        - sheet: Tên sheet hiện tại
        - active_cell: Địa chỉ ô đang chọn (VD: '$C$7')
        - cell_clean_address: 'C7'
        - cell_value: Giá trị hiện tại của ô
        - cell_format: Định dạng ô (VD: '@', 'General', ...)
        - cell_rect: (x, y, w, h) tọa độ màn hình
        - selection_address: Địa chỉ toàn bộ vùng chọn (VD: 'D18:O30')
        - selection_rect: Khung pixel của toàn bộ phần vùng chọn đang hiển thị
        """
        state = {
            "connected": False,
            "workbook": "",
            "sheet": "",
            "active_cell": "",
            "cell_clean_address": "",
            "cell_value": None,
            "cell_format": "",
            "cell_rect": None,
            "selection_address": "",
            "selection_rect": None,
            "selection_rows": 1,
            "selection_columns": 1,
            "selection_area_count": 1,
            "is_range_selection": False,
            "excel_rect": None,
            "ribbon_available": False,
            "ribbon_tab_id": "",
            "ribbon_tab_name": "",
            "number_format_expanded": False,
            "number_format_focused": False,
        }

        if not self.excel_app:
            if not self.connect():
                return state

        try:
            wb = self.excel_app.ActiveWorkbook
            if not wb:
                return state

            state["connected"] = True
            state["workbook"] = wb.Name
            
            ws = self.excel_app.ActiveSheet
            if ws:
                state["sheet"] = ws.Name
            
            cell = self.excel_app.ActiveCell
            if cell:
                addr = cell.Address
                state["active_cell"] = addr
                state["cell_clean_address"] = addr.replace("$", "")
                state["cell_value"] = cell.Value
                state["cell_format"] = str(cell.NumberFormat)
                state["cell_rect"] = self.get_cell_screen_rect(cell)

            # ActiveCell chỉ là ô neo của Selection. Khi người dùng kéo chọn cả
            # vùng, phải lấy chính Selection để khung đỏ bao trọn vùng đó.
            try:
                selection = self.excel_app.Selection
                selection_address = str(selection.Address).replace("$", "")
                selection_rows = max(1, int(selection.Rows.Count))
                selection_columns = max(1, int(selection.Columns.Count))
                selection_area_count = max(1, int(selection.Areas.Count))

                state["selection_address"] = selection_address
                state["selection_rows"] = selection_rows
                state["selection_columns"] = selection_columns
                state["selection_area_count"] = selection_area_count
                state["is_range_selection"] = bool(
                    selection_area_count > 1
                    or selection_rows > 1
                    or selection_columns > 1
                )

                if selection_area_count == 1:
                    if state["is_range_selection"]:
                        state["selection_rect"] = self.get_visible_range_screen_rect(selection)
                    else:
                        # Không gọi COM lần hai cho trường hợp chỉ chọn một ô.
                        state["selection_rect"] = state["cell_rect"]
            except Exception:
                # Selection có thể là Shape/Chart thay vì Range.
                if cell:
                    state["selection_address"] = state["cell_clean_address"]
                    state["selection_rect"] = state["cell_rect"]

            # Lấy vị trí cửa sổ Excel
            hwnd = self.excel_app.Hwnd
            if hwnd:
                state["excel_rect"] = self._get_physical_window_rect(hwnd)
                state.update(
                    self._ribbon_observer.get_state(
                        int(hwnd),
                        self.excel_app,
                    )
                )

            return state
        except Exception as e:
            # Nếu COM bị đứt hoặc Excel đóng
            self.excel_app = None
            self._ribbon_observer.reset()
            return state

    def get_range_values(self, sheet_name: str, range_address: str) -> Optional[list]:
        """Đọc giá trị của một vùng ô để kiểm tra đáp án tổng thể."""
        if not self.excel_app:
            return None
        try:
            ws = self.excel_app.ActiveWorkbook.Sheets(sheet_name)
            rng = ws.Range(range_address)
            return rng.Value
        except Exception:
            return None

    def get_range_formats(self, sheet_name: str, range_address: str) -> Optional[list]:
        """Đọc NumberFormat theo từng ô để phát hiện vùng định dạng chưa đều.

        COM trả ``None`` khi một Range có nhiều định dạng khác nhau. Teaching
        Agent cần biết chính xác ô nào đã đổi sang Text, nên với vùng nhiều ô ta
        luôn trả về một ma trận có cùng kích thước với Range.
        """
        if not self.excel_app:
            return None
        try:
            ws = self.excel_app.ActiveWorkbook.Sheets(sheet_name)
            rng = ws.Range(range_address)
            row_count = int(rng.Rows.Count)
            column_count = int(rng.Columns.Count)
            if row_count == 1 and column_count == 1:
                return rng.NumberFormat
            return tuple(
                tuple(
                    str(rng.Cells(row_index, column_index).NumberFormat)
                    for column_index in range(1, column_count + 1)
                )
                for row_index in range(1, row_count + 1)
            )
        except Exception:
            return None

    def write_cell(self, cell_address: str, value: Any, sheet_name: str = "") -> bool:
        """Ghi giá trị vào một ô tính cụ thể trong Excel."""
        for attempt in range(2):
            if not self.excel_app:
                if not self.connect():
                    return False
            try:
                wb = self.excel_app.ActiveWorkbook
                if not wb:
                    self.excel_app = None
                    continue
                ws = wb.Sheets(sheet_name) if sheet_name else self.excel_app.ActiveSheet
                if not ws:
                    return False
                ws.Range(cell_address).Value = value
                return True
            except Exception:
                self.excel_app = None
        return False
