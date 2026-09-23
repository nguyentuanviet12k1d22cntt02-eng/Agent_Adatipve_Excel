"""Chẩn đoán cây Microsoft Active Accessibility của Excel Ribbon.

Chỉ đọc trạng thái UI; không bấm nút hay thay đổi workbook.
"""

from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes
from pathlib import Path

import pythoncom
import pywintypes
import win32com.client
import win32gui

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.excel_monitor import ExcelMonitor


IID_IACCESSIBLE = pywintypes.IID("{618736E0-3C3D-11CF-810C-00AA00389B71}")
OBJID_CLIENT = -4


def accessible_from_window(hwnd: int):
    pointer = ctypes.c_void_p()
    result = ctypes.oledll.oleacc.AccessibleObjectFromWindow(
        wintypes.HWND(int(hwnd)),
        ctypes.c_long(OBJID_CLIENT),
        bytes(IID_IACCESSIBLE),
        ctypes.byref(pointer),
    )
    if result != 0 or not pointer.value:
        return None
    dispatch = pythoncom.ObjectFromAddress(pointer.value, pythoncom.IID_IDispatch)
    return win32com.client.Dispatch(dispatch)


def safe_call(accessible, name: str, child_id=0):
    dispids = {
        "accChild": -5002,
        "accName": -5003,
        "accRole": -5006,
        "accState": -5007,
    }
    if name in dispids:
        try:
            return accessible._oleobj_.InvokeTypes(
                dispids[name],
                0,
                pythoncom.DISPATCH_PROPERTYGET,
                (pythoncom.VT_VARIANT, 0),
                ((pythoncom.VT_VARIANT, pythoncom.PARAMFLAG_FIN),),
                int(child_id),
            )
        except Exception:
            pass
    try:
        member = getattr(accessible, name)
        return member(child_id) if callable(member) else member
    except Exception:
        return None


def walk(accessible, depth=0, max_depth=8, seen=None):
    if accessible is None or depth > max_depth:
        return
    seen = seen if seen is not None else {}
    identity = id(accessible)
    if identity in seen:
        return
    # Giữ reference sống để Python không tái sử dụng ``id`` cho wrapper COM kế.
    seen[identity] = accessible

    name = safe_call(accessible, "accName")
    role = safe_call(accessible, "accRole")
    state = safe_call(accessible, "accState")
    count = safe_call(accessible, "accChildCount")
    if name or role in {37, 60}:
        clean_name = str(name or "").encode("unicode_escape").decode("ascii")
        print("  " * depth + f"name={clean_name!r} role={role!r} state={state!r} children={count!r}")

    try:
        count = min(int(count or 0), 200)
    except Exception:
        count = 0
    for child_id in range(1, count + 1):
        child = safe_call(accessible, "accChild", child_id)
        if child is not None:
            try:
                walk(win32com.client.Dispatch(child), depth + 1, max_depth, seen)
                continue
            except Exception:
                pass
        child_name = safe_call(accessible, "accName", child_id)
        child_role = safe_call(accessible, "accRole", child_id)
        child_state = safe_call(accessible, "accState", child_id)
        if child_name or child_role in {37, 60}:
            clean_name = str(child_name or "").encode("unicode_escape").decode("ascii")
            print(
                "  " * (depth + 1)
                + f"simple name={clean_name!r} role={child_role!r} state={child_state!r} id={child_id}"
            )


def main() -> int:
    pythoncom.CoInitialize()
    monitor = ExcelMonitor()
    if not monitor.connect():
        print("Excel not connected")
        return 1
    hwnd_main = int(monitor.excel_app.Hwnd)
    candidates = []

    def collect(hwnd, _extra):
        try:
            class_name = win32gui.GetClassName(hwnd)
            title = win32gui.GetWindowText(hwnd)
            if win32gui.IsWindowVisible(hwnd):
                candidates.append((hwnd, class_name, title))
        except Exception:
            pass
        return True

    win32gui.EnumChildWindows(hwnd_main, collect, None)
    for hwnd, class_name, title in candidates:
        if "NetUI" not in class_name and class_name not in {"MsoCommandBar", "EXCEL2"}:
            continue
        print(f"WINDOW hwnd={hwnd} class={class_name!r} title={title!r}")
        walk(accessible_from_window(hwnd))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
