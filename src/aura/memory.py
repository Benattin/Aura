from __future__ import annotations
import json
import re
import threading
import uuid
from datetime import datetime
from pathlib import Path

from aura.config import data_dir
_MAX = 16

_LIKE = re.compile(
    r"(?:eu\s+)?(?:gosto|adoro|amo|curto|prefiro)\s+(?:de\s+|do\s+|da\s+|dos\s+|das\s+)?(.+)$",
    re.I,
)
_DISLIKE = re.compile(
    r"(?:eu\s+)?(?:n[aã]o\s+gosto|odeio|detesto|evite)\s+(?:de\s+|do\s+|da\s+)?(.+)$",
    re.I,
)
_FACT = re.compile(
    r"(?:eu\s+sou|meu nome [eé]|me chamo|eu tenho|eu uso|eu trabalho|eu moro)\s+(.+)$",
    re.I,
)
_FORGET = re.compile(r"esque[cç]a\s+(tudo|o que sabe|minha mem[oó]ria|o que aprendeu)", re.I)


def wants_forget(text: str) -> bool:
    return bool(_FORGET.search(text.strip()))


class Memory:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (data_dir() / "memory.json")
        self.likes: list[str] = []
        self.dislikes: list[str] = []
        self.facts: list[str] = []
        self.style: list[str] = []
        self.notes: list[dict] = []
        self.todos: list[dict] = []
        self.reminders: list[dict] = []
        self.recent: list[str] = []
        self.chats: list[dict] = []
        self.active_id: str = ""
        self._save_timer: threading.Timer | None = None
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        self.likes = list(data.get("likes") or [])
        self.dislikes = list(data.get("dislikes") or [])
        self.facts = list(data.get("facts") or [])
        self.style = list(data.get("style") or [])
        self.notes = list(data.get("notes") or [])
        self.todos = list(data.get("todos") or [])
        self.reminders = list(data.get("reminders") or [])
        self.recent = list(data.get("recent") or [])
        self.chats = list(data.get("chats") or [])
        self.active_id = str(data.get("active_id") or "")
        if self.chats and not self.active_id:
            self.active_id = str(self.chats[-1].get("id") or "")

    def save(self) -> None:
        if self._save_timer is not None:
            self._save_timer.cancel()
            self._save_timer = None
        self._write()

    def _schedule_save(self) -> None:
        if self._save_timer is not None:
            self._save_timer.cancel()
        self._save_timer = threading.Timer(0.35, self._flush_save)
        self._save_timer.daemon = True
        self._save_timer.start()

    def _flush_save(self) -> None:
        self._save_timer = None
        self._write()

    def _write(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(
                {
                    "likes": self.likes[-_MAX:],
                    "dislikes": self.dislikes[-_MAX:],
                    "facts": self.facts[-_MAX:],
                    "style": self.style[-8:],
                    "notes": self.notes[-40:],
                    "todos": self.todos[-40:],
                    "reminders": self.reminders[-40:],
                    "recent": self.recent[-20:],
                    "active_id": self.active_id,
                    "chats": self._chats_for_disk(),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def clear(self) -> None:
        self.likes, self.dislikes, self.facts, self.style = [], [], [], []
        self.recent = []
        self.save()

    def _chats_for_disk(self) -> list[dict]:
        out: list[dict] = []
        for c in self.chats[-24:]:
            msgs = list(c.get("messages") or [])[-60:]
            out.append({
                "id": c.get("id"),
                "title": c.get("title") or "Conversa",
                "updated": c.get("updated") or "",
                "messages": msgs,
            })
        return out

    def new_chat(self) -> str:
        cid = uuid.uuid4().hex[:12]
        self.chats.append({
            "id": cid,
            "title": "Nova conversa",
            "updated": datetime.now().isoformat(timespec="seconds"),
            "messages": [],
        })
        self.chats = self.chats[-24:]
        self.active_id = cid
        self.save()
        return cid

    def chat_messages(self, cid: str) -> list[dict]:
        for c in self.chats:
            if c.get("id") == cid:
                return list(c.get("messages") or [])
        return []

    def write_chat(self, cid: str, messages: list[dict], *, flush: bool = False) -> None:
        title = "Nova conversa"
        for m in messages:
            if m.get("role") == "user" and (m.get("content") or "").strip():
                title = m["content"].strip().split("\n")[0][:48]
                break
        payload = {
            "id": cid,
            "title": title,
            "updated": datetime.now().isoformat(timespec="seconds"),
            "messages": messages[-60:],
        }
        for i, c in enumerate(self.chats):
            if c.get("id") == cid:
                self.chats[i] = payload
                break
        else:
            self.chats.append(payload)
        self.active_id = cid
        if flush:
            self.save()
        else:
            self._schedule_save()

    def chats_index(self) -> list[dict]:
        items: list[dict] = []
        for c in reversed(self.chats):
            items.append({"id": c.get("id"), "title": c.get("title") or "Conversa"})
        return items

    def other_chats(self, active_id: str, n: int = 4) -> str:
        bits: list[str] = []
        for c in reversed(self.chats):
            if c.get("id") == active_id:
                continue
            title = c.get("title") or "Conversa"
            last_a = ""
            for m in reversed(c.get("messages") or []):
                if m.get("role") == "assistant":
                    last_a = (m.get("content") or "")[:80].replace("\n", " ")
                    break
            bits.append(f"- {title}" + (f": {last_a}" if last_a else ""))
            if len(bits) >= n:
                break
        if not bits:
            return ""
        return "Outras conversas (use se o senhor voltar ao assunto):\n" + "\n".join(bits)

    def observe(self, text: str) -> None:
        t = " ".join(text.strip().split())
        if len(t) < 3:
            return
        if wants_forget(t):
            self.clear()
            return
        self.recent.append(t[:160])
        self.recent = self.recent[-16:]
        changed = True
        if m := _LIKE.search(t):
            self._push("likes", m.group(1).strip(" .!,"))
            changed = True
        elif m := _DISLIKE.search(t):
            self._push("dislikes", m.group(1).strip(" .!,"))
            changed = True
        elif m := _FACT.search(t):
            self._push("facts", t[:180])
            changed = True
        if changed:
            self.save()

    def _push(self, key: str, value: str) -> None:
        value = value.strip()
        if len(value) < 2:
            return
        bucket: list[str] = getattr(self, key)
        low = value.lower()
        if any(x.lower() == low for x in bucket):
            return
        bucket.append(value)
        setattr(self, key, bucket[-_MAX:])

    def count(self) -> int:
        return len(self.likes) + len(self.dislikes) + len(self.facts) + len(self.notes)

    def render(self) -> str:
        lines = ["Memória local do senhor (use para tom e preferências):"]
        if self.likes:
            lines.append("Gosta: " + "; ".join(self.likes[-8:]))
        if self.dislikes:
            lines.append("Não gosta: " + "; ".join(self.dislikes[-8:]))
        if self.facts:
            lines.append("Fatos: " + "; ".join(self.facts[-8:]))
        if self.notes:
            lines.append("Notas: " + "; ".join(n.get("text", "") for n in self.notes[-8:]))
        if self.recent:
            lines.append("Falou recentemente: " + " | ".join(self.recent[-8:]))
        if self.style:
            lines.append("Como fala (espelhe o tom): " + " | ".join(self.style[-3:]))
        open_todos = [t["text"] for t in self.todos if not t.get("done")]
        if open_todos:
            lines.append("Tarefas: " + "; ".join(open_todos[-8:]))
        upcoming = [r for r in self.reminders if not r.get("done")][-4:]
        if upcoming:
            lines.append(
                "Lembretes: "
                + "; ".join(f"{r.get('at', '')[11:16]} {r.get('text', '')}" for r in upcoming)
            )
        if len(lines) == 1:
            return ""
        lines.append("Fale no mesmo registro que o senhor: direto, em português do Brasil.")
        return "\n".join(lines)

    def remember(self, fact: str) -> None:
        self._push("facts", fact[:180])
        self.save()

    def add_note(self, text: str) -> None:
        self.notes.append({"text": text[:400], "ts": datetime.now().isoformat(timespec="seconds")})
        self.notes = self.notes[-40:]
        self.save()

    def list_notes(self) -> str:
        if not self.notes:
            return "Nenhuma nota guardada, senhor."
        items = "; ".join(n.get("text", "") for n in self.notes[-8:])
        return f"Notas: {items}"

    def add_todo(self, text: str) -> None:
        self.todos.append({"text": text[:240], "done": False})
        self.todos = self.todos[-40:]
        self.save()

    def list_todos(self) -> str:
        open_ = [t["text"] for t in self.todos if not t.get("done")]
        if not open_:
            return "Nenhuma tarefa pendente, senhor."
        return "Tarefas: " + "; ".join(open_[-12:])

    def complete_todo(self, query: str) -> str | None:
        q = query.lower().strip()
        for t in reversed(self.todos):
            if not t.get("done") and q in t.get("text", "").lower():
                t["done"] = True
                self.save()
                return t["text"]
        return None

    def add_reminder(self, text: str, at: datetime) -> None:
        self.reminders.append(
            {"text": text[:240], "at": at.isoformat(timespec="seconds"), "done": False}
        )
        self.reminders = self.reminders[-40:]
        self.save()

    def list_reminders(self) -> str:
        pending = [r for r in self.reminders if not r.get("done")]
        if not pending:
            return "Nenhum lembrete pendente, senhor."
        bits = []
        for r in pending[-8:]:
            try:
                when = datetime.fromisoformat(r["at"]).strftime("%H:%M")
            except (KeyError, ValueError):
                when = "?"
            bits.append(f"{when} {r.get('text', '')}")
        return "Lembretes: " + "; ".join(bits)

    def clear_reminders(self) -> int:
        n = sum(1 for r in self.reminders if not r.get("done"))
        for r in self.reminders:
            r["done"] = True
        self.save()
        return n

    def pop_due(self) -> list[dict]:
        now = datetime.now()
        due: list[dict] = []
        for r in self.reminders:
            if r.get("done"):
                continue
            try:
                at = datetime.fromisoformat(r["at"])
            except (KeyError, ValueError):
                continue
            if at <= now:
                r["done"] = True
                due.append(r)
        if due:
            self.save()
        return due

    def recall_speech(self) -> str:
        if not self.count():
            return "Ainda não guardei fatos sobre o senhor. Diga «lembre que…»."
        return self.render().replace(
            "Memória local do senhor (use para tom e preferências):",
            "O que sei do senhor:",
        )
