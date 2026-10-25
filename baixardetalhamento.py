"""Baixar Detalhamento MIO.

Entra no MIO (mesma sessão do Atualizar MIO), vai em Engenharia > Consulta de
Detalhamentos, filtra UO/Plat. = P-68 e Portfólio = PP, baixa o zip "Por
Projeto" de cada linha e junta somente os PDFs, sem duplicados, na pasta
"Detalhamentos DD-MM" dentro da pasta do dia.

Uso para testes: baixardetalhamento.exe --limite 1   (ou 10; sem o parâmetro baixa todos)
"""
from __future__ import annotations

import argparse
import logging
import re
import shutil
import tempfile
import traceback
import zipfile
from datetime import date
from pathlib import Path

from playwright.sync_api import BrowserContext, Page, sync_playwright

import atualizar_mio as mio
from atualizar_mio import MioError, ROOT, REPORTS_URL, first_visible, status, visible

HOME_URL = "https://mio.app.br/home/"
FILTER_UOP = "P-68"
FILTER_PORTFOLIO = "PP"


def detail_folder() -> Path:
    now = date.today()
    folder = mio.today_folder() / f"Detalhamentos {now:%d-%m}"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def open_consulta(page: Page) -> None:
    """Home > Engenharia > Consulta (card Detalhamentos)."""
    page.goto(HOME_URL, wait_until="load", timeout=120000)
    page.wait_for_timeout(3000)
    mio.dismiss_news_modal(page)
    engenharia = page.locator("a[data-title='Engenharia']").first
    # O menu só responde depois que o JS da página termina de carregar; repete
    # o clique até o módulo abrir.
    for _ in range(4):
        engenharia.click()
        try:
            page.wait_for_selector("a.module-action-item:visible", timeout=8000)
            break
        except Exception:
            continue
    else:
        raise MioError("O módulo Engenharia não abriu ao clicar no menu.")
    # O menu lateral abre sobre a página enquanto o mouse está nele.
    page.mouse.move(1200, 700)
    page.wait_for_timeout(1500)
    # Há vários "Consulta" na página (cards recolhidos); o do card Detalhamentos
    # é o primeiro visível.
    link = page.locator("a.module-action-item:visible").filter(has_text=re.compile(r"^\s*Consulta\s*$"))
    link.first.click(timeout=15000)
    page.wait_for_selector("#frm_eng_det_list", timeout=60000)
    page.wait_for_timeout(1500)
    status("Tela de Consulta de Detalhamentos aberta.")


def set_column_filter(page: Page, header: str, value: str) -> None:
    """Apaga o que estiver no filtro da coluna e digita o valor de novo."""
    field = page.locator("#frm_eng_det_list_wrapper th").filter(
        has_text=re.compile(rf"^\s*{re.escape(header)}\s*$")
    ).locator("input.filter-row").first
    field.click()
    field.fill("")
    field.press_sequentially(value, delay=80)
    page.wait_for_timeout(1000)
    if field.input_value() != value:
        raise MioError(f"O filtro '{header}' não ficou com o valor '{value}'.")


def show_all_rows(page: Page) -> None:
    select = page.locator("select[name='frm_eng_det_list_length']")
    if not visible(select):
        return
    values = select.locator("option").evaluate_all("o => o.map(x => x.value)")
    numeric = [int(v) for v in values if v.lstrip("-").isdigit()]
    biggest = -1 if -1 in numeric else max(numeric)
    select.select_option(str(biggest))
    page.wait_for_timeout(1500)


def collect_forms(page: Page, limit: int | None) -> list[dict]:
    """Lê os formulários 'Por Projeto' de todas as páginas da tabela filtrada."""
    forms: list[dict] = []
    seen: set[str] = set()
    while True:
        batch = page.locator("#frm_eng_det_list tbody form[id^='frm_down_eng_det_']").evaluate_all(
            """forms => forms.map(f => ({
                id: f.id, action: f.action,
                fields: Object.fromEntries([...f.querySelectorAll('input[name]')].map(i => [i.name, i.value]))
            }))"""
        )
        for item in batch:
            if item["id"] not in seen:
                seen.add(item["id"])
                forms.append(item)
        if limit and len(forms) >= limit:
            return forms[:limit]
        nxt = page.locator("#frm_eng_det_list_next")
        if not nxt.count() or "disabled" in (nxt.get_attribute("class") or ""):
            return forms
        nxt.click()
        page.wait_for_timeout(700)


