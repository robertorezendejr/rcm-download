"""Atualizador de relatórios MIO.

Mantém a sessão no diretório _perfil_mio ao lado do executável e salva a
versão mais recente dos três arquivos solicitados na pasta do dia corrente.
"""
from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
from datetime import date
from pathlib import Path
from tkinter import Tk, messagebox

from playwright.sync_api import BrowserContext, Download, Locator, Page, TimeoutError as PlaywrightTimeoutError, sync_playwright


REPORTS_URL = "https://mio.app.br/home/?p=Y2dzL3JlcG9ydHMvbGlzdD90eXBlPXJlYWQ="
SUPPLIES_URL = "https://mio.app.br/home/?p=c3Vw"
ROOT = Path(r"C:\Users\roberto.rezende\Downloads\00-Atualização de sistema")
PCS_SOURCE = Path(
    r"C:\Users\roberto.rezende\OneDrive - ESTRUTURAL PADRÃO\Site de comunicação - P-68-PP-SharePoint"
    r"\09-Planejamento\06-Acompanhamento de SS\UN_BS_Acompanhamento_de_SS-P-68PP.xlsm"
)
PCS_SHEET = "PCS"


class MioError(RuntimeError):
    pass


def show(title: str, text: str, error: bool = False) -> None:
    root = Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    (messagebox.showerror if error else messagebox.showinfo)(title, text, parent=root)
    root.destroy()


def setup_logging() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=ROOT / "Atualizar_MIO.log",
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        encoding="utf-8",
    )


def status(text: str) -> None:
    logging.info(text)


def today_folder() -> Path:
    now = date.today()
    folder = ROOT / now.strftime("%m-%Y") / now.strftime("%d-%m-%Y")
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def visible(locator: Locator) -> Locator | None:
    try:
        if locator.count() and locator.first.is_visible():
            return locator.first
    except Exception:
        pass
    return None


def first_visible(*locators: Locator) -> Locator:
    for locator in locators:
        item = visible(locator)
        if item:
            return item
    raise MioError("Não foi possível localizar o controle esperado na página.")


def dismiss_expired_session_notice(page: Page) -> None:
    """Fecha o modal Bootstrap de sessão expirada sem interferir no login."""
    modal = page.locator("#modal_err")
    if not visible(modal):
        return
    controls = (
        modal.get_by_role("button", name=re.compile(r"^(Close|Cancelar)$", re.I)),
        modal.locator("[data-bs-dismiss='modal'], [data-dismiss='modal'], .btn-close, button.close"),
        modal.locator(".modal-header button"),
        modal.locator("button"),
    )
    for control in controls:
        button = visible(control)
        if button:
            button.click(force=True)
            page.wait_for_timeout(250)
            if not visible(modal):
                status("Aviso de sessão encerrada fechado.")
                return
    raise MioError("Não foi possível fechar o aviso 'Sessão Encerrada!' do MIO.")


def dismiss_news_modal(page: Page) -> None:
    """Fecha o informativo de novidades do MIO que cobre a lista de relatórios."""
    modal = page.locator("#modal_read_imgs")
    if not visible(modal):
        return
    close_button = first_visible(
        modal.get_by_role("button", name=re.compile(r"^Fechar$", re.I)),
        modal.get_by_text("Fechar", exact=True),
    )
    close_button.click()
    page.wait_for_timeout(300)
    if visible(modal):
        raise MioError("O informativo do MIO não fechou ao clicar em 'Fechar'.")
    status("Informativo de novidades do MIO fechado.")


def submit_microsoft_password(page: Page) -> bool:
    """Clica em "Entrar" quando há uma senha preenchida na tela Microsoft."""
    password_field = first_visible(
        page.get_by_label(re.compile(r"^Senha$", re.I)),
        page.locator("input[type='password']"),
    )
    if not password_field.input_value():
        return False
    first_visible(
        page.get_by_role("button", name=re.compile(r"^Entrar$", re.I)),
        page.locator("input[type='submit'][value='Entrar']"),
        page.locator("#idSIButton9"),
    ).click()
    return True


def enter_microsoft_password(page: Page) -> bool:
    """Preenche a senha corporativa fornecida apenas para esta execução."""
    password = os.environ.pop("MIO_MICROSOFT_PASSWORD", "")
    if not password:
        return False
    password_field = first_visible(
        page.get_by_label(re.compile(r"^Senha$", re.I)),
        page.locator("input[type='password']"),
    )
    password_field.fill(password)
    submit_microsoft_password(page)
    status("Senha da conta corporativa enviada ao Microsoft.")
    return True


