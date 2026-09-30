"""Teste de carga: tokens ilimitados e contexto grande."""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

from aura.config import ROOT, Settings, load_settings
from aura.memory import Memory
from aura.session import Session


@dataclass
class StressResult:
    name: str
    ok: bool
    detail: str
    seconds: float = 0.0


def _ollama_chat(
    model: str,
    host: str,
    messages: list[dict[str, str]],
    *,
    num_predict: int,
    num_ctx: int,
    timeout: float = 300.0,
) -> tuple[str, float, int]:
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {"num_predict": num_predict, "num_ctx": num_ctx, "temperature": 0.2},
    }
    t0 = time.perf_counter()
    req = urllib.request.Request(
        f"{host.rstrip('/')}/api/chat",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode())
    elapsed = time.perf_counter() - t0
    text = data.get("message", {}).get("content") or ""
    tokens = int(data.get("eval_count") or len(text.split()))
    return text, elapsed, tokens


def check_session_history(max_ctx: int = 8192) -> StressResult:
    t0 = time.perf_counter()
    try:
        mem = Memory()
        sess = Session(mem, followup_seconds=15)
        big = "palavra " * 3000
        sess.add_user(big)
        user = sess.llm_messages("system", max_ctx=max_ctx)[-1]["content"]
        ok = len(user) > 10_000
        detail = f"histórico {len(user)} chars"
        return StressResult("Histórico", ok, detail, time.perf_counter() - t0)
    except Exception as exc:
        return StressResult("Histórico", False, str(exc), time.perf_counter() - t0)


def check_unlimited_predict(settings: Settings | None = None) -> StressResult:
    s = settings or load_settings()
    t0 = time.perf_counter()
    try:
        text, elapsed, tokens = _ollama_chat(
            s.model,
            s.ollama_host,
            [
                {"role": "system", "content": "Responda em português. Seja detalhado."},
                {
                    "role": "user",
                    "content": (
                        "Liste e explique 8 conceitos de estoque inteligente para um sistema web. "
                        "Para cada um, dê 3 frases. Não resuma."
                    ),
                },
            ],
            num_predict=s.num_predict,
            num_ctx=s.num_ctx,
        )
        ok = len(text) > 400 and tokens > 80
        detail = f"{len(text)} chars, ~{tokens} tokens, {elapsed:.1f}s"
        return StressResult("Geração ilimitada", ok, detail, time.perf_counter() - t0)
    except urllib.error.URLError as exc:
        return StressResult("Geração ilimitada", False, f"Ollama indisponível: {exc}", time.perf_counter() - t0)
    except Exception as exc:
        return StressResult("Geração ilimitada", False, str(exc), time.perf_counter() - t0)


def check_large_context(settings: Settings | None = None) -> StressResult:
    s = settings or load_settings()
    chunk = (
        "O módulo de estoque registra entrada, saída, lote, validade e alerta de mínimo. "
    ) * 120
    t0 = time.perf_counter()
    try:
        text, elapsed, _ = _ollama_chat(
            s.model,
            s.ollama_host,
            [
                {"role": "system", "content": "Use o texto abaixo para responder."},
                {
                    "role": "user",
                    "content": (
                        f"CONTEXTO:\n{chunk}\n\n"
                        "Pergunta: quantas vezes aparece 'lote'? Responda só o número e uma frase."
                    ),
                },
            ],
            num_predict=128,
            num_ctx=s.num_ctx,
        )
        ok = "lote" in text.lower() or any(c.isdigit() for c in text)
        detail = f"ctx {len(chunk)} chars, resposta {len(text)} chars, {elapsed:.1f}s"
        return StressResult("Contexto grande", ok, detail, time.perf_counter() - t0)
    except urllib.error.URLError as exc:
        return StressResult("Contexto grande", False, f"Ollama indisponível: {exc}", time.perf_counter() - t0)
    except Exception as exc:
        return StressResult("Contexto grande", False, str(exc), time.perf_counter() - t0)


def run_all(settings: Settings | None = None) -> list[StressResult]:
    s = settings or load_settings()
    return [
        check_session_history(s.num_ctx if s.num_ctx > 0 else 8192),
        check_unlimited_predict(s),
        check_large_context(s),
    ]


def main() -> int:
    s = load_settings()
    print("AURA — teste de tokens e contexto")
    print(f"Modelo: {s.model} | num_predict={s.num_predict} | num_ctx={s.num_ctx}")
    print("-" * 50)
    ok_all = True
    for r in run_all(s):
        mark = "OK" if r.ok else "FALHOU"
        if not r.ok:
            ok_all = False
        print(f"[{mark}] {r.name}: {r.detail} ({r.seconds:.1f}s)")
    print("-" * 50)
    if ok_all:
        print("Todos os testes passaram. A AURA aguenta a configuração atual.")
        return 0
    print("Algum teste falhou. Verifique Ollama e a configuração.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
