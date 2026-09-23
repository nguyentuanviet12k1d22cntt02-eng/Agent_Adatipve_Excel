"""Kiểm thử logic Ribbon observer không cần Excel đang chạy."""

import unittest
from unittest.mock import patch

from src.core.excel_ribbon_observer import (
    ExcelRibbonObserver,
    ROLE_SYSTEM_COMBOBOX,
    ROLE_SYSTEM_PAGETAB,
    ROLE_SYSTEM_PAGETABLIST,
    STATE_SYSTEM_EXPANDED,
    STATE_SYSTEM_FOCUSED,
    STATE_SYSTEM_SELECTED,
)


class Node:
    def __init__(self, name="", role=0, state=0, children=()):
        self.name = name
        self.role = role
        self.state = state
        self.children = list(children)


class FakeRibbonObserver(ExcelRibbonObserver):
    @classmethod
    def _name(cls, accessible):
        return accessible.name

    @classmethod
    def _role(cls, accessible):
        return accessible.role

    @classmethod
    def _state(cls, accessible):
        return accessible.state

    @classmethod
    def _children(cls, accessible):
        yield from accessible.children


class ExcelRibbonObserverTests(unittest.TestCase):
    def test_simple_msaa_child_ids_are_preserved_as_accessible_nodes(self):
        class Parent:
            accChildCount = 1

        class SimpleObserver(ExcelRibbonObserver):
            @staticmethod
            def _invoke(_accessible, member, child_id=0):
                values = {
                    "accChild": None,
                    "accName": "Home",
                    "accRole": ROLE_SYSTEM_PAGETAB,
                    "accState": STATE_SYSTEM_SELECTED,
                }
                return values[member]

        children = list(SimpleObserver._children(Parent()))

        self.assertEqual(len(children), 1)
        self.assertEqual(SimpleObserver._name(children[0]), "Home")
        self.assertEqual(SimpleObserver._role(children[0]), ROLE_SYSTEM_PAGETAB)
        self.assertTrue(
            SimpleObserver._state(children[0]) & STATE_SYSTEM_SELECTED
        )

    def test_switching_excel_hwnd_discards_previous_child_cache(self):
        class Root:
            pass

        root_two = Root()
        tab_list_two = Node("Ribbon Tabs", ROLE_SYSTEM_PAGETABLIST)

        class SwitchingObserver(FakeRibbonObserver):
            @staticmethod
            def _accessible_from_window(_hwnd):
                return root_two

            @classmethod
            def _find_descendant(cls, root, *, role, max_depth):
                return tab_list_two if root is root_two else None

        observer = SwitchingObserver()
        observer._root_hwnd = 1
        observer._root = Root()
        observer._tab_list = Node("Old tabs", ROLE_SYSTEM_PAGETABLIST)
        observer._tabs = [Node("Old Home", ROLE_SYSTEM_PAGETAB)]
        observer._home_tab = observer._tabs[0]

        with (
            patch(
                "src.core.excel_ribbon_observer.win32gui.EnumChildWindows",
                side_effect=lambda _hwnd, callback, extra: callback(99, extra),
            ),
            patch(
                "src.core.excel_ribbon_observer.win32gui.GetClassName",
                return_value="NetUIHWND",
            ),
            patch(
                "src.core.excel_ribbon_observer.win32gui.IsWindowVisible",
                return_value=True,
            ),
        ):
            result = observer._get_ribbon_root(2)

        self.assertIs(result, root_two)
        self.assertEqual(observer._root_hwnd, 2)
        self.assertEqual(observer._tabs, [])
        self.assertIs(observer._tab_list, tab_list_two)

    def test_selected_home_is_detected_even_with_multiple_state_bits(self):
        home = Node(
            "Home",
            ROLE_SYSTEM_PAGETAB,
            STATE_SYSTEM_SELECTED | STATE_SYSTEM_FOCUSED,
        )
        tabs = Node("Ribbon Tabs", ROLE_SYSTEM_PAGETABLIST, children=[home])
        number_format = Node(
            "Number Format",
            ROLE_SYSTEM_COMBOBOX,
            STATE_SYSTEM_EXPANDED | STATE_SYSTEM_FOCUSED,
        )
        root = Node("Ribbon", children=[tabs, number_format])
        observer = FakeRibbonObserver()

        state = observer._read_ribbon_state(root)

        self.assertTrue(state["ribbon_available"])
        self.assertEqual(state["ribbon_tab_id"], "TabHome")
        self.assertEqual(state["ribbon_tab_name"], "Home")
        self.assertTrue(state["number_format_expanded"])
        self.assertTrue(state["number_format_focused"])

    def test_localized_home_label_is_used(self):
        insert = Node("Chèn", ROLE_SYSTEM_PAGETAB, 0)
        home = Node("Trang đầu", ROLE_SYSTEM_PAGETAB, STATE_SYSTEM_SELECTED)
        tabs = Node(
            "Các thẻ Ribbon",
            ROLE_SYSTEM_PAGETABLIST,
            children=[insert, home],
        )
        observer = FakeRibbonObserver()
        observer._home_label = "Trang đầu"

        state = observer._read_ribbon_state(Node("Ribbon", children=[tabs]))

        self.assertEqual(state["ribbon_tab_id"], "TabHome")
        self.assertEqual(state["ribbon_tab_name"], "Trang đầu")

    def test_non_selected_home_does_not_report_tabhome(self):
        home = Node("Home", ROLE_SYSTEM_PAGETAB, 0)
        tabs = Node("Ribbon Tabs", ROLE_SYSTEM_PAGETABLIST, children=[home])
        observer = FakeRibbonObserver()

        state = observer._read_ribbon_state(Node("Ribbon", children=[tabs]))

        # Không đọc được tab selected là trạng thái mơ hồ; observer phải mở
        # fallback thay vì khóa học viên chờ một tín hiệu không chắc chắn.
        self.assertFalse(state["ribbon_available"])
        self.assertEqual(state["ribbon_tab_id"], "")
        self.assertEqual(state["ribbon_tab_name"], "")

    def test_missing_home_control_marks_observer_unavailable_for_fallback(self):
        insert = Node("Insert", ROLE_SYSTEM_PAGETAB, STATE_SYSTEM_SELECTED)
        tabs = Node("Ribbon Tabs", ROLE_SYSTEM_PAGETABLIST, children=[insert])
        observer = FakeRibbonObserver()

        state = observer._read_ribbon_state(Node("Ribbon", children=[tabs]))

        self.assertFalse(state["ribbon_available"])
        self.assertEqual(state["ribbon_tab_name"], "Insert")

    def test_all_stale_tab_wrappers_clear_cache_and_enable_fallback(self):
        stale_home = Node("", ROLE_SYSTEM_PAGETAB, 0)
        tabs = Node("Ribbon Tabs", ROLE_SYSTEM_PAGETABLIST, children=[stale_home])
        observer = FakeRibbonObserver()
        observer._tab_list = tabs
        observer._tabs = [stale_home]
        observer._home_tab = stale_home

        state = observer._read_ribbon_state(Node("Ribbon", children=[tabs]))

        self.assertFalse(state["ribbon_available"])
        self.assertEqual(observer._tabs, [])

    def test_number_format_control_is_resolved_after_switching_to_home(self):
        insert = Node("Insert", ROLE_SYSTEM_PAGETAB, STATE_SYSTEM_SELECTED)
        home = Node("Home", ROLE_SYSTEM_PAGETAB, 0)
        tabs = Node("Ribbon Tabs", ROLE_SYSTEM_PAGETABLIST, children=[insert, home])
        root = Node("Ribbon", children=[tabs])
        observer = FakeRibbonObserver()

        first = observer._read_ribbon_state(root)
        self.assertEqual(first["ribbon_tab_name"], "Insert")
        self.assertIsNone(observer._number_format_control)

        insert.state = 0
        home.state = STATE_SYSTEM_SELECTED
        number_format = Node(
            "Number Format",
            ROLE_SYSTEM_COMBOBOX,
            STATE_SYSTEM_EXPANDED,
        )
        root.children.append(number_format)
        observer._last_control_scan_at = -100.0

        second = observer._read_ribbon_state(root)
        self.assertEqual(second["ribbon_tab_id"], "TabHome")
        self.assertTrue(second["number_format_expanded"])

    def test_transient_label_failure_is_retried(self):
        class CommandBars:
            def __init__(self):
                self.fail = True

            def GetLabelMso(self, control_id):
                if self.fail:
                    raise RuntimeError("Excel busy")
                return "Trang đầu" if control_id == "TabHome" else "Định dạng số"

        app = type("App", (), {})()
        app.CommandBars = CommandBars()

        observer = FakeRibbonObserver()
        observer._refresh_labels(app)
        self.assertFalse(observer._labels_resolved)

        app.CommandBars.fail = False
        observer._last_label_retry_at = -100.0
        observer._refresh_labels(app)
        self.assertTrue(observer._labels_resolved)
        self.assertEqual(observer._home_label, "Trang đầu")
        self.assertEqual(observer._number_format_label, "Định dạng số")


if __name__ == "__main__":
    unittest.main()
