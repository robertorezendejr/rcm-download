"""Ponto de entrada da automação de download do relatório RCM.

Orquestra: login (com reaproveitamento de sessão), navegação até o relatório,
preenchimento dos filtros e download do Excel. Em caso de falha, captura um
screenshot e registra tudo em logs/log.txt.
"""

from __future__ import annotations

import sys
import time

from modules.browser import browser_session, save_session
from modules.config import load_config
from modules.download import ReportDownloader
from modules.login import LoginManager
from modules.logger import setup_logger
from modules.navegacao import Navigator
from modules.progress import ProgressReporter
from modules.utils import take_screenshot


def run() -> int:
    logger = setup_logger()
    progress = ProgressReporter()
    config = load_config()

    start = time.perf_counter()
    logger.info("=== Execução iniciada ===")
    progress.stage("Abrindo navegador...")

    with browser_session(keep_open=True) as (context, page):
        try:
            progress.stage("Verificando login...")
            login = LoginManager(page, config, logger, progress)
            login.ensure_logged_in()
            save_session(context)

            navigator = Navigator(page, logger, progress)
            navigator.open_suprimentos()
            navigator.open_rcm()

            downloader = ReportDownloader(page, config, logger, progress)
            downloader.fill_filters()
            target = downloader.export_excel()

            progress.success(f"Arquivo salvo em: {target}")
            return 0

        except Exception as exc:  # noqa: BLE001 - queremos capturar tudo p/ screenshot
            screenshot = take_screenshot(page, "erro")
            logger.exception("Erro encontrado: %s | screenshot: %s", exc, screenshot)
            progress.error(f"Erro: {exc}")
            progress.warn(f"Screenshot salvo em: {screenshot}")
            return 1

        finally:
            elapsed = time.perf_counter() - start
            logger.info("Tempo total: %.1fs", elapsed)
            logger.info("=== Execução finalizada ===")
            progress.stage(f"Tempo total: {elapsed:.1f}s")


if __name__ == "__main__":
    sys.exit(run())
