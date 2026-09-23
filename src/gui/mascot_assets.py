"""Ánh xạ trạng thái Teaching Agent sang pose và màu giao diện."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True)
class MascotStyle:
    key: str
    asset_name: str
    accent: str
    title: str


MASCOT_STYLES: Mapping[str, MascotStyle] = {
    "welcome": MascotStyle("welcome", "pose-welcome.png", "#3B82F6", "CÙNG BẮT ĐẦU"),
    "thinking": MascotStyle("thinking", "pose-thinking.png", "#8B5CF6", "MÌNH CÙNG SUY NGHĨ"),
    "teaching": MascotStyle("teaching", "pose-teaching.png", "#EF4444", "THAO TÁC Ở ĐÂY"),
    "success": MascotStyle("success", "pose-success.png", "#22C55E", "LÀM TỐT LẮM"),
    "warning": MascotStyle("warning", "pose-warning.png", "#F59E0B", "MÌNH KIỂM TRA LẠI"),
}

NON_ERROR_ASSESSMENTS = {None, "", "empty", "in_progress", "partial_format"}


def visual_state_for_guidance(info: Mapping) -> str:
    """Chọn pose theo ý nghĩa sư phạm, không chỉ theo màu/mức gợi ý."""
    status = str(info.get("agent_status", "idle"))
    event = str(info.get("event", ""))

    if bool(info.get("is_correct")) or status in {"step_correct", "completed"}:
        return "success"
    if status in {"waiting_for_workbook", "waiting_for_sheet"}:
        return "warning"
    if info.get("error_type") not in NON_ERROR_ASSESSMENTS:
        return "warning"
    if status in {"idle", "waiting_for_excel"} or event == "lesson_started":
        return "welcome"
    if status == "paused" or bool(info.get("teachable_active")):
        return "thinking"

    level = int(info.get("hint_level", 1) or 1)
    return "thinking" if level <= 1 else "teaching"


def mascot_style(state: str) -> MascotStyle:
    return MASCOT_STYLES.get(state, MASCOT_STYLES["teaching"])


def mascot_asset_path(state: str) -> Path:
    project_root = Path(__file__).resolve().parents[2]
    return project_root / "assets" / "mascot" / mascot_style(state).asset_name
