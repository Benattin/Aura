from __future__ import annotations
from datetime import datetime
from pathlib import Path
import ctypes
import os
import re
import subprocess
import webbrowser
from urllib.parse import quote_plus

from aura.config import ROOT

HOME = Path.home()
SKIP_DIRS = {
    "appdata", "application data", "node_modules", ".git", "__pycache__",
    ".venv", "venv", ".cache", "windows", "$recycle.bin", "temp", "tmp",
    "program files", "program files (x86)", "programdata", "system volume information",
}
_PROJECT = ROOT.resolve()


def _is_inside_project(path: Path) -> bool:
    try:
        path.resolve().relative_to(_PROJECT)
        return True
    except (ValueError, OSError):
        return False


def search_roots() -> list[Path]:
    roots: list[Path] = [
        HOME / "Desktop",
        HOME / "Documents",
        HOME / "Downloads",
        HOME / "Music",
        HOME / "Videos",
        HOME / "Pictures",
        HOME / "OneDrive",
        Path(r"C:\Users\Public"),
    ]
    for letter in "DEFGHIJKLMNOPQRSTUVWXYZ":
        drive = Path(f"{letter}:/")
        if drive.exists():
            roots.append(drive)
    roots.append(HOME)
    seen: set[Path] = set()
    out: list[Path] = []
    for r in roots:
        try:
            key = r.resolve()
        except OSError:
            continue
        if not r.exists() or key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def _score_name(fn: str, needle: str) -> int:
    fn_low = fn.lower()
    if fn_low == needle:
        return 100
    if fn_low.endswith(needle) and needle.startswith("."):
        return 90
    stem = Path(fn_low).stem
    if stem == needle or stem == Path(needle).stem:
        return 80
    if needle in fn_low:
        return 50
    return 0


def _walk_hits(name: str, roots: list[Path], *, limit: int, deadline: float, skip_project: bool) -> list[Path]:
    hits: list[tuple[int, Path]] = []
    needle = name.lower()
    for root in roots:
        try:
            for dirpath, dirnames, filenames in os.walk(root):
                if datetime.now().timestamp() > deadline or len(hits) >= limit * 3:
                    dirnames[:] = []
                    break
                here = Path(dirpath)
                if skip_project and _is_inside_project(here):
                    dirnames[:] = []
                    continue
                dirnames[:] = [
                    d for d in dirnames
                    if d.lower() not in SKIP_DIRS
                    and not (skip_project and _is_inside_project(here / d))
                ]
                for fn in filenames:
                    score = _score_name(fn, needle)
                    if score > 0:
                        hits.append((score, here / fn))
                hits.sort(key=lambda x: (-x[0], str(x[1]).lower()))
                if len(hits) >= limit:
                    break
        except OSError:
            continue
        if len(hits) >= limit:
            break
    return [p for _, p in hits[:limit]]


def search_files(name: str, *, limit: int = 12, seconds: float = 6.0) -> list[Path]:
    needle = name.lower().strip().replace("/", "\\")
    if "\\" in needle or (len(needle) >= 2 and needle[1] == ":"):
        direct = resolve_existing(name)
        return [direct] if direct else []
    if len(needle) < 2:
        return []
    deadline = datetime.now().timestamp() + seconds
    roots = search_roots()
    outside = _walk_hits(needle, roots, limit=limit, deadline=deadline, skip_project=True)
    if outside:
        return outside
    return _walk_hits(needle, [_PROJECT], limit=limit, deadline=deadline, skip_project=False)


def resolve_existing(raw: str) -> Path | None:
    t = os.path.expandvars(os.path.expanduser(raw.strip().strip("\"'")))
    p = Path(t)
    try:
        if p.is_file():
            return p.resolve()
        parent = p.parent
        if parent.is_dir() and p.name and (parent / p.name).is_file():
            return (parent / p.name).resolve()
    except OSError:
        return None
    return None

