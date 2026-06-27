"""Relato de progresso no terminal (etapas do robô)."""

from __future__ import annotations

from rich.console import Console


class ProgressReporter:
    """Imprime as etapas da automação de forma legível e colorida."""

    def __init__(self) -> None:
        self._console = Console()

    def stage(self, message: str) -> None:
        self._console.print(f"[bold cyan]▶[/] {message}")

    def success(self, message: str) -> None:
        self._console.print(f"[bold green]✔[/] {message}")

    def warn(self, message: str) -> None:
        self._console.print(f"[bold yellow]![/] {message}")

    def error(self, message: str) -> None:
        self._console.print(f"[bold red]✖[/] {message}")
