from __future__ import annotations
import logging
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.request

import uvicorn

from aura.config import load_settings
from aura.logutil import setup_logging
from aura.server import create_app
from aura.shell import WindowApi, open_window, start_tray

log = logging.getLogger("aura")
_CREATE_NO_WINDOW = 0x08000000


def _pids_on_port(port: int) -> list[int]:
    try:
        out = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True,
            text=True,
            check=False,
            creationflags=_CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        ).stdout
    except OSError:
        return []
    pids: set[int] = set()
    needle = f":{port}"
    for line in out.splitlines():
        if needle not in line or "LISTENING" not in line:
            continue
        parts = line.split()
        if not parts:
            continue
        try:
            pid = int(parts[-1])
        except ValueError:
            continue
        if pid > 0:
            pids.add(pid)
    return sorted(pids)


def _kill_port(port: int) -> None:
    me = os.getpid()
    for pid in _pids_on_port(port):
        if pid == me:
            continue
        args = ["taskkill", "/F", "/PID", str(pid)]
        if sys.platform == "win32":
            subprocess.run(args, check=False, capture_output=True, creationflags=_CREATE_NO_WINDOW)
        else:
            subprocess.run(args, check=False, capture_output=True)


def _wait_dead(url: str, seconds: float = 6.0) -> bool:
    deadline = time.time() + seconds
    while time.time() < deadline:
        if not _alive(url):
            return True
        time.sleep(0.2)
    return not _alive(url)


def _alive(url: str) -> bool:
    try:
        urllib.request.urlopen(f"{url}/api/health", timeout=0.6)
        return True
    except Exception:
        return False


def _request_show(url: str) -> bool:
    ok = False
    for path in ("/api/reload_ui", "/api/show"):
        req = urllib.request.Request(f"{url}{path}", method="POST")
        try:
            urllib.request.urlopen(req, timeout=2)
            ok = True
        except Exception:
            if path == "/api/show":
                log.info("instância já ativa, mas a janela não respondeu")
    return ok


def _ollama_up(host: str) -> bool:
    try:
        urllib.request.urlopen(host.rstrip("/") + "/api/tags", timeout=0.5)
        return True
    except Exception:
        return False


def _ensure_ollama(host: str) -> None:
    if _ollama_up(host):
        return
    exe = shutil.which("ollama")
    if not exe:
        return
    kwargs: dict = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    if sys.platform == "win32":
        kwargs["creationflags"] = _CREATE_NO_WINDOW
    subprocess.Popen([exe, "serve"], **kwargs)


def _wait_ollama(host: str, seconds: int) -> None:
    for _ in range(seconds):
        if _ollama_up(host):
            return
        time.sleep(1)


def main() -> None:
    setup_logging()
    if "--install-startup" in sys.argv:
        from aura.startup import install
        print(install())
        return
    if "--uninstall-startup" in sys.argv:
        from aura.startup import uninstall
        uninstall()
        return
    if "--test-tokens" in sys.argv:
        from aura.token_stress import main as test_tokens
        raise SystemExit(test_tokens())

    settings = load_settings()
    if settings.auto_start:
        try:
            from aura.startup import install
            install()
        except Exception:
            log.exception("não foi possível registrar o auto-start")

    url = f"http://{settings.host}:{settings.port}"
    if _alive(url):
        if _request_show(url):
            return
        log.warning("instância ativa sem janela; encerrando processo antigo")
        _kill_port(settings.port)
        if not _wait_dead(url):
            log.error("não foi possível liberar a porta %s", settings.port)
            return

    def _warm_ollama() -> None:
        _ensure_ollama(settings.ollama_host)
        _wait_ollama(settings.ollama_host, 90)

    threading.Thread(target=_warm_ollama, daemon=True, name="aura-ollama").start()
    _wait_ollama(settings.ollama_host, 3)

    api = WindowApi()
    app = create_app(settings, on_show=api.show, on_reload=api.reload)
    config = uvicorn.Config(app, host=settings.host, port=settings.port, log_level="warning")
    server = uvicorn.Server(config)
    threading.Thread(target=server.run, daemon=True, name="aura-http").start()
    for _ in range(120):
        if _alive(url):
            break
        time.sleep(0.1)
    else:
        log.error("servidor HTTP não subiu em %s", url)
        return

    def quit_app() -> None:
        server.should_exit = True
        os._exit(0)

    start_tray(url, api, quit_app)
    try:
        open_window(url, api, minimized=False)
    except Exception:
        log.exception("falha ao abrir a janela")
    quit_app()


if __name__ == "__main__":
    main()