APPS = {
    "edge": ["msedge"],
    "chrome": ["chrome"],
    "firefox": ["firefox"],
    "navegador": ["msedge"],
    "notepad": ["notepad"],
    "bloco de notas": ["notepad"],
    "calculadora": ["calc"],
    "explorer": ["explorer"],
    "explorador": ["explorer"],
    "spotify": ["spotify"],
    "discord": ["discord"],
    "vscode": ["code"],
    "cursor": ["cursor"],
    "word": ["winword"],
    "excel": ["excel"],
    "paint": ["mspaint"],
    "cmd": ["cmd"],
    "terminal": ["wt"],
    "outlook": ["outlook"],
    "whatsapp": ["whatsapp:"],
    "configurações": ["ms-settings:"],
    "configuracoes": ["ms-settings:"],
}

_USER32 = ctypes.WinDLL("user32", use_last_error=True)
_KEYUP = 0x0002
_EXT = 0x0001
VK_PLAY = 0xB3
VK_NEXT = 0xB0
VK_PREV = 0xB1
VK_STOP = 0xB2
VK_VOL_UP = 0xAF
VK_VOL_DOWN = 0xAE
VK_MUTE = 0xAD


def dispatch(text: str) -> str | None:
    raw = text.strip()
    t = _norm(raw)
    if not t:
        return None
    for rx, fn in _ROUTES:
        m = rx.search(t)
        if m:
            return fn(m, raw)
    return None


def _norm(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"^(aura[,:\s]+|olá aura[,:\s]+|ola aura[,:\s]+|hey aura[,:\s]+)", "", s)
    return s.strip()


def _tap(vk: int) -> None:
    _USER32.keybd_event(vk, 0, _EXT, 0)
    _USER32.keybd_event(vk, 0, _EXT | _KEYUP, 0)


def _start(*args: str) -> None:
    subprocess.Popen(["cmd", "/c", "start", "", *args], shell=False)


def _open_app(_m: re.Match, raw: str) -> str:
    name = _m.group("app").strip()
    cmd = APPS.get(name)
    if not cmd:
        return f"Não reconheço o aplicativo {name}, senhor."
    try:
        if cmd[0].startswith("ms-") or cmd[0].endswith(":"):
            os.startfile(cmd[0])
        else:
            _start(*cmd)
        return f"Abrindo {name}, senhor."
    except OSError:
        return f"Não consegui abrir {name}, senhor."


def _open_url(_m: re.Match, raw: str) -> str:
    url = _m.group("url").strip()
    if not re.match(r"^https?://", url):
        url = "https://" + url
    webbrowser.open(url)
    return "Abrindo no navegador, senhor."


def _open_browser(_m: re.Match, raw: str) -> str:
    webbrowser.open("https://www.bing.com")
    return "Abrindo o navegador, senhor."


def _web_search(_m: re.Match, raw: str) -> str:
    q = (_m.group("q") or "").strip()
    if not q:
        return "O que o senhor deseja pesquisar?"
    webbrowser.open("https://www.bing.com/search?q=" + quote_plus(q))
    return f"Pesquisando {q}, senhor."


def _youtube(m: re.Match, raw: str) -> str:
    q = ""
    if "q" in m.re.groupindex:
        q = (m.group("q") or "").strip()
        q = re.sub(r"^(o\s+|a\s+|no\s+)", "", q)
    if q:
        webbrowser.open("https://www.youtube.com/results?search_query=" + quote_plus(q))
        return f"Abrindo o YouTube com {q}, senhor."
    webbrowser.open("https://www.youtube.com")
    return "Abrindo o YouTube, senhor."


def _play_music(_m: re.Match, raw: str) -> str:
    q = (_m.group("q") or "").strip()
    if q:
        try:
            os.startfile("spotify:search:" + quote_plus(q))
            return f"Buscando {q} no Spotify, senhor."
        except OSError:
            webbrowser.open("https://www.youtube.com/results?search_query=" + quote_plus(q))
            return f"Abrindo {q} no YouTube, senhor."
    music = HOME / "Music"
    try:
        if music.exists():
            os.startfile(music)
        _tap(VK_PLAY)
        return "Colocando a música, senhor."
    except OSError:
        _tap(VK_PLAY)
        return "Dando play, senhor."


def _media(_m: re.Match, raw: str) -> str:
    kind = _m.group("act")
    if "próxim" in kind or "proxima" in kind or "next" in kind:
        _tap(VK_NEXT)
        return "Próxima faixa, senhor."
    if "anter" in kind or "previous" in kind:
        _tap(VK_PREV)
        return "Faixa anterior, senhor."
    if "paus" in kind or "pare" in kind and "mús" in _norm(raw):
        _tap(VK_PLAY)
        return "Pausando, senhor."
    _tap(VK_PLAY)
    return "Pronto, senhor."