def wait_for_reports_or_login(page: Page) -> None:
    """Entra pelo SSO Microsoft quando a sessão do MIO não estiver salva."""
    deadline = time.monotonic() + 600
    microsoft_started = False
    corporate_account_selected = False
    microsoft_password_sent = False
    manual_notice_logged = False
    while time.monotonic() < deadline:
        if visible(page.get_by_text("000005", exact=False)):
            return
        # O MIO pode exibir um aviso "Sessão Encerrada!" ao abrir uma sessão
        # expirada; fechamos somente esse aviso para liberar os campos de login.
        expired = page.get_by_text(re.compile(r"Sessão\s+Encerrada", re.I))
        if visible(expired):
            dismiss_expired_session_notice(page)
        # O aviso de cookies bloqueia a entrada no primeiro uso. O MIO alterou
        # o texto do botão em outubro de 2026 para "Aceite os Cookies para Entrar".
        consent = page.get_by_role(
            "button", name=re.compile(r"Aceit[eo].*(Cookies|I\s*Agree)", re.I)
        )
        if not visible(consent):
            consent = page.get_by_text(re.compile(r"Aceit[eo].*(Cookies|I\s*Agree)", re.I))
        if visible(consent):
            consent.click()
            status("Cookies do MIO aceitos automaticamente.")
            page.wait_for_timeout(800)
            continue
        microsoft_password_page = page.get_by_text("Insira a senha", exact=True)
        if visible(microsoft_password_page):
            if not microsoft_password_sent:
                microsoft_password_sent = enter_microsoft_password(page)
                # Quando a senha é digitada por você, detecta o preenchimento
                # e aciona "Entrar" automaticamente, sem salvar a senha.
                if not microsoft_password_sent:
                    microsoft_password_sent = submit_microsoft_password(page)
                if microsoft_password_sent:
                    status("Botão 'Entrar' da Microsoft acionado automaticamente.")
                    page.wait_for_timeout(1500)
                    continue
            if not manual_notice_logged:
                status("Aguardando senha da conta corporativa Microsoft.")
                manual_notice_logged = True
            page.wait_for_timeout(1500)
            continue
        # Quando o e-mail existe como conta pessoal e corporativa, escolhe a
        # corporativa da Estrutural pelo rótulo visível, não pela posição.
        corporate_account = page.get_by_text("Conta corporativa ou de estudante", exact=True)
        if visible(corporate_account) and not corporate_account_selected:
            corporate_account.click()
            corporate_account_selected = True
            status("Conta corporativa Microsoft selecionada.")
            page.wait_for_timeout(1500)
            continue
        # O MIO usa a conta corporativa Microsoft; localiza pelo nome, não por posição.
        if visible(page.locator("input[type='password']")):
            if not microsoft_started:
                # O aviso pode aparecer depois da leitura dos campos; confere de
                # novo no instante anterior ao clique no provedor Microsoft.
                page.wait_for_timeout(350)
                dismiss_expired_session_notice(page)
                microsoft = None
                for candidate in (
                    page.get_by_role("link", name=re.compile(r"^Microsoft$", re.I)),
                    page.get_by_role("button", name=re.compile(r"^Microsoft$", re.I)),
                    page.get_by_text("Microsoft", exact=True),
                ):
                    microsoft = visible(candidate)
                    if microsoft:
                        break
                if microsoft:
                    microsoft.click()
                    microsoft_started = True
                    status("Login Microsoft iniciado.")
                    page.wait_for_timeout(1500)
                    continue
            if not manual_notice_logged:
                status("Aguardando a tela de autenticação do MIO ou da Microsoft.")
                manual_notice_logged = True
        page.wait_for_timeout(1500)
    raise MioError("O login não foi concluído em 10 minutos.")


def find_report_row(page: Page, code: str) -> Locator:
    candidates = [
        page.locator("tr").filter(has_text=code),
        page.locator("[role='row']").filter(has_text=code),
        page.locator("li").filter(has_text=code),
        page.locator("div").filter(has_text=re.compile(rf"\b{code}\b")),
    ]
    for rows in candidates:
        try:
            count = rows.count()
            for i in range(min(count, 25)):
                row = rows.nth(i)
                if row.is_visible() and visible(row.get_by_text("Exportar", exact=False)):
                    return row
        except Exception:
            continue
    raise MioError(f"Não encontrei a linha do relatório {code} com a ação Exportar.")


def save_download(download: Download, destination: Path) -> None:
    temp = download.path()
    if not temp:
        raise MioError("O MIO iniciou o download, mas não disponibilizou o arquivo.")
    destination.unlink(missing_ok=True)
    shutil.copy2(temp, destination)


