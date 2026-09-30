from __future__ import annotations
import ast
import operator
import re
from datetime import datetime, timedelta

from aura.memory import Memory

_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.Pow: operator.pow, ast.USub: operator.neg,
    ast.Mod: operator.mod, ast.FloorDiv: operator.floordiv,
}

_HELP = re.compile(
    r"^(ajuda|comandos|o que (voc[eê]|voce) (faz|sabe fazer|consegue( fazer)?)|"
    r"quais (s[aã]o )?seus (comandos|recursos))\s*[?.!]?$",
    re.I,
)
_RECALL = re.compile(
    r"^(o que (voc[eê]|voce) (sabe|lembra)( de mim)?|minha mem[oó]ria|"
    r"o que (voc[eê]|voce) aprendeu)\s*[?.!]?$",
    re.I,
)
_REMEMBER = re.compile(
    r"^(?:lembr[ea]\s+que|guarde(?:\s+na\s+mem[oó]ria)?\s+que|"
    r"anote\s+na\s+mem[oó]ria\s+que)\s+(?P<q>.+)$",
    re.I,
)
_NOTE_ADD = re.compile(
    r"^(?:anot[ae]|cria(?:\s+uma)?\s+nota|salva(?:\s+uma)?\s+nota)\s+(?P<q>.+)$",
    re.I,
)
_NOTE_LIST = re.compile(r"^(minhas\s+notas|l[eê]\s+as\s+notas|lista\s+de\s+notas)\s*[?.!]?$", re.I)
_TODO_ADD = re.compile(
    r"^(?:adicion[ae]|p[oô]e|coloca)\s+(?:na\s+lista|na\s+tarefa|às\s+tarefas|nas\s+tarefas)\s+(?P<q>.+)$"
    r"|^(?:tarefa|to-?do)\s*[:\-]\s*(?P<q2>.+)$",
    re.I,
)
_TODO_LIST = re.compile(
    r"^(minhas\s+tarefas|o\s+que\s+tenho\s+pra\s+fazer|lista\s+de\s+tarefas)\s*[?.!]?$",
    re.I,
)
_TODO_DONE = re.compile(
    r"^(?:marca|conclu[ia]|risca)\s+(?:a\s+tarefa\s+)?(?P<q>.+?)(?:\s+como\s+feito)?$",
    re.I,
)
_REMIND_AFTER = re.compile(
    r"(?:me\s+)?lembr[ea](?:-me)?(?:\s+de)?\s+(?P<q>.+?)\s+"
    r"(?:em|daqui(?:\s+a)?)\s+(?P<n>\d+)\s+(?P<u>minutos?|min|horas?|h|segundos?|seg)\s*$",
    re.I,
)
_REMIND_IN = re.compile(
    r"(?:me\s+)?lembr[ea](?:-me)?\s+(?:em|daqui(?:\s+a)?)\s+(?P<n>\d+)\s+"
    r"(?P<u>minutos?|min|horas?|h|segundos?|seg)\s+(?:de\s+|para\s+|que\s+)?(?P<q>.+)$",
    re.I,
)
_REMIND_AT = re.compile(
    r"(?:me\s+)?lembr[ea](?:-me)?\s+(?:às|as)\s+(?P<h>\d{1,2})(?:[:h](?P<m>\d{2}))?\s+"
    r"(?:de\s+|para\s+|que\s+)?(?P<q>.+)$",
    re.I,
)
_TIMER = re.compile(
    r"^(?:timer|cron[oô]metro|alarme)\s+(?:de\s+)?(?P<n>\d+)\s+"
    r"(?P<u>minutos?|min|horas?|h|segundos?|seg)\s*$",
    re.I,
)
_REMIND_LIST = re.compile(r"^(meus\s+lembretes|o que (voc[eê]|voce) vai me lembrar)\s*[?.!]?$", re.I)
_REMIND_CANCEL = re.compile(r"^(cancela|cancele|apaga)\s+(os\s+)?lembretes\s*$", re.I)
_CLIP_GET = re.compile(
    r"(o que (tem|est[áa]|eu copiei)|l[eê]|mostra).{0,24}"
    r"(área de transfer[eê]ncia|area de transferencia|clipboard)"
    r"|^(área de transfer[eê]ncia|clipboard)\s*[?.!]?$",
    re.I,
)
_CLIP_COPY = re.compile(
    r"copia\s+(isso|a resposta|o (que|último|ultimo) (que )?(voc[eê]|voce) (disse|falou))",
    re.I,
)
_CLIP_LLM = re.compile(
    r"(analis[ea]|explica|resum[ae]|traduz).{0,28}"
    r"(área de transfer[eê]ncia|area de transferencia|o que (eu )?copiei|clipboard)",
    re.I,
)
_CALC = re.compile(r"^(quanto [eé]|calcul[ea]|calcule)\s+(?P<q>.+)$", re.I)
_BATTERY = re.compile(r"\b(bateria|carga do (notebook|pc|laptop))\b", re.I)
_BRIEF = re.compile(
    r"^(bom dia|boa tarde|boa noite|resumo( do dia)?|o que tenho pra hoje|briefing)\s*[!.]?$",
    re.I,
)
_HELP_TEXT = (
    "Senhor, eu fico neste PC. Posso: conversar e calcular; lembrar fatos, notas, "
    "tarefas e alarmes; ler a área de transferência; olhar a tela; anexar ou abrir e analisar "
    "arquivos fora da pasta AURA; escrever e corrigir código sem restrição de tema; abrir apps, pastas, Gmail, mapas, calendário e sites; "
    "música, volume, clima, hora e captura de tela. Diga «lembre que…», «anota…», "
    "«me lembre em 10 minutos de…», «resumo do dia» ou use Histórico. Não apago arquivos nem desligo "
    "o Windows sem o senhor confirmar."
)


