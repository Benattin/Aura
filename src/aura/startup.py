from __future__ import annotations
from pathlib import Path
import json
import subprocess
import sys
import winreg

from aura.config import ICON_ICO, ROOT

STARTUP_DIR = Path.home() / "AppData/Roaming/Microsoft/Windows/Start Menu/Programs/Startup"
VBS = ROOT / "scripts" / "start-silent.vbs"
LNK = STARTUP_DIR / "AURA.lnk"
TASK = "AURA"
RUN_NAME = "AURA"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def pythonw() -> Path:
    exe = Path(sys.executable)
    if exe.name.lower() == "python.exe":
        cand = exe.with_name("pythonw.exe")
        if cand.exists():
            return cand
    return exe


def write_vbs() -> Path:
    VBS.parent.mkdir(parents=True, exist_ok=True)
    launcher = ROOT / "scripts" / "launch-aura.bat"
    lines = [
        'Set sh = CreateObject("WScript.Shell")',
        f'sh.CurrentDirectory = "{ROOT}"',
    ]
    local = ROOT / "config" / "local.json"
    if local.exists():
        try:
            raw = json.loads(local.read_text(encoding="utf-8"))
            data_dir = raw.get("data_dir", "").strip()
            if data_dir:
                lines.append(f'sh.Environment("Process")("AURA_DATA") = "{data_dir}"')
        except (OSError, json.JSONDecodeError):
            pass
    ollama = ROOT.parent / "ollama-models"
    if ollama.is_dir():
        lines.append(f'sh.Environment("Process")("OLLAMA_MODELS") = "{ollama}"')
    lines.extend(
        [
            f'sh.Run "cmd /c ""{launcher}""", 0, False',
            "",
        ]
    )
    VBS.write_text("\n".join(lines), encoding="utf-8")
    return VBS


def _wscript_cmd() -> str:
    return f'wscript.exe "{VBS}"'


def _install_shortcut() -> Path:
    STARTUP_DIR.mkdir(parents=True, exist_ok=True)
    from win32com.client import Dispatch

    shortcut = Dispatch("WScript.Shell").CreateShortCut(str(LNK))
    shortcut.Targetpath = "wscript.exe"
    shortcut.Arguments = f'"{VBS}"'
    shortcut.WorkingDirectory = str(ROOT)
    shortcut.WindowStyle = 1
    shortcut.Description = "AURA"
    if ICON_ICO.exists():
        shortcut.IconLocation = str(ICON_ICO)
    shortcut.save()
    return LNK


def _install_run_key() -> None:
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
        winreg.SetValueEx(key, RUN_NAME, 0, winreg.REG_SZ, _wscript_cmd())


def _install_task() -> None:
    created = subprocess.run(
        [
            "schtasks", "/Create", "/F", "/TN", TASK, "/SC", "ONLOGON",
            "/DELAY", "0000:25", "/RL", "LIMITED", "/TR", _wscript_cmd(),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if created.returncode == 0:
        return
    try:
        from win32com.client import Dispatch

        service = Dispatch("Schedule.Service")
        service.Connect()
        folder = service.GetFolder("\\")
        definition = service.NewTask(0)
        definition.RegistrationInfo.Description = "AURA"
        definition.Settings.Enabled = True
        definition.Settings.StopIfGoingOnBatteries = False
        definition.Settings.DisallowStartIfOnBatteries = False
        definition.Settings.ExecutionTimeLimit = "PT0S"
        trigger = definition.Triggers.Create(9)
        trigger.Delay = "PT25S"
        trigger.Enabled = True
        action = definition.Actions.Create(0)
        action.Path = "wscript.exe"
        action.Arguments = f'"{VBS}"'
        action.WorkingDirectory = str(ROOT)
        folder.RegisterTaskDefinition(TASK, definition, 6, None, None, 3)
    except Exception:
        pass


def install() -> Path:
    write_vbs()
    lnk = _install_shortcut()
    _install_run_key()
    _install_task()
    return lnk


def uninstall() -> None:
    if LNK.exists():
        LNK.unlink()
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, RUN_NAME)
    except OSError:
        pass
    subprocess.run(
        ["schtasks", "/Delete", "/TN", TASK, "/F"],
        check=False,
        capture_output=True,
    )
