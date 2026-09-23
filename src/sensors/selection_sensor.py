"""
Selection Sensor: Giám sát thay đổi con trỏ ô tính và phạm vi vùng chọn trong Excel.
"""

from typing import Any, Dict, List
from src.sensors.base_sensor import BaseSensor, RawEvent


class SelectionSensor(BaseSensor):
    def __init__(self, enabled: bool = True):
        super().__init__(name="SelectionSensor", enabled=enabled)
        self.last_cell = ""
        self.last_selection = ""

    def reset(self):
        self.last_cell = ""
        self.last_selection = ""

    def _do_detect(self, excel_state: Dict[str, Any], mouse_state: Dict[str, Any], context: Dict[str, Any]) -> List[RawEvent]:
        events = []
        if not excel_state.get("connected"):
            return events

        current_cell = excel_state.get("cell_clean_address", "")
        current_selection = excel_state.get("selection_address", "")
        is_range = excel_state.get("is_range_selection", False)

        session_id = context.get("session_id", "")
        lesson_id = context.get("lesson_id", "")
        step_index = context.get("step_index", 0)

        # 1. Phát hiện chọn ô đơn lẻ mới
        if current_cell and current_cell != self.last_cell:
            events.append(
                RawEvent(
                    event_type="CELL_SELECTION",
                    session_id=session_id,
                    lesson_id=lesson_id,
                    step_index=step_index,
                    cell=current_cell,
                    metadata={
                        "previous_cell": self.last_cell,
                        "sheet": excel_state.get("sheet", ""),
                        "workbook": excel_state.get("workbook", ""),
                    },
                )
            )
            self.last_cell = current_cell

        # 2. Phát hiện quét chọn vùng nhiều ô (Range Selection)
        if is_range and current_selection and current_selection != self.last_selection:
            events.append(
                RawEvent(
                    event_type="RANGE_SELECTION",
                    session_id=session_id,
                    lesson_id=lesson_id,
                    step_index=step_index,
                    cell=current_selection,
                    metadata={
                        "previous_selection": self.last_selection,
                        "rows": excel_state.get("selection_rows", 1),
                        "columns": excel_state.get("selection_columns", 1),
                        "areas": excel_state.get("selection_area_count", 1),
                    },
                )
            )
            self.last_selection = current_selection

        return events
