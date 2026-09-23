"""
Sensor Manager: Bộ điều phối trung tâm gom và quản lý toàn bộ các cảm biến hành vi.
Hỗ trợ kích hoạt có chọn lọc (Selective/Lazy Sensing) để tối ưu hóa hiệu năng Zero-Lag.
"""

from typing import Any, Dict, List, Optional
from src.sensors.base_sensor import BaseSensor, RawEvent
from src.sensors.selection_sensor import SelectionSensor
from src.sensors.cell_value_sensor import CellValueSensor
from src.sensors.mouse_sensor import MouseSensor
from src.sensors.timing_sensor import TimingSensor


class SensorManager:
    """
    Quản trị viên đa cảm biến:
    - Gom dữ liệu từ Excel COM, Chuột, Đồng hồ thời gian thực
    - Sinh ra dòng sự kiện thô có cấu trúc (RawEvent Stream)
    - Tự động lọc trùng lặp và điều tiết tần suất
    """

    def __init__(self):
        self.sensors: Dict[str, BaseSensor] = {
            "selection": SelectionSensor(enabled=True),
            "cell_value": CellValueSensor(enabled=True),
            "mouse": MouseSensor(enabled=True),
            "timing": TimingSensor(enabled=True),
        }

    def reset_all(self):
        """Khởi động lại toàn bộ cảm biến khi mở phiên bài học mới."""
        for sensor in self.sensors.values():
            sensor.reset()

    def set_sensor_enabled(self, name: str, enabled: bool):
        """Bật/tắt cảm biến phục vụ cơ chế Lazy Sensing."""
        sensor = self.sensors.get(name)
        if sensor:
            sensor.enabled = enabled

    def process_tick(
        self,
        excel_state: Dict[str, Any],
        mouse_state: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> List[RawEvent]:
        """
        Xử lý một nhịp quan sát từ Worker Thread và trả về danh sách sự kiện mới.
        """
        if context is None:
            context = {}

        collected_events: List[RawEvent] = []
        for sensor in self.sensors.values():
            if sensor.enabled:
                try:
                    events = sensor.detect(excel_state, mouse_state, context)
                    if events:
                        collected_events.extend(events)
                except Exception as e:
                    # Đảm bảo lỗi của một cảm biến không làm ngưng trệ toàn bộ hệ thống
                    print(f"[SensorManager] Cảnh báo lỗi từ {sensor.name}: {e}")

        return collected_events
