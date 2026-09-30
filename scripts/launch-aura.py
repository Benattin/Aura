from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_CREATE_NO_WINDOW = 0x08000000


def run_aura() -> None:
    os.chdir(ROOT)
    env = os.environ.copy()
    env.setdefault("AURA_DATA", "D:/AURA/data")
    ollama = ROOT.parent / "ollama-models"
    if ollama.is_dir():
        env.setdefault("OLLAMA_MODELS", str(ollama))
    os.environ.update(env)
    from aura.__main__ import main

    main()


def main() -> None:
    if "--worker" in sys.argv:
        run_aura()
        return
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    subprocess.Popen(
        [sys.executable, str(Path(__file__).resolve()), "--worker"],
        cwd=ROOT,
        env=os.environ.copy(),
        creationflags=flags,
    )


if __name__ == "__main__":
    main()
