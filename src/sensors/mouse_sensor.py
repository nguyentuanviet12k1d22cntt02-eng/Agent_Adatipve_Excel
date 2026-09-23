"""
Mouse Sensor: Theo dõi hành vi thần kinh cơ học qua vận tốc chuột, ngập ngừng và lúng túng.
"""

from typing import Any, Dict, List
from src.sensors.base_sensor import BaseSensor, RawEvent


class MouseSensor(BaseSensor):
    def __init__(self, enabled: bool = True):
        super().__init__(name="MouseSensor", enabled=enabled)
        self.was_hesitating = False
        self.last_state_code = "IDLE"

    def reset(self):
        self.was_hesitating = False
        self.last_state_code = "IDLE"

    def _do_detect(self, excel_state: Dict[str, Any], mouse_state: Dict[str, Any], context: Dict[str, Any]) -> List[RawEvent]:
        events = []
        if not mouse_state:
            return events

        is_hesitating = mouse_state.get("is_hesitating", False)
        state_code = mouse_state.get("state_code", "IDLE")
        speed = mouse_state.get("speed", 0.0)
        idle_duration = mouse_state.get("idle_duration", 0.0)
        current_cell = excel_state.get("cell_clean_address", "")

        session_id = context.get("session_id", "")
        lesson_id = context.get("lesson_id", "")
        step_index = context.get("step_index", 0)

        # 1. Phát hiện chuyển sang trạng thái ngập ngừng (Hesitation)
        if is_hesitating and not self.was_hesitating:
            events.append(
                RawEvent(
                    event_type="MOUSE_HESITATION_START",
                    session_id=session_id,
                    lesson_id=lesson_id,
                    step_index=step_index,
                    cell=current_cell,
                    metadata={
                        "idle_duration": idle_duration,
                        "hovered_cell": mouse_state.get("hovered_cell", ""),
                    },
                )
            )
            self.was_hesitating = True
        elif not is_hesitating and self.was_hesitating:
            # Kết thúc ngập ngừng
            events.append(
                RawEvent(
                    event_type="MOUSE_HESITATION_END",
                    session_id=session_id,
                    lesson_id=lesson_id,
                    step_index=step_index,
                    cell=current_cell,
                    metadata={"resumed_speed": speed},
                )
            )
            self.was_hesitating = False

        # 2. Phát hiện hành vi lắc chuột mạnh / bối rối (Erratic Movement)
        if state_code == "ERRATIC" and self.last_state_code != "ERRATIC":
            events.append(
                RawEvent(
                    event_type="ERRATIC_MOUSE_MOVEMENT",
                    session_id=session_id,
                    lesson_id=lesson_id,
                    step_index=step_index,
                    cell=current_cell,
                    metadata={
                        "instant_speed": mouse_state.get("instant_speed", 0.0),
                        "max_speed": mouse_state.get("max_speed", 0.0),
                    },
                )
            )

        self.last_state_code = state_code
        return events
