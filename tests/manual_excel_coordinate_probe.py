"""Manual integration probe: Excel scroll + mixed-DPI three-monitor coordinates."""

import json
import os
import sys
import time

import win32com.client
import win32con
import win32gui

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.core.excel_monitor import ExcelMonitor


MONITORS = (
    ("left", -1920, 0, 1920, 1040),
    ("primary", 0, 0, 1920, 1020),
    ("right", 1920, 0, 1366, 728),
)


def main():
    app = win32com.client.DispatchEx("Excel.Application")
    app.Visible = True
    app.DisplayAlerts = False
    workbook = app.Workbooks.Add()
    monitor = ExcelMonitor()
    monitor.excel_app = app
    results = []

    try:
        sheet = workbook.ActiveSheet
        target = sheet.Range("G50")
        target.Select()
        window = app.ActiveWindow
        window.Zoom = 100
        window.ScrollRow = 43
        window.ScrollColumn = 1

        for name, left, top, width, height in MONITORS:
            win32gui.SetWindowPos(
                int(app.Hwnd), 0, left, top, width, height,
                win32con.SWP_NOACTIVATE | win32con.SWP_SHOWWINDOW,
            )
            time.sleep(0.8)
            rect = monitor.get_cell_screen_rect(target)
            hit_address = None
            if rect:
                x, y, w, h = rect
                hit = window.RangeFromPoint(x + w // 2, y + h // 2)
                hit_address = str(hit.Address).replace("$", "") if hit else None
            results.append({
                "monitor": name,
                "window_rect": list(win32gui.GetWindowRect(int(app.Hwnd))),
                "scroll_row": int(window.ScrollRow),
                "target": "G50",
                "rect": rect,
                "range_from_point": hit_address,
                "ok": hit_address == "G50",
            })
        print(json.dumps(results, ensure_ascii=False, indent=2))
        if not all(item["ok"] for item in results):
            raise SystemExit(1)
    finally:
        workbook.Close(False)
        app.Quit()


if __name__ == "__main__":
    main()
