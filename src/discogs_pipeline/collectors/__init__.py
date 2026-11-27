"""Bronze collectors. Each function receives the client, the lake, the tracking config and the run date (ds)."""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)


class TooManyFailures(RuntimeError):
    pass


def check_failures(step: str, failed: int, total: int, max_ratio: float) -> None:
    """Occasional failures are tolerated (the item is retried tomorrow); too many fail the task."""
    if total and failed / total > max_ratio:
        raise TooManyFailures(f"{step}: {failed} of {total} calls failed (limit {max_ratio:.0%}).")
    if failed:
        log.warning("%s: %s of %s calls failed and will be retried on the next run.", step, failed, total)
