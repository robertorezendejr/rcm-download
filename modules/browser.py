"""Ciclo de vida do navegador Google Chrome e persistência de sessão."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright

BASE_DIR = Path(__file__).resolve().parent.parent
STORAGE_STATE = BASE_DIR / "storage_state.json"


@contextmanager
def browser_session(
    headless: bool = False,
    keep_open: bool = False,
) -> Iterator[tuple[BrowserContext, Page]]:
    """Abre o Google Chrome e devolve (context, page).

    Reaproveita a sessão salva em storage_state.json quando existir,
    tornando os próximos acessos praticamente instantâneos.
    """
    with sync_playwright() as playwright:
        browser: Browser = playwright.chromium.launch(
            channel="msedge",  # usa o Microsoft Edge instalado na máquina
            headless=headless,
        )

        context_kwargs: dict = {"accept_downloads": True}
        if STORAGE_STATE.exists():
            context_kwargs["storage_state"] = str(STORAGE_STATE)

        context: BrowserContext = browser.new_context(**context_kwargs)
        page = context.new_page()
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
                browser.close()


def save_session(context: BrowserContext) -> None:
    """Persiste cookies/localStorage em storage_state.json."""
    context.storage_state(path=str(STORAGE_STATE))
