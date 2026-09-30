from __future__ import annotations
import base64
import re
from datetime import datetime
from pathlib import Path

from aura.config import data_dir
from aura.readers import SUPPORTED, BINARY_EXT, ReadResult, read_bytes, read_path
from aura.skills import resolve_existing, search_files

_HELP = re.compile(
    r"\b(leia|lê|ler|analis[ea]|analise|abre|abra|abrir|mostra|mostre|exiba|veja|"
    r"corrija|corrige|conserta|resolv[ae]|debug(?:ue|ar)?|explica|revis[ea]|"
    r"procure|procura|encontre|encontra|ache|busque|busca|"
    r"o\s+que\s+(h[áa]|tem)\s+de\s+errado)\b",
    re.I,
)
_NAME = re.compile(
    r"([a-zA-Z]:[\\/][^\s\"']+\.[A-Za-z0-9]+"
    r"|[^\s\"']+\.(?:py|txt|md|json|csv|log|toml|ya?ml|js|ts|tsx|css|html|xml|ini|cfg|ps1|bat|rs|go|java|sql|c|cpp|h|"
    r"pdf|docx?|xlsx?|pptx?|png|jpe?g|gif|webp|bmp))",
    re.I,
)
_QUOTED = re.compile(r"[\"']([^\"']{2,260})[\"']")
_AFTER = re.compile(
    r"(?:leia|lê|ler|analis[ea]|abre|abra|abrir|mostra|mostre|corrija|resolv[ae]|conserta|"
    r"explica|revis[ea]|procure|procura|encontre|encontra|ache|busque|busca)\s+"
    r"(?:o\s+|a\s+|um\s+|uma\s+)?(?:arquivo\s+|imagem\s+|c[oó]digo\s+)?(?:chamado\s+)?(.+)$",
    re.I,
)
_EXT = re.compile(
    r"\.(py|txt|md|json|csv|log|toml|ya?ml|js|ts|tsx|css|html|xml|ini|cfg|ps1|bat|rs|go|java|sql|c|cpp|h|"
    r"pdf|docx?|xlsx?|pptx?|png|jpe?g|gif|webp|bmp)\b",
    re.I,
)
READABLE = SUPPORTED
_CODE = re.compile(
    r"(escrev[ae]|cri[ae]|implement|corrig[ea]|debug|refator|otimiz|"
    r"fun[cç][aã]o|algoritm|script|programa|typeerror|syntaxerror|"
    r"\b(python|javascript|typescript|golang|rust|java|sql|html|css|react|node|php|ruby|kotlin)\b|"
    r"como (fa[cç]o|fazer).{0,48}(c[oó]digo|programa|fun[cç][aã]o)|"
    r"erro (de |no |na )?(compila|sintaxe|type|null)|"
    r"```)",
    re.I,
)
_DELIVER = re.compile(
    r"\b(cri[ae]|ger[ae]|salv[ae]|export[ae]|escrev\w+|mont[ae]|me\s+entreg\w*|grava)\b",
    re.I,
)
_REMOVE = re.compile(r"\b(apag\w+|remov\w+|exclu\w+|delete|tir\w+)\b", re.I)


def wants_code(text: str) -> bool:
    t = text.strip()
    if len(t) < 4:
        return False
    if re.search(r"\b(tela|youtube|gmail|volume|m[uú]sica|clima|hora)\b", t, re.I):
        return False
    return bool(_CODE.search(t))


def wants_file_help(text: str) -> bool:
    t = text.strip()
    if re.search(r"\b(tela|youtube|gmail|volume|m[uú]sica|musica|pasta\s+de)\b", t, re.I):
        return False
    from aura.docedit import wants_doc_image_edit

    if wants_deliver(text) or wants_remove_file(text) or wants_doc_image_edit(text):
        return False
    if _NAME.search(t) or _QUOTED.search(t) or _AFTER.search(t):
        return True
    if _EXT.search(t) and _HELP.search(t):
        return True
    if re.search(r"\b(arquivo|imagem|código|codigo|pdf|documento)\b", t, re.I) and _HELP.search(t):
        return True
    if re.search(r"[a-zA-Z]:[\\/][^\s]+", t):
        return _HELP.search(t) or bool(_EXT.search(t))
    return False


def wants_deliver(text: str) -> bool:
    t = text.strip()
    if not _DELIVER.search(t):
        return False
    return bool(
        re.search(r"\b(arquivo|documento|pdf|txt|docx?|xlsx?|pptx?|imagem|png|relat[oó]rio|nota|planilha|apresenta[cç][aã]o)\b", t, re.I)
        or re.search(r"\.(txt|md|pdf|docx?|xlsx?|pptx?|png|json|csv)\b", t, re.I)
    )


