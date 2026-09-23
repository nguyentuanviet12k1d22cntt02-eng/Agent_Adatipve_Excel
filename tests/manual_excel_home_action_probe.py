"""Probe end-to-end: Excel Ribbon thật tự chuyển thao tác Home 2/4 → 3/4."""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.excel_monitor import ExcelMonitor
from src.core.lesson_models import SessionStatus
from src.core.realtime_teaching_agent import RealtimeTeachingAgent


def main() -> int:
    monitor = ExcelMonitor()
    if not monitor.connect():
        print({"connected": False})
        return 1

    # Cố định assessment ở General để probe chỉ đo tín hiệu Home, không phụ
    # thuộc nội dung hiện tại của workbook và tuyệt đối không ghi dữ liệu.
    def read_range(_sheet, address):
        if address == "F7:F10":
            return {
                "values": ((None,), (None,), (None,), (None,)),
                "formats": (
                    ("General",),
                    ("General",),
                    ("General",),
                    ("General",),
                ),
            }
        return {"values": None, "formats": None}

    agent = RealtimeTeachingAgent(read_range, lambda _address, _sheet: None)
    agent.start_lesson("BAI_08")
    agent.session.current_step_index = 1
    agent.session.status = SessionStatus.OBSERVING
    agent.session.procedure_action_index = 1

    first = agent.observe(monitor.get_state())
    time.sleep(0.35)
    second = agent.observe(monitor.get_state())
    passed = bool(
        first.get("action_position") == "2/4"
        and first.get("verification_state") == "correct"
        and second.get("action_position") == "3/4"
    )
    print(
        {
            "passed": passed,
            "first_action": first.get("action_position"),
            "first_verification": first.get("verification_state"),
            "second_action": second.get("action_position"),
            "live_tab": monitor.get_state().get("ribbon_tab_name"),
        }
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
