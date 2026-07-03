"""Ciclo de vida do navegador Google Chrome e persistência de sessão."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from playwright.sync_api import BrowserContext, Page, sync_playwright

from modules.base import BASE_DIR
STORAGE_STATE = BASE_DIR / "storage_state.json"
USER_DATA_DIR = BASE_DIR / "edge_profile"


@contextmanager
def browser_session(
    headless: bool = False,
    keep_open: bool = False,
) -> Iterator[tuple[BrowserContext, Page]]:
    """Abre o Microsoft Edge e devolve (context, page).

    Usa um perfil persistente em edge_profile/, evitando que o navegador
    abra como uma janela anônima/InPrivate a cada execução.
    """
    with sync_playwright() as playwright:
        USER_DATA_DIR.mkdir(parents=True, exist_ok=True)

        context: BrowserContext = playwright.chromium.launch_persistent_context(
            str(USER_DATA_DIR),
            channel="msedge",  # usa o Microsoft Edge instalado na máquina
            headless=headless,
            accept_downloads=True,
        )
        page = context.pages[0] if context.pages else context.new_page()
        try:
            yield context, page
        finally:
            if keep_open:
                # Mantém o Edge aberto até o usuário fechar manualmente
                try:
                    page.wait_for_event("close", timeout=0)
                except Exception:
                    pass
            else:
                context.close()


def save_session(context: BrowserContext) -> None:
    """Persiste cookies/localStorage em storage_state.json."""
    context.storage_state(path=str(STORAGE_STATE))
