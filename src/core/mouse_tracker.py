"""
Mouse Speed Tracker: Theo dõi tọa độ, tính toán tốc độ chuột thời gian thực (pixels/giây)
và liên kết với ngữ cảnh ô tính trong Microsoft Excel.
"""

import time
import math
import ctypes
from typing import Dict, Any, Optional, Tuple
import win32gui
import win32process

# Thiết lập DPI Awareness để tọa độ chuột khớp chính xác với điểm ảnh hiển thị
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Per-monitor DPI aware
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class MouseSpeedTracker:
    """
    Bộ đo và phân tích tốc độ di chuyển chuột trong môi trường Excel.
    """

    # Phân loại trạng thái nhận thức dựa trên dải tốc độ (pixels / second)
    SPEED_THRESHOLDS = {
        "IDLE_MAX": 20.0,         # Dưới 20 px/s: Coi như chuột đứng yên (ngập ngừng / đọc bài)
        "PRECISION_MAX": 350.0,   # 20 - 350 px/s: Rê chuột cẩn thận để chọn ô / click nút
        "NORMAL_MAX": 900.0,      # 350 - 900 px/s: Di chuyển điều hướng bình thường
        "SCANNING_MAX": 1800.0,   # 900 - 1800 px/s: Lướt nhanh quét tìm kiếm thông tin
                                  # Trên 1800 px/s: Lắc chuột mạnh / bối rối (erratic)
    }

    def __init__(self, excel_monitor=None, smoothing_alpha: float = 0.3):
        """
        :param excel_monitor: Tham chiếu tới ExcelMonitor (nếu có) để truy xuất COM
        :param smoothing_alpha: Hệ số lọc hàm mũ EMA (0 < alpha <= 1) để làm mượt tốc độ
        """
        self.excel_monitor = excel_monitor
        self.alpha = smoothing_alpha

        # Tọa độ và thời gian mẫu trước
        self.last_x = 0
        self.last_y = 0
        self.last_time = time.perf_counter()

        # Tốc độ
        self.instant_speed = 0.0      # Tốc độ tức thời (px/s)
        self.smoothed_speed = 0.0     # Tốc độ đã làm mượt (px/s)
        self.acceleration = 0.0       # Gia tốc (px/s^2)
        self.max_speed = 0.0          # Tốc độ cao nhất ghi nhận được

        # Đo thời gian ngập ngừng (Hesitation)
        self.idle_start_time: Optional[float] = None
        self.idle_duration = 0.0      # Số giây chuột đứng yên liên tục

        # Lịch sử tốc độ để vẽ đồ thị sparkline
        self.speed_history = [0.0] * 60

        # Lưu vết ô tính đang hover
        self.last_hovered_cell = ""
        self.last_hovered_value = None

        self._initialized = False

    def _query_cursor_pos(self) -> Tuple[int, int]:
        """Truy vấn tọa độ chuột vật lý toàn màn hình bằng Win32 API."""
        pt = POINT()
        ok = ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
        if ok:
            return int(pt.x), int(pt.y)
        return self.last_x, self.last_y

    def is_inside_excel(self, x: int, y: int) -> Tuple[bool, int, str]:
        """
        Kiểm tra xem tọa độ (x, y) có đang nằm trong cửa sổ ứng dụng Excel không.
        Trả về: (is_inside, hwnd, window_title)
        """
        hwnd = win32gui.WindowFromPoint((x, y))
        if not hwnd:
            return False, 0, ""

        # Lấy cửa sổ gốc cha cao nhất nếu hwnd là điều khiển con
        root_hwnd = win32gui.GetAncestor(hwnd, 2)  # GA_ROOT = 2
        target_hwnd = root_hwnd if root_hwnd else hwnd

        try:
            _, pid = win32process.GetWindowThreadProcessId(target_hwnd)
            title = win32gui.GetWindowText(target_hwnd)
            class_name = win32gui.GetClassName(target_hwnd)

            # Nhận diện Excel thông qua ClassName hoặc Window Title
            is_excel = "XLMAIN" in class_name or "excel" in title.lower()
            return is_excel, target_hwnd, title
        except Exception:
            return False, 0, ""

    def get_cell_under_cursor(self, x: int, y: int) -> Tuple[str, Any]:
        """
        Sử dụng Excel COM ActiveWindow.RangeFromPoint(x, y) để đọc ô tính
        ngay dưới con trỏ chuột.
        """
        if not self.excel_monitor or not self.excel_monitor.excel_app:
            return "", None

        try:
            win = self.excel_monitor.excel_app.ActiveWindow
            if not win:
                return "", None

            # Gọi API nội tại của Excel
            obj = win.RangeFromPoint(x, y)
            if obj is not None:
                try:
                    addr = obj.Address.replace("$", "")
                    val = obj.Value
                    return addr, val
                except Exception:
                    # Trỏ vào hình vẽ, biểu đồ hoặc header
                    return "SHAPE/OBJECT", None
            return "OUTSIDE_GRID", None
        except Exception:
            # Excel đang ở Edit Mode (đang gõ dở công thức) khiến COM từ chối phản hồi
            return "EXCEL_BUSY", None

    def update(self, custom_pos: Optional[Tuple[int, int]] = None) -> Dict[str, Any]:
        """
        Cập nhật trạng thái đo tốc độ tại khung thời gian hiện tại.
        :param custom_pos: Cho phép truyền tọa độ tùy ý (dùng cho testing/mô phỏng)
        :return: Dict chứa toàn bộ telemetry tốc độ và ngữ cảnh
        """
        now = time.perf_counter()

        # Lấy tọa độ chuột
        if custom_pos is not None:
            cur_x, cur_y = custom_pos
        else:
            cur_x, cur_y = self._query_cursor_pos()

        if not self._initialized:
            self.last_x = cur_x
            self.last_y = cur_y
            self.last_time = now
            self._initialized = True

        dt = now - self.last_time
        # Tránh chia cho 0 nếu gọi quá nhanh
        if dt <= 0.0001:
            dt = 0.001

        # Tính khoảng cách dịch chuyển Euclide (pixels)
        dx = cur_x - self.last_x
        dy = cur_y - self.last_y
        dist = math.sqrt(dx * dx + dy * dy)

        # 1. Tính tốc độ tức thời (pixels / second)
        raw_speed = dist / dt

        # 2. Làm mượt tốc độ bằng bộ lọc hàm mũ (Exponential Moving Average)
        self.smoothed_speed = (self.alpha * raw_speed) + ((1.0 - self.alpha) * self.smoothed_speed)
        self.instant_speed = raw_speed

        # 3. Tính gia tốc
        self.acceleration = (self.smoothed_speed - self.speed_history[-1]) / dt

        # Cập nhật tốc độ tối đa
        if self.smoothed_speed > self.max_speed:
            self.max_speed = self.smoothed_speed

        # 4. Đo lường thời gian ngập ngừng (Hesitation Timer)
        if self.smoothed_speed < self.SPEED_THRESHOLDS["IDLE_MAX"]:
            if self.idle_start_time is None:
                self.idle_start_time = now
            self.idle_duration = now - self.idle_start_time
        else:
            self.idle_start_time = None
            self.idle_duration = 0.0

        # Cập nhật lịch sử tốc độ
        self.speed_history.append(self.smoothed_speed)
        if len(self.speed_history) > 60:
            self.speed_history.pop(0)

        # 5. Phân loại trạng thái nhận thức và hành vi
        state_code, state_label, state_color = self._classify_state(self.smoothed_speed, self.idle_duration)

        # 6. Kiểm tra ngữ cảnh Excel
        is_inside, hwnd, title = self.is_inside_excel(cur_x, cur_y)
        hovered_cell = ""
        cell_val = None

        if is_inside:
            # Tối ưu Zero-Lag: Tuyệt đối không gọi COM RangeFromPoint khi chuột đang di chuyển nhanh.
            # Chỉ truy vấn khi chuột rê chậm (Precision) hoặc đứng yên (Idle/Hesitating) và có throttle >= 150ms.
            can_query_com = (
                self.smoothed_speed <= self.SPEED_THRESHOLDS["PRECISION_MAX"]
                and (now - getattr(self, "_last_cell_query_time", 0.0)) >= 0.15
            )
            if can_query_com:
                self._last_cell_query_time = now
                hovered_cell, cell_val = self.get_cell_under_cursor(cur_x, cur_y)
                if hovered_cell:
                    self.last_hovered_cell = hovered_cell
                    self.last_hovered_value = cell_val
            else:
                hovered_cell = self.last_hovered_cell
                cell_val = self.last_hovered_value

        # Cập nhật vết cho lần gọi tiếp theo
        self.last_x = cur_x
        self.last_y = cur_y
        self.last_time = now

        return {
            "x": cur_x,
            "y": cur_y,
            "dx": dx,
            "dy": dy,
            "dt": dt,
            "instant_speed": round(raw_speed, 1),
            "speed": round(self.smoothed_speed, 1),
            "acceleration": round(self.acceleration, 1),
            "max_speed": round(self.max_speed, 1),
            "idle_duration": round(self.idle_duration, 2),
            "is_hesitating": self.idle_duration >= 2.0,  # Ngập ngừng > 2 giây
            "state_code": state_code,
            "state_label": state_label,
            "state_color": state_color,
            "is_inside_excel": is_inside,
            "excel_title": title,
            "hovered_cell": hovered_cell or self.last_hovered_cell,
            "cell_value": cell_val if hovered_cell else self.last_hovered_value,
            "speed_history": list(self.speed_history),
        }

    def _classify_state(self, speed: float, idle_duration: float) -> Tuple[str, str, str]:
        """Phân loại trạng thái hành vi từ tốc độ."""
        if idle_duration >= 2.0:
            return "HESITATING", f"TĨNH / NGẬP NGỪNG ({idle_duration:.1f}s)", "#10b981"  # Emerald Green
        if speed < self.SPEED_THRESHOLDS["IDLE_MAX"]:
            return "IDLE", "TĨNH (CHUẨN BỊ THAO TÁC)", "#06b6d4"  # Cyan
        elif speed < self.SPEED_THRESHOLDS["PRECISION_MAX"]:
            return "PRECISION", "ĐIỀU HƯỚNG CHÍNH XÁC (RÊ CHUỘT)", "#3b82f6"  # Blue
        elif speed < self.SPEED_THRESHOLDS["NORMAL_MAX"]:
            return "NORMAL", "DI CHUYỂN BÌNH THƯỜNG", "#8b5cf6"  # Purple
        elif speed < self.SPEED_THRESHOLDS["SCANNING_MAX"]:
            return "SCANNING", "LƯỚT QUÉT TÌM KIẾM NHANH", "#f59e0b"  # Amber
        else:
            return "ERRATIC", "CHUYỂN ĐỘNG NHANH / BỐI RỐI", "#ef4444"  # Crimson Red
