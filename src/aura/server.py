from __future__ import annotations
import base64
import logging
from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import Body, FastAPI, File, Form, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response

from aura.config import ICON_ICO, ROOT, Settings, data_dir, load_settings
from aura.hub import Hub
from aura.state import AuraState

log = logging.getLogger("aura")

DIST = ROOT / "ui" / "dist"
INDEX = DIST / "index.html"
UI_BUILD = DIST / "assets"


class NoCacheStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope) -> Response:
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        return response


def create_app(settings: Settings | None = None, *, on_show=None, on_reload=None) -> FastAPI:
    settings = settings or load_settings()
    clients: set[WebSocket] = set()
    hub_ref: dict[str, Hub] = {}

    async def emit(msg: dict) -> None:
        stale: list[WebSocket] = []
        for ws in list(clients):
            try:
                await ws.send_json(msg)
            except Exception:
                stale.append(ws)
        for ws in stale:
            clients.discard(ws)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        hub = Hub(settings, emit)
        hub_ref["hub"] = hub
        app.state.hub = hub
        await hub.boot()
        yield

    app = FastAPI(title="AURA", lifespan=lifespan)

    def hub() -> Hub:
        return hub_ref["hub"]

    @app.get("/api/health")
    async def health() -> dict:
        return hub().snapshot()

    @app.post("/api/toggle_pause")
    async def toggle_pause() -> dict:
        h = hub()
        if h.machine.state is AuraState.PAUSED:
            await h.resume()
        else:
            await h.pause()
        return h.snapshot()

    @app.post("/api/show")
    async def show_window() -> dict:
        if on_show is not None:
            on_show()
        return {"ok": True}

    @app.post("/api/reload_ui")
    async def reload_ui() -> dict:
        if on_reload is not None:
            on_reload()
        return {"ok": True}

    @app.post("/api/upload")
    async def upload_file(file: UploadFile = File(...), ask: str = Form(default="")) -> dict:
        raw = await file.read()
        if not raw:
            return {"ok": False, "error": "Arquivo vazio, senhor."}
        name = file.filename or "arquivo.bin"
        prompt = ask.strip() or "Analise este arquivo, explique o conteúdo e responda ao pedido do senhor."
        log.info("upload %s (%d bytes)", name, len(raw))
        inbox = data_dir() / "inbox"
        inbox.mkdir(parents=True, exist_ok=True)
        safe = Path(name).name[:120]
        try:
            (inbox / safe).write_bytes(raw)
        except OSError:
            log.warning("não salvei cópia em inbox: %s", safe)
        try:
            await hub().process_upload(name, base64.b64encode(raw).decode("ascii"), prompt)
        except Exception as exc:
            log.exception("upload falhou: %s", name)
            h = hub()
            h.error_detail = str(exc)
            snap = h.snapshot()
            snap["ok"] = False
            snap["error"] = str(exc)
            return snap
        snap = hub().snapshot()
        snap["ok"] = True
        return snap

    @app.post("/api/triage")
    async def triage_emails(body: dict = Body(...)) -> dict:
        from aura.triage import heuristic_triage, triage_batch

        emails = body.get("emails") or []
        h = hub()
        if not emails:
            return {"items": []}
        try:
            items = await triage_batch(h.llm, emails)
        except Exception:
            items = heuristic_triage(emails)
        return {"items": items}

    @app.post("/api/digest")
    async def morning_digest(body: dict = Body(...)) -> dict:
        from aura.digest import build_digest, offline_digest

        pkg = body.get("pkg") or body
        h = hub()
        try:
            text = await build_digest(h.llm, pkg, short=True)
        except Exception:
            text = offline_digest(pkg)
        return {"text": text}

    @app.websocket("/ws")
    async def ws_endpoint(ws: WebSocket) -> None:
        await ws.accept()
        clients.add(ws)
        await ws.send_json(hub().snapshot())
        try:
            while True:
                msg = await ws.receive_json()
                if isinstance(msg, dict):
                    await hub().handle(msg)
        except WebSocketDisconnect:
            pass
        finally:
            clients.discard(ws)

    def _asset_response(path: str) -> FileResponse | HTMLResponse:
        if not UI_BUILD.exists():
            return HTMLResponse(status_code=404)
        target = (UI_BUILD / path).resolve()
        root = UI_BUILD.resolve()
        if not str(target).startswith(str(root)) or not target.is_file():
            return HTMLResponse(status_code=404)
        media = "text/css" if target.suffix == ".css" else "application/javascript"
        return FileResponse(
            target,
            media_type=media,
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate",
                "Pragma": "no-cache",
            },
        )

    @app.get("/assets/{path:path}")
    async def assets(path: str):
        return _asset_response(path)

    if UI_BUILD.exists():
        app.mount("/assets", NoCacheStaticFiles(directory=UI_BUILD), name="assets")

    @app.get("/aura.ico")
    async def favicon():
        if ICON_ICO.exists():
            return FileResponse(ICON_ICO)
        return HTMLResponse(status_code=404)

    @app.get("/")
    async def index():
        if INDEX.exists():
            return FileResponse(
                INDEX,
                headers={
                    "Cache-Control": "no-store, no-cache, must-revalidate",
                    "Pragma": "no-cache",
                },
            )
        return HTMLResponse("<p>AURA: npm run build em ui/</p>")

    return app
