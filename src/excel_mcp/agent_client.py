"""MCP client điều phối Realtime Excel Teaching Agent."""

import os
import sys
from typing import Any, Callable, Dict, Optional

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.ai.tutor_agent import TutorAgent
from src.core.lesson_models import SessionStatus
from src.core.realtime_teaching_agent import RealtimeTeachingAgent
from src.excel_mcp.server import (
    excel_get_active_state,
    excel_get_cell_rect,
    excel_launch_exercise,
    excel_read_range,
    mouse_get_telemetry,
)


class AITutorMCPAgent:
    """Agent quan sát, suy luận sư phạm, hành động và tự kiểm chứng kết quả."""

    def __init__(self, hesitation_threshold: float = 8.0):
        self.tutor_ai = TutorAgent()
        self.runtime = RealtimeTeachingAgent(
            range_reader=self._read_range,
            rect_resolver=self._resolve_rect,
            hesitation_threshold=hesitation_threshold,
        )
        self.runtime.start_lesson("BAI_07")

        self.on_guidance_update: Optional[Callable[[Dict[str, Any]], None]] = None
        self.on_overlay_update: Optional[Callable[[Optional[tuple], str], None]] = None

    @property
    def current_exercise(self) -> str:
        return self.runtime.lesson.id if self.runtime.lesson else ""

    @property
    def current_hint_level(self) -> int:
        return self.runtime.session.hint_level

    def _read_range(self, sheet_name: str, range_address: str) -> Dict[str, Any]:
        return excel_read_range(range_address=range_address, sheet_name=sheet_name)

    def _resolve_rect(self, range_address: str, sheet_name: str):
        return excel_get_cell_rect(range_address, sheet_name)

    def set_exercise(self, exercise_code: str) -> Dict[str, Any]:
        """Khởi động giáo án và yêu cầu Excel mở đúng workbook."""
        lesson_id = "BAI_07" if str(exercise_code) in {"07", "7", "BAI_07"} else "BAI_08"
        guidance = self.runtime.start_lesson(lesson_id)
        result = excel_launch_exercise("07" if lesson_id == "BAI_07" else "08")
        result["guidance"] = guidance
        return result

    def step(self) -> Dict[str, Any]:
        """Một chu kỳ Observe → Interpret → Decide → Act → Verify."""
        if self.runtime.session.status == SessionStatus.PAUSED:
            return self.runtime.last_guidance
        needs_ribbon = self.runtime.needs_ribbon_sensing
        excel_state = excel_get_active_state(needs_ribbon=needs_ribbon)
        mouse_state = mouse_get_telemetry()
        guidance = self.runtime.observe(excel_state, mouse_state)

        if self.on_guidance_update:
            self.on_guidance_update(guidance)
        if self.on_overlay_update:
            self.on_overlay_update(guidance.get("target_rect"), guidance.get("badge_text", ""))
        return guidance

    def request_next_hint(self) -> Dict[str, Any]:
        return self.runtime.request_next_hint()

    def repeat_instruction(self) -> Dict[str, Any]:
        return self.runtime.repeat_instruction()

    def toggle_pause(self) -> Dict[str, Any]:
        return self.runtime.toggle_pause()

    def continue_lesson(self) -> Dict[str, Any]:
        return self.runtime.acknowledge_step()

    def evaluate_student_reflection(self, question: str, answer: str) -> str:
        """LLM chỉ dùng ở điểm tương tác sư phạm, không nằm trong vòng poll realtime."""
        feedback = self.tutor_ai.evaluate_reflection(question, answer)
        if self.runtime.last_guidance:
            guidance = dict(self.runtime.last_guidance)
            guidance["hint_text"] = (
                f"Bạn giải thích: “{answer}”\n\nNhận xét của Gia sư AI:\n{feedback}"
            )
            self.runtime.last_guidance = guidance
        return feedback
