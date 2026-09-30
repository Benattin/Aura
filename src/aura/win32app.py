from __future__ import annotations
import ctypes
import sys
from pathlib import Path

APP_ID = "Gustavo.AURA.Desktop"


def set_app_id() -> None:
    if sys.platform != "win32":
        return
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)


def apply_window_icon(window, ico: Path) -> None:
    if sys.platform != "win32" or not ico.exists():
        return
    hwnd = _hwnd(window)
    if not hwnd:
        hwnd = ctypes.windll.user32.FindWindowW(None, "AURA")
    if not hwnd:
        return
    user32 = ctypes.windll.user32
    IMAGE_ICON, LR_LOADFROMFILE = 1, 0x0010
    WM_SETICON, ICON_SMALL, ICON_BIG = 0x0080, 0, 1
    path = str(ico)
    big = user32.LoadImageW(None, path, IMAGE_ICON, 256, 256, LR_LOADFROMFILE)
    small = user32.LoadImageW(None, path, IMAGE_ICON, 32, 32, LR_LOADFROMFILE)
    if big:
        user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, big)
    if small:
        user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, small)


def _hwnd(window) -> int:
    native = getattr(window, "native", None)
    if native is None:
        return 0
    handle = getattr(native, "Handle", None)
    if handle is not None:
        try:
            return int(handle.ToInt64())
        except Exception:
            try:
                return int(handle)
            except Exception:
                return 0
    hwnd = getattr(native, "hwnd", None)
    return int(hwnd) if hwnd else 0
