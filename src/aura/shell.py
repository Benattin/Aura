from __future__ import annotations
import logging
import shutil
import threading
import urllib.request
from pathlib import Path

from PIL import Image

from aura.config import ICON_ICO, ICON_PNG, data_dir
from aura.icons import ensure_icons
from aura.win32app import apply_window_icon, set_app_id

log = logging.getLogger("aura.shell")
UI_VERSION = "v7"


def _prepare_webview_storage(webview_dir: Path) -> None:
    webview_dir.mkdir(parents=True, exist_ok=True)
    stamp = webview_dir / ".ui_version"
    if stamp.exists() and stamp.read_text(encoding="utf-8").strip() == UI_VERSION:
        return
    if webview_dir.exists():
        shutil.rmtree(webview_dir, ignore_errors=True)
    webview_dir.mkdir(parents=True, exist_ok=True)
    stamp.write_text(UI_VERSION, encoding="utf-8")


class WindowApi:
    def __init__(self) -> None:
        self.window = None

    def show(self) -> None:
        win = self.window
        if win is None:
            return
        try:
            win.restore()
            win.show()
            win.on_top = True
            win.on_top = False
        except Exception:
            log.exception("falha ao exibir janela")

    def reload(self) -> None:
        win = self.window
        if win is None:
            return
        try:
            win.evaluate_js("location.reload()")
        except Exception:
            log.exception("falha ao recarregar interface")


def make_icon() -> Image.Image:
    ensure_icons()
    for path in (ICON_ICO, ICON_PNG):
        if path.exists():
            return Image.open(path).convert("RGBA")
    img = Image.new("RGBA", (64, 64), (5, 5, 5, 255))
    return img


def start_tray(url: str, api: WindowApi, on_quit) -> None:
    import pystray

    def toggle() -> None:
        req = urllib.request.Request(f"{url}/api/toggle_pause", method="POST")
        try:
            urllib.request.urlopen(req, timeout=2)
        except Exception:
            log.debug("toggle pause falhou", exc_info=True)

    menu = pystray.Menu(
        pystray.MenuItem("Abrir AURA", api.show, default=True),
        pystray.MenuItem("Pausar / continuar", lambda: toggle()),
        pystray.MenuItem("Sair", lambda: on_quit()),
    )
    icon = pystray.Icon("AURA", make_icon(), "AURA", menu)
    threading.Thread(target=icon.run, daemon=True, name="aura-tray").start()


def open_window(url: str, api: WindowApi, *, minimized: bool = False) -> None:
    import webview

    ico = ensure_icons()
    set_app_id()
    webview_dir = data_dir() / "webview"
    _prepare_webview_storage(webview_dir)
    api.window = webview.create_window(
        "AURA",
        url,
        width=1280,
        height=820,
        background_color="#020203",
        frameless=False,
        easy_drag=False,
        shadow=True,
        minimized=minimized,
        text_select=True,
        focus=True,
    )

    def on_shown() -> None:
        apply_window_icon(api.window, ico)
        from aura.vision import restore_aura
        restore_aura()
        if not minimized:
            api.show()

    def on_loaded() -> None:
        try:
            api.window.evaluate_js(
                "var i=document.querySelector('input'); if(i){i.focus();}"
            )
        except Exception:
            pass

    try:
        api.window.events.shown += on_shown
        api.window.events.loaded += on_loaded
    except Exception:
        log.debug("events da janela indisponíveis", exc_info=True)

    start_kwargs: dict = {
        "storage_path": str(webview_dir),
        "private_mode": False,
    }
    if ico.exists():
        start_kwargs["icon"] = str(ico)
    log.info("abrindo janela %s", url)
    webview.start(**start_kwargs)
