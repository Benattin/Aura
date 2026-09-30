from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from aura.config import data_dir

_CODE_EXT = (
    r"py|js|ts|tsx|jsx|json|md|txt|html|css|yaml|yml|toml|ini|cfg|"
    r"rs|go|java|sql|c|cpp|h|hpp|cs|rb|php|sh|bat|ps1|xml|env"
)

_LIST = re.compile(
    r"\b(list[ae]|mostr[ae])\s+(?:os\s+)?(?:projetos|pastas|arquivos)\s+"
    r"(?:da\s+aura|do\s+workspace|de\s+c[oó]digo|no\s+workspace)\b",
    re.I,
)
_IN_AURA = re.compile(r"\b(na\s+aura|no\s+workspace|workspace\s+da\s+aura|dentro\s+da\s+aura)\b", re.I)
_CREATE = re.compile(
    r"\b(cri[ae]|fa[cç]a|faz|nova|mont[ae]|inici[ae]|ger[ae]|escrev[ae]|salv[ae]|armazen[ae]|desenvolv\w*)\b",
    re.I,
)
_MAKE_SITE = re.compile(
    r"\b(?:quero\s+que\s+(?:voc[eê]|vc)\s+)?"
    r"(?:fa[cç]a|cri[ae]|mont[ae]|desenvolv\w*)\s+"
    r"(?:um[a]?\s+)?(?:projeto\s+)?(?:de\s+)?(?:um[a]?\s+)?"
    r"(?:site|aplicativo|app|sistema|portal|web|website|p[aá]gina(?:\s+web)?)\b",
    re.I,
)
_THEME = re.compile(
    r"\b(?:tema|tem[aá]tica)\s+(?:de\s+)?(?P<theme>[\w][\w\s\-]{1,48})",
    re.I,
)
_CREATE_PROJECT = re.compile(
    r"\b(?:cri[ae]|nova|mont[ae]|inici[ae])\s+(?:um[a]?\s+|o\s+|a\s+)?"
    r"(?:pasta|projeto|diret[oó]rio|workspace|reposit[oó]rio)\s+"
    r"(?:de\s+c[oó]digo\s+|chamad[oa]\s+|nome\s+|denominad[oa]\s+)?"
    r"(?P<name>[\w][\w\-]*)",
    re.I,
)
_PROJECT_REF = re.compile(
    r"\b(?:no|na|em|do|da)\s+(?:projeto|pasta|workspace|diret[oó]rio)\s+"
    r"(?P<project>[\w][\w\-]*)",
    re.I,
)
_FILE_HINT = re.compile(
    rf"\b(?:arquivo\s+)?(?P<file>[\w./\\-]+\.(?:{_CODE_EXT}))\b",
    re.I,
)
_FILE_BLOCK = re.compile(
    r"(?:###\s*FILE:\s*|#\s*file:\s*|//\s*file:\s*)(?P<path>[^\n`]+)\s*"
    rf"\n```[\w]*\n(?P<body>.*?)```",
    re.I | re.S,
)
_FOLDER_ONLY = re.compile(
    r"\b(?:cri[ae]|nova|mont[ae]|inici[ae])\s+(?:um[a]?\s+|o\s+|a\s+)?"
    r"(?:pasta|projeto|diret[oó]rio)\b",
    re.I,
)

WORKSPACE_PROMPT = (
    "\nQuando o senhor pedir código para o workspace da AURA, responda SOMENTE com blocos:\n"
    "### FILE: caminho/relativo.ext\n"
    "```linguagem\n"
    "conteúdo\n"
    "```\n"
    "Inclua todos os arquivos necessários. Sem explicação fora dos blocos FILE."
)


@dataclass
class WorkspaceRequest:
    project: str = ""
    files: list[str] = field(default_factory=list)
    folder_only: bool = False
    list_only: bool = False


def workspace_dir() -> Path:
    p = data_dir() / "workspace"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _active_file() -> Path:
    return workspace_dir() / ".active_project"


def set_active_project(name: str) -> None:
    clean = _safe_segment(name)
    if clean:
        _active_file().write_text(clean, encoding="utf-8")


def active_project() -> str:
    path = _active_file()
    if path.exists():
        name = path.read_text(encoding="utf-8").strip()
        if name and (workspace_dir() / name).is_dir():
            return name
    projects = list_projects()
    return projects[-1] if projects else ""


def _safe_segment(name: str) -> str:
    name = (name or "").strip().strip("\"'")
    name = re.sub(r'[<>:"|?*\\/]', "_", name)
    name = re.sub(r"\s+", "-", name.strip(". "))
    return (name[:80] or "projeto").lower()


def _guard(project: str, rel: str = "") -> Path:
    proj = _safe_segment(project)
    if not proj:
        raise ValueError("nome de projeto inválido")
    root = workspace_dir() / proj
    ws = workspace_dir().resolve()
    if rel:
        rel_path = Path(rel.replace("\\", "/"))
        if rel_path.is_absolute() or ".." in rel_path.parts:
            raise ValueError("caminho inválido")
        target = (root / rel_path).resolve()
    else:
        target = root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    if not str(target).startswith(str(ws)):
        raise ValueError("fora do workspace")
    return target


