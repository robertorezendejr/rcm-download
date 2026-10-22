"""Carregamento de configuração (config.json) e segredos (.env)."""

from __future__ import annotations

from datetime import datetime
import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

from modules.base import BASE_DIR


@dataclass(frozen=True)
class AppConfig:
    """Configuração imutável usada por toda a automação."""

    url: str
    reports_url: str
    tipo: str
    contrato: str
    contrato_uop: str
    portfolio: str
    download_path: Path
    relatorios: list[str]
    pcs_source: Path | None
    pcs_sheet: str
    email: str
    password: str

    def get_today_folder(self) -> Path:
        """Cria e retorna a pasta do dia no padrão: <download_path>/MM-YYYY/DD-MM-YYYY."""
        now = datetime.now()
        folder = self.download_path / now.strftime("%m-%Y") / now.strftime("%d-%m-%Y")
        folder.mkdir(parents=True, exist_ok=True)
        return folder


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

    raw_path = data.get("download_path", "~/Downloads/00-Atualização de sistema")
    download_path = Path(raw_path).expanduser().resolve()
    download_path.mkdir(parents=True, exist_ok=True)

    pcs_raw = data.get("pcs_source")
    pcs_source = Path(pcs_raw).expanduser().resolve() if pcs_raw else None

    return AppConfig(
        url=data.get("url", "https://mio.app.br/"),
        reports_url=data.get(
            "reports_url",
            "https://mio.app.br/home/?p=Y2dzL3JlcG9ydHMvbGlzdD90eXBlPXJlYWQ=",
        ),
        tipo=data.get("tipo", "Detalhado"),
        contrato=data.get("contrato", "UOBS_2025"),
        contrato_uop=data.get("contrato_uop", "UOBS_2025 - P-68 - PETROBRAS - EDISE"),
        portfolio=data.get("portfolio", "P68-2026-PP"),
        download_path=download_path,
        relatorios=data.get("relatorios", ["000002", "000005", "000010"]),
        pcs_source=pcs_source,
        pcs_sheet=data.get("pcs_sheet", "PCS"),
        email=email,
        password=password,
    )