def run_excel_script(script: str, *arguments: str) -> None:
    """Executa uma automação local do Excel sem depender de bibliotecas Python extras."""
    script_file = None
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".ps1", encoding="utf-8", delete=False) as temporary:
            temporary.write(script)
            script_file = Path(temporary.name)
        result = subprocess.run(
            [
                "powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                "-File", str(script_file), *arguments,
            ],
            text=True,
            capture_output=True,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode:
            details = (result.stderr or result.stdout or "erro desconhecido").strip()
            raise MioError(f"O Excel não concluiu a etapa solicitada: {details}")
    finally:
        if script_file:
            script_file.unlink(missing_ok=True)


def convert_csv_to_xlsx(csv_file: Path) -> Path:
    """Converte o CSV do MIO para uma pasta de trabalho Excel (.xlsx)."""
    xlsx_file = csv_file.with_suffix(".xlsx")
    xlsx_file.unlink(missing_ok=True)
    script = r'''
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
'''
    run_excel_script(script, str(csv_file), str(xlsx_file))
    csv_file.unlink(missing_ok=True)
    return xlsx_file


def export_pcs(folder: Path) -> Path:
    """Gera PCS.xlsx com valores e formatação da aba PCS, sem filtros ativos."""
    if not PCS_SOURCE.is_file():
        raise MioError(f"Não encontrei o arquivo PCS em: {PCS_SOURCE}")
    destination = folder / "PCS.xlsx"
    destination.unlink(missing_ok=True)
    script = r'''
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
'''
    run_excel_script(script, str(PCS_SOURCE), str(destination), PCS_SHEET)
    return destination


def download_report(page: Page, code: str, destination: Path) -> Path:
    status(f"Iniciando relatório {code}.")
    dismiss_news_modal(page)
    row = find_report_row(page, code)
    export = first_visible(
        row.get_by_role("button", name=re.compile("Exportar", re.I)),
        row.get_by_role("link", name=re.compile("Exportar", re.I)),
        row.get_by_text("Exportar", exact=False),
    )
    # O MIO fornece a URL de exportação no próprio botão, porém responde sem o
    # evento de download do Edge. A requisição compartilhada usa os mesmos
    # cookies da sessão autenticada e recebe o arquivo diretamente.
    export_url = export.get_attribute("data-export-url") or export.get_attribute("href")
    if not export_url:
        raise MioError(f"O botão Exportar do relatório {code} não informou uma URL.")
    response = page.context.request.get(export_url, headers={"Referer": page.url}, timeout=180000)
    if not response.ok:
        raise MioError(f"A exportação do relatório {code} retornou HTTP {response.status}.")
    content_type = (response.headers.get("content-type") or "").lower()
    payload = response.body()
    if not payload or "text/html" in content_type:
        raise MioError(f"O MIO não retornou um arquivo para o relatório {code}.")
    disposition = response.headers.get("content-disposition") or ""
    name_match = re.search(r"filename[^=]*=\"?([^\";]+)", disposition, flags=re.I)
    extension = Path(name_match.group(1)).suffix if name_match else ".csv"
    file_path = destination.with_suffix(extension or ".csv")
    file_path.unlink(missing_ok=True)
    file_path.write_bytes(payload)
    if file_path.suffix.lower() == ".csv":
        file_path = convert_csv_to_xlsx(file_path)
    status(f"Relatório {code} baixado com sucesso: {file_path.name}")
    return file_path


def click_rcm(page: Page) -> None:
    button = first_visible(
        page.get_by_role("button", name=re.compile(r"^RCM$", re.I)),
        page.get_by_role("link", name=re.compile(r"^RCM$", re.I)),
        page.get_by_text("RCM", exact=True),
    )
    button.click()
    page.wait_for_timeout(800)


def choose_combobox(page: Page, label: str, value: str, contains: bool = False) -> None:
    """Seleciona controles nativos, ARIA e componentes usuais de dropdown."""
    pattern = re.compile(re.escape(label), re.I)
    controls = [
        page.get_by_label(pattern),
        page.get_by_role("combobox", name=pattern),
        page.locator("select").filter(has=page.locator("option")),
    ]
    control = None
    for item in controls:
        matched = visible(item)
        if matched:
            # Guarda o elemento visível individual, e não o conjunto de
            # correspondências (select nativo + componente Select2).
            control = matched
            break
    if not control:
        # Campos que exibem o rótulo próximo ao controle.
        label_node = page.get_by_text(pattern).first
        if visible(label_node):
            container = label_node.locator("xpath=..")
            control = first_visible(container.locator("select"), container.get_by_role("combobox"), container.locator("input"))
    if not control:
        raise MioError(f"Não encontrei o filtro '{label}'.")
    try:
        tag = control.evaluate("el => el.tagName")
        if tag == "SELECT":
            if contains:
                options = control.locator("option")
                # Este campo é preenchido de forma assíncrona após selecionar
                # o contrato. Aguarda a opção P-68, sem assumir posição.
                deadline = time.monotonic() + 60
                while time.monotonic() < deadline:
                    for i in range(options.count()):
                        text = (options.nth(i).inner_text() or "").strip()
                        if value.lower() in text.lower():
                            control.select_option(index=i)
                            page.wait_for_timeout(400)
                            return
                    page.wait_for_timeout(500)
                raise MioError(f"Não há opção com '{value}' em '{label}'.")
            control.select_option(label=value)
            page.wait_for_timeout(500)
            return
    except PlaywrightTimeoutError:
        pass

    control.click()
    option = page.get_by_role("option", name=re.compile(re.escape(value), re.I) if contains else re.compile(rf"^{re.escape(value)}$", re.I))
    if not visible(option):
        option = page.get_by_text(re.compile(re.escape(value), re.I), exact=False)
    first_visible(option).click()


def download_rcm(page: Page, folder: Path) -> None:
    status("Abrindo RCM.")
    page.goto(SUPPLIES_URL, wait_until="domcontentloaded", timeout=120000)
    page.wait_for_timeout(1000)
    click_rcm(page)
    choose_combobox(page, "Tipo", "Detalhado")
    choose_combobox(page, "Contrato", "UOBS_2025")
    choose_combobox(page, "Contrato/UO/Plat.", "P-68", contains=True)
    choose_combobox(page, "Portfólio", "P68-2026-PP")
    export = first_visible(
        page.get_by_role("button", name=re.compile("Exportar em Excel", re.I)),
        page.get_by_role("link", name=re.compile("Exportar em Excel", re.I)),
        page.get_by_text("Exportar em Excel", exact=False),
    )
    with page.expect_download(timeout=180000) as event:
        export.click()
    destination = folder / f"RCM_{date.today():%d-%m-%Y}.xlsx"
    save_download(event.value, destination)
    status(f"RCM baixado com sucesso: {destination.name}")


def run() -> None:
    setup_logging()
    folder = today_folder()
    status("Execução iniciada.")
    profile = ROOT / "_perfil_mio"
    profile.mkdir(exist_ok=True)
    with sync_playwright() as playwright:
        try:
            context: BrowserContext = playwright.chromium.launch_persistent_context(
                str(profile), channel="msedge", headless=False, accept_downloads=True,
                args=["--start-maximized"], no_viewport=True,
            )
        except Exception:
            context = playwright.chromium.launch_persistent_context(
                str(profile), headless=False, accept_downloads=True, args=["--start-maximized"], no_viewport=True,
            )
        page = context.pages[0] if context.pages else context.new_page()
        try:
            page.goto(REPORTS_URL, wait_until="domcontentloaded", timeout=120000)
            wait_for_reports_or_login(page)
            download_report(page, "000002", folder / "relatorio_000002.csv")
            download_report(page, "000005", folder / "relatorio_000005.csv")
            download_report(page, "000010", folder / "relatorio_000010.csv")
            download_rcm(page, folder)
            export_pcs(folder)
            status("Execução concluída com sucesso.")
            show("Atualização MIO concluída", f"Os cinco arquivos foram salvos em:\n{folder}")
        except Exception as exc:
            details = f"{type(exc).__name__}: {exc}"
            logging.error("Falha na automação: %s\n%s", details, traceback.format_exc())
            show("Erro no Atualizar MIO", f"A automação parou nesta etapa:\n{details}\n\nO navegador permanecerá aberto para conferência.\nVeja também: {ROOT / 'Atualizar_MIO.log'}", error=True)
            # Mantém a janela aberta para inspeção quando há falha.
            try:
                page.wait_for_timeout(600000)
            except Exception as wait_error:
                # Fechar o navegador durante a inspeção é esperado; não exibe
                # uma segunda exceção técnica do Playwright para o usuário.
                status(f"Navegador fechado após o erro: {type(wait_error).__name__}.")
        finally:
            try:
                context.close()
            except Exception as close_error:
                status(f"Contexto do navegador já estava fechado: {type(close_error).__name__}.")


if __name__ == "__main__":
    run()
