"""Ferramenta de inspeção de seletores.

Abre o Edge, navega até o sistema, faz login (se a sessão não estiver salva),
deixa o navegador ABERTO e imprime, a cada ENTER no terminal, todos os
elementos interativos visíveis (inputs, botões, links, comboboxes) com seus
id / name / placeholder / aria-label / texto.

Use para descobrir os seletores reais de cada tela pós-login:
  ./.venv/bin/python tools/inspecionar.py

Fluxo sugerido:
  1. Rode o script. Faça o login Microsoft na janela (MFA) na 1ª vez.
  2. Navegue manualmente OU deixe o robô navegar; a cada tela, volte ao
     terminal e pressione ENTER para listar os elementos daquela tela.
  3. Anote os id/textos e atualize modules/navegacao.py e modules/download.py.
  4. Digite 'q' + ENTER para sair (a sessão é salva em storage_state.json).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from modules.browser import browser_session, save_session  # noqa: E402
from modules.config import load_config  # noqa: E402


def dump(page) -> None:
    print("\n" + "=" * 70)
    print("URL atual:", page.url)

    print("\n--- INPUTS / TEXTAREAS / SELECTS ---")
    for el in page.locator("input, textarea, select").all():
        try:
            if not el.is_visible():
                continue
            print({
                "tag": el.evaluate("e => e.tagName.toLowerCase()"),
                "type": el.get_attribute("type"),
                "id": el.get_attribute("id"),
                "name": el.get_attribute("name"),
                "placeholder": el.get_attribute("placeholder"),
                "aria-label": el.get_attribute("aria-label"),
            })
        except Exception:
            pass

    print("\n--- BOTÕES / LINKS / COMBOBOX (texto visível) ---")
    for sel in ["button", "a", "[role=button]", "[role=combobox]", "[role=option]"]:
        for el in page.locator(sel).all():
            try:
                if not el.is_visible():
                    continue
                txt = (el.inner_text() or "").strip().replace("\n", " ")
                if txt:
                    print(f"{sel:16} | id={el.get_attribute('id')} "
                          f"| aria-label={el.get_attribute('aria-label')} | '{txt[:70]}'")
            except Exception:
                pass
    print("=" * 70)


def main() -> None:
    config = load_config()
    with browser_session() as (context, page):
        page.goto(config.url, wait_until="domcontentloaded")
        print("\nNavegador aberto em", config.url)
        print("Faça o login na janela (se necessário) e navegue até a tela desejada.")
        print("Pressione ENTER para listar os elementos da tela atual.")
        print("Digite 'q' + ENTER para sair e salvar a sessão.\n")

        while True:
            cmd = input(">> ENTER para inspecionar / 'q' para sair: ").strip().lower()
            if cmd == "q":
                break
            dump(page)

        save_session(context)
        print("Sessão salva em storage_state.json")


if __name__ == "__main__":
    main()
