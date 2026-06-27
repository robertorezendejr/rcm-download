"""Descoberta automática de seletores do mio.app.br.

Abre o Edge, aguarda o login + MFA (até 5 minutos), depois navega
automaticamente por cada tela e salva:
  - tools/discovery/NN_<etapa>.json  → atributos de todos os elementos visíveis
  - tools/discovery/NN_<etapa>.png   → screenshot da tela

Execute uma única vez para gerar os arquivos de inspeção:
    cd /Users/robertorezendejr/Documents/www/RCM-Download
    ./.venv/bin/python tools/descobrir.py

Após o MFA, o script roda sozinho. Os arquivos ficam em tools/discovery/.
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeout

from modules.browser import browser_session, save_session  # noqa: E402
from modules.config import load_config  # noqa: E402

OUT_DIR = Path(__file__).resolve().parent / "discovery"
OUT_DIR.mkdir(parents=True, exist_ok=True)


# ------------------------------------------------------------------ #
# Coleta de elementos
# ------------------------------------------------------------------ #

def dump_page(page: Page, step: str) -> dict:
    """Coleta todos os elementos visíveis e salva JSON + screenshot."""
    step_slug = step.lower().replace(" ", "_")
    index = len(list(OUT_DIR.glob("*.json"))) + 1
    prefix = OUT_DIR / f"{index:02d}_{step_slug}"

    # Screenshot
    try:
        page.screenshot(path=str(prefix.with_suffix(".png")), full_page=True)
    except Exception as e:
        print(f"  [!] screenshot falhou: {e}")

    # Elementos
    data: dict = {"step": step, "url": page.url, "inputs": [], "interactive": []}

    for el in page.locator("input, textarea, select").all():
        try:
            if not el.is_visible():
                continue
            data["inputs"].append({
                "tag": el.evaluate("e => e.tagName.toLowerCase()"),
                "type": el.get_attribute("type"),
                "id": el.get_attribute("id"),
                "name": el.get_attribute("name"),
                "placeholder": el.get_attribute("placeholder"),
                "aria-label": el.get_attribute("aria-label"),
                "class": (el.get_attribute("class") or "")[:80],
            })
        except Exception:
            pass

    for sel in ["button", "a", "[role=button]", "[role=combobox]",
                "[role=listbox]", "[role=option]", "[role=menuitem]",
                "[role=tab]", "li"]:
        for el in page.locator(sel).all():
            try:
                if not el.is_visible():
                    continue
                txt = (el.inner_text() or "").strip().replace("\n", " ")[:80]
                if not txt:
                    continue
                data["interactive"].append({
                    "selector": sel,
                    "id": el.get_attribute("id"),
                    "class": (el.get_attribute("class") or "")[:80],
                    "aria-label": el.get_attribute("aria-label"),
                    "role": el.get_attribute("role"),
                    "text": txt,
                })
            except Exception:
                pass

    json_path = prefix.with_suffix(".json")
    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    print(f"  ✔ Salvo: {json_path.name}  ({len(data['inputs'])} inputs, "
          f"{len(data['interactive'])} interativos)")
    return data


# ------------------------------------------------------------------ #
# Utilitários de navegação
# ------------------------------------------------------------------ #

def wait_for_login(page: Page, timeout_s: int = 300) -> None:
    """Aguarda o usuário concluir o login/MFA. Polling a cada 2 s."""
    print(f"\nAguardando login (até {timeout_s}s)... conclua o MFA na janela do Edge.")
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        url = page.url
        if "mio.app.br" in url and "microsoftonline" not in url:
            try:
                page.wait_for_load_state("networkidle", timeout=10_000)
            except PlaywrightTimeout:
                pass
            print("  ✔ Login detectado!")
            return
        time.sleep(2)
    raise TimeoutError("Login não detectado em 5 minutos. Tente novamente.")


def try_click(page: Page, *locators, timeout: int = 6000) -> bool:
    """Tenta clicar em uma lista de locators; retorna True no primeiro que funcionar."""
    from playwright.sync_api import TimeoutError as PWT
    for loc in locators:
        try:
            loc.first.wait_for(state="visible", timeout=timeout)
            loc.first.click()
            return True
        except (PWT, Exception):
            continue
    return False


# ------------------------------------------------------------------ #
# Etapas de navegação
# ------------------------------------------------------------------ #

def step_pos_login(page: Page) -> None:
    print("\n[1/4] Capturando tela pós-login...")
    dump_page(page, "01_pos_login")


def step_menu_suprimentos(page: Page) -> bool:
    print("\n[2/4] Tentando abrir Suprimentos no menu...")

    # Tenta expandir menu (toggle/hamburguer)
    toggle = page.locator(
        "button[aria-label*='menu' i], button[aria-label*='navigation' i], "
        "[class*='menu-toggle' i], [class*='hamburger' i], [class*='sidebar-toggle' i]"
    )
    try_click(page, toggle, timeout=3000)
    page.wait_for_timeout(800)

    # Tenta clicar em Suprimentos
    suprimentos = page.get_by_role("link", name=re.compile(r"suprimentos", re.I))
    suprimentos2 = page.get_by_text(re.compile(r"^\s*suprimentos\s*$", re.I))
    suprimentos3 = page.locator("[href*='suprimentos' i], [data-menu*='suprimentos' i]")

    clicked = try_click(page, suprimentos, suprimentos2, suprimentos3, timeout=6000)
    if clicked:
        try:
            page.wait_for_load_state("networkidle", timeout=10_000)
        except PlaywrightTimeout:
            pass
        print("  ✔ Clicou em Suprimentos")
    else:
        print("  ⚠ Não encontrou Suprimentos — capturando tela para análise")

    dump_page(page, "02_menu_suprimentos")
    return clicked


def step_rcm(page: Page) -> bool:
    print("\n[3/4] Tentando abrir RCM...")

    rcm_btn = page.get_by_role("button", name=re.compile(r"^\s*rcm\s*$", re.I))
    rcm_link = page.get_by_role("link", name=re.compile(r"\brcm\b", re.I))
    rcm_text = page.get_by_text(re.compile(r"^\s*rcm\s*$", re.I))
    rcm_css = page.locator("[class*='rcm' i], [href*='rcm' i], [data-name*='rcm' i]")

    clicked = try_click(page, rcm_btn, rcm_link, rcm_text, rcm_css, timeout=6000)
    if clicked:
        try:
            page.wait_for_load_state("networkidle", timeout=10_000)
        except PlaywrightTimeout:
            pass
        print("  ✔ Clicou em RCM")
    else:
        print("  ⚠ Não encontrou RCM — capturando tela para análise")

    dump_page(page, "03_rcm")
    return clicked


def step_filtros(page: Page) -> None:
    print("\n[4/4] Capturando tela de filtros (sem preencher)...")
    # Abre cada dropdown para capturar as opções
    for label_pattern in [r"tipo", r"contrato", r"portf"]:
        combo = page.locator(
            f"[aria-label*='{label_pattern}' i], "
            f"select[name*='{label_pattern}' i], "
            f"[placeholder*='{label_pattern}' i]"
        )
        try:
            combo.first.wait_for(state="visible", timeout=3000)
            combo.first.click()
            page.wait_for_timeout(600)
        except Exception:
            pass
    dump_page(page, "04_filtros")


# ------------------------------------------------------------------ #
# Main
# ------------------------------------------------------------------ #

def main() -> None:
    config = load_config()
    print("=" * 60)
    print("  DESCOBERTA DE SELETORES — mio.app.br / RCM")
    print("=" * 60)
    print(f"Saída em: {OUT_DIR}")

    with browser_session() as (context, page):
        page.goto(config.url, wait_until="domcontentloaded")

        # Aceita cookies se aparecer
        try:
            cookie_link = page.get_by_role(
                "link", name=re.compile(r"aceito\s*/\s*i agree|i agree|aceito", re.I)
            )
            cookie_link.first.wait_for(state="visible", timeout=5000)
            cookie_link.first.click()
            page.wait_for_timeout(1000)
            print("  ✔ Cookies aceitos")
        except Exception:
            pass

        # Verifica se já está autenticado
        ms_btn = page.locator("#btn_microsoft")
        needs_login = False
        try:
            ms_btn.wait_for(state="visible", timeout=5000)
            needs_login = True
        except Exception:
            pass

        if needs_login:
            print("\n  Botão Microsoft detectado — clicando...")
            try:
                ms_btn.click()
            except Exception:
                pass
            wait_for_login(page)
        else:
            print("  ✔ Sessão reutilizada — já autenticado")
            try:
                page.wait_for_load_state("networkidle", timeout=10_000)
            except PlaywrightTimeout:
                pass

        save_session(context)
        print("  ✔ Sessão salva em storage_state.json")

        # Executa cada etapa
        step_pos_login(page)
        opened_suprimentos = step_menu_suprimentos(page)
        if opened_suprimentos:
            step_rcm(page)
            step_filtros(page)
        else:
            print("\n  ⚠ Não foi possível navegar automaticamente além do login.")
            print("  Navegue manualmente até a tela de filtros do RCM e rode:")
            print("  ./.venv/bin/python tools/inspecionar.py")

        print("\n" + "=" * 60)
        print("  DESCOBERTA CONCLUÍDA")
        print(f"  Arquivos em: {OUT_DIR}")
        print("=" * 60)


if __name__ == "__main__":
    main()
