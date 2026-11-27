"""Coletores da camada bronze. Cada função recebe cliente, lake e data de execução (ds)."""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)


class TooManyFailures(RuntimeError):
    pass


def check_failures(step: str, failed: int, total: int, max_ratio: float) -> None:
    """Falhas pontuais são toleradas (o item é tentado de novo amanhã); muitas derrubam a tarefa."""
    if total and failed / total > max_ratio:
        raise TooManyFailures(f"{step}: {failed} de {total} chamadas falharam (limite {max_ratio:.0%}).")
    if failed:
        log.warning("%s: %s de %s chamadas falharam e serão tentadas na próxima execução.", step, failed, total)
