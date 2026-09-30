"""Triagem de e-mails via Ollama (uma chamada por lote)."""
from __future__ import annotations

import json
import re
from typing import Any

from aura.llm import OllamaClient

BALDES = {"acao", "info", "ruido"}

def heuristic_triage(emails: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    noise = re.compile(r"noreply|newsletter|unsubscribe|promo[cç][aã]o|marketing|no-reply", re.I)
    action = re.compile(
        r"\?|urgente|prazo|fatura|reuni[aã]o|por favor|confirme|pendente|vencimento|action required",
        re.I,
    )
    for e in emails:
        blob = f"{e.get('assunto','')} {e.get('trecho','')}"
        if noise.search(blob):
            balde = "ruido"
        elif action.search(blob):
            balde = "acao"
        else:
            balde = "info"
        out.append({
            "id": e.get("id") or e.get("assunto"),
            "balde": balde,
            "resumo": (e.get("assunto") or "Sem assunto")[:120],
            "local": True,
        })
    return out


async def triage_batch(llm: OllamaClient, emails: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not emails:
        return []
    lines = []
    for e in emails[:25]:
        lines.append(
            f"ID:{e.get('id','?')}|DE:{e.get('remetente','?')}|ASSUNTO:{e.get('assunto','')}|"
            f"TRECHO:{(e.get('trecho') or '')[:200]}"
        )
    prompt = (
        "Classifique cada e-mail em JSON array: [{\"id\":\"...\",\"balde\":\"acao|info|ruido\",\"resumo\":\"uma frase\"}].\n"
        "acao=pede resposta/tarefa/prazo; info=vale saber sem ação; ruido=promo/newsletter.\n"
        "Responda SOMENTE o JSON.\n\n" + "\n".join(lines)
    )
    chunks: list[str] = []
    try:
        async for delta in llm.chat(
            [{"role": "user", "content": prompt}],
            num_predict=512,
            num_ctx=4096,
            temperature=0.1,
        ):
            chunks.append(delta)
        raw = "".join(chunks).strip()
        start = raw.find("[")
        end = raw.rfind("]") + 1
        if start >= 0 and end > start:
            return _merge(json.loads(raw[start:end]), emails)
    except Exception:
        pass
    return heuristic_triage(emails)


def _merge(parsed: Any, emails: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Aceita só itens válidos do modelo; o que faltar cai na heurística."""
    by_id: dict[str, dict[str, Any]] = {}
    if isinstance(parsed, list):
        for item in parsed:
            if not isinstance(item, dict):
                continue
            balde = str(item.get("balde", "")).lower().replace("ç", "c").replace("ã", "a").replace("í", "i")
            if balde not in BALDES:
                continue
            by_id[str(item.get("id"))] = {
                "id": item.get("id"),
                "balde": balde,
                "resumo": str(item.get("resumo") or "")[:160],
            }
    fallback = {str(h["id"]): h for h in heuristic_triage(emails)}
    return [by_id.get(key) or fallback[key] for key in fallback]
