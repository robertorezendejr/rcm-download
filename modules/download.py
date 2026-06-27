"""Preenchimento dos filtros Select2 e exportação do relatório RCM em Excel.

Estrutura da tela (inspecionada em 27/06/2026):
  - Todos os campos são <select> com Select2 (id: tipo, contrato, plat_uo, portfolio)
  - Cascata: contrato → plat_uo → portfolio  (cada um carrega via AJAX no change)
  - Botão exportar: <button id="btn_export" type="submit">
  - Formulário: <form id="frm_export">

Estratégia para Select2:
  Usamos page.evaluate() para setar o valor por texto e disparar o evento
  'change' via jQuery (presente na página), garantindo que a cascata AJAX
  funcione corretamente.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from playwright.sync_api import Page
from playwright.sync_api import TimeoutError as PlaywrightTimeout

from .config import AppConfig
from .progress import ProgressReporter
from .utils import ElementNotFoundError


class ReportDownloader:
    """Preenche os filtros do relatório RCM e exporta o arquivo Excel."""

    def __init__(
        self,
        page: Page,
        config: AppConfig,
        logger: logging.Logger,
        progress: ProgressReporter,
    ) -> None:
        self._page = page
        self._config = config
        self._log = logger
        self._progress = progress

    # ------------------------------------------------------------------ #
    # Fluxo público
    # ------------------------------------------------------------------ #

    def fill_filters(self) -> None:
        """Preenche os 4 filtros na ordem correta respeitando a cascata AJAX."""
        self._progress.stage("Preenchendo filtros...")

        # 1. Tipo (independente)
        self._select_s2("tipo", self._config.tipo)
        self._page.wait_for_timeout(2000)

        # 2. Contrato (independente) → dispara carga de plat_uo
        self._select_s2("contrato", self._config.contrato)
        self._wait_options("plat_uo", label="Contrato/UO/Plat.")
        self._page.wait_for_timeout(2000)

        # 3. Contrato/UO/Plat. → dispara carga de portfolio
        self._select_s2("plat_uo", self._config.contrato_uop)
        self._wait_options("portfolio", label="Portfólio")
        self._page.wait_for_timeout(2000)

        # 4. Portfólio
        self._select_s2("portfolio", self._config.portfolio)
        self._page.wait_for_timeout(2000)

        self._log.info("Filtros preenchidos")

    def export_excel(self) -> Path:
        """Clica em 'Exportar em Excel' e salva o arquivo baixado."""
        self._progress.stage("Baixando Excel...")
        self._log.info("Download iniciado")

        btn = self._page.locator("#btn_export")
        try:
            btn.wait_for(state="visible", timeout=8_000)
        except PlaywrightTimeout as exc:
            raise ElementNotFoundError(
                "Botão 'Exportar em Excel' (#btn_export) não encontrado"
            ) from exc

        target = self._config.download_path / self._target_filename()
        with self._page.expect_download(timeout=120_000) as dl:
            btn.click()
        dl.value.save_as(str(target))

        self._progress.success("Download concluído")
        self._log.info("Download concluído: %s", target)
        return target

    # ------------------------------------------------------------------ #
    # Select2
    # ------------------------------------------------------------------ #

    def _select_s2(self, field_id: str, label: str) -> None:
        """Seleciona uma opção em um campo Select2 pelo texto visível.

        Procura a opção pelo texto (match exato após strip), seta o valor
        no <select> subjacente e dispara o evento 'change' via jQuery para
        que a cascata AJAX funcione corretamente.
        """
        found = self._page.evaluate(
            """([id, label]) => {
                const sel = document.querySelector('#' + id);
                if (!sel) return {ok: false, err: 'elemento #' + id + ' não encontrado'};
                const opt = Array.from(sel.options).find(
                    o => o.text.trim() === label
                );
                if (!opt) {
                    const available = Array.from(sel.options).map(o => o.text.trim());
                    return {ok: false, err: 'opção "' + label + '" não encontrada; disponíveis: ' + available.join(', ')};
                }
                sel.value = opt.value;
                if (window.$) {
                    $(sel).trigger('change');
                } else {
                    sel.dispatchEvent(new Event('change', {bubbles: true}));
                }
                return {ok: true};
            }""",
            [field_id, label],
        )
        if not found.get("ok"):
            raise ElementNotFoundError(
                f"Falha ao selecionar '{label}' em #{field_id}: {found.get('err')}"
            )
        self._log.debug("Selecionado '%s' em #%s", label, field_id)

    def _wait_options(self, field_id: str, label: str, timeout: int = 10_000) -> None:
        """Aguarda o campo Select2 ter ao menos 2 opções (vazio + 1 real)."""
        try:
            self._page.wait_for_function(
                f"document.querySelector('#{field_id}').options.length > 1",
                timeout=timeout,
            )
        except PlaywrightTimeout as exc:
            raise ElementNotFoundError(
                f"Campo '{label}' (#{field_id}) não carregou opções em {timeout}ms"
            ) from exc

    # ------------------------------------------------------------------ #
    # Auxiliares
    # ------------------------------------------------------------------ #

    @staticmethod
    def _target_filename() -> str:
        return f"RCM_{datetime.now():%Y-%m-%d_%H-%M}.xlsx"
