"""Quan sát trạng thái Microsoft Excel Ribbon qua MSAA/oleacc.

Office không công bố tab đang active qua Excel Object Model. Module này chỉ đọc
cây IAccessible sẵn có của Ribbon, không bấm control và không sửa workbook.
"""

from __future__ import annotations

import ctypes
import re
import time
import unicodedata
from collections import deque
from ctypes import wintypes
from typing import Any, Dict, Iterable, Optional

import pythoncom
import pywintypes
import win32com.client
import win32gui


IID_IACCESSIBLE = pywintypes.IID("{618736E0-3C3D-11CF-810C-00AA00389B71}")
OBJID_CLIENT = -4

ROLE_SYSTEM_PAGETAB = 0x25
ROLE_SYSTEM_PAGETABLIST = 0x3C
ROLE_SYSTEM_COMBOBOX = 0x2E

STATE_SYSTEM_SELECTED = 0x2
STATE_SYSTEM_FOCUSED = 0x4
STATE_SYSTEM_EXPANDED = 0x200

_DISPIDS = {
    "accChild": -5002,
    "accName": -5003,
    "accRole": -5006,
    "accState": -5007,
}


class _SimpleAccessibleChild:
    """Đại diện MSAA simple child không có IDispatch riêng."""

    __slots__ = ("parent", "child_id")

    def __init__(self, parent, child_id: int):
        self.parent = parent
        self.child_id = int(child_id)