def wants_remove_file(text: str) -> bool:
    t = text.strip()
    return bool(_REMOVE.search(t) and (file_query(t) or _NAME.search(t)))


def file_query(text: str) -> str:
    if m := re.search(r"([a-zA-Z]:[\\/][^\s\"']+)", text):
        return m.group(1).strip()
    if m := _QUOTED.search(text):
        return m.group(1).strip()
    if m := _NAME.search(text):
        return m.group(1).strip()
    if m := _AFTER.search(text):
        q = m.group(1).strip().strip("\"'")
        q = re.sub(r"^(o\s+|a\s+|arquivo\s+|imagem\s+|c[oó]digo\s+|chamado\s+)", "", q, flags=re.I)
        return q.strip()
    return ""


def output_dir() -> Path:
    p = data_dir() / "output"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _safe_name(name: str) -> str:
    name = Path(name.replace("\\", "/")).name.strip() or "aura_entrega.txt"
    name = re.sub(r'[<>:"|?*]', "_", name)
    return name[:120]


def deliver_text(name: str, content: str) -> Path:
    path = output_dir() / _safe_name(name)
    path.write_text(content, encoding="utf-8")
    return path


def deliver_bytes(name: str, data: bytes) -> Path:
    path = output_dir() / _safe_name(name)
    path.write_bytes(data)
    return path


def remove_named_file(text: str) -> tuple[bool, str]:
    q = file_query(text) or ""
    if not q:
        return False, "Qual arquivo o senhor quer remover? Diga o nome ou caminho."
    direct = resolve_existing(q)
    if direct:
        target = direct
    else:
        hits = [p for p in search_files(q) if p.is_file()]
        if not hits:
            out = output_dir() / _safe_name(q)
            if out.exists():
                target = out
            else:
                return False, f"Não encontrei {q}."
        else:
            target = hits[0]
    out_root = output_dir().resolve()
    try:
        resolved = target.resolve()
    except OSError:
        return False, f"Não consegui acessar {target.name}."
    if not resolved.is_file():
        return False, f"{resolved.name} não é um arquivo."
    allowed = resolved == out_root / resolved.name or str(resolved).startswith(str(out_root))
    if not allowed:
        return False, "Por segurança só removo arquivos em D:\\AURA\\data\\output, senhor."
    try:
        resolved.unlink()
    except OSError as exc:
        return False, f"Não consegui remover: {exc}"
    return True, f"Removi {resolved.name}, senhor."


def read_for_help(text: str) -> ReadResult:
    q = file_query(text)
    if len(q) < 2:
        return ReadResult(
            Path("arquivo"),
            note="Qual arquivo o senhor quer? Pode colar o caminho, tipo D:\\pasta\\arquivo.pdf",
        )
    direct = resolve_existing(q)
    hits = [direct] if direct else search_files(q)
    hits = [p for p in hits if p.is_file()]
    if not hits:
        return ReadResult(Path(q), note=f"Não encontrei {q} no PC.")
    return read_path(hits[0])


def from_attachment(name: str, content: str) -> ReadResult:
    ext = Path(name).suffix.lower()
    if ext in BINARY_EXT:
        return ReadResult(
            Path(name),
            note=(
                f"{Path(name).name} é binário. Use o botão Arquivo na interface "
                "(não cole o conteúdo no chat)."
            ),
        )
    raw = (content or "").encode("utf-8", errors="replace")
    return read_bytes(name, raw)


def from_attachment_b64(name: str, data_b64: str) -> ReadResult:
    try:
        raw = base64.b64decode(data_b64, validate=False)
    except Exception:
        return ReadResult(Path(name), note="Anexo corrompido, senhor.")
    return read_bytes(name, raw)


_DOC_LIMIT = 0  # 0 = sem truncar documentos no contexto


def solve_prompt(user_text: str, path: Path, content: str, *, kind: str = "text") -> str:
    label = {"image": "Imagem analisada", "document": "Documento", "text": "Arquivo"}.get(kind, "Arquivo")
    body = content.strip()
    if not body:
        return f"Pedido: {user_text.strip()}\nArquivo {path.name} veio sem texto legível."
    if kind == "document" and _DOC_LIMIT > 0 and len(body) > _DOC_LIMIT:
        body = body[:_DOC_LIMIT] + "\n\n[conteúdo truncado para caber no contexto]"
    return (
        f"TEXTO EXTRAÍDO DE «{path.name}»:\n{body}\n\n"
        f"PEDIDO: {user_text.strip()}\n"
        "Responda em português usando somente o texto acima."
    )


def deliver_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")
