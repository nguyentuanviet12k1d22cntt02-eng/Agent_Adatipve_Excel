"""
Base Sensor: Định nghĩa cấu trúc sự kiện thô (RawEvent) và lớp cảm biến cơ sở (BaseSensor).
"""

from dataclasses import dataclass, field
from datetime import datetime
import time
from typing import Any, Dict, List, Optional


@dataclass
class RawEvent:
    """Sự kiện tương tác thô được thu thập từ Excel hoặc hành vi người học."""

    event_type: str
    timestamp: float = field(default_factory=time.time)
    iso_time: str = field(default_factory=lambda: datetime.now().isoformat())
    session_id: str = ""
    lesson_id: str = ""
    step_index: int = 0
    cell: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "timestamp": self.timestamp,
            "iso_time": self.iso_time,
            "session_id": self.session_id,
            "lesson_id": self.lesson_id,
            "step_index": self.step_index,
            "cell": self.cell,
            "metadata": self.metadata,
        }


class BaseSensor:
    """Lớp trừu tượng cho tất cả các cảm biến trong hệ thống."""

    def __init__(self, name: str, enabled: bool = True):
        self.name = name
        self.enabled = enabled

    def reset(self):
        """Khởi tạo lại trạng thái nội bộ của cảm biến khi bắt đầu phiên mới."""
        pass

    def detect(self, excel_state: Dict[str, Any], mouse_state: Dict[str, Any], context: Dict[str, Any]) -> List[RawEvent]:
        """
        Phát hiện sự kiện từ dữ liệu trạng thái hiện tại.
        :return: Danh sách các RawEvent được sinh ra (nếu có).
        """
        if not self.enabled:
            return []
        return self._do_detect(excel_state, mouse_state, context)

    def _do_detect(self, excel_state: Dict[str, Any], mouse_state: Dict[str, Any], context: Dict[str, Any]) -> List[RawEvent]:
        raise NotImplementedError
