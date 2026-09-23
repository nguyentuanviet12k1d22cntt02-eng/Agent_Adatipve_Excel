"""
Timing Sensor: Đo lường thời gian thực hiện bước, khoảng cách thời gian giữa các thao tác.
"""

import time
from typing import Any, Dict, List
from src.sensors.base_sensor import BaseSensor, RawEvent


class TimingSensor(BaseSensor):
    def __init__(self, enabled: bool = True):
        super().__init__(name="TimingSensor", enabled=enabled)
        self.last_step_index = -1
        self.step_start_time = 0.0
        self.last_action_time = 0.0

    def reset(self):
        self.last_step_index = -1
        self.step_start_time = 0.0
        self.last_action_time = 0.0

    def _do_detect(self, excel_state: Dict[str, Any], mouse_state: Dict[str, Any], context: Dict[str, Any]) -> List[RawEvent]:
        events = []
        now = time.time()
        step_index = context.get("step_index", 0)
        session_id = context.get("session_id", "")
        lesson_id = context.get("lesson_id", "")
        current_cell = excel_state.get("cell_clean_address", "")

        # 1. Phát hiện chuyển bước bài học
        if step_index != self.last_step_index:
            if self.last_step_index >= 0:
                duration = now - self.step_start_time
                events.append(
                    RawEvent(
                        event_type="STEP_FINISHED",
                        session_id=session_id,
                        lesson_id=lesson_id,
                        step_index=self.last_step_index,
                        cell=current_cell,
                        metadata={"time_on_step": round(duration, 2)},
                    )
                )

            events.append(
                RawEvent(
                    event_type="STEP_STARTED",
                    session_id=session_id,
                    lesson_id=lesson_id,
                    step_index=step_index,
                    cell=current_cell,
                    metadata={"step_title": context.get("step_title", "")},
                )
            )
            self.last_step_index = step_index
            self.step_start_time = now
            self.last_action_time = now

        return events
