from __future__ import annotations
import base64
import ctypes
import io
import re

from PIL import ImageGrab

_SCREEN = re.compile(
    r"(olha|olhe|veja|vê|le[ia]|descrev\w*|o\s+que\s+(tem|est[áa]|aparece)|me\s+(ajuda|auxilia)|explica)"
    r".{0,40}tela"
    r"|tela.{0,20}(o\s+que|ajuda|auxilia|diz|fala)"
    r"|o\s+que\s+(eu\s+)?estou\s+vendo"
    r"|o\s+que\s+tem\s+a[ií]\s+na\s+tela"
    r"|^(olha|veja|ver)\s+a\s+tela$"
    r"|^tela$",
    re.IGNORECASE,
)
_SW_RESTORE = 9
_SW_SHOW = 5


def wants_screen(text: str) -> bool:
    t = text.lower().strip()
    if re.search(r"print(\s+da)?\s+tela|screenshot|captur(a|e)\s+(a\s+|da\s+)?tela", t):
        return False
    return bool(_SCREEN.search(t))


def _aura_hwnd() -> int:
    return int(ctypes.windll.user32.FindWindowW(None, "AURA") or 0)


def restore_aura() -> None:
    hwnd = _aura_hwnd()
    if not hwnd:
        return
    user32 = ctypes.windll.user32
    show = getattr(user32, "ShowWindowAsync", user32.ShowWindow)
    show(hwnd, _SW_RESTORE)
    show(hwnd, _SW_SHOW)
    user32.PostMessageW(hwnd, 0x0112, 0xF120, 0)


def grab_jpeg_b64(*, max_side: int = 960, quality: int = 62) -> str:
    restore_aura()
    try:
        img = ImageGrab.grab(all_screens=True)
    except TypeError:
        img = ImageGrab.grab()
    if img is None:
        raise RuntimeError("captura vazia")
    w, h = img.size
    scale = max_side / max(w, h)
    if scale < 1:
        img = img.resize((int(w * scale), int(h * scale)))
    if img.mode != "RGB":
        img = img.convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def screen_prompt(user_text: str) -> str:
    return (
        "Descreva o que aparece nesta captura da tela do Windows. "
        "Se houver uma janela da AURA (preta e dourada), ignore-a e descreva o restante. "
        "Responda em português do Brasil, objetivo, sem enrolar.\n"
        f"Pedido: {user_text.strip()}"
    )