def create_project(name: str) -> Path:
    path = _guard(name)
    path.mkdir(parents=True, exist_ok=True)
    return path


def create_folder(project: str, folder: str = "") -> Path:
    path = _guard(project, folder) if folder else _guard(project)
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_file(project: str, rel_path: str, content: str) -> Path:
    path = _guard(project, rel_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def list_projects() -> list[str]:
    root = workspace_dir()
    return sorted(p.name for p in root.iterdir() if p.is_dir())


def list_files(project: str) -> list[str]:
    base = _guard(project)
    if not base.exists():
        return []
    out: list[str] = []
    for p in base.rglob("*"):
        if p.is_file():
            out.append(p.relative_to(base).as_posix())
    return sorted(out)


def _project_from_theme(text: str) -> str:
    if m := _THEME.search(text):
        return _safe_segment(m.group("theme"))
    if m := _MAKE_SITE.search(text):
        return "site"
    return ""


def wants_workspace(text: str) -> bool:
    t = text.strip()
    if len(t) < 4:
        return False
    if _LIST.search(t):
        return True
    if _CREATE_PROJECT.search(t):
        return True
    if _MAKE_SITE.search(t):
        return True
    if _PROJECT_REF.search(t) and _CREATE.search(t):
        return True
    if _IN_AURA.search(t) and _CREATE.search(t):
        return True
    if re.search(r"\bfa[cç]a\b", t, re.I) and re.search(
        r"\b(projeto|site|aplicativo|app|sistema|portal|web|website)\b", t, re.I
    ):
        return True
    if re.search(r"\b(projeto|pasta)\s+[\w\-]+\s+com\b", t, re.I) and re.search(
        rf"\.(?:{_CODE_EXT})\b", t, re.I
    ):
        return True
    return False


def parse_request(text: str) -> WorkspaceRequest | None:
    t = text.strip()
    if not t:
        return None
    if _LIST.search(t):
        return WorkspaceRequest(list_only=True)
    project = ""
    if m := _CREATE_PROJECT.search(t):
        project = _safe_segment(m.group("name"))
    elif m := _PROJECT_REF.search(t):
        project = _safe_segment(m.group("project"))
    elif _MAKE_SITE.search(t):
        project = _project_from_theme(t) or "site"
    files = [m.group("file").replace("\\", "/") for m in _FILE_HINT.finditer(t)]
    folder_only = bool(project and _FOLDER_ONLY.search(t) and not files and not re.search(
        rf"\b(?:fun[cç][aã]o|script|implement|programa|api|app)\b", t, re.I
    ))
    if not project and not files and not _LIST.search(t):
        return None
    return WorkspaceRequest(project=project, files=files, folder_only=folder_only)


def extract_files_from_llm(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for m in _FILE_BLOCK.finditer(text):
        rel = m.group("path").strip().replace("\\", "/").lstrip("/")
        body = m.group("body").rstrip()
        if rel and body:
            out[rel] = body + ("\n" if not body.endswith("\n") else "")
    if out:
        return out
    blocks = re.findall(r"```[\w]*\n(.*?)```", text, re.S)
    if len(blocks) == 1 and blocks[0].strip():
        return {"main.py": blocks[0].rstrip() + "\n"}
    return out


def apply_workspace(user_text: str, llm_output: str) -> tuple[bool, str]:
    req = parse_request(user_text)
    if req and req.list_only:
        projects = list_projects()
        if not projects:
            return True, "O workspace da AURA ainda está vazio, senhor."
        lines = "\n".join(f"• {name}" for name in projects)
        return True, f"Projetos no workspace:\n{lines}"

    files = extract_files_from_llm(llm_output)
    project = (req.project if req else "") or "projeto"
    hinted = req.files if req else []

    if not files and llm_output.strip():
        if hinted:
            files = {hinted[0]: llm_output.strip() + "\n"}
        elif len(hinted) == 0 and re.search(rf"\.(?:{_CODE_EXT})\b", user_text, re.I):
            m = _FILE_HINT.search(user_text)
            fname = m.group("file").replace("\\", "/") if m else "main.py"
            files = {fname: llm_output.strip() + "\n"}

    if req and req.folder_only and not files:
        path = create_project(project)
        set_active_project(project)
        return True, f"Pasta do projeto «{project}» criada em {path}, senhor."

    if not files:
        return False, "Não identifiquei arquivos para salvar no workspace, senhor."

    create_project(project)
    set_active_project(project)
    saved: list[str] = []
    for rel, body in files.items():
        path = write_file(project, rel, body)
        saved.append(path.relative_to(workspace_dir()).as_posix())

    if len(saved) == 1:
        return True, f"Arquivo salvo no projeto «{project}»: {workspace_dir() / saved[0]}, senhor."
    listing = ", ".join(saved)
    return True, f"{len(saved)} arquivos salvos no projeto «{project}»: {listing}"


def workspace_summary() -> str:
    projects = list_projects()
    if not projects:
        return str(workspace_dir())
    return f"{workspace_dir()} ({len(projects)} projetos)"
