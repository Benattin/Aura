import io

import pymupdf
from fastapi.testclient import TestClient

from aura.config import load_settings
from aura.hub import Hub
from aura.server import create_app
from aura.state import AuraState


def _pdf_bytes(text: str = "Conteudo do PDF de teste AURA") -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    data = doc.tobytes()
    doc.close()
    return data


def test_upload_pdf(monkeypatch):
    async def _fast(self, name, data_b64, ask):
        self.reply = "PDF recebido e lido."
        self.session.add_assistant(self.reply)
        await self._go(AuraState.IDLE)

    monkeypatch.setattr(Hub, "process_upload", _fast)
    app = create_app(load_settings())
    with TestClient(app) as client:
        data = _pdf_bytes()
        res = client.post(
            "/api/upload",
            files={"file": ("teste.pdf", io.BytesIO(data), "application/pdf")},
            data={"ask": "resuma este pdf"},
        )
        assert res.status_code == 200
        body = res.json()
        assert body.get("ok") is True
        assert "PDF recebido" in body.get("reply", "")
