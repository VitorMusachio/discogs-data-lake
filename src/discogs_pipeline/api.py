"""Cliente da API do Discogs com controle de rate limit, novas tentativas e paginação.

Limites documentados: 60 requisições/minuto autenticado (janela móvel de 60 s).
A API informa o consumo nos cabeçalhos X-Discogs-Ratelimit-*.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, Iterator

import requests

log = logging.getLogger(__name__)

BASE_URL = "https://api.discogs.com"


class DiscogsError(RuntimeError):
    pass


class DiscogsClient:
    def __init__(
        self,
        token: str,
        user_agent: str,
        *,
        session: requests.Session | None = None,
        min_interval: float = 1.05,
        max_retries: int = 4,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ):
        if not token:
            raise DiscogsError("DISCOGS_TOKEN não definido: a busca e o limite de 60 req/min exigem token.")
        self.session = session or requests.Session()
        self.session.headers.update(
            {"Authorization": f"Discogs token={token}", "User-Agent": user_agent}
        )
        self.min_interval = min_interval
        self.max_retries = max_retries
        self._sleep = sleep
        self._clock = clock
        self._last_request = float("-inf")

    def _throttle(self) -> None:
        wait = self._last_request + self.min_interval - self._clock()
        if wait > 0:
            self._sleep(wait)
        self._last_request = self._clock()

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict | None:
        """GET com tentativas. Retorna None em 404 (recurso removido ou inexistente)."""
        url = path if path.startswith("http") else f"{BASE_URL}{path}"
        for attempt in range(self.max_retries + 1):
            self._throttle()
            try:
                resp = self.session.get(url, params=params, timeout=30)
            except requests.RequestException as exc:
                if attempt == self.max_retries:
                    raise DiscogsError(f"Falha de rede em {url}: {exc}") from exc
                self._sleep(2**attempt)
                continue

            remaining = resp.headers.get("X-Discogs-Ratelimit-Remaining")
            if remaining is not None and remaining.isdigit() and int(remaining) <= 1:
                log.info("Rate limit quase esgotado; aguardando a janela renovar.")
                self._sleep(10)

            if resp.status_code == 200:
                return resp.json()
            if resp.status_code == 404:
                return None
            if resp.status_code == 429 or resp.status_code >= 500:
                if attempt == self.max_retries:
                    break
                delay = 60 if resp.status_code == 429 else 2**attempt
                log.warning("HTTP %s em %s; nova tentativa em %ss", resp.status_code, url, delay)
                self._sleep(delay)
                continue
            raise DiscogsError(f"HTTP {resp.status_code} em {url}: {resp.text[:200]}")
        raise DiscogsError(f"Esgotadas as tentativas em {url}")

    def paginate(self, path: str, key: str, params: dict[str, Any] | None = None,
                 max_pages: int | None = None) -> Iterator[dict]:
        """Itera os itens de um recurso paginado (campo `key` da resposta)."""
        page = 1
        while True:
            data = self.get(path, {**(params or {}), "page": page, "per_page": 100})
            if not data:
                return
            yield from data.get(key, [])
            pages = data.get("pagination", {}).get("pages", 1)
            if page >= pages or (max_pages and page >= max_pages):
                return
            page += 1