def _volume(_m: re.Match, raw: str) -> str:
    act = _m.group("act")
    if "mut" in act or "silen" in act:
        _tap(VK_MUTE)
        return "Som alterado, senhor."
    if "mais" in act or "aument" in act or "sobe" in act:
        for _ in range(4):
            _tap(VK_VOL_UP)
        return "Aumentando o volume, senhor."
    for _ in range(4):
        _tap(VK_VOL_DOWN)
    return "Diminuindo o volume, senhor."


def _find_files(_m: re.Match, raw: str) -> str:
    name = (_m.group("q") or "").strip().strip("\"'")
    if len(name) < 2:
        return "Qual arquivo o senhor procura?"
    hits = search_files(name)
    if not hits:
        return f"Não encontrei {name} no PC. Passe o caminho completo, tipo C:\\pasta\\arquivo.py"
    try:
        os.startfile(hits[0])
    except OSError:
        return f"Encontrei, mas não consegui abrir {hits[0].name}."
    extra = len(hits) - 1
    if extra:
        return f"Abri {hits[0].name}. Há mais {extra} arquivos parecidos no seu usuário."
    return f"Abri {hits[0].name}, senhor."


def _open_folder(_m: re.Match, raw: str) -> str:
    key = _m.group("folder")
    mapping = {
        "documentos": HOME / "Documents",
        "downloads": HOME / "Downloads",
        "área de trabalho": HOME / "Desktop",
        "area de trabalho": HOME / "Desktop",
        "desktop": HOME / "Desktop",
        "música": HOME / "Music",
        "musica": HOME / "Music",
        "imagens": HOME / "Pictures",
        "vídeos": HOME / "Videos",
        "videos": HOME / "Videos",
    }
    path = mapping.get(key, HOME)
    os.startfile(path)
    return f"Abrindo {key}, senhor."


def _screenshot(_m: re.Match, raw: str) -> str:
    _USER32.keybd_event(0x2C, 0, 0, 0)
    _USER32.keybd_event(0x2C, 0, _KEYUP, 0)
    return "Captura de tela feita, senhor. Está na área de transferência."


def _now(_m: re.Match, raw: str) -> str:
    now = datetime.now()
    return f"São {now.strftime('%H:%M')} de {now.strftime('%d/%m/%Y')}, senhor."


def _weather(_m: re.Match, raw: str) -> str:
    q = ""
    if "q" in _m.re.groupindex:
        q = (_m.group("q") or "").strip()
    query = f"clima {q}".strip() if q else "clima"
    webbrowser.open("https://www.bing.com/search?q=" + quote_plus(query))
    return "Abrindo o clima, senhor."


def _gmail(_m: re.Match, raw: str) -> str:
    webbrowser.open("https://mail.google.com")
    return "Abrindo o Gmail, senhor."


def _maps(_m: re.Match, raw: str) -> str:
    q = (_m.group("q") or "").strip()
    if not q:
        webbrowser.open("https://www.bing.com/maps")
        return "Abrindo o mapa, senhor."
    webbrowser.open("https://www.bing.com/maps?q=" + quote_plus(q))
    return f"Abrindo o mapa de {q}, senhor."


def _calendar(_m: re.Match, raw: str) -> str:
    try:
        _start("outlook", "/select", "outlook:calendar")
        return "Abrindo o calendário, senhor."
    except OSError:
        webbrowser.open("https://calendar.google.com")
        return "Abrindo o calendário no navegador, senhor."


def _translate(_m: re.Match, raw: str) -> str:
    q = ""
    if "q" in _m.re.groupindex:
        q = (_m.group("q") or "").strip()
    if not q:
        webbrowser.open("https://www.bing.com/translator")
        return "Abrindo o tradutor, senhor."
    webbrowser.open("https://www.bing.com/translator?from=auto&to=pt&text=" + quote_plus(q))
    return f"Abrindo a tradução de {q}, senhor."


def _mailto(_m: re.Match, raw: str) -> str:
    to = (_m.group("to") or "").strip()
    if not to:
        os.startfile("mailto:")
        return "Abrindo o e-mail, senhor."
    os.startfile("mailto:" + to)
    return f"Abrindo um e-mail para {to}, senhor."


