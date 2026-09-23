"""Teaching Agent quan sát Excel realtime và điều phối hướng dẫn từng bước.

Vòng quan sát được thiết kế để chạy nhanh bằng dữ liệu có cấu trúc. Không có
lời gọi LLM trong ``observe``; AI sinh ngôn ngữ chỉ nên được dùng ở những điểm
hiếm như đánh giá câu trả lời phản biện của học viên.
"""

from datetime import date, datetime
import math
import re
import time
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from src.core.lesson_catalog import get_lesson, normalize_text
from src.core.lesson_models import (
    CheckKind,
    LessonPlan,
    LessonStep,
    ProcedureAction,
    ProcedureActionKind,
    SessionStatus,
    StepAssessment,
    TeachingSession,
)


RangeReader = Callable[[str, str], Dict[str, Any]]
RectResolver = Callable[[str, str], Any]


class RealtimeTeachingAgent:
    """Một agent điều phối: Observe → Interpret → Decide → Act → Verify."""

    def __init__(
        self,
        range_reader: RangeReader,
        rect_resolver: RectResolver,
        hesitation_threshold: float = 8.0,
        auto_advance_delay: float = 1.2,
    ):
        self.range_reader = range_reader
        self.rect_resolver = rect_resolver
        self.hesitation_threshold = max(1.0, float(hesitation_threshold))
        self.auto_advance_delay = max(0.0, float(auto_advance_delay))
        self.lesson: Optional[LessonPlan] = None
        self.session = TeachingSession()
        self.last_excel_state: Dict[str, Any] = {}
        self.last_mouse_state: Dict[str, Any] = {}
        self.last_guidance: Dict[str, Any] = {}
        self._last_assessment_signature = ""
        self._last_interaction_signature = ""

    @property
    def current_step(self) -> Optional[LessonStep]:
        if not self.lesson or not self.lesson.steps:
            return None
        index = min(self.session.current_step_index, len(self.lesson.steps) - 1)
        return self.lesson.steps[index]

    def start_lesson(self, lesson_id: str, now: Optional[float] = None) -> Dict[str, Any]:
        now = time.monotonic() if now is None else float(now)
        self.lesson = get_lesson(lesson_id)
        self.session = TeachingSession(
            lesson_id=self.lesson.id,
            current_step_index=0,
            status=SessionStatus.WAITING_FOR_EXCEL,
            hint_level=1,
            started_at=now,
            step_started_at=now,
            last_activity_at=now,
        )
        self._last_assessment_signature = ""
        self._last_interaction_signature = ""
        self.last_guidance = self._build_guidance(
            mode_badge="ĐANG KHỞI ĐỘNG BÀI HỌC",
            hint_text=f"Hãy mở Bài {self.lesson.code}. Agent sẽ tự nhận biết khi Excel sẵn sàng.",
            agent_status=SessionStatus.WAITING_FOR_EXCEL,
            event="lesson_started",
        )
        return self.last_guidance

    def pause(self) -> Dict[str, Any]:
        if self.session.status != SessionStatus.PAUSED:
            self.session.status = SessionStatus.PAUSED
            self.session.paused_at = time.monotonic()
        self.last_guidance = self._build_guidance(
            mode_badge="ĐÃ TẠM DỪNG",
            hint_text="Agent đã tạm dừng quan sát bài học. Dữ liệu trong Excel không bị thay đổi.",
            agent_status=SessionStatus.PAUSED,
            event="paused",
        )
        return self.last_guidance

    def resume(self, now: Optional[float] = None) -> Dict[str, Any]:
        now = time.monotonic() if now is None else float(now)
        self.session.status = SessionStatus.OBSERVING
        self.session.paused_at = None
        self.session.last_activity_at = now
        self.session.step_started_at = now
        self.last_guidance = self._build_guidance(
            mode_badge="ĐANG QUAN SÁT REALTIME",
            hint_text=self.current_step.instruction if self.current_step else "Đang tiếp tục bài học.",
            agent_status=SessionStatus.OBSERVING,
            event="resumed",
        )
        return self.last_guidance

    def toggle_pause(self) -> Dict[str, Any]:
        return self.resume() if self.session.status == SessionStatus.PAUSED else self.pause()

    def request_next_hint(self) -> Dict[str, Any]:
        if self.session.status in {SessionStatus.PAUSED, SessionStatus.COMPLETED}:
            return self.last_guidance
        self.session.hint_level = min(3, self.session.hint_level + 1)
        return self.observe(self.last_excel_state, self.last_mouse_state)

    def repeat_instruction(self) -> Dict[str, Any]:
        step = self.current_step
        if not step:
            return self.last_guidance
        guidance = dict(self.last_guidance or {})
        current_instruction = guidance.get("action_instruction") or step.instruction
        guidance["mode_badge"] = "NHẮC LẠI THAO TÁC HIỆN TẠI"
        guidance["hint_text"] = current_instruction
        guidance["event"] = "instruction_repeated"
        self.last_guidance = guidance
        return self.last_guidance

    def acknowledge_step(self, now: Optional[float] = None) -> Dict[str, Any]:
        """Tiến tới thao tác thủ công kế tiếp hoặc sang bước bài học mới."""
        step = self.current_step
        if self.session.status == SessionStatus.OBSERVING and step:
            actions = self._actions_for_step(step)
            index = min(self.session.procedure_action_index, len(actions) - 1)
            current_kind = actions[index].kind if actions else None
            can_confirm_manually = bool(
                current_kind in {
                    ProcedureActionKind.MANUAL,
                    ProcedureActionKind.RIBBON_CONTROL,
                }
                or (
                    current_kind == ProcedureActionKind.RIBBON_TAB
                    and not self.last_excel_state.get("ribbon_available", False)
                )
            )
            if actions and can_confirm_manually:
                self.session.procedure_action_index = min(index + 1, len(actions) - 1)
                self.session.procedure_evidence_action_id = ""
                self.session.procedure_evidence_streak = 0
                now = time.monotonic() if now is None else float(now)
                self.session.last_activity_at = now
                self.session.hint_level = 1
                return self.observe(self.last_excel_state, self.last_mouse_state, now=now)

        if self.session.status != SessionStatus.STEP_CORRECT or not self.lesson:
            return self.last_guidance

        now = time.monotonic() if now is None else float(now)
        if self.session.current_step_index >= len(self.lesson.steps) - 1:
            self.session.status = SessionStatus.COMPLETED
            self.last_guidance = self._completed_guidance()
            return self.last_guidance

        self.session.current_step_index += 1
        self.session.status = SessionStatus.OBSERVING
        self.session.hint_level = 1
        self.session.wrong_attempts = 0
        self.session.procedure_action_index = 0
        self.session.last_progress = 0.0
        self.session.last_signature = ""
        self.session.step_confirmed_at = None
        self.session.procedure_evidence_action_id = ""
        self.session.procedure_evidence_streak = 0
        self.session.procedure_inferred_action_ids = []
        self.session.step_started_at = now
        self.session.last_activity_at = now
        self._last_assessment_signature = ""
        self._last_interaction_signature = ""

        step = self.current_step
        self.last_guidance = self._build_guidance(
            mode_badge="ĐANG QUAN SÁT REALTIME",
            hint_text=step.instruction,
            agent_status=SessionStatus.OBSERVING,
            event="step_advanced",
        )
        return self.last_guidance

    def observe(
        self,
        excel_state: Optional[Dict[str, Any]],
        mouse_state: Optional[Dict[str, Any]] = None,
        now: Optional[float] = None,
    ) -> Dict[str, Any]:
        now = time.monotonic() if now is None else float(now)
        self.last_excel_state = dict(excel_state or {})
        self.last_mouse_state = dict(mouse_state or {})

        if not self.lesson:
            return self.start_lesson("BAI_07", now=now)

        if self.session.status == SessionStatus.PAUSED:
            return self.last_guidance or self.pause()
        if self.session.status == SessionStatus.COMPLETED:
            return self.last_guidance or self._completed_guidance()
        if self.session.status == SessionStatus.STEP_CORRECT:
            step = self.current_step
            confirmed_at = self.session.step_confirmed_at
            if (
                step
                and not step.reflection_question
                and confirmed_at is not None
                and now - confirmed_at >= self.auto_advance_delay
            ):
                return self.acknowledge_step(now=now)
            if self.last_guidance:
                remaining = max(
                    0.0,
                    self.auto_advance_delay - (now - (confirmed_at or now)),
                )
                self.last_guidance["auto_advance_remaining_ms"] = int(round(remaining * 1000))
            return self.last_guidance

        if not self.last_excel_state.get("connected"):
            self.session.status = SessionStatus.WAITING_FOR_EXCEL
            self.last_guidance = self._build_guidance(
                mode_badge="ĐANG CHỜ EXCEL",
                hint_text=f"Mở file Bài {self.lesson.code} để Teaching Agent bắt đầu quan sát.",
                agent_status=SessionStatus.WAITING_FOR_EXCEL,
                event="waiting_for_excel",
            )
            return self.last_guidance

        workbook = self.last_excel_state.get("workbook", "")
        if not self._workbook_matches(workbook):
            self.session.status = SessionStatus.WAITING_FOR_WORKBOOK
            self.last_guidance = self._build_guidance(
                mode_badge="CHƯA ĐÚNG FILE BÀI TẬP",
                hint_text=(
                    f"Agent đang thấy file “{workbook}”. Hãy mở đúng file Bài {self.lesson.code}: "
                    f"{self.lesson.title}."
                ),
                agent_status=SessionStatus.WAITING_FOR_WORKBOOK,
                event="wrong_workbook",
            )
            return self.last_guidance

        step = self.current_step
        active_sheet = self.last_excel_state.get("sheet", "")
        if normalize_text(active_sheet) != normalize_text(step.sheet):
            self.session.status = SessionStatus.WAITING_FOR_SHEET
            self.last_guidance = self._build_guidance(
                mode_badge="CHUYỂN ĐÚNG SHEET",
                hint_text=f"Bước này thực hiện tại sheet “{step.sheet}”. Hãy mở sheet đó để tiếp tục.",
                agent_status=SessionStatus.WAITING_FOR_SHEET,
                event="wrong_sheet",
            )
            return self.last_guidance

        self.session.status = SessionStatus.OBSERVING
        assessment = self._assess_step(step)
        interaction_signature = "|".join(
            (
                assessment.signature,
                str(self.last_excel_state.get("active_cell", "")),
                str(self.last_excel_state.get("selection_address", "")),
                str(self.last_excel_state.get("ribbon_tab_id", "")),
                str(self.last_excel_state.get("number_format_expanded", False)),
                str(self.last_excel_state.get("number_format_focused", False)),
            )
        )

        if interaction_signature != self._last_interaction_signature:
            self.session.last_activity_at = now
            self._last_interaction_signature = interaction_signature

        if assessment.signature != self._last_assessment_signature:
            if self._last_assessment_signature and not assessment.passed:
                if assessment.progress <= self.session.last_progress + 1e-9:
                    self.session.wrong_attempts += 1
                elif assessment.progress > self.session.last_progress:
                    # Có tiến bộ: giảm trợ giúp để học viên tiếp tục tự làm.
                    self.session.hint_level = 1
            self._last_assessment_signature = assessment.signature
            self.session.last_signature = assessment.signature
            self.session.last_progress = assessment.progress

        procedure = self._sync_procedure(step, assessment)

        # Kết quả cuối đúng vẫn chưa đủ: với một quy trình nhiều thao tác, học
        # viên phải đi tới action VERIFY_RESULT theo đúng thứ tự. Điều này ngăn
        # trạng thái có sẵn trong file làm Agent bỏ qua phần chọn vùng/Ribbon.
        if assessment.passed and procedure.get("ready_for_final", True):
            procedure = self._procedure_payload(step, assessment, completed=True)
            if step.id not in self.session.completed_steps:
                self.session.completed_steps.append(step.id)
            if self.session.current_step_index >= len(self.lesson.steps) - 1:
                self.session.status = SessionStatus.COMPLETED
                self.last_guidance = self._completed_guidance(
                    step.success_message,
                    step.reflection_question,
                )
                return self.last_guidance

            self.session.status = SessionStatus.STEP_CORRECT
            self.session.step_confirmed_at = now
            success_text = step.success_message
            if step.reflection_question:
                success_text += f"\n\nCâu hỏi củng cố: {step.reflection_question}"
            self.last_guidance = self._build_guidance(
                mode_badge="HOÀN THÀNH BƯỚC",
                hint_text=success_text,
                agent_status=SessionStatus.STEP_CORRECT,
                is_correct=True,
                teachable_active=bool(step.reflection_question),
                reflection_question=step.reflection_question,
                event="step_correct",
                assessment=assessment,
                procedure=procedure,
            )
            self.last_guidance["auto_advance"] = not bool(step.reflection_question)
            self.last_guidance["auto_advance_delay_ms"] = int(
                round(self.auto_advance_delay * 1000)
            )
            self.last_guidance["auto_advance_remaining_ms"] = int(
                round(self.auto_advance_delay * 1000)
            )
            return self.last_guidance

        elapsed = max(0.0, now - self.session.last_activity_at)
        mouse_idle = float(self.last_mouse_state.get("idle_duration", 0.0) or 0.0)
        hesitation = max(elapsed, mouse_idle if self.last_mouse_state.get("is_inside_excel") else 0.0)
        if hesitation >= self.hesitation_threshold * 2.25 or self.session.wrong_attempts >= 4:
            self.session.hint_level = 3
        elif hesitation >= self.hesitation_threshold or self.session.wrong_attempts >= 2:
            self.session.hint_level = max(2, self.session.hint_level)

        target_range = procedure["action_target_range"] or step.target_range
        target_rect = None
        if target_range:
            # Khi học viên đã chọn đúng, dùng chính khung Selection mà Excel vừa
            # đo. Nếu chưa chọn đúng, đo trực tiếp range đích để chỉ dẫn.
            if (
                procedure["selection_is_exact"]
                and self._selection_matches(target_range)
                and self.last_excel_state.get("selection_rect")
            ):
                target_rect = tuple(self.last_excel_state["selection_rect"])
            else:
                target_rect = self._resolve_rect(target_range, step.sheet)

        hint_index = min(2, max(0, self.session.hint_level - 1))
        hint_text = procedure["action_instruction"]
        if procedure["verification_message"]:
            hint_text = f"{procedure['verification_message']}\n\n{hint_text}"
        if self.session.hint_level > 1:
            hint_text = f"{hint_text}\n\nGợi ý thêm: {step.hints[hint_index]}"

        mode = f"QUY TRÌNH · THAO TÁC {procedure['action_position']}"
        self.last_guidance = self._build_guidance(
            mode_badge=mode,
            hint_text=hint_text,
            agent_status=SessionStatus.OBSERVING,
            target_rect=target_rect,
            event="observing",
            assessment=assessment,
            procedure=procedure,
            display_target_range=target_range,
        )
        return self.last_guidance

    def _workbook_matches(self, workbook_name: str) -> bool:
        normalized = normalize_text(workbook_name)
        return any(normalize_text(token) in normalized for token in self.lesson.workbook_tokens)

    def _actions_for_step(self, step: LessonStep) -> Tuple[ProcedureAction, ...]:
        """Trả quy trình khai báo hoặc bọc bước cũ thành chọn → thực hiện."""
        if step.procedure_actions:
            return step.procedure_actions
        return (
            ProcedureAction(
                id=f"{step.id}_select",
                title=f"Chọn chính xác {step.target_range}",
                instruction=(
                    f"Chọn đúng ô hoặc vùng {step.target_range}. "
                    "Gia sư sẽ đối chiếu địa chỉ vùng chọn theo thời gian thực."
                ),
                kind=ProcedureActionKind.SELECT_RANGE,
                target_range=step.target_range,
            ),
            ProcedureAction(
                id=f"{step.id}_result",
                title=step.title,
                instruction=step.instruction,
                kind=ProcedureActionKind.VERIFY_RESULT,
                target_range=step.target_range,
            ),
        )

    def _sync_procedure(self, step: LessonStep, assessment: StepAssessment) -> Dict[str, Any]:
        """Tự chuyển vi-bước khi Selection hoặc bằng chứng Ribbon đã đúng."""
        actions = self._actions_for_step(step)
        if not actions:
            return {}
        index = min(max(0, self.session.procedure_action_index), len(actions) - 1)
        current = actions[index]
        if (
            current.kind == ProcedureActionKind.SELECT_RANGE
            and self._selection_matches(current.target_range or step.target_range)
            and index < len(actions) - 1
        ):
            index += 1
            self.session.procedure_action_index = index
            self.session.procedure_evidence_action_id = ""
            self.session.procedure_evidence_streak = 0
        elif current.kind in {
            ProcedureActionKind.RIBBON_TAB,
            ProcedureActionKind.RIBBON_CONTROL,
        }:
            # Popup Ribbon có thể mở/đóng giữa hai poll. Khi kết quả cuối đã đúng,
            # cho phép tiếp tục để không làm học viên bị kẹt, nhưng đánh dấu vi-bước
            # là suy ra từ kết quả — không tuyên bố đã quan sát được đúng đường đi.
            result_supersedes_transient_control = bool(
                current.kind == ProcedureActionKind.RIBBON_CONTROL
                and assessment.passed
                and index < len(actions) - 1
                and actions[index + 1].kind == ProcedureActionKind.VERIFY_RESULT
            )
            if result_supersedes_transient_control:
                if current.id not in self.session.procedure_inferred_action_ids:
                    self.session.procedure_inferred_action_ids.append(current.id)
                index += 1
                self.session.procedure_action_index = index
                self.session.procedure_evidence_action_id = ""
                self.session.procedure_evidence_streak = 0
            elif self._ui_action_satisfied(current):
                if self.session.procedure_evidence_action_id == current.id:
                    self.session.procedure_evidence_streak += 1
                else:
                    self.session.procedure_evidence_action_id = current.id
                    self.session.procedure_evidence_streak = 1
                # Tab phải ổn định hai poll liên tiếp; popup/control ngắn nên
                # nhận ngay một mẫu để không bỏ lỡ thao tác của học viên.
                required_streak = (
                    2 if current.kind == ProcedureActionKind.RIBBON_TAB else 1
                )
                if (
                    self.session.procedure_evidence_streak >= required_streak
                    and index < len(actions) - 1
                ):
                    index += 1
                    self.session.procedure_action_index = index
                    self.session.procedure_evidence_action_id = ""
                    self.session.procedure_evidence_streak = 0
            else:
                self.session.procedure_evidence_action_id = current.id
                self.session.procedure_evidence_streak = 0
        return self._procedure_payload(step, assessment)

    def _ui_action_satisfied(self, action: ProcedureAction) -> bool:
        if action.kind == ProcedureActionKind.RIBBON_TAB:
            if not self.last_excel_state.get("ribbon_available", False):
                return False
            expected = str(action.ui_target or "").strip().casefold()
            actual = str(self.last_excel_state.get("ribbon_tab_id", "")).strip().casefold()
            return bool(expected and actual == expected)
        if action.kind == ProcedureActionKind.RIBBON_CONTROL:
            if str(action.ui_target or "").casefold() == "numberformat".casefold():
                return bool(
                    self.last_excel_state.get("number_format_expanded", False)
                    or self.last_excel_state.get("number_format_focused", False)
                )
        return False

    def _procedure_payload(
        self,
        step: LessonStep,
        assessment: Optional[StepAssessment] = None,
        completed: bool = False,
    ) -> Dict[str, Any]:
        actions = self._actions_for_step(step)
        if not actions:
            return {}

        index = len(actions) - 1 if completed else min(
            max(0, self.session.procedure_action_index), len(actions) - 1
        )
        current = actions[index]
        exact_now = self._selection_matches(current.target_range or step.target_range)
        selection_completed = completed or any(
            action.kind == ProcedureActionKind.SELECT_RANGE
            for action in actions[:index]
        ) or (current.kind == ProcedureActionKind.SELECT_RANGE and exact_now)

        if completed:
            verification_state = "correct"
            verification_message = (
                "Gia sư đã xác nhận đúng vùng chọn và kết quả cuối trực tiếp trong Excel."
            )
        elif current.kind == ProcedureActionKind.SELECT_RANGE:
            actual = self._normalize_a1_range(self.last_excel_state.get("selection_address", ""))
            verification_state = "correct" if exact_now else ("wrong" if actual else "waiting")
            verification_message = (
                f"Đã chọn đúng {current.target_range or step.target_range}."
                if exact_now
                else (
                    f"Bạn đang chọn {actual}. Hãy chọn đúng chính xác "
                    f"{current.target_range or step.target_range}, không thừa ô."
                    if actual
                    else f"Đang chờ bạn chọn {current.target_range or step.target_range}."
                )
            )
        elif current.kind == ProcedureActionKind.RIBBON_TAB:
            ribbon_available = bool(self.last_excel_state.get("ribbon_available", False))
            detected = self._ui_action_satisfied(current)
            verification_state = "correct" if detected else "waiting"
            if detected:
                verification_message = "Đã nhận diện thẻ Home; đang xác nhận trạng thái ổn định."
            elif ribbon_available:
                verification_message = "Đang chờ bạn mở đúng thẻ Home trên Ribbon."
            else:
                verification_message = (
                    "Chưa đọc được Ribbon. Hãy mở Home rồi dùng nút xác nhận bên dưới."
                )
        elif current.kind == ProcedureActionKind.RIBBON_CONTROL:
            ribbon_available = bool(self.last_excel_state.get("ribbon_available", False))
            detected = self._ui_action_satisfied(current)
            verification_state = "correct" if detected else "waiting"
            if detected:
                verification_message = "Đã nhận diện hoạt động tại control Number Format."
            elif ribbon_available:
                verification_message = "Đang chờ bạn mở danh sách Number Format trong nhóm Number."
            else:
                verification_message = (
                    "Chưa đọc được control Ribbon. Hãy mở Number Format rồi dùng nút xác nhận."
                )
        elif current.kind == ProcedureActionKind.MANUAL:
            verification_state = "waiting"
            verification_message = (
                "Vùng ô đã được chọn đúng. Thực hiện thao tác trên Ribbon rồi bấm “Bước tiếp theo”."
            )
        else:
            status_code = assessment.status_code if assessment else ""
            verification_state = (
                "wrong"
                if status_code not in {"", "empty", "in_progress", "partial_format"}
                else "waiting"
            )
            verification_message = (
                assessment.feedback
                if assessment and assessment.feedback
                else "Gia sư đang kiểm tra kết quả trực tiếp trong Excel."
            )

        action_rows = []
        for action_index, action in enumerate(actions):
            if action.id in self.session.procedure_inferred_action_ids:
                status = "inferred"
            elif completed or action_index < index:
                status = "done"
            elif action_index == index:
                status = "current"
            else:
                status = "pending"
            action_rows.append(
                {
                    "id": action.id,
                    "number": action_index + 1,
                    "title": action.title,
                    "instruction": action.instruction,
                    "kind": action.kind.value,
                    "target_range": action.target_range or step.target_range,
                    "ui_target": action.ui_target,
                    "status": status,
                }
            )

        fractional = 1.0 if completed else 0.0
        if not completed and current.kind == ProcedureActionKind.VERIFY_RESULT and assessment:
            fractional = max(0.0, min(1.0, float(assessment.progress)))
        progress = 100.0 if completed else ((index + fractional) / len(actions) * 100.0)

        return {
            "procedure_active": True,
            "procedure_actions": action_rows,
            "action_id": current.id,
            "action_number": index + 1,
            "total_actions": len(actions),
            "action_position": f"{index + 1}/{len(actions)}",
            "action_title": current.title,
            "action_instruction": current.instruction,
            "action_kind": current.kind.value,
            "action_target_range": current.target_range or step.target_range,
            "action_ui_target": current.ui_target,
            "verification_state": verification_state,
            "verification_message": verification_message,
            "next_action_preview": actions[index + 1].title if index + 1 < len(actions) else "",
            "selection_is_exact": bool(selection_completed),
            "can_advance_action": (
                not completed
                and (
                    current.kind in {
                        ProcedureActionKind.MANUAL,
                        ProcedureActionKind.RIBBON_CONTROL,
                    }
                    or (
                        current.kind == ProcedureActionKind.RIBBON_TAB
                        and not self.last_excel_state.get("ribbon_available", False)
                    )
                )
            ),
            "ready_for_final": bool(
                completed
                or (
                    index == len(actions) - 1
                    and current.kind == ProcedureActionKind.VERIFY_RESULT
                )
            ),
            "step_progress_percent": round(progress, 1),
        }

    def _selection_matches(self, target_range: str) -> bool:
        if int(self.last_excel_state.get("selection_area_count", 1) or 1) != 1:
            return False
        expected = self._normalize_a1_range(target_range)
        actual = self._normalize_a1_range(
            self.last_excel_state.get("selection_address", "")
        )
        return bool(expected and actual and expected == actual)

    @classmethod
    def _normalize_a1_range(cls, address: str) -> str:
        """Chuẩn hóa tuyệt đối một vùng A1; không chấp nhận vùng gần đúng."""
        text = str(address or "").strip().upper().replace("$", "")
        if not text or "," in text or ";" in text:
            return ""
        if "!" in text:
            text = text.rsplit("!", 1)[-1]
        parts = text.split(":")
        if len(parts) not in {1, 2}:
            return ""

        def parse_cell(value):
            match = re.fullmatch(r"([A-Z]+)([1-9]\d*)", value.strip())
            if not match:
                return None
            return cls._column_number(match.group(1)), int(match.group(2))

        first = parse_cell(parts[0])
        second = parse_cell(parts[-1])
        if not first or not second:
            return ""
        col1, row1 = first
        col2, row2 = second
        left, right = sorted((col1, col2))
        top, bottom = sorted((row1, row2))

        def column_label(number):
            label = ""
            while number > 0:
                number, remainder = divmod(number - 1, 26)
                label = chr(ord("A") + remainder) + label
            return label

        start = f"{column_label(left)}{top}"
        end = f"{column_label(right)}{bottom}"
        return start if start == end else f"{start}:{end}"

    def _assess_step(self, step: LessonStep) -> StepAssessment:
        target = self._read_range(step.sheet, step.target_range)
        rows, columns = self._range_shape(step.target_range)
        values = self._matrix(target.get("values"), rows, columns)
        formats = self._matrix(target.get("formats"), rows, columns, broadcast_scalar=True)
        signature = repr((values, formats))

        if target.get("error") or (
            target.get("values") is None and target.get("formats") is None
        ):
            return StepAssessment(False, 0.0, "unavailable", "Chưa đọc được vùng mục tiêu từ Excel.", signature)

        if step.check_kind == CheckKind.VALUE_MATRIX:
            expected = self._matrix(step.expected, rows, columns)
            return self._compare_matrices(values, expected, signature, step)

        if step.check_kind == CheckKind.TEXT_FORMAT:
            flat = self._flatten(formats)
            correct = sum(1 for value in flat if str(value or "").strip() == "@")
            progress = correct / max(1, len(flat))
            passed = correct == len(flat) and bool(flat)
            feedback = ""
            code = "in_progress"
            if not passed and correct:
                code = "partial_format"
                feedback = f"Đã có {correct}/{len(flat)} ô ở định dạng Text; vẫn còn ô chưa được đổi."
            elif not passed:
                code = "wrong_format"
                feedback = "Vùng này vẫn đang ở định dạng General hoặc một định dạng khác Text."
            return StepAssessment(passed, progress, code, feedback, signature)

        if step.check_kind == CheckKind.MATCH_SOURCE:
            source = self._read_range(step.source_sheet or step.sheet, step.source_range)
            source_rows, source_columns = self._range_shape(step.source_range)
            expected = self._matrix(source.get("values"), source_rows, source_columns)
            assessment = self._compare_matrices(values, expected, signature + repr(expected), step)
            if not assessment.passed and self._has_lost_leading_zero(values, expected):
                assessment.status_code = "leading_zero_lost"
                assessment.feedback = "Có dữ liệu đã mất số 0 ở đầu. Hãy kiểm tra định dạng Text trước khi nhập lại."
            return assessment

        if step.check_kind == CheckKind.DEMONSTRATE_LEADING_ZERO_LOSS:
            source = self._read_range(step.source_sheet or step.sheet, step.source_range)
            original = self._matrix(source.get("values"), 1, 1)[0][0]
            actual = values[0][0]
            if self._is_empty(actual):
                return StepAssessment(False, 0.0, "empty", "", signature + repr(original))
            original_text = str(original or "").strip()
            actual_text = self._number_to_text(actual)
            lost = original_text.startswith("0") and not actual_text.startswith("0")
            if lost:
                return StepAssessment(True, 1.0, "observed_zero_loss", "", signature + repr(original))
            return StepAssessment(
                False,
                0.5,
                "zero_preserved",
                "Số 0 vẫn còn, nên hiện tượng mất số 0 chưa xuất hiện. Hãy bảo đảm E7 vẫn ở General và nhập trực tiếp.",
                signature + repr(original),
            )

        if step.check_kind == CheckKind.DECIMAL_SEPARATOR_TEST:
            nonempty = [[not self._is_empty(value) for value in row] for row in values]
            filled = sum(1 for row in nonempty for item in row if item)
            total = rows * columns
            numeric_rows = []
            for row in values:
                numeric_rows.append(any(self._is_number(value) for value in row))
            passed = filled == total and all(numeric_rows)
            if filled < total:
                return StepAssessment(False, filled / max(1, total), "in_progress", "", signature)
            if not all(numeric_rows):
                return StepAssessment(
                    False,
                    0.8,
                    "decimal_not_recognized",
                    "Có dòng mà cả hai cách nhập đều chưa được Excel nhận là Number.",
                    signature,
                )
            return StepAssessment(True, 1.0, "decimal_test_complete", "", signature)

        if step.check_kind == CheckKind.DATE_VALUES:
            expected_dates = list(step.expected or [])
            flat_values = self._flatten(values)
            flat_formats = self._flatten(formats)
            matches = 0
            for index, value in enumerate(flat_values):
                actual_date = self._date_tuple(value, flat_formats[index] if index < len(flat_formats) else "")
                if index < len(expected_dates) and actual_date == tuple(expected_dates[index]):
                    matches += 1
            total = max(1, len(expected_dates))
            passed = matches == total
            feedback = "" if passed or matches == 0 else f"Đã có {matches}/{total} ngày được Excel nhận đúng."
            code = "date_complete" if passed else ("in_progress" if matches else "invalid_date")
            if code == "invalid_date" and any(not self._is_empty(v) for v in flat_values):
                feedback = "Excel chưa nhận đúng các giá trị này là ngày tháng hợp lệ."
            return StepAssessment(passed, matches / total, code, feedback, signature)

        return StepAssessment(False, 0.0, "unsupported", "Tiêu chí bước này chưa được hỗ trợ.", signature)

    def _compare_matrices(
        self,
        actual: Sequence[Sequence[Any]],
        expected: Sequence[Sequence[Any]],
        signature: str,
        step: LessonStep,
    ) -> StepAssessment:
        actual_flat = self._flatten(actual)
        expected_flat = self._flatten(expected)
        comparisons = [
            self._values_equal(actual_flat[index] if index < len(actual_flat) else None, expected_value)
            for index, expected_value in enumerate(expected_flat)
        ]
        correct = sum(1 for item in comparisons if item)
        total = max(1, len(expected_flat))
        passed = bool(expected_flat) and correct == len(expected_flat)
        nonempty = sum(1 for value in actual_flat if not self._is_empty(value))

        if passed:
            return StepAssessment(True, 1.0, "correct", "", signature)
        if nonempty == 0:
            return StepAssessment(False, 0.0, "empty", "", signature)

        code = "in_progress" if nonempty < len(expected_flat) else "incorrect_value"
        feedback = ""
        if len(expected_flat) == 1:
            actual_text = str(actual_flat[0] or "").strip().upper()
            expected_text = str(expected_flat[0] or "").strip().upper()
            if actual_text == expected_text[::-1] and actual_text != expected_text:
                code = "reversed_address"
                feedback = step.error_messages.get(
                    "reversed_address",
                    "Thứ tự chữ và số đang bị đảo ngược.",
                )
        if not feedback and code == "incorrect_value":
            feedback = f"Có {correct}/{len(expected_flat)} ô đúng; hãy đối chiếu lại các ô còn lại."
        elif not feedback and code == "in_progress" and correct:
            feedback = f"Bạn đã điền đúng {correct}/{len(expected_flat)} ô."
        return StepAssessment(False, correct / total, code, feedback, signature)

    def _read_range(self, sheet: str, address: str) -> Dict[str, Any]:
        try:
            result = self.range_reader(sheet, address)
            return dict(result or {})
        except Exception as exc:
            return {"values": None, "formats": None, "error": str(exc)}

    def _resolve_rect(self, address: str, sheet: str) -> Optional[Tuple[int, int, int, int]]:
        try:
            result = self.rect_resolver(address, sheet)
            if isinstance(result, dict):
                if not result.get("success"):
                    return None
                return (
                    int(result["x"]),
                    int(result["y"]),
                    int(result["width"]),
                    int(result["height"]),
                )
            if result and len(result) == 4:
                return tuple(int(value) for value in result)
        except Exception:
            pass
        return None

    def _build_guidance(
        self,
        *,
        mode_badge: str,
        hint_text: str,
        agent_status: SessionStatus,
        target_rect=None,
        is_correct=False,
        teachable_active=False,
        reflection_question="",
        event="",
        assessment: Optional[StepAssessment] = None,
        procedure: Optional[Dict[str, Any]] = None,
        display_target_range: Optional[str] = None,
    ) -> Dict[str, Any]:
        step = self.current_step
        total = len(self.lesson.steps) if self.lesson else 0
        index = self.session.current_step_index if total else 0
        current_progress = assessment.progress if assessment else self.session.last_progress
        completed = len(self.session.completed_steps)
        progress_percent = 100.0 if agent_status == SessionStatus.COMPLETED else (
            ((index + max(0.0, min(1.0, current_progress))) / total * 100.0) if total else 0.0
        )
        target_range = display_target_range or (step.target_range if step else "")
        procedure = dict(procedure or {})
        guidance = {
            "lesson_id": self.lesson.id if self.lesson else "",
            "lesson_title": self.lesson.title if self.lesson else "",
            "agent_status": agent_status.value,
            "mode_badge": mode_badge,
            "hint_level": self.session.hint_level,
            "step_id": step.id if step else "",
            "step_title": step.title if step else "",
            "instruction": step.instruction if step else "",
            "hint_text": hint_text,
            "is_correct": bool(is_correct),
            "error_type": assessment.status_code if assessment else None,
            "target_cell": target_range,
            "target_range": target_range,
            "target_rect": target_rect,
            "badge_text": (
                f"BƯỚC {procedure.get('action_position')} · {procedure.get('action_title')}"
                if target_rect and procedure.get("action_title")
                else (f"THAO TÁC TẠI: {target_range}" if target_rect and target_range else "")
            ),
            "teachable_active": bool(teachable_active),
            "reflection_question": reflection_question,
            "step_number": index + 1 if total else 0,
            "total_steps": total,
            "step_position": f"Bước {index + 1}/{total}" if total else "",
            "progress_percent": round(progress_percent, 1),
            "completed_steps": completed,
            "wrong_attempts": self.session.wrong_attempts,
            "event": event,
            "is_paused": agent_status == SessionStatus.PAUSED,
            "can_request_hint": agent_status == SessionStatus.OBSERVING and self.session.hint_level < 3,
            "can_continue": agent_status == SessionStatus.STEP_CORRECT,
        }
        guidance.update(
            {
                "procedure_active": False,
                "procedure_actions": [],
                "action_id": "",
                "action_number": 0,
                "total_actions": 0,
                "action_position": "",
                "action_title": "",
                "action_instruction": "",
                "action_kind": "",
                "action_target_range": "",
                "verification_state": "",
                "verification_message": "",
                "next_action_preview": "",
                "selection_is_exact": False,
                "can_advance_action": False,
                "ready_for_final": False,
                "step_progress_percent": 0.0,
                "auto_advance": False,
                "auto_advance_delay_ms": 0,
                "auto_advance_remaining_ms": 0,
            }
        )
        guidance.update(procedure)
        return guidance

    def _completed_guidance(
        self,
        final_message: str = "",
        reflection_question: str = "",
    ) -> Dict[str, Any]:
        hint_text = final_message or "Bạn đã hoàn thành toàn bộ bài học. Agent đã kiểm chứng từng bước trực tiếp từ Excel."
        if reflection_question:
            hint_text += f"\n\nCâu hỏi tổng kết: {reflection_question}"
        return self._build_guidance(
            mode_badge="HOÀN THÀNH BÀI HỌC",
            hint_text=hint_text,
            agent_status=SessionStatus.COMPLETED,
            is_correct=True,
            teachable_active=bool(reflection_question),
            reflection_question=reflection_question,
            event="lesson_completed",
        )

    @staticmethod
    def _range_shape(address: str) -> Tuple[int, int]:
        match = re.fullmatch(r"([A-Z]+)(\d+)(?::([A-Z]+)(\d+))?", str(address or "").replace("$", "").upper())
        if not match:
            return 1, 1
        col1, row1, col2, row2 = match.groups()
        col2 = col2 or col1
        row2 = row2 or row1
        return abs(int(row2) - int(row1)) + 1, abs(RealtimeTeachingAgent._column_number(col2) - RealtimeTeachingAgent._column_number(col1)) + 1

    @staticmethod
    def _column_number(label: str) -> int:
        result = 0
        for char in label:
            result = result * 26 + (ord(char) - ord("A") + 1)
        return result

    @staticmethod
    def _matrix(value: Any, rows: int, columns: int, broadcast_scalar: bool = False) -> List[List[Any]]:
        if rows <= 0 or columns <= 0:
            return []
        if isinstance(value, (tuple, list)):
            if value and isinstance(value[0], (tuple, list)):
                matrix = [list(row) for row in value]
            elif rows == 1:
                matrix = [list(value)]
            elif columns == 1:
                matrix = [[item] for item in value]
            else:
                matrix = [list(value)]
        else:
            if broadcast_scalar:
                return [[value for _ in range(columns)] for _ in range(rows)]
            matrix = [[value]]

        normalized = []
        for row_index in range(rows):
            source_row = matrix[row_index] if row_index < len(matrix) else []
            normalized.append([
                source_row[column_index] if column_index < len(source_row) else None
                for column_index in range(columns)
            ])
        return normalized

    @staticmethod
    def _flatten(matrix: Iterable[Iterable[Any]]) -> List[Any]:
        return [value for row in matrix for value in row]

    @staticmethod
    def _is_empty(value: Any) -> bool:
        return value is None or (isinstance(value, str) and not value.strip())

    @staticmethod
    def _is_number(value: Any) -> bool:
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))

    @classmethod
    def _values_equal(cls, actual: Any, expected: Any) -> bool:
        if cls._is_empty(actual) and cls._is_empty(expected):
            return True
        if isinstance(actual, (datetime, date)) or isinstance(expected, (datetime, date)):
            return cls._date_tuple(actual, "") == cls._date_tuple(expected, "")
        if cls._is_number(actual) and cls._is_number(expected):
            return abs(float(actual) - float(expected)) < 1e-9
        return str(actual or "").strip().casefold() == str(expected or "").strip().casefold()

    @staticmethod
    def _number_to_text(value: Any) -> str:
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return str(value or "").strip()

    @classmethod
    def _has_lost_leading_zero(cls, actual, expected) -> bool:
        for actual_value, expected_value in zip(cls._flatten(actual), cls._flatten(expected)):
            expected_text = cls._number_to_text(expected_value)
            actual_text = cls._number_to_text(actual_value)
            if expected_text.startswith("0") and actual_text and not actual_text.startswith("0"):
                return True
        return False

    @staticmethod
    def _date_tuple(value: Any, number_format: str) -> Optional[Tuple[int, int, int]]:
        if isinstance(value, (datetime, date)):
            return value.year, value.month, value.day
        # COM thường trả datetime. Không tự suy đoán số serial nếu định dạng
        # không mang dấu hiệu ngày tháng.
        if isinstance(value, (int, float)):
            fmt = str(number_format or "").lower()
            if any(token in fmt for token in ("yy", "dd", "mm")):
                try:
                    origin = datetime(1899, 12, 30)
                    converted = origin.fromordinal(origin.toordinal() + int(value))
                    return converted.year, converted.month, converted.day
                except Exception:
                    return None
        return None
