"""Navegação no sistema mio.app.br até a tela de exportação do RCM.

O sistema é uma SPA que usa a função global fnc_nav_url(path) para trocar
de módulo sem recarregar a página. Não é necessário expandir menu manualmente.

Caminhos descobertos em inspeção real (27/06/2026):
  - Suprimentos : fnc_nav_url('sup')
  - RCM         : fnc_nav_url('sup/rcm/aplic/export_excel?type=read&modulo=4')
"""

from __future__ import annotations

import logging

from playwright.sync_api import Page
from playwright.sync_api import TimeoutError as PlaywrightTimeout

from .progress import ProgressReporter
from .utils import ElementNotFoundError


class Navigator:
    """Conduz o usuário autenticado até a tela do relatório RCM."""

    _PATH_SUP = "sup"
    _PATH_RCM = "sup/rcm/aplic/export_excel?type=read&modulo=4"

    def __init__(
        self,
        page: Page,
        logger: logging.Logger,
        progress: ProgressReporter,
    ) -> None:
        self._page = page
        self._log = logger
        self._progress = progress

    # ------------------------------------------------------------------ #
    # Fluxo público
    # ------------------------------------------------------------------ #

    def open_suprimentos(self) -> None:
        """Abre o módulo Suprimentos via fnc_nav_url e confirma carregamento."""
        self._progress.stage("Abrindo Suprimentos...")
        self._dismiss_popups()
        self._nav(self._PATH_SUP)
        self._page.wait_for_timeout(2000)

        # Confirma que o sub-menu de Suprimentos carregou (link RCM visível)
        try:
            self._page.locator("a[href*='rcm']").first.wait_for(
                state="attached", timeout=10_000
            )
        except PlaywrightTimeout as exc:
            raise ElementNotFoundError(
                "Sub-menu de Suprimentos não carregou — link RCM não encontrado"
            ) from exc

        self._log.info("Suprimentos aberto")

    def open_rcm(self) -> None:
        """Abre a tela de exportação do RCM e aguarda o formulário de filtros."""
        self._progress.stage("Abrindo RCM...")
        self._nav(self._PATH_RCM)
        self._page.wait_for_timeout(2000)

        # Aguarda o formulário de filtros (#frm_export) estar no DOM
        try:
            self._page.locator("#frm_export").wait_for(
                state="attached", timeout=12_000
            )
        except PlaywrightTimeout as exc:
            raise ElementNotFoundError(
                "Formulário de filtros do RCM (#frm_export) não carregou"
            ) from exc

        # Pausa para o Select2 inicializar os campos
        self._page.wait_for_timeout(2000)
        self._log.info("RCM aberto — formulário pronto")

    # ------------------------------------------------------------------ #
    # Auxiliar
    # ------------------------------------------------------------------ #

    def _dismiss_popups(self) -> None:
        """Fecha modais/popups que possam aparecer após o login (ex: novidades do sistema)."""
        # Aguarda um pouco para o popup carregar
        self._page.wait_for_timeout(2000)

        for locator in [
            self._page.get_by_role("button", name="Não perguntar novamente"),
            self._page.get_by_role("button", name="Fechar"),
            self._page.get_by_role("button", name="Close"),
            self._page.locator("button.close"),
            self._page.locator("[data-dismiss='modal']"),
            self._page.locator(".modal .btn"),
        ]:
            try:
                locator.first.wait_for(state="visible", timeout=4000)
                locator.first.click()
                self._page.wait_for_timeout(800)
                self._log.info("Popup fechado")
                return
            except Exception:
                continue

        # Fallback: tenta ESC caso nenhum botão tenha sido encontrado
        try:
            self._page.keyboard.press("Escape")
            self._page.wait_for_timeout(500)
        except Exception:
            pass

    def _nav(self, path: str) -> None:
        """Chama fnc_nav_url(path) — função global de navegação do sistema."""
        self._page.evaluate(f"fnc_nav_url({path!r})")
