from collections.abc import AsyncIterator
import json
import os
import httpx


class LlmError(Exception):
    def __init__(self, message: str, *, needs_model: bool = False, model: str | None = None) -> None:
        super().__init__(message)
        self.needs_model = needs_model
        self.model = model


def _threads() -> int:
    n = os.cpu_count() or 4
    return max(2, n - 2)


class OllamaClient:
    def __init__(self, host: str, model: str, *, num_predict: int = -1, num_ctx: int = 8192, keep_alive: str = "60m") -> None:
        self.host = host.rstrip("/")
        self.model = model
        self.num_predict = num_predict
        self.num_ctx = num_ctx
        self.keep_alive = keep_alive
        self._client: httpx.AsyncClient | None = None
        self._known: set[str] | None = None

    def _options(
        self,
        num_predict: int | None = None,
        *,
        num_ctx: int | None = None,
        temperature: float | None = None,
    ) -> dict:
        return {
            "num_predict": num_predict if num_predict is not None else self.num_predict,
            "num_ctx": num_ctx if num_ctx is not None else self.num_ctx,
            "temperature": 0.25 if temperature is None else temperature,
            "top_p": 0.8,
            "repeat_penalty": 1.08,
            "num_thread": _threads(),
            "num_batch": 256,
        }

    async def _http(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=None)
        return self._client

    async def warmup(self, model: str | None = None) -> None:
        used = model or self.model
        try:
            client = await self._http()
            await client.post(
                f"{self.host}/api/generate",
                json={
                    "model": used, "prompt": "ok", "stream": False,
                    "keep_alive": -1,
                    "options": {"num_predict": 1, "num_ctx": 512, "num_thread": _threads()},
                },
            )
        except httpx.HTTPError:
            pass

    async def has_model(self, name: str, *, refresh: bool = False) -> bool:
        if refresh:
            self._known = None
        if self._known is None:
            try:
                client = await self._http()
                resp = await client.get(f"{self.host}/api/tags")
                resp.raise_for_status()
                names = {m.get("name", "") for m in resp.json().get("models", [])}
                self._known = names
            except httpx.HTTPError:
                return False
        return any(
            n == name or n.startswith(name + ":") or n.split(":")[0] == name.split(":")[0]
            for n in self._known
        )

    async def chat(
        self,
        messages: list[dict],
        *,
        model: str | None = None,
        num_predict: int | None = None,
        num_ctx: int | None = None,
        temperature: float | None = None,
    ) -> AsyncIterator[str]:
        used = model or self.model
        payload = {
            "model": used, "messages": messages, "stream": True,
            "keep_alive": -1,
            "options": self._options(num_predict, num_ctx=num_ctx, temperature=temperature),
        }
        try:
            client = await self._http()
            async with client.stream("POST", f"{self.host}/api/chat", json=payload) as resp:
                if resp.status_code == 404:
                    raise LlmError(
                        f"Senhor, o modelo {used} não está instalado. Posso baixá-lo se o senhor confirmar.",
                        needs_model=True,
                        model=used,
                    )
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    data = json.loads(line)
                    if err := data.get("error"):
                        low = str(err).lower()
                        raise LlmError(str(err), needs_model="not found" in low or "try pulling" in low, model=used)
                    chunk = data.get("message", {}).get("content") or ""
                    if chunk:
                        yield chunk
        except LlmError:
            raise
        except httpx.HTTPError as exc:
            raise LlmError(
                "Senhor, o modelo principal está indisponível. Posso tentar novamente em alguns instantes."
            ) from exc

    async def vision(self, prompt: str, image_b64: str, *, model: str, num_predict: int = -1) -> AsyncIterator[str]:
        payload = {
            "model": model,
            "prompt": prompt,
            "images": [image_b64],
            "stream": True,
            "keep_alive": "30m",
            "options": {
                "num_predict": num_predict,
                "temperature": 0.2,
                "num_thread": _threads(),
                "num_ctx": 2048,
            },
        }
        try:
            client = await self._http()
            async with client.stream("POST", f"{self.host}/api/generate", json=payload) as resp:
                if resp.status_code == 404:
                    raise LlmError(
                        f"Senhor, o modelo {model} não está instalado. Posso baixá-lo se o senhor confirmar.",
                        needs_model=True,
                        model=model,
                    )
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    data = json.loads(line)
                    if err := data.get("error"):
                        low = str(err).lower()
                        raise LlmError(str(err), needs_model="not found" in low or "try pulling" in low, model=model)
                    chunk = data.get("response") or ""
                    if chunk:
                        yield chunk
        except LlmError:
            raise
        except httpx.HTTPError as exc:
            raise LlmError("Não consegui ler a tela, senhor. O modelo de visão falhou.") from exc

    async def pull(self, name: str | None = None) -> AsyncIterator[str]:
        target = name or self.model
        client = await self._http()
        async with client.stream("POST", f"{self.host}/api/pull", json={"name": target, "stream": True}) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line:
                    continue
                data = json.loads(line)
                status = data.get("status") or data.get("error") or ""
                if status:
                    yield status
                if data.get("error"):
                    raise LlmError(str(data["error"]))
        self._known = None
