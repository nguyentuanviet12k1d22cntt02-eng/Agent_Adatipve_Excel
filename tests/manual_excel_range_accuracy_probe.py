"""Kiểm tra tích hợp tọa độ Range thật trên Microsoft Excel.

Script mở Bài 08 trong một Excel instance riêng, không sửa dữ liệu và đóng mà
không lưu. Mỗi case chỉ đạt khi bốn góc trong của rectangle trả về đều map đúng
về các ô biên của phần Range đang nhìn thấy.
"""

from __future__ import annotations

import time
import sys
from pathlib import Path

import win32com.client
import win32con
import win32gui

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.excel_monitor import ExcelMonitor


def main() -> int:
    workbook_path = (
        Path(__file__).resolve().parents[1]
        / "bài tập"
        / "Bài 08. Các bước cần thực hiện trước khi nhập dữ liệu 10092026 (1).xlsx"
    )
    app = win32com.client.DispatchEx("Excel.Application")
    app.Visible = True
    app.DisplayAlerts = False
    workbook = None
    failures = []
    try:
        workbook = app.Workbooks.Open(str(workbook_path))
        sheet = workbook.Sheets("1. Thuc_Hanh_Tung_Buoc")
        sheet.Activate()
        # RangeFromPoint phụ thuộc vào cửa sổ worksheet đang thực sự được vẽ.
        # Đưa instance thử nghiệm lên foreground để mô phỏng đúng lúc học viên
        # đang thao tác trong Excel (overlay của ứng dụng không nhận focus).
        win32gui.ShowWindow(int(app.Hwnd), win32con.SW_MAXIMIZE)
        try:
            win32gui.SetForegroundWindow(int(app.Hwnd))
        except Exception:
            # Windows có thể từ chối foreground-stealing từ tiến trình test;
            # ShowWindow + Window.Activate vẫn đủ để workbook được layout.
            app.ActiveWindow.Activate()
        time.sleep(0.75)
        monitor = ExcelMonitor()
        monitor.excel_app = app
        window = app.ActiveWindow

        cases = (
            ("normal", 55, 1, 1, None),
            ("normal", 85, 1, 1, None),
            ("normal", 100, 1, 1, None),
            ("normal", 125, 1, 1, None),
            ("scrolled", 85, 5, 3, None),
            ("scrolled", 125, 7, 5, None),
            ("frozen", 85, 6, 3, "C5"),
            ("frozen", 125, 7, 5, "C5"),
        )
        for mode, zoom, scroll_row, scroll_column, freeze_at in cases:
            window.FreezePanes = False
            window.SplitRow = 0
            window.SplitColumn = 0
            window.Zoom = zoom
            if freeze_at:
                sheet.Range(freeze_at).Select()
                window.FreezePanes = True
            window.ScrollRow = scroll_row
            window.ScrollColumn = scroll_column
            monitor._viewport_cache_key = None
            monitor._viewport_calibration = None
            monitor._exact_rect_cache_key = None
            monitor._exact_rect_cache = None
            time.sleep(0.25)

            target = sheet.Range("F7:F10")
            target.Select()
            rect = monitor.get_cell_rect_by_address("F7:F10", sheet.Name)
            visible = app.Intersect(target, window.VisibleRange)
            valid = bool(rect and visible and monitor._rect_matches_cell(window, visible, rect))
            print(
                {
                    "mode": mode,
                    "zoom": zoom,
                    "scroll_row": scroll_row,
                    "scroll_column": scroll_column,
                    "rect": rect,
                    "four_corners_exact": valid,
                }
            )
            if not valid:
                if visible is None:
                    print({"diagnostic": True, "reason": "target_not_visible"})
                    failures.append((mode, zoom, scroll_row, scroll_column, rect))
                    continue
                anchor_left, anchor_top = monitor._get_view_anchor(window, sheet, visible)
                origin_x = int(window.PointsToScreenPixelsX(int(round(anchor_left))))
                origin_y = int(window.PointsToScreenPixelsY(int(round(anchor_top))))
                dpi = monitor._get_window_dpi(int(app.Hwnd))
                candidate = monitor._excel_points_to_screen_rect(
                    left=float(visible.Left),
                    top=float(visible.Top),
                    width=float(visible.Width),
                    height=float(visible.Height),
                    origin_x=origin_x,
                    origin_y=origin_y,
                    zoom=float(window.Zoom),
                    dpi=dpi,
                    scroll_left=anchor_left,
                    scroll_top=anchor_top,
                )
                print(
                    {
                        "diagnostic": True,
                        "visible": str(visible.Address),
                        "dpi": dpi,
                        "anchor": (anchor_left, anchor_top),
                        "origin": (origin_x, origin_y),
                        "candidate": candidate,
                        "grid_rects": monitor._get_excel_grid_rects(),
                    }
                )
                for grid_rect in monitor._get_excel_grid_rects():
                    calibration = monitor._build_viewport_calibration(
                        window,
                        grid_rect,
                        dpi=dpi,
                        zoom=float(window.Zoom),
                    )
                    calibrated = (
                        monitor._rect_from_calibration(visible, calibration)
                        if calibration
                        else None
                    )
                    print(
                        {
                            "grid": grid_rect,
                            "calibration": calibration,
                            "calibrated": calibrated,
                            "candidate_refined": monitor._refine_range_rect(
                                window, visible, candidate
                            ),
                            "calibrated_refined": (
                                monitor._refine_range_rect(window, visible, calibrated)
                                if calibrated
                                else None
                            ),
                        }
                    )
                failures.append((mode, zoom, scroll_row, scroll_column, rect))

        return 1 if failures else 0
    finally:
        if workbook is not None:
            workbook.Close(SaveChanges=False)
        app.Quit()


if __name__ == "__main__":
    raise SystemExit(main())
