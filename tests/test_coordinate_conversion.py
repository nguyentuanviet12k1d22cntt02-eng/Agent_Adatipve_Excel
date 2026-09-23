"""Regression tests cho quy đổi tọa độ Excel/Win32 sang overlay Qt."""

import ctypes
import unittest
from ctypes import wintypes

from src.core.excel_monitor import ExcelMonitor
from src.gui.overlay_window import OverlayWindow
from test_mcp_interactive import MCPInteractiveTestWindow


class TestCoordinateConversion(unittest.TestCase):
    def test_physical_window_rect_restores_thread_dpi_context(self):
        class Setter:
            def __init__(self):
                self.calls = []

            def __call__(self, context):
                self.calls.append(context.value)
                return 123 if len(self.calls) == 1 else 456

        setter = Setter()

        class User32:
            SetThreadDpiAwarenessContext = setter

        rect = ExcelMonitor._get_physical_window_rect(
            77,
            _user32=User32(),
            _get_rect=lambda _hwnd: (10, 20, 110, 220),
        )

        self.assertEqual(rect, (10, 20, 110, 220))
        self.assertEqual(setter.calls[0], ctypes.c_void_p(-4).value)
        self.assertEqual(setter.calls[1], 123)

    def test_physical_window_rect_restores_context_when_get_rect_raises(self):
        class Setter:
            def __init__(self):
                self.calls = []

            def __call__(self, context):
                self.calls.append(context.value)
                return 321

        setter = Setter()

        class User32:
            SetThreadDpiAwarenessContext = setter

        def fail(_hwnd):
            raise RuntimeError("window disappeared")

        with self.assertRaises(RuntimeError):
            ExcelMonitor._get_physical_window_rect(
                77,
                _user32=User32(),
                _get_rect=fail,
            )
        self.assertEqual(setter.calls[-1], 321)

    def test_physical_window_rect_falls_back_to_per_monitor_conversion(self):
        class Setter:
            def __call__(self, _context):
                return None

        class Converter:
            def __call__(self, _hwnd, point_pointer):
                point = ctypes.cast(
                    point_pointer,
                    ctypes.POINTER(wintypes.POINT),
                ).contents
                point.x = int(point.x * 1.5)
                point.y = int(point.y * 1.5)
                return True

        class User32:
            SetThreadDpiAwarenessContext = Setter()
            LogicalToPhysicalPointForPerMonitorDPI = Converter()

        rect = ExcelMonitor._get_physical_window_rect(
            77,
            _user32=User32(),
            _get_rect=lambda _hwnd: (0, 100, 1280, 658),
        )
        self.assertEqual(rect, (0, 150, 1920, 987))

    def test_state_exposes_whole_selected_range(self):
        class Count:
            def __init__(self, count):
                self.Count = count

        class FakeCell:
            Address = "$D$18"
            Value = ""
            NumberFormat = "General"

        class FakeSelection:
            Address = "$D$18:$O$30"
            Rows = Count(13)
            Columns = Count(12)
            Areas = Count(1)

        class FakeWorkbook:
            Name = "Book1.xlsx"

        class FakeSheet:
            Name = "Sheet1"

        class FakeApp:
            ActiveWorkbook = FakeWorkbook()
            ActiveSheet = FakeSheet()
            ActiveCell = FakeCell()
            Selection = FakeSelection()
            Hwnd = 0

        monitor = ExcelMonitor()
        monitor.excel_app = FakeApp()
        monitor.get_cell_screen_rect = lambda _cell: (100, 200, 45, 20)
        monitor.get_visible_range_screen_rect = lambda _range: (100, 200, 540, 260)

        state = monitor.get_state()

        self.assertEqual(state["cell_clean_address"], "D18")
        self.assertEqual(state["selection_address"], "D18:O30")
        self.assertEqual(state["selection_rect"], (100, 200, 540, 260))
        self.assertEqual(state["selection_rows"], 13)
        self.assertEqual(state["selection_columns"], 12)
        self.assertTrue(state["is_range_selection"])

    def test_excel_points_include_zoom_and_dpi(self):
        # Trường hợp giống ảnh lỗi: Windows 150%, Excel zoom 85%.
        rect = ExcelMonitor._excel_points_to_screen_rect(
            left=253,
            top=154,
            width=70,
            height=24,
            origin_x=37,
            origin_y=435,
            zoom=85,
            dpi=144,
        )
        self.assertEqual(rect, (467, 697, 119, 41))

    def test_excel_points_compensate_scroll_and_frozen_area(self):
        rect = ExcelMonitor._excel_points_to_screen_rect(
            left=500,
            top=600,
            width=60,
            height=15,
            origin_x=40,
            origin_y=200,
            zoom=100,
            dpi=96,
            scroll_left=300,
            scroll_top=450,
        )
        self.assertEqual(rect, (307, 400, 80, 20))

    def test_excel_points_round_transformed_edges_not_size(self):
        rect = ExcelMonitor._excel_points_to_screen_rect(
            left=0.8,
            top=0.8,
            width=1.6,
            height=1.6,
            origin_x=0,
            origin_y=0,
            zoom=75,
            dpi=96,
        )
        # scale = 1; round(left)=1, round(right)=2, nên width chính xác là 1.
        self.assertEqual(rect, (1, 1, 1, 1))

    def test_scroll_anchor_uses_first_visible_row(self):
        class FakeCell:
            Row = 28
            Column = 9

        class FakeRange:
            def __init__(self, left=0, top=0):
                self.Left = left
                self.Top = top

        class FakeSheet:
            def Cells(self, row, column):
                # Row 19 starts at 270 points; column A starts at 0.
                return FakeRange(left=(column - 1) * 70, top=(row - 1) * 15)

        class FakeWindow:
            ScrollRow = 19
            ScrollColumn = 1
            SplitRow = 0
            SplitColumn = 0
            FreezePanes = False

        anchor = ExcelMonitor._get_view_anchor(FakeWindow(), FakeSheet(), FakeCell())
        self.assertEqual(anchor, (0.0, 270.0))

    def test_overlay_scales_all_four_values(self):
        logical = OverlayWindow.physical_to_local_rect(
            (37, 697, 192, 41), dpr=1.5, overlay_origin=(0, 0)
        )
        self.assertEqual(logical, (25, 465, 128, 27))

    def test_overlay_maps_right_and_left_monitors(self):
        right = OverlayWindow.physical_to_local_rect(
            (2500, 300, 100, 30), dpr=1.0, physical_origin=(1920, 0)
        )
        left = OverlayWindow.physical_to_local_rect(
            (-1200, 300, 100, 30), dpr=1.0, physical_origin=(-1920, 0)
        )
        self.assertEqual(right, (580, 300, 100, 30))
        self.assertEqual(left, (720, 300, 100, 30))

    def test_overlay_rounds_both_edges_at_fractional_dpi(self):
        logical = OverlayWindow.physical_to_local_rect(
            (1, 0, 2, 2), dpr=1.25, physical_origin=(0, 0)
        )
        self.assertEqual(logical, (1, 0, 1, 2))
        self.assertEqual(
            logical[0] + logical[2],
            round((1 + 2) / 1.25),
        )

    def test_cell_rect_refuses_inactive_sheet(self):
        class Count:
            Count = 1

        class Cell:
            Rows = Count()
            Columns = Count()

        class Sheet:
            def __init__(self, name):
                self.Name = name

            def Range(self, _address):
                return Cell()

        target = Sheet("Target")
        active = Sheet("Active")

        class Workbook:
            def Sheets(self, name):
                self.last_name = name
                return target

        class App:
            ActiveWorkbook = Workbook()
            ActiveSheet = active

        monitor = ExcelMonitor()
        monitor.excel_app = App()
        self.assertIsNone(monitor.get_cell_rect_by_address("F7:F10", "Target"))

    def test_range_address_uses_visible_range_geometry(self):
        class Count:
            def __init__(self, count):
                self.Count = count

        class Cell:
            Rows = Count(4)
            Columns = Count(1)

        class Sheet:
            Name = "Target"

            def Range(self, _address):
                return Cell()

        sheet = Sheet()

        class Workbook:
            def Sheets(self, _name):
                return sheet

        class App:
            ActiveWorkbook = Workbook()
            ActiveSheet = sheet

        monitor = ExcelMonitor()
        monitor.excel_app = App()
        monitor.get_visible_range_screen_rect = lambda _cell: (10, 20, 30, 80)
        monitor.get_cell_screen_rect = lambda _cell: self.fail(
            "Range nhiều ô phải dùng visible geometry"
        )
        self.assertEqual(
            monitor.get_cell_rect_by_address("F7:F10", "Target"),
            (10, 20, 30, 80),
        )

    def test_rect_verification_checks_all_range_corners(self):
        class Count:
            def __init__(self, count):
                self.Count = count

        class Sheet:
            Name = "Sheet1"

        class Range:
            def __init__(self, row, column, rows=1, columns=1):
                self.Row = row
                self.Column = column
                self.Rows = Count(rows)
                self.Columns = Count(columns)
                self.Worksheet = Sheet()

        target = Range(7, 6, rows=4, columns=1)

        class Window:
            def RangeFromPoint(self, x, y):
                if not (100 <= x < 140 and 200 <= y < 280):
                    return None
                return Range(7 + (y - 200) // 20, 6)

        self.assertTrue(
            ExcelMonitor._rect_matches_cell(Window(), target, (100, 200, 40, 80))
        )
        self.assertFalse(
            ExcelMonitor._rect_matches_cell(Window(), target, (100, 200, 40, 60))
        )

    def test_range_from_point_refines_approximate_rect_to_exact_edges(self):
        class Count:
            def __init__(self, count):
                self.Count = count

        class Sheet:
            Name = "Sheet1"

        class Parent:
            Name = "Book.xlsx"

        Sheet.Parent = Parent()

        class Range:
            Address = "$F$7:$F$10"
            Row = 7
            Column = 6
            Rows = Count(4)
            Columns = Count(1)
            Worksheet = Sheet()
            Left = 350.0
            Top = 90.0
            Width = 30.0
            Height = 60.0

        target = Range()

        class Hit:
            Column = 6
            Columns = Count(1)
            Rows = Count(1)
            Worksheet = Sheet()

            def __init__(self, row):
                self.Row = row

        class Window:
            Hwnd = 77
            ScrollRow = 1
            ScrollColumn = 1
            SplitRow = 0
            SplitColumn = 0
            FreezePanes = False
            Zoom = 100

            def RangeFromPoint(self, x, y):
                if 100 <= x < 140 and 200 <= y < 280:
                    return Hit(7 + (y - 200) // 20)
                return None

        monitor = ExcelMonitor()
        monitor._get_excel_grid_rects = lambda: [(0, 100, 500, 500)]
        refined = monitor._refine_range_rect(
            Window(), target, (102, 203, 35, 72)
        )
        self.assertEqual(refined, (100, 200, 40, 80))

    def test_union_rects_covers_whole_visible_selection(self):
        rect = ExcelMonitor._union_rects(
            [(100, 200, 80, 30), (180, 200, 120, 30), (100, 230, 200, 45)]
        )
        self.assertEqual(rect, (100, 200, 200, 75))

    def test_range_from_point_measures_exact_cell_after_scroll(self):
        class Count:
            Count = 1

        class FakeRange:
            Row = 50
            Column = 7
            Rows = Count()
            Columns = Count()

        reference = FakeRange()

        class FakeWindow:
            def RangeFromPoint(self, x, y):
                if 100 <= x < 200 and 300 <= y < 330:
                    return reference
                return None

        bounds = ExcelMonitor._measure_range_bounds(
            FakeWindow(), reference, 150, 315, (40, 200, 500, 600)
        )
        self.assertEqual(bounds, (100, 300, 200, 330))

    def test_new_excel_selection_releases_typed_target(self):
        self.assertTrue(
            MCPInteractiveTestWindow.should_release_pinned_target("I5", "I28", "I5")
        )
        self.assertFalse(
            MCPInteractiveTestWindow.should_release_pinned_target("I5", "I5", "I5")
        )
        # Việc nhập C8 trong form không tự mất ghim nếu ActiveCell vẫn là A1.
        self.assertFalse(
            MCPInteractiveTestWindow.should_release_pinned_target("A1", "A1", "C8")
        )
        # Kéo chọn một vùng có thể giữ nguyên ActiveCell neo, nhưng vẫn phải bỏ
        # ghim ô đơn để khung đỏ chuyển sang bao toàn bộ Selection.
        self.assertTrue(
            MCPInteractiveTestWindow.should_release_pinned_target(
                "D18", "D18", "D18", "D18", "D18:O30"
            )
        )


if __name__ == "__main__":
    unittest.main()
