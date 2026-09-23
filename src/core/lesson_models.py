"""Các mô hình dữ liệu cho hệ thống Gia sư Excel theo hướng agentic."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional, Tuple


class CheckKind(str, Enum):
    """Kiểu tiêu chí mà Teaching Agent có thể tự kiểm chứng."""

    VALUE_MATRIX = "value_matrix"
    TEXT_FORMAT = "text_format"
    MATCH_SOURCE = "match_source"
    DEMONSTRATE_LEADING_ZERO_LOSS = "demonstrate_leading_zero_loss"
    DECIMAL_SEPARATOR_TEST = "decimal_separator_test"
    DATE_VALUES = "date_values"


class ProcedureActionKind(str, Enum):
    """Cách một vi-bước trong quy trình được xác nhận."""

    SELECT_RANGE = "select_range"
    MANUAL = "manual"
    RIBBON_TAB = "ribbon_tab"
    RIBBON_CONTROL = "ribbon_control"
    VERIFY_RESULT = "verify_result"


@dataclass(frozen=True)
class ProcedureAction:
    """Một thao tác nhỏ, có thứ tự, hiển thị trực tiếp cho học viên."""

    id: str
    title: str
    instruction: str
    kind: ProcedureActionKind
    target_range: str = ""
    ui_target: str = ""


class SessionStatus(str, Enum):
    IDLE = "idle"
    WAITING_FOR_EXCEL = "waiting_for_excel"
    WAITING_FOR_WORKBOOK = "waiting_for_workbook"
    WAITING_FOR_SHEET = "waiting_for_sheet"
    OBSERVING = "observing"
    STEP_CORRECT = "step_correct"
    PAUSED = "paused"
    COMPLETED = "completed"


@dataclass(frozen=True)
class LessonStep:
    id: str
    title: str
    instruction: str
    sheet: str
    target_range: str
    check_kind: CheckKind
    hints: Tuple[str, str, str]
    success_message: str
    expected: Any = None
    source_sheet: str = ""
    source_range: str = ""
    reflection_question: str = ""
    error_messages: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    procedure_actions: Tuple[ProcedureAction, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class LessonPlan:
    id: str
    code: str
    title: str
    workbook_tokens: Tuple[str, ...]
    steps: Tuple[LessonStep, ...]


@dataclass
class StepAssessment:
    passed: bool
    progress: float
    status_code: str
    feedback: str
    signature: str
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TeachingSession:
    lesson_id: str = ""
    current_step_index: int = 0
    status: SessionStatus = SessionStatus.IDLE
    hint_level: int = 1
    wrong_attempts: int = 0
    procedure_action_index: int = 0
    completed_steps: list = field(default_factory=list)
    started_at: float = 0.0
    step_started_at: float = 0.0
    last_activity_at: float = 0.0
    last_signature: str = ""
    last_progress: float = 0.0
    paused_at: Optional[float] = None
    step_confirmed_at: Optional[float] = None
    procedure_evidence_action_id: str = ""
    procedure_evidence_streak: int = 0
    procedure_inferred_action_ids: list = field(default_factory=list)