_ROUTES: list[tuple[re.Pattern[str], callable]] = [
    (re.compile(r"captur(a|e)|print(\s+da)?\s+tela|screenshot"), _screenshot),
    (re.compile(r"volume\s+(?P<act>mais|menos|aument\w*|diminu\w*|sobe|desce|mute|mudo|silen\w*|baixa\w*)"), _volume),
    (re.compile(r"(?P<act>aumenta\w*|diminui\w*|sobe|desce|abaixa\w*|baixa)\s+(o\s+)?volume"), _volume),
    (re.compile(r"(?P<act>próxima|proxima|anterior|pause|pausa|continue)\s+(a\s+)?(música|musica|faixa)?"), _media),
    (re.compile(r"\bplay\s+(a\s+)?(música|musica|faixa)\b"), _media),
    (re.compile(r"\b(toque|toca|ponha|coloque|reproduz\w*)\s+(uma\s+)?(música|musica)\s*(?P<q>.*)$"), _play_music),
    (re.compile(r"^(toque|toca|ponha|coloque|reproduz\w*|play)\s+(uma\s+)?(música|musica)?\s*(?P<q>.+)$"), _play_music),
    (re.compile(r"(música|musica)\s+(do\s+|de\s+)?(?P<q>.+)$"), _play_music),
    (re.compile(r"(abra|abre|abrir).{0,20}youtube\s*(?P<q>.*)$"), _youtube),
    (re.compile(r"youtube(?:\s+de|\s+com)?\s*(?P<q>.*)$"), _youtube),
    (re.compile(r"(que\s+horas|qual\s+(é\s+|e\s+)?a\s+hora|qual\s+(é\s+|e\s+)?a\s+data|que\s+dia\s+(é\s+|e\s+)?hoje)"), _now),
    (re.compile(r"^(o\s+|me\s+(diga|fala)\s+o\s+)?(clima|previsão(\s+do\s+tempo)?|previsao(\s+do\s+tempo)?)(?:\s+(em|de|para)\s+(?P<q>.+))?$"), _weather),
    (re.compile(r"(abra|abre|abrir).{0,12}gmail"), _gmail),
    (re.compile(r"(abra|abre|abrir).{0,16}(o\s+)?calend[aá]rio"), _calendar),
    (re.compile(r"^(traduz(?:a|ir)?|translate)\s+(?P<q>.+)$"), _translate),
    (re.compile(r"(mapa|mapas|como\s+chegar)\s+(de\s+|para\s+|em\s+)?(?P<q>.+)$"), _maps),
    (re.compile(r"(e-?mail|email)\s+(para|pro|pra)\s+(?P<to>\S+)"), _mailto),
    (re.compile(r"(pesquise|pesquisa|google)\s+(por\s+|pelo\s+|pela\s+)?(?P<q>.+)$"), _web_search),
    (re.compile(r"(busca|busque|procure)\s+(no\s+google|na\s+internet|na\s+web)\s+(por\s+)?(?P<q>.+)$"), _web_search),
    (re.compile(r"(procure|encontre|busque|ache)\s+(o\s+|a\s+)?arquivo\s+(chamado\s+)?(?P<q>.+)$"), _find_files),
    (re.compile(r"(abra|abre|abrir)\s+(o\s+|a\s+)?pasta\s+(de\s+|dos\s+|das\s+)?(?P<folder>documentos|downloads|desktop|área de trabalho|area de trabalho|música|musica|imagens|vídeos|videos)"), _open_folder),
    (re.compile(r"(abra|abre|abrir)\s+(o\s+|a\s+)?(?P<app>edge|chrome|firefox|navegador|notepad|bloco de notas|calculadora|explorer|explorador|spotify|discord|vscode|cursor|word|excel|paint|cmd|terminal|outlook|whatsapp|configurações|configuracoes)\b"), _open_app),
    (re.compile(r"(abra|abre|abrir)\s+(o\s+site\s+|a\s+página\s+|a\s+pagina\s+)?(?P<url>(https?://)?[\w.-]+\.[a-z]{2,}[^\s]*)"), _open_url),
    (re.compile(r"(abra|abre)\s+(o\s+)?navegador"), _open_browser),
]
