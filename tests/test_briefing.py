import asyncio

import pytest

from aura.briefing import compact_context, try_local_command
from aura.digest import offline_digest
from aura.triage import _merge, heuristic_triage, triage_batch

CTX = {
    "todaySpeech": "10:00, Reunião",
    "weekSpeech": "Reunião, Dentista",
    "emailSpeech": "3 e-mails.",
    "actionSpeech": "Pagar fatura",
    "newsSpeech": "IA: novidade",
    "nextEvent": "Próximo: Reunião, em 1h",
    "todayCompact": "10:00 Reunião",
    "actionCount": 1,
}


@pytest.mark.parametrize("text,expected", [
    ("bom dia", "__digest__"),
    ("Bom dia AURA", "__digest__"),
    ("atualiza briefing", "__refresh__"),
    ("atualizar os e-mails", "__refresh__"),
    ("minha agenda", "10:00, Reunião"),
    ("o que eu tenho hoje?", "10:00, Reunião"),
    ("agenda da semana", "Reunião, Dentista"),
    ("próximo compromisso", "Próximo: Reunião, em 1h"),
    ("meus e-mails", "3 e-mails."),
    ("tem e-mail importante?", "Pagar fatura"),
    ("notícias", "IA: novidade"),
])
def test_local_commands(text, expected):
    assert try_local_command(text, CTX) == expected


@pytest.mark.parametrize("text", [
    "escreve um e-mail para o João",
    "coloca na minha agenda reunião amanhã",
    "resume essas notícias que te mandei",
    "o que você acha da semana que vem na agenda?",
    "",
])
def test_free_text_goes_to_llm(text):
    assert try_local_command(text, CTX) is None


def test_compact_context():
    out = compact_context(CTX)
    assert "10:00 Reunião" in out and "1" in out


def test_heuristic_buckets():
    out = heuristic_triage([
        {"id": "1", "assunto": "Fatura vence amanhã"},
        {"id": "2", "assunto": "Newsletter semanal", "trecho": "unsubscribe"},
        {"id": "3", "assunto": "Foto da viagem"},
    ])
    assert [o["balde"] for o in out] == ["acao", "ruido", "info"]


def test_merge_drops_invalid_and_fills_missing():
    emails = [{"id": "1", "assunto": "Oi"}, {"id": "2", "assunto": "Fatura urgente"}]
    parsed = [{"id": "1", "balde": "ação", "resumo": "Responder"}, {"id": "2", "balde": "xyz"}, "lixo"]
    out = _merge(parsed, emails)
    assert out[0] == {"id": "1", "balde": "acao", "resumo": "Responder"}
    assert out[1]["balde"] == "acao" and out[1]["local"] is True


class _BrokenLLM:
    async def chat(self, *a, **k):
        raise RuntimeError("offline")
        yield ""


def test_triage_falls_back_when_llm_offline():
    out = asyncio.run(triage_batch(_BrokenLLM(), [{"id": "1", "assunto": "Promoção imperdível"}]))
    assert out[0]["balde"] == "ruido"


def test_offline_digest_contains_sections():
    text = offline_digest({"weather": "Sol, 25°C.", "agenda": "10:00 Reunião", "news": "IA sobe"})
    assert text.startswith("Bom dia, senhor.")
    assert "25°C" in text and "10:00 Reunião" in text and "IA sobe" in text
