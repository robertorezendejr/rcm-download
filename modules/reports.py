"""Gerenciador de download dos relatórios CGS (000002, 000005, 000010) e exportação do PCS."""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from tkinter import Tk, messagebox
from typing import TYPE_CHECKING

from playwright.sync_api import Locator, Page

if TYPE_CHECKING:
    from .config import AppConfig
    from .progress import ProgressReporter


class ReportError(RuntimeError):
    """Erro em operações de relatórios ou exportação."""


def show_popup(title: str, text: str, error: bool = False) -> None:
    """Exibe caixa de diálogo nativa do Windows informando o status ao usuário."""
    try:
        root = Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        (messagebox.showerror if error else messagebox.showinfo)(title, text, parent=root)
        root.destroy()
    except Exception:
        pass


def run_excel_script(script: str, *arguments: str) -> None:
    """Executa script PowerShell com Excel COM automation para operações com planilhas."""
    script_file = None
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".ps1", encoding="utf-8", delete=False) as temporary:
            temporary.write(script)
            script_file = Path(temporary.name)
        result = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script_file),
                *arguments,
            ],
            text=True,
            capture_output=True,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode:
            details = (result.stderr or result.stdout or "erro desconhecido").strip()
            raise ReportError(f"Falha na automação do Excel: {details}")
    finally:
        if script_file:
            script_file.unlink(missing_ok=True)


def convert_csv_to_xlsx(csv_file: Path) -> Path:
    """Converte o arquivo CSV gerado pelo MIO para pasta de trabalho Excel (.xlsx)."""
    xlsx_file = csv_file.with_suffix(".xlsx")
    xlsx_file.unlink(missing_ok=True)
    script = r"""
param([string]$Source, [string]$Destination)
$ErrorActionPreference = 'Stop'
$excel = $null
$book = $null
try {
    $excel = New-Object -ComObject Excel.Application
    $excel.Visible = $false
    $excel.DisplayAlerts = $false
    $book = $excel.Workbooks.Open($Source, 0, $true)
    $book.SaveAs($Destination, 51)
} finally {
    if ($book) { $book.Close($false) }
    if ($excel) { $excel.Quit() }
}
"""
    run_excel_script(script, str(csv_file), str(xlsx_file))
    csv_file.unlink(missing_ok=True)
    return xlsx_file