class ExcelRibbonObserver:
    """Đọc tab Ribbon active và trạng thái Number Format với chi phí nhỏ."""

    def __init__(self):
        self._root_hwnd = 0
        self._root = None
        self._tab_list = None
        self._tabs = []
        self._home_tab = None
        self._number_format_control = None
        self._home_label = "Home"
        self._number_format_label = "Number Format"
        self._labels_resolved = False
        self._home_label_resolved = False
        self._number_label_resolved = False
        self._last_label_retry_at = 0.0
        self._last_control_scan_at = 0.0
        self._control_scan_failures = 0

    def reset(self):
        self._clear_accessibility_cache()
        self._labels_resolved = False
        self._home_label_resolved = False
        self._number_label_resolved = False
        self._last_label_retry_at = 0.0

    def _clear_accessibility_cache(self):
        self._root_hwnd = 0
        self._root = None
        self._tab_list = None
        self._tabs = []
        self._home_tab = None
        self._number_format_control = None
        self._last_control_scan_at = 0.0
        self._control_scan_failures = 0

    def get_state(self, excel_hwnd: int, excel_app=None) -> Dict[str, Any]:
        state = {
            "ribbon_available": False,
            "ribbon_tab_id": "",
            "ribbon_tab_name": "",
            "number_format_expanded": False,
            "number_format_focused": False,
        }
        if not excel_hwnd:
            return state

        self._refresh_labels(excel_app)
        try:
            root = self._get_ribbon_root(int(excel_hwnd))
            if root is None:
                return state
            state.update(self._read_ribbon_state(root))
            return state
        except Exception:
            # Cây Ribbon có thể bị tái tạo khi đổi chế độ hiển thị/tab. Xóa cache
            # để vòng poll sau tự tìm lại, không làm gián đoạn giám sát Excel.
            self._clear_accessibility_cache()
            return state

    def _refresh_labels(self, excel_app):
        if excel_app is None or self._labels_resolved:
            return
        now = time.monotonic()
        if now - self._last_label_retry_at < 1.5:
            return
        self._last_label_retry_at = now
        if not self._home_label_resolved:
            try:
                label = str(excel_app.CommandBars.GetLabelMso("TabHome") or "").strip()
                if label:
                    self._home_label = label
                    self._home_label_resolved = True
            except Exception:
                pass
        if not self._number_label_resolved:
            try:
                label = str(
                    excel_app.CommandBars.GetLabelMso("NumberFormatGallery") or ""
                ).strip()
                if label:
                    self._number_format_label = label
                    self._number_label_resolved = True
            except Exception:
                pass
        # Chỉ cache khi cả hai nhãn thực sự đọc được. Lỗi COM tạm thời sẽ được
        # thử lại ở poll sau thay vì khóa cứng nhãn fallback cho cả phiên.
        self._labels_resolved = (
            self._home_label_resolved and self._number_label_resolved
        )

    def _read_ribbon_state(self, root) -> Dict[str, Any]:
        if self._tab_list is None or not self._tabs:
            self._resolve_controls(root)

        selected_name = ""
        tab_id = ""
        valid_tab_count = 0
        for tab in self._tabs:
            live_name = self._name(tab)
            if not live_name:
                continue
            valid_tab_count += 1
            if self._state(tab) & STATE_SYSTEM_SELECTED:
                selected_name = live_name
                if self._normalize_label(live_name) == self._normalize_label(
                    self._home_label
                ):
                    tab_id = "TabHome"
                break

        # Nếu toàn bộ wrapper tab đã stale, bỏ cache ngay để poll sau dựng lại.
        if self._tabs and valid_tab_count == 0:
            self._clear_accessibility_cache()
            return {
                "ribbon_available": False,
                "ribbon_tab_id": "",
                "ribbon_tab_name": "",
                "number_format_expanded": False,
                "number_format_focused": False,
            }

        # Available chỉ khi observer vừa đọc được danh tính tab đang selected và
        # đã map được control Home. Trạng thái mơ hồ phải mở fallback thủ công.
        ribbon_available = bool(
            self._tab_list is not None
            and self._home_tab is not None
            and selected_name
        )

        if (
            tab_id == "TabHome"
            and self._number_format_control is None
            and time.monotonic() - self._last_control_scan_at
            >= min(30.0, 1.5 * (2 ** min(4, self._control_scan_failures)))
        ):
            self._resolve_number_format_control(root)

        number_format_expanded = False
        number_format_focused = False
        if self._number_format_control is not None:
            if not self._name(self._number_format_control):
                self._number_format_control = None
            else:
                control_state = self._state(self._number_format_control)
                number_format_expanded = bool(control_state & STATE_SYSTEM_EXPANDED)
                number_format_focused = bool(control_state & STATE_SYSTEM_FOCUSED)

        return {
            "ribbon_available": ribbon_available,
            "ribbon_tab_id": tab_id,
            "ribbon_tab_name": selected_name,
            "number_format_expanded": number_format_expanded,
            "number_format_focused": number_format_focused,
        }

    def _resolve_controls(self, root):
        if self._tab_list is None:
            self._tab_list = self._find_descendant(
                root,
                role=ROLE_SYSTEM_PAGETABLIST,
                max_depth=2,
            )
        self._tabs = []
        self._home_tab = None
        if self._tab_list is not None:
            expected = self._normalize_label(self._home_label)
            for tab in self._children(self._tab_list):
                if self._role(tab) != ROLE_SYSTEM_PAGETAB:
                    continue
                self._tabs.append(tab)
                if self._normalize_label(self._name(tab)) == expected:
                    self._home_tab = tab

        self._resolve_number_format_control(root)

    def _resolve_number_format_control(self, root):
        """Tìm lại Number Format có rate-limit để không làm chậm vòng 300 ms."""
        self._last_control_scan_at = time.monotonic()
        self._number_format_control = None
        for control in self._iter_descendants(root, max_depth=5):
            if self._role(control) != ROLE_SYSTEM_COMBOBOX:
                continue
            if self._normalize_label(self._name(control)) == self._normalize_label(
                self._number_format_label
            ):
                self._number_format_control = control
                self._control_scan_failures = 0
                break
        if self._number_format_control is None:
            self._control_scan_failures += 1

    def _get_ribbon_root(self, excel_hwnd: int):
        if self._root_hwnd and self._root_hwnd != excel_hwnd:
            self._clear_accessibility_cache()
        if self._root is not None and self._root_hwnd == excel_hwnd:
            # Dùng role thay vì tên "Ribbon" để không phụ thuộc ngôn ngữ Office.
            if self._role(self._root):
                return self._root
            self._clear_accessibility_cache()

        candidates = []

        def collect(hwnd, _extra):
            try:
                if (
                    win32gui.GetClassName(hwnd) == "NetUIHWND"
                    and win32gui.IsWindowVisible(hwnd)
                ):
                    candidates.append(int(hwnd))
            except Exception:
                pass
            return True

        win32gui.EnumChildWindows(int(excel_hwnd), collect, None)
        for hwnd in candidates:
            accessible = self._accessible_from_window(hwnd)
            if accessible is None:
                continue
            tab_list = self._find_descendant(
                accessible,
                role=ROLE_SYSTEM_PAGETABLIST,
                max_depth=2,
            )
            if tab_list is None:
                continue
            self._root_hwnd = excel_hwnd
            self._root = accessible
            self._tab_list = tab_list
            return accessible
        return None

    @staticmethod
    def _accessible_from_window(hwnd: int):
        pointer = ctypes.c_void_p()
        result = ctypes.oledll.oleacc.AccessibleObjectFromWindow(
            wintypes.HWND(int(hwnd)),
            ctypes.c_long(OBJID_CLIENT),
            bytes(IID_IACCESSIBLE),
            ctypes.byref(pointer),
        )
        if result != 0 or not pointer.value:
            return None
        dispatch = pythoncom.ObjectFromAddress(
            pointer.value,
            pythoncom.IID_IDispatch,
        )
        return win32com.client.Dispatch(dispatch)

    @staticmethod
    def _invoke(accessible, member: str, child_id: int = 0):
        return accessible._oleobj_.InvokeTypes(
            _DISPIDS[member],
            0,
            pythoncom.DISPATCH_PROPERTYGET,
            (pythoncom.VT_VARIANT, 0),
            ((pythoncom.VT_VARIANT, pythoncom.PARAMFLAG_FIN),),
            int(child_id),
        )

    @classmethod
    def _name(cls, accessible) -> str:
        try:
            if isinstance(accessible, _SimpleAccessibleChild):
                value = cls._invoke(
                    accessible.parent,
                    "accName",
                    accessible.child_id,
                )
            else:
                value = cls._invoke(accessible, "accName")
            return str(value or "")
        except Exception:
            return ""

    @classmethod
    def _role(cls, accessible) -> int:
        try:
            if isinstance(accessible, _SimpleAccessibleChild):
                value = cls._invoke(
                    accessible.parent,
                    "accRole",
                    accessible.child_id,
                )
            else:
                value = cls._invoke(accessible, "accRole")
            return int(value or 0)
        except Exception:
            return 0

    @classmethod
    def _state(cls, accessible) -> int:
        try:
            if isinstance(accessible, _SimpleAccessibleChild):
                value = cls._invoke(
                    accessible.parent,
                    "accState",
                    accessible.child_id,
                )
            else:
                value = cls._invoke(accessible, "accState")
            return int(value or 0)
        except Exception:
            return 0

    @classmethod
    def _children(cls, accessible) -> Iterable[Any]:
        if isinstance(accessible, _SimpleAccessibleChild):
            return
        try:
            count = max(0, min(250, int(accessible.accChildCount or 0)))
        except Exception:
            count = 0
        for child_id in range(1, count + 1):
            yielded_object = False
            try:
                child = cls._invoke(accessible, "accChild", child_id)
                if child is not None:
                    yield win32com.client.Dispatch(child)
                    yielded_object = True
            except Exception:
                pass
            if yielded_object:
                continue
            simple = _SimpleAccessibleChild(accessible, child_id)
            if cls._role(simple) or cls._name(simple):
                yield simple

    @classmethod
    def _find_descendant(cls, root, *, role: int, max_depth: int):
        queue = deque([(root, 0)])
        retained = []
        while queue:
            node, depth = queue.popleft()
            retained.append(node)
            if depth > 0 and cls._role(node) == role:
                return node
            if depth >= max_depth:
                continue
            queue.extend((child, depth + 1) for child in cls._children(node))
        return None

    @classmethod
    def _iter_descendants(cls, root, max_depth: int):
        queue = deque([(root, 0)])
        retained = []
        while queue:
            node, depth = queue.popleft()
            retained.append(node)
            if depth > 0:
                yield node
            if depth >= max_depth:
                continue
            queue.extend((child, depth + 1) for child in cls._children(node))

    @staticmethod
    def _normalize_label(value: str) -> str:
        text = unicodedata.normalize("NFKC", str(value or ""))
        text = text.replace("&", "").replace("\u202a", "").replace("\u202c", "")
        text = re.sub(r"\s+", " ", text).strip().casefold()
        return text