def download_zip(page: Page, form: dict, destination: Path) -> Path:
    response = page.context.request.post(
        form["action"],
        multipart=form["fields"],
        headers={"Referer": page.url},
        timeout=300000,
    )
    if not response.ok:
        raise MioError(f"HTTP {response.status} ao baixar {form['fields'].get('output_file_name')}.")
    payload = response.body()
    if not payload.startswith(b"PK"):
        raise MioError(f"O MIO não devolveu um zip para {form['fields'].get('output_file_name')}.")
    name = form["fields"].get("output_file_name") or form["id"]
    destination.mkdir(parents=True, exist_ok=True)
    path = destination / f"{name}.zip"
    path.write_bytes(payload)
    return path


def merge_pdfs(zip_path: Path, target: Path, names: set[str]) -> tuple[int, int]:
    """Extrai só PDFs do zip (inclusive de subpastas). Retorna (novos, duplicados).

    Os PDFs saem do MIO com marca d'água, então o conteúdo muda a cada download;
    o nome do arquivo é que identifica o detalhamento e define o duplicado.
    """
    added = dupes = 0
    with zipfile.ZipFile(zip_path) as archive:
        for entry in archive.infolist():
            if entry.is_dir() or not entry.filename.lower().endswith(".pdf"):
                continue
            name = Path(entry.filename).name.strip()
            if name.lower() in names:
                dupes += 1
                continue
            (target / name).write_bytes(archive.read(entry))
            names.add(name.lower())
            added += 1
    return added, dupes


def run(limit: int | None) -> None:
    mio.setup_logging()
    status(f"Baixar Detalhamento iniciado (limite={limit or 'todos'}).")
    target = detail_folder()
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
            mio.wait_for_reports_or_login(page)
            open_consulta(page)
            set_column_filter(page, "UO/Plat.", FILTER_UOP)
            set_column_filter(page, "Portfólio", FILTER_PORTFOLIO)
            show_all_rows(page)
            forms = collect_forms(page, limit)
            if not forms:
                raise MioError("Nenhum detalhamento encontrado com os filtros P-68 / PP.")
            status(f"{len(forms)} detalhamento(s) para baixar.")
            names = {existing.name.lower() for existing in target.glob("*.pdf")}
            added = dupes = failed = 0
            with tempfile.TemporaryDirectory(prefix="mio_det_") as temp:
                for index, form in enumerate(forms, 1):
                    try:
                        zip_path = download_zip(page, form, Path(temp))
                        new, dup = merge_pdfs(zip_path, target, names)
                        zip_path.unlink(missing_ok=True)
                        added += new
                        dupes += dup
                        status(f"[{index}/{len(forms)}] {form['fields'].get('output_file_name')}: {new} PDF(s) novo(s), {dup} duplicado(s).")
                    except Exception as exc:  # um zip com problema não derruba o lote
                        failed += 1
                        logging.error("Falha em %s: %s", form["id"], exc)
            summary = f"{added} PDF(s) salvos, {dupes} duplicado(s) descartado(s), {failed} falha(s).\n{target}"
            status("Concluído: " + summary.replace("\n", " "))
            mio.show("Baixar Detalhamento concluído", summary, error=bool(failed))
        except Exception as exc:
            details = f"{type(exc).__name__}: {exc}"
            logging.error("Falha na automação: %s\n%s", details, traceback.format_exc())
            try:
                page.screenshot(path=str(ROOT / "baixardetalhamento_erro.png"))
            except Exception:
                pass
            mio.show("Erro no Baixar Detalhamento", f"A automação parou nesta etapa:\n{details}\n\nVeja: {ROOT / 'Atualizar_MIO.log'}", error=True)
        finally:
            try:
                context.close()
            except Exception as close_error:
                status(f"Contexto do navegador já estava fechado: {type(close_error).__name__}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limite", type=int, default=None, help="baixa só os N primeiros (teste)")
    run(parser.parse_args().limite)
