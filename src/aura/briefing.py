"""Comandos locais de briefing — sem gastar API."""
from __future__ import annotations

import re
from typing import Any


def try_local_command(text: str, ctx: dict[str, Any]) -> str | None:
    t = text.strip().lower()
    if not t:
        return None
    if re.search(r"\b(bom\s+dia|morning\s+digest|digest\s+da\s+manh[aã])\b", t):
        return "__digest__"
    if re.search(r"\batualiz\w*\s+(?:o\s+|os\s+|as\s+)?(briefing|e-?mails?|not[ií]cias|agenda|pain[eé]is)\b", t):
        return "__refresh__"
    if re.search(r"\b(pr[oó]ximo\s+compromisso|pr[oó]xima\s+reuni[aã]o)\b", t):
        nxt = ctx.get("nextEvent") or ""
        return nxt or "Não há compromissos próximos na agenda, senhor."
    if re.search(r"^(?:(?:qual|como\s+est[aá]|mostra|ver)\s+)?(?:a\s+)?(?:minha\s+)?agenda\s+da\s+semana\??$", t):
        return ctx.get("weekSpeech") or "Não encontrei eventos na semana, senhor."
    if re.search(r"^(?:(?:qual|como\s+est[aá]|mostra|ver)\s+)?(?:a\s+)?(?:minha\s+agenda|agenda\s+de\s+hoje)\??$|^o\s+que\s+eu\s+tenho\s+hoje\??$", t):
        return ctx.get("todaySpeech") or "Sua agenda de hoje está vazia, senhor."
    if re.search(r"\b(e-?mails?\s+importantes?|tem\s+(?:algum\s+)?e-?mail)\b", t):
        return ctx.get("actionSpeech") or "Nenhum e-mail pedindo ação, senhor."
    if re.search(r"^(?:(?:quais|como\s+est[aã]o|l[eê]|ler|mostra|ver)\s+)?(?:os\s+)?(?:meus\s+)?e-?mails\??$|\bcaixa\s+de\s+entrada\b", t):
        return ctx.get("emailSpeech") or "Não há e-mails carregados, senhor. Configure na antena."
    if m := re.search(r"^(?:quais\s+(?:as\s+|s[aã]o\s+as\s+)?)?not[ií]cias(?:\s+(?:de|sobre)\s+(.+?))?\??$", t):
        topic = (m.group(1) or "").strip()
        topics = ctx.get("newsTopics") or {}
        if topic and topic in topics:
            return topics[topic]
        return ctx.get("newsSpeech") or "Notícias indisponíveis no momento, senhor."
    return None


def compact_context(ctx: dict[str, Any]) -> str:
    parts: list[str] = []
    if ctx.get("todayCompact"):
        parts.append(f"Agenda de hoje: {ctx['todayCompact']}")
    if ctx.get("actionCount") is not None:
        parts.append(f"E-mails pedindo ação: {ctx['actionCount']}")
    return "\n".join(parts)
