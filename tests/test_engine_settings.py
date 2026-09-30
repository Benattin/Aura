import asyncio
from types import SimpleNamespace

import pytest

from aura.config import Settings
from aura.hub import Hub


class _FakeLLM:
    def __init__(self):
        self.model = "llama3.2:3b"
        self.warmed: list[str] = []

    async def list_models(self):
        return ["llama3.2:3b", "qwen2.5:7b", "qwen2.5-coder:3b"]

    async def warmup(self, model=None):
        self.warmed.append(model)

    async def chat(self, *a, **k):
        raise AssertionError("modo economia não deveria chamar o modelo")
        yield ""


def _hub(saved: dict):
    async def _broadcast():
        saved["broadcast"] = True
    return SimpleNamespace(settings=Settings(), llm=_FakeLLM(), _active_model="", _broadcast=_broadcast)


@pytest.fixture
def saved(monkeypatch):
    out: dict = {}
    monkeypatch.setattr("aura.hub.save_local", lambda d: out.update(d))
    return out


def test_apply_switches_model_live_and_persists(saved):
    h = _hub(saved)

    async def run():
        applied = await Hub.apply_settings(h, {"model": "qwen2.5:7b", "economy_mode": False})
        await asyncio.sleep(0)
        return applied

    applied = asyncio.run(run())
    assert applied == {"model": "qwen2.5:7b", "economy_mode": False}
    assert h.settings.model == h.llm.model == h._active_model == "qwen2.5:7b"
    assert h.settings.economy_mode is False
    assert saved["model"] == "qwen2.5:7b" and saved["broadcast"]


def test_apply_rejects_missing_model(saved):
    h = _hub(saved)
    with pytest.raises(ValueError):
        asyncio.run(Hub.apply_settings(h, {"model": "inexistente:1b"}))
    assert h.settings.model == "llama3.2:3b" and not saved


def test_economy_skips_llm_triage_and_reasoning():
    h = _hub({})
    h.settings.economy_mode = True
    items = asyncio.run(Hub.triage(h, [{"id": "1", "assunto": "Fatura urgente"}]))
    assert items[0]["balde"] == "acao"
    assert Hub._deep(h, "compare e analise passo a passo as vantagens") is False
