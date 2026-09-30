from __future__ import annotations
import logging
from pathlib import Path

from aura.config import data_dir


def setup_logging() -> Path:
    log_dir = data_dir()
    log_file = log_dir / "aura.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(),
        ],
        force=True,
    )
    return log_file