def wants_clip_help(text: str) -> bool:
    return bool(_CLIP_LLM.search(text.strip()))


def clip_prompt(user_text: str, clip: str) -> str:
    return (
        f"Pedido do senhor: {user_text.strip()}\n"
        "Conteúdo da área de transferência:\n---\n"
        f"{clip}\n---\n"
        "Use só esse texto. Explique ou resolva o que foi pedido."
    )


def handle(text: str, mem: Memory, *, last_reply: str = "") -> str | None:
    t = text.strip()
    if not t:
        return None
    if _HELP.match(t):
        return _HELP_TEXT
    if _RECALL.match(t):
        return mem.recall_speech()
    if m := _REMEMBER.match(t):
        q = m.group("q").strip()
        mem.remember(q)
        return f"Guardei: {q}"
    if _NOTE_LIST.match(t):
        return mem.list_notes()
    if m := _NOTE_ADD.match(t):
        q = m.group("q").strip()
        mem.add_note(q)
        return f"Anotado: {q}"
    if _TODO_LIST.match(t):
        return mem.list_todos()
    if m := _TODO_ADD.match(t):
        q = (m.group("q") or m.group("q2") or "").strip()
        mem.add_todo(q)
        return f"Entrou na lista: {q}"
    if m := _TODO_DONE.match(t):
        hit = mem.complete_todo(m.group("q").strip())
        return f"Marquei como feito: {hit}" if hit else "Não achei essa tarefa na lista."
    if _REMIND_LIST.match(t):
        return mem.list_reminders()
    if _REMIND_CANCEL.match(t):
        n = mem.clear_reminders()
        return f"Cancelei {n} lembrete(s), senhor." if n else "Não havia lembretes."
    if m := _TIMER.match(t):
        at, label = _when(m.group("n"), m.group("u"), "o timer")
        mem.add_reminder(label, at)
        return f"Timer às {at.strftime('%H:%M:%S')}."
    if m := _REMIND_IN.match(t) or _REMIND_AFTER.match(t):
        at, _ = _when(m.group("n"), m.group("u"), m.group("q"))
        q = m.group("q").strip()
        mem.add_reminder(q, at)
        return f"Lembro o senhor às {at.strftime('%H:%M')} de {q}."
    if m := _REMIND_AT.match(t):
        at = _today_at(int(m.group("h")), int(m.group("m") or 0))
        q = m.group("q").strip()
        mem.add_reminder(q, at)
        return f"Lembro o senhor às {at.strftime('%H:%M')} de {q}."
    if _CLIP_COPY.search(t):
        if not last_reply.strip():
            return "Ainda não tenho uma resposta para copiar, senhor."
        set_clipboard(last_reply)
        return "Copiei a última resposta, senhor."
    if _CLIP_GET.search(t):
        clip = get_clipboard()
        return clip[:1500] if clip.strip() else "A área de transferência está vazia, senhor."
    if m := _CALC.match(t):
        return _calc(m.group("q"))
    if _BATTERY.search(t):
        return battery_speech()
    if _BRIEF.match(t):
        return briefing(mem)
    return None


