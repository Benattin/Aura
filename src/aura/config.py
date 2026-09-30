from dataclasses import dataclass
from pathlib import Path
import json
import os

ROOT = Path(__file__).resolve().parents[2]
_DATA_DIR: Path | None = None
DEFAULT_PATH = ROOT / "config" / "default.json"
ICON_ICO = ROOT / "assets" / "aura.ico"
ICON_PNG = ROOT / "assets" / "aura-icon.png"


@dataclass
class Settings:
    host: str = "127.0.0.1"
    port: int = 8765
    ollama_host: str = "http://127.0.0.1:11434"
    model: str = "llama3.2:3b"
    vision_model: str = "moondream"
    followup_seconds: int = 15
    tts_enabled: bool = True
    tts_rate: int = 200
    user_name: str = "Gustavo"
    num_predict: int = -1
    num_ctx: int = 8192
    reason_num_predict: int = -1
    reason_num_ctx: int = 8192
    code_model: str = "qwen2.5-coder:3b"
    auto_start: bool = True
    economy_mode: bool = True


def data_dir() -> Path:
    global _DATA_DIR
    if _DATA_DIR is not None:
        return _DATA_DIR
    env = os.environ.get("AURA_DATA", "").strip()
    if env:
        p = Path(env)
    else:
        p = None
        local = ROOT / "config" / "local.json"
        if local.exists():
            try:
                raw = json.loads(local.read_text(encoding="utf-8"))
                if raw.get("data_dir"):
                    p = Path(raw["data_dir"])
            except (OSError, json.JSONDecodeError):
                pass
        if p is None:
            p = Path.home() / "AppData/Local/AURA"
    p.mkdir(parents=True, exist_ok=True)
    _DATA_DIR = p
    return p


def load_settings() -> Settings:
    data: dict = {}
    if DEFAULT_PATH.exists():
        data = json.loads(DEFAULT_PATH.read_text(encoding="utf-8"))
    local = ROOT / "config" / "local.json"
    if local.exists():
        data.update(json.loads(local.read_text(encoding="utf-8")))
    known = {k: v for k, v in data.items() if k in Settings.__dataclass_fields__}
    return Settings(**known)


def save_local(updates: dict) -> None:
    local = ROOT / "config" / "local.json"
    data: dict = {}
    if local.exists():
        try:
            data = json.loads(local.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
    data.update(updates)
    local.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def system_prompt(settings: Settings, extra: str = "") -> str:
    path = ROOT / "prompts" / "system.txt"
    raw = path.read_text(encoding="utf-8") if path.exists() else (
        "Você é AURA. Trate o usuário como senhor. Responda em português do Brasil."
    )
    text = raw.replace("{user_name}", settings.user_name)
    extra = extra.strip()
    if extra:
        text = text + "\n" + extra
    return text
