"""Configuração de logging em arquivo (logs/log.txt)."""

from __future__ import annotations

import logging
from pathlib import Path

from modules.base import BASE_DIR

LOG_DIR = BASE_DIR / "logs"


def setup_logger(name: str = "rcm") -> logging.Logger:
    """Cria (uma única vez) o logger que grava em logs/log.txt."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(name)
    if logger.handlers:  # evita handlers duplicados em reexecuções
        return logger

    logger.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler = logging.FileHandler(LOG_DIR / "log.txt", encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    return logger
