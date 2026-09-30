from datetime import datetime, timedelta, timezone
import re

from aura.memory import Memory

_STOP = re.compile(r"^\s*(aura[,\s]+)?pare\s*[.!]?\s*$", re.IGNORECASE)


class Session:
    def __init__(self, memory: Memory, followup_seconds: int = 15) -> None:
        self.memory = memory
        self.followup_seconds = followup_seconds
        self.id = memory.active_id or memory.new_chat()
        self.messages: list[dict[str, str]] = list(memory.chat_messages(self.id))
        self._last_assistant: datetime | None = None

    def add_user(self, text: str, at: datetime | None = None) -> None:
        self.messages.append({"role": "user", "content": text.strip()})
        self._persist()

    def add_assistant(self, text: str, at: datetime | None = None) -> None:
        self.messages.append({"role": "assistant", "content": text.strip()})
        self._last_assistant = at or datetime.now(timezone.utc)
        self._persist(flush=True)

    def _persist(self, *, flush: bool = False) -> None:
        self.memory.write_chat(self.id, self.messages, flush=flush)

    def open(self, cid: str) -> None:
        self.id = cid
        self.messages = list(self.memory.chat_messages(cid))
        self.memory.active_id = cid
        self.memory.save()
        self._last_assistant = None

    def new(self) -> None:
        self.id = self.memory.new_chat()
        self.messages = []
        self._last_assistant = None

    def turns(self) -> list[dict[str, str]]:
        out: list[dict[str, str]] = []
        for m in self.messages[-40:]:
            role = "aura" if m.get("role") == "assistant" else "user"
            out.append({"role": role, "text": m.get("content") or ""})
        return out

    def in_followup(self, now: datetime | None = None) -> bool:
        if self._last_assistant is None:
            return False
        now = now or datetime.now(timezone.utc)
        return now - self._last_assistant <= timedelta(seconds=self.followup_seconds)

    @staticmethod
    def is_stop(text: str) -> bool:
        return bool(_STOP.match(text.strip()))

    def llm_messages(self, system: str, *, max_ctx: int = 8192) -> list[dict[str, str]]:
        extra = self.memory.other_chats(self.id)
        sys = f"{system}\n{extra}".strip() if extra else system
        ctx = 8192 if max_ctx <= 0 else max_ctx
        last_limit = ctx * 2
        other_limit = max(ctx // 2, 2000)
        keep = min(30, max(10, ctx // 512))
        trimmed: list[dict[str, str]] = []
        recent = self.messages[-keep:]
        for i, m in enumerate(recent):
            c = m.get("content") or ""
            limit = last_limit if i == len(recent) - 1 else other_limit
            if len(c) > limit:
                c = c[:limit] + "…"
            trimmed.append({"role": m["role"], "content": c})
        return [{"role": "system", "content": sys}, *trimmed]
