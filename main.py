"""Ponto de entrada da automação de download dos relatórios MIO (000002, 000005, 000010, RCM e PCS).

Orquestra:
1. Criação da pasta organizada por data de hoje: <download_path>/MM-YYYY/DD-MM-YYYY/
2. Login no MIO (com reaproveitamento de sessão Microsoft MFA).
3. Download dos relatórios CGS: 000002, 000005 e 000010 (convertidos para .xlsx).
4. Download do relatório RCM com os filtros preenchidos.
5. Exportação da aba PCS da planilha de acompanhamento (SharePoint/OneDrive).
6. Exibição de notificação de conclusão informando a pasta e todos os arquivos gerados.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

from modules.browser import browser_session, save_session
from modules.config import load_config
from modules.download import ReportDownloader
from modules.login import LoginManager
from modules.logger import setup_logger
from modules.navegacao import Navigator
from modules.progress import ProgressReporter
from modules.reports import ReportsManager, show_popup
from modules.utils import take_screenshot


def run() -> int:
    logger = setup_logger()
    progress = ProgressReporter()
    config = load_config()

    start = time.perf_counter()
    logger.info("=== Execução iniciada ===")

    # 1. Cria a pasta com a data de hoje: <download_path>/MM-YYYY/DD-MM-YYYY
    today_folder = config.get_today_folder()
    logger.info("Pasta de destino do dia: %s", today_folder)
    progress.stage(f"Pasta do dia: {today_folder.name}")

    saved_files: list[Path] = []

    with browser_session(keep_open=False) as (context, page):
        try:
            # 2. Login
            progress.stage("Verificando login...")
            login = LoginManager(page, config, logger, progress)
            login.ensure_logged_in()
            save_session(context)

            # 3. Download dos relatórios CGS (000002, 000005, 000010)
            reports_mgr = ReportsManager(page, config, logger, progress)
            if config.relatorios:
                reports_mgr.open_reports_page()
                for code in config.relatorios:
                    try:
                        file_path = reports_mgr.download_report(code, today_folder)
                        saved_files.append(file_path)
                    except Exception as err:
                        logger.warning("Falha ao baixar relatório %s: %s", code, err)
                        progress.warn(f"Falha no relatório {code}: {err}")

            # 4. Navegação e Download do RCM
            progress.stage("Abrindo módulo RCM...")
            navigator = Navigator(page, logger, progress)
            navigator.open_suprimentos()
            navigator.open_rcm()

            rcm_downloader = ReportDownloader(page, config, logger, progress)
            rcm_downloader.fill_filters()
            rcm_target = rcm_downloader.export_excel(target_folder=today_folder)
            saved_files.append(rcm_target)

            # 5. Exportação da aba PCS (se o arquivo existir)
            if config.pcs_source and config.pcs_source.is_file():
                try:
                    pcs_target = reports_mgr.export_pcs(today_folder)
                    saved_files.append(pcs_target)
                except Exception as err:
                    logger.warning("Falha ao exportar PCS: %s", err)
                    progress.warn(f"Falha ao exportar PCS: {err}")
            elif config.pcs_source:
                logger.info("Arquivo PCS não encontrado em: %s (etapa ignorada)", config.pcs_source)

            # 6. Finalização e Notificação
            elapsed = time.perf_counter() - start
            logger.info("Tempo total: %.1fs", elapsed)
            logger.info("=== Execução finalizada com sucesso (%d arquivos) ===", len(saved_files))

            resumo_arquivos = "\n".join(f"• {f.name}" for f in saved_files)
            msg = (
                f"Atualização concluída em {elapsed:.1f}s!\n\n"
                f"Pasta de destino:\n{today_folder}\n\n"
                f"Arquivos salvos ({len(saved_files)}):\n{resumo_arquivos}"
            )
            progress.success(f"{len(saved_files)} arquivos salvos em: {today_folder}")
            show_popup("Atualização Concluída", msg)
            return 0

        except Exception as exc:  # noqa: BLE001
            screenshot = take_screenshot(page, "erro")
            logger.exception("Erro encontrado: %s | screenshot: %s", exc, screenshot)
            progress.error(f"Erro: {exc}")
            progress.warn(f"Screenshot salvo em: {screenshot}")
            show_popup(
                "Erro na Atualização",
                f"A automação parou com o seguinte erro:\n{exc}\n\n"
                f"Screenshot salvo em:\n{screenshot}\n\n"
                f"Veja os detalhes em logs/log.txt",
                error=True,
            )
            return 1

        finally:
            elapsed = time.perf_counter() - start
            progress.stage(f"Tempo total: {elapsed:.1f}s")


if __name__ == "__main__":
    sys.exit(run())
