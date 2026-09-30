"""Morning Digest via Ollama ou template local."""
from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from aura.llm import OllamaClient

TZ = ZoneInfo("America/Sao_Paulo")


def offline_digest(pkg: dict[str, Any]) -> str:
    now = datetime.now(TZ)
    days = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]
    parts = [
        f"Bom dia, senhor. Hoje é {days[now.weekday()]}, {now.day:02d}/{now.month:02d}.",
    ]
    if pkg.get("weather"):
        parts.append(pkg["weather"])
    if pkg.get("agenda"):
        parts.append("Sua agenda: " + pkg["agenda"])
    if pkg.get("emails"):
        parts.append(pkg["emails"])
    if pkg.get("news"):
        parts.append("Notícias: " + pkg["news"])
    if pkg.get("focus"):
        parts.append(pkg["focus"])
    else:
        parts.append("Tenha um dia produtivo, senhor.")
    return " ".join(parts)


async def build_digest(llm: OllamaClient, pkg: dict[str, Any], *, short: bool = True) -> str:
    prompt = (
        "Monte um briefing matinal falado, natural, em português do Brasil, tratando o usuário como senhor. "
        f"{'Curto (~30s de fala).' if short else 'Médio (~1 minuto).'} "
        "Termine com uma frase de foco do dia.\n\n"
        f"DADOS:\n{pkg}"
    )
    chunks: list[str] = []
    try:
        async for delta in llm.chat(
            [{"role": "user", "content": prompt}],
            num_predict=500 if short else 800,
            num_ctx=4096,
            temperature=0.25,
        ):
            chunks.append(delta)
        text = "".join(chunks).strip()
        if text:
            return text
    except Exception:
        pass
    return offline_digest(pkg)
