"""Utilitários compartilhados: screenshots e ações tolerantes a ausência."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from playwright.sync_api import Locator, Page
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from modules.base import BASE_DIR

SCREENSHOT_DIR = BASE_DIR / "logs" / "screenshots"


class ElementNotFoundError(RuntimeError):
    """Erro lançado quando um elemento essencial não é encontrado."""


def take_screenshot(page: Page, label: str) -> Path:
    """Salva um screenshot em logs/screenshots/ com data e hora."""
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    path = SCREENSHOT_DIR / f"{label}_{stamp}.png"
    try:
        page.screenshot(path=str(path), full_page=True)
    except Exception:  # screenshot é "best effort"; nunca deve mascarar o erro real
        return path
    return path


def is_visible(locator: Locator, timeout: float = 4000) -> bool:
    """True se o elemento ficar visível dentro do timeout (ms)."""
    try:
        locator.first.wait_for(state="visible", timeout=timeout)
        return True
    except PlaywrightTimeoutError:
        return False


def click_if_visible(locator: Locator, timeout: float = 4000) -> bool:
    """Clica no elemento se ele aparecer; caso contrário, devolve False sem erro."""
    if is_visible(locator, timeout):
        locator.first.click()
        return True
    return False