class ReportsManager:
    """Gerencia os relatórios gerais da tela CGS Reports e a extração do PCS."""

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

    def open_reports_page(self) -> None:
        """Navega até a página de listagem de relatórios."""
        self._progress.stage("Acessando lista de relatórios...")
        self._log.info("Navegando para: %s", self._config.reports_url)
        self._page.goto(self._config.reports_url, wait_until="domcontentloaded", timeout=120_000)
        self._dismiss_modals()

    def dismiss_news_modal(self) -> None:
        """Fecha o modal de novidades do sistema (#modal_read_imgs)."""
        modal = self._page.locator("#modal_read_imgs")
        try:
            if modal.count() and modal.first.is_visible():
                close_btn = modal.get_by_role("button", name=re.compile(r"^Fechar$", re.I)).or_(
                    modal.get_by_text("Fechar", exact=True)
                )
                if close_btn.count() and close_btn.first.is_visible():
                    close_btn.first.click()
                    self._page.wait_for_timeout(300)
                    self._log.info("Modal de novidades fechado.")
        except Exception:
            pass

    def dismiss_expired_session(self) -> None:
        """Fecha aviso de sessão encerrada (#modal_err) se aparecer."""
        modal = self._page.locator("#modal_err")
        try:
            if modal.count() and modal.first.is_visible():
                btn = modal.locator(
                    "[data-bs-dismiss='modal'], [data-dismiss='modal'], .btn-close, button.close, button"
                ).first
                if btn.is_visible():
                    btn.click(force=True)
                    self._page.wait_for_timeout(250)
                    self._log.info("Aviso de sessão encerrada fechado.")
        except Exception:
            pass

    def _dismiss_modals(self) -> None:
        self.dismiss_expired_session()
        self.dismiss_news_modal()

    def find_report_row(self, code: str) -> Locator:
        """Localiza a linha na tabela referente ao código de relatório informado."""
        candidates = [
            self._page.locator("tr").filter(has_text=code),
            self._page.locator("[role='row']").filter(has_text=code),
            self._page.locator("li").filter(has_text=code),
            self._page.locator("div").filter(has_text=re.compile(rf"\b{code}\b")),
        ]
        for rows in candidates:
            try:
                count = rows.count()
                for i in range(min(count, 25)):
                    row = rows.nth(i)
                    if row.is_visible() and row.get_by_text("Exportar", exact=False).first.is_visible():
                        return row
            except Exception:
                continue
        raise ReportError(f"Não foi possível encontrar a linha do relatório {code} com opção Exportar.")

    def download_report(self, code: str, target_folder: Path) -> Path:
        """Baixa o relatório do MIO via requisição autenticada e converte para .xlsx."""
        self._progress.stage(f"Baixando relatório {code}...")
        self._log.info("Iniciando download do relatório %s", code)
        self._dismiss_modals()

        row = self.find_report_row(code)
        export_btn = row.get_by_role("button", name=re.compile("Exportar", re.I)).or_(
            row.get_by_role("link", name=re.compile("Exportar", re.I))
        ).or_(row.get_by_text("Exportar", exact=False))

        export_el = export_btn.first
        export_url = export_el.get_attribute("data-export-url") or export_el.get_attribute("href")
        if not export_url:
            raise ReportError(f"O botão Exportar do relatório {code} não informou uma URL.")

        response = self._page.context.request.get(
            export_url,
            headers={"Referer": self._page.url},
            timeout=180_000,
        )
        if not response.ok:
            raise ReportError(f"A exportação do relatório {code} retornou HTTP {response.status}.")

        content_type = (response.headers.get("content-type") or "").lower()
        payload = response.body()
        if not payload or "text/html" in content_type:
            raise ReportError(f"O MIO não retornou arquivo válido para o relatório {code}.")

        disposition = response.headers.get("content-disposition") or ""
        name_match = re.search(r"filename[^=]*=\"?([^\";]+)", disposition, flags=re.I)
        extension = Path(name_match.group(1)).suffix if name_match else ".csv"

        destination = target_folder / f"relatorio_{code}{extension or '.csv'}"
        destination.unlink(missing_ok=True)
        destination.write_bytes(payload)

        if destination.suffix.lower() == ".csv":
            destination = convert_csv_to_xlsx(destination)

        self._log.info("Relatório %s salvo em: %s", code, destination.name)
        self._progress.success(f"Relatório {code} salvo: {destination.name}")
        return destination

    def export_pcs(self, target_folder: Path) -> Path:
        """Extrai os dados da aba PCS da planilha matriz para PCS.xlsx."""
        if not self._config.pcs_source or not self._config.pcs_source.is_file():
            raise ReportError(f"Arquivo de origem PCS não encontrado: {self._config.pcs_source}")

        self._progress.stage("Exportando planilha PCS...")
        self._log.info("Exportando aba %s de %s", self._config.pcs_sheet, self._config.pcs_source)
        destination = target_folder / "PCS.xlsx"
        destination.unlink(missing_ok=True)

        script = r"""
param([string]$Source, [string]$Destination, [string]$SheetName)
$ErrorActionPreference = 'Stop'
$excel = $null
$sourceBook = $null
$destinationBook = $null
$sourceSheet = $null
$destinationSheet = $null
try {
    $excel = New-Object -ComObject Excel.Application
    $excel.Visible = $false
    $excel.DisplayAlerts = $false
    $sourceBook = $excel.Workbooks.Open($Source, 0, $true)
    $sourceSheet = $sourceBook.Worksheets.Item($SheetName)
    if ($sourceSheet.FilterMode) { $sourceSheet.ShowAllData() }
    foreach ($table in $sourceSheet.ListObjects) {
        if ($table.AutoFilter.FilterMode) { $table.AutoFilter.ShowAllData() }
    }
    $sourceSheet.UsedRange.Copy()
    $destinationBook = $excel.Workbooks.Add()
    $destinationSheet = $destinationBook.Worksheets.Item(1)
    $destinationSheet.Name = 'PCS'
    $destinationSheet.Range('A1').PasteSpecial(-4163)
    $destinationSheet.Range('A1').PasteSpecial(-4122)
    $destinationBook.SaveAs($Destination, 51)
} finally {
    if ($destinationBook) { try { $destinationBook.Close($false) } catch {} }
    if ($sourceBook) { try { $sourceBook.Close($false) } catch {} }
    if ($excel) { try { $excel.Quit() } catch {} }
    foreach ($object in @($destinationSheet, $sourceSheet, $destinationBook, $sourceBook, $excel)) {
        if ($null -ne $object) {
            try { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($object) } catch {}
        }
    }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}
"""
        run_excel_script(
            script,
            str(self._config.pcs_source),
            str(destination),
            self._config.pcs_sheet,
        )
        self._log.info("Planilha PCS salva em: %s", destination.name)
        self._progress.success("Planilha PCS gerada com sucesso.")
        return destination