def _when(n: str, unit: str, text: str) -> tuple[datetime, str]:
    k = int(n)
    u = unit.lower()
    delta = timedelta(minutes=k)
    if u.startswith("hora") or u == "h":
        delta = timedelta(hours=k)
    elif u.startswith("seg"):
        delta = timedelta(seconds=k)
    at = datetime.now() + delta
    return at, text.strip()


def _today_at(hour: int, minute: int) -> datetime:
    now = datetime.now()
    at = now.replace(hour=hour % 24, minute=minute, second=0, microsecond=0)
    if at <= now:
        at += timedelta(days=1)
    return at


def _eval_node(node: ast.AST) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval_node(node.operand))
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval_node(node.left), _eval_node(node.right))
    raise ValueError("expressão inválida")


def _calc(raw: str) -> str:
    expr = raw.lower()
    expr = expr.replace("mais", "+").replace("menos", "-")
    expr = expr.replace("vezes", "*").replace("x", "*")
    expr = re.sub(r"dividido\s+por", "/", expr)
    expr = re.sub(r"[^0-9+\-*/().%\s]", "", expr)
    if not expr.strip():
        return "Não entendi a conta, senhor."
    try:
        tree = ast.parse(expr, mode="eval")
        val = _eval_node(tree.body)
    except (SyntaxError, ValueError, ZeroDivisionError, OverflowError):
        return "Não consegui calcular isso, senhor."
    if val == int(val):
        val = int(val)
    return f"Dá {val}, senhor."


def get_clipboard() -> str:
    try:
        import win32clipboard
        win32clipboard.OpenClipboard()
        try:
            return str(win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT) or "")
        finally:
            win32clipboard.CloseClipboard()
    except Exception:
        return ""


def set_clipboard(text: str) -> None:
    try:
        import win32clipboard
        win32clipboard.OpenClipboard()
        try:
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardText(text, win32clipboard.CF_UNICODETEXT)
        finally:
            win32clipboard.CloseClipboard()
    except Exception:
        pass


def battery_speech() -> str:
    try:
        import ctypes

        class STATUS(ctypes.Structure):
            _fields_ = [
                ("ACLineStatus", ctypes.c_byte),
                ("BatteryFlag", ctypes.c_byte),
                ("BatteryLifePercent", ctypes.c_byte),
                ("SystemStatusFlag", ctypes.c_byte),
                ("BatteryLifeTime", ctypes.c_ulong),
                ("BatteryFullLifeTime", ctypes.c_ulong),
            ]

        st = STATUS()
        if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(st)):
            return "Não consegui ler a bateria, senhor."
        pct = int(st.BatteryLifePercent)
        if pct > 100:
            return "Este PC não reporta bateria, senhor."
        plug = "na tomada" if st.ACLineStatus == 1 else "no modo bateria"
        return f"Bateria em {pct} por cento, {plug}."
    except Exception:
        return "Não consegui ler a bateria, senhor."


def briefing(mem: Memory) -> str:
    now = datetime.now()
    parts = [f"São {now.strftime('%H:%M')} de {now.strftime('%d/%m/%Y')}."]
    bat = battery_speech()
    if "por cento" in bat:
        parts.append(bat)
    parts.append(mem.list_todos())
    parts.append(mem.list_reminders())
    notes = mem.list_notes()
    if not notes.startswith("Nenhuma"):
        parts.append(notes)
    return " ".join(parts)
