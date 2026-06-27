"""Fluxo de login: cookies, autenticação Microsoft e reaproveitamento de sessão.

Os seletores da tela Microsoft (login.microsoftonline.com) seguem o padrão
estável da Microsoft. Os seletores do site mio.app.br são "best effort" e
podem precisar de ajuste fino na primeira execução real (veja README).
"""

from __future__ import annotations

import logging
import re

from playwright.sync_api import Page

from .config import AppConfig
from .progress import ProgressReporter
from .utils import ElementNotFoundError, click_if_visible, is_visible


class LoginManager:
    """Garante que a sessão esteja autenticada antes de navegar no sistema."""

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
    def ensure_logged_in(self) -> bool:
        """Faz login se necessário. Retorna True se o login foi executado."""
        self._page.goto(self._config.url, wait_until="domcontentloaded")
        self._accept_cookies()

        if self._already_authenticated():
            self._progress.success("Sessão reutilizada — login não necessário")
            self._log.info("Login reutilizado via storage_state.json")
            return False

        self._click_microsoft()
        self._fill_email()
        self._choose_corporate_account()
        self._fill_password()
        self._handle_stay_signed_in()
        self._wait_app_loaded()

        self._progress.success("Login realizado")
        self._log.info("Login realizado")
        return True

    # ------------------------------------------------------------------ #
    # Etapas internas
    # ------------------------------------------------------------------ #
    def _accept_cookies(self) -> None:
        """Aceita o aviso de cookies, se existir. Nunca gera erro se ausente.

        No mio.app.br o aceite é um link com o texto "Aceito / I Agree";
        só após aceitar é que o botão Microsoft fica disponível.
        """
        link = self._page.get_by_text(re.compile(r"aceito|i agree", re.I))
        if click_if_visible(link, timeout=5000):
            self._page.wait_for_timeout(1000)
            self._log.info("Cookie encontrado e aceito")
        else:
            self._log.info("Cookie não encontrado")

    def _already_authenticated(self) -> bool:
        """Considera autenticado quando o botão Microsoft não aparece."""
        microsoft = self._microsoft_locator()
        return not is_visible(microsoft, timeout=5000)

    def _click_microsoft(self) -> None:
        self._progress.stage("Autenticando com a Microsoft...")
        if not click_if_visible(self._microsoft_locator(), timeout=8000):
            raise ElementNotFoundError("Botão de login Microsoft não encontrado")

    def _fill_email(self) -> None:
        field = self._page.locator("input[type='email'], input[name='loginfmt']")
        if is_visible(field, timeout=8000):
            field.first.fill(self._config.email)
            self._click_next()

    def _choose_corporate_account(self) -> None:
        """Escolhe sempre 'Conta corporativa', se a tela aparecer."""
        tile = self._page.get_by_text(
            re.compile(r"conta corporativa|trabalho ou escola|work or school", re.I)
        )
        if click_if_visible(tile, timeout=4000):
            self._log.info("Conta corporativa selecionada")

    def _fill_password(self) -> None:
        field = self._page.locator("input[type='password'], input[name='passwd']")
        if is_visible(field, timeout=8000):
            # Só preenche se o campo estiver vazio (ex.: senha já salva no navegador).
            if not field.first.input_value():
                field.first.fill(self._config.password)
            self._click_sign_in()

    def _handle_stay_signed_in(self) -> None:
        """Clica em 'Sim/Yes' no prompt 'Manter conectado?' da Microsoft."""
        # O botão "Sim" na tela de manter conectado tem id="idSIButton9"
        yes_button = self._page.locator("#idSIButton9").or_(
            self._page.get_by_role("button", name=re.compile(r"sim|yes", re.I))
        )
        click_if_visible(yes_button, timeout=8000)

    def _wait_app_loaded(self) -> None:
        """Aguarda o retorno ao sistema e o carregamento completo."""
        self._page.wait_for_url(re.compile(r"mio\.app\.br"), timeout=120000)
        self._page.wait_for_load_state("networkidle")

    # ------------------------------------------------------------------ #
    # Auxiliares
    # ------------------------------------------------------------------ #
    def _microsoft_locator(self):
        # No mio.app.br o link de login Microsoft tem href contendo "loginMicrosoft".
        return self._page.locator("a[href*='loginMicrosoft']")

    def _click_next(self) -> None:
        button = self._page.get_by_role(
            "button", name=re.compile(r"avançar|próximo|next", re.I)
        ).or_(self._page.locator("input#idSIButton9"))
        click_if_visible(button, timeout=6000)

    def _click_sign_in(self) -> None:
        button = self._page.get_by_role(
            "button", name=re.compile(r"entrar|sign in|fazer login", re.I)
        ).or_(self._page.locator("input#idSIButton9"))
        click_if_visible(button, timeout=6000)
