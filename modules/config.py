"""Carregamento de configuração (config.json) e segredos (.env)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
import os

from modules.base import BASE_DIR


@dataclass(frozen=True)
class AppConfig:
    """Configuração imutável usada por toda a automação."""

    url: str
    tipo: str
    contrato: str
    contrato_uop: str
    portfolio: str
    download_path: Path
    email: str
    password: str


def load_config(config_file: Path | None = None) -> AppConfig:
    """Lê config.json + .env e devolve um AppConfig validado.

    A senha NUNCA fica no código: vem exclusivamente do arquivo .env.
    """
    config_file = config_file or (BASE_DIR / "config.json")
    load_dotenv(BASE_DIR / ".env")

    data = json.loads(config_file.read_text(encoding="utf-8"))

    email = os.getenv("EMAIL", "").strip()
    password = os.getenv("PASSWORD", "").strip()
    if not email or not password:
        raise RuntimeError(
            "EMAIL e PASSWORD precisam estar definidos no arquivo .env "
            "(use o .env.example como modelo)."
        )

    raw_path = data["download_path"]
    download_path = Path(raw_path).expanduser().resolve()
    download_path.mkdir(parents=True, exist_ok=True)

    return AppConfig(
        url=data["url"],
        tipo=data["tipo"],
        contrato=data["contrato"],
        contrato_uop=data["contrato_uop"],
        portfolio=data["portfolio"],
        download_path=download_path,
        email=email,
        password=password,
    )
