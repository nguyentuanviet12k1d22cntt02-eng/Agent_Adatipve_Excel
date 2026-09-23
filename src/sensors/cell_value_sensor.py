"""
Cell Value Sensor: Giám sát thao tác nhập liệu, công thức, thay đổi định dạng và lỗi ô tính.
"""

from typing import Any, Dict, List
from src.sensors.base_sensor import BaseSensor, RawEvent


class CellValueSensor(BaseSensor):
    ERROR_TOKENS = {"#NAME?", "#VALUE!", "#REF!", "#DIV/0!", "#N/A", "#NULL!", "#NUM!"}

    def __init__(self, enabled: bool = True):
        super().__init__(name="CellValueSensor", enabled=enabled)
        self.last_cell = ""
        self.last_value = None
        self.last_format = ""

    def reset(self):
        self.last_cell = ""
        self.last_value = None
        self.last_format = ""

    def _do_detect(self, excel_state: Dict[str, Any], mouse_state: Dict[str, Any], context: Dict[str, Any]) -> List[RawEvent]:
        events = []
        if not excel_state.get("connected"):
            return events

        current_cell = excel_state.get("cell_clean_address", "")
        current_value = excel_state.get("cell_value")
        current_format = str(excel_state.get("cell_format") or "")

        session_id = context.get("session_id", "")
        lesson_id = context.get("lesson_id", "")
        step_index = context.get("step_index", 0)

        # Nếu chuyển ô mới, đồng bộ trạng thái ban đầu mà không coi là thay đổi giá trị
        if current_cell != self.last_cell:
            self.last_cell = current_cell
            self.last_value = current_value
            self.last_format = current_format
            return events

        # 1. Phát hiện thay đổi giá trị trong cùng một ô
        if current_value != self.last_value and current_value is not None:
            val_str = str(current_value).strip()
            is_formula = val_str.startswith("=")
            events.append(
                RawEvent(
                    event_type="FORMULA_ENTRY" if is_formula else "CELL_VALUE_CHANGE",
                    session_id=session_id,
                    lesson_id=lesson_id,
                    step_index=step_index,
                    cell=current_cell,
                    metadata={
                        "previous_value": str(self.last_value) if self.last_value is not None else "",
                        "new_value": val_str,
                        "is_formula": is_formula,
                    },
                )
            )

            # Phát hiện lỗi công thức Excel
            if any(err in val_str.upper() for err in self.ERROR_TOKENS):
                events.append(
                    RawEvent(
                        event_type="FORMULA_ERROR",
                        session_id=session_id,
                        lesson_id=lesson_id,
                        step_index=step_index,
                        cell=current_cell,
                        metadata={"error_token": val_str},
                    )
                )

            self.last_value = current_value

        # 2. Phát hiện thay đổi định dạng NumberFormat (ví dụ: chuyển sang Text '@')
        if current_format and current_format != self.last_format and self.last_format:
            events.append(
                RawEvent(
                    event_type="CELL_FORMAT_CHANGE",
                    session_id=session_id,
                    lesson_id=lesson_id,
                    step_index=step_index,
                    cell=current_cell,
                    metadata={
                        "previous_format": self.last_format,
                        "new_format": current_format,
                    },
                )
            )
            self.last_format = current_format

        return events
