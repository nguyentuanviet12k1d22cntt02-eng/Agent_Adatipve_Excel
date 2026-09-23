"""Kiểm tra tích hợp observer với Ribbon thật của Excel.

Script chỉ đổi tab Ribbon Insert → Home rồi trả về Home; không sửa workbook.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.excel_monitor import ExcelMonitor
from src.core.excel_ribbon_observer import ExcelRibbonObserver


def main() -> int:
    monitor = ExcelMonitor()
    if not monitor.connect():
        print({"connected": False})
        return 1

    app = monitor.excel_app
    observer = ExcelRibbonObserver()
    hwnd = int(app.Hwnd)
    cases = []

    def activate_tab(id_mso: str) -> bool:
        try:
            label = str(app.CommandBars.GetLabelMso(id_mso) or "").strip()
        except Exception:
            return False
        # Dựng/cache danh sách tab trước, sau đó dùng chính default action của
        # IAccessible. Đây là cách độc lập vị trí màn hình và DPI.
        observer.get_state(hwnd, app)
        expected = observer._normalize_label(label)
        for tab in observer._tabs:
            if observer._normalize_label(observer._name(tab)) != expected:
                continue
            try:
                tab.accDoDefaultAction(0)
                return True
            except Exception:
                return False
        return False

    try:
        if not activate_tab("TabInsert"):
            print({"case": "activate_insert", "passed": False})
            return 1
        time.sleep(0.35)
        insert_state = observer.get_state(hwnd, app)
        cases.append(
            (
                "insert",
                bool(
                    insert_state["ribbon_available"]
                    and insert_state["ribbon_tab_name"] == "Insert"
                    and insert_state["ribbon_tab_id"] == ""
                ),
                insert_state,
            )
        )

        if not activate_tab("TabHome"):
            print({"case": "activate_home", "passed": False})
            return 1
        time.sleep(0.35)
        home_state = observer.get_state(hwnd, app)
        cases.append(
            (
                "home",
                bool(
                    home_state["ribbon_available"]
                    and home_state["ribbon_tab_id"] == "TabHome"
                ),
                home_state,
            )
        )
    finally:
        # Luôn trả UI về đúng tab người học đang cần.
        try:
            activate_tab("TabHome")
        except Exception:
            pass

    for name, passed, state in cases:
        print({"case": name, "passed": passed, "state": state})
    return 0 if cases and all(passed for _, passed, _ in cases) else 1


if __name__ == "__main__":
    raise SystemExit(main())
