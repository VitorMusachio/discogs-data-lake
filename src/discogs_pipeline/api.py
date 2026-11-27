"""Discogs API client with rate limiting, retries and pagination.

Documented limits: 60 requests/minute when authenticated (moving 60 s window).
The API reports usage in the X-Discogs-Ratelimit-* headers.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Iterator
from typing import Any

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
            raise DiscogsError("DISCOGS_TOKEN is not set: search and the 60 req/min limit require a token.")
        self.session = session or requests.Session()
        self.session.headers.update({"Authorization": f"Discogs token={token}", "User-Agent": user_agent})
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
        """GET with retries. Returns None on 404 (removed or missing resource)."""
        url = path if path.startswith("http") else f"{BASE_URL}{path}"
        for attempt in range(self.max_retries + 1):
            self._throttle()
            try:
                resp = self.session.get(url, params=params, timeout=30)
            except requests.RequestException as exc:
                if attempt == self.max_retries:
                    raise DiscogsError(f"Network error on {url}: {exc}") from exc
                self._sleep(2**attempt)
                continue

            remaining = resp.headers.get("X-Discogs-Ratelimit-Remaining")
            if remaining is not None and remaining.isdigit() and int(remaining) <= 1:
                log.info("Rate limit almost exhausted; waiting for the window to renew.")
                self._sleep(10)

            if resp.status_code == 200:
                return resp.json()
            if resp.status_code == 404:
                return None
            if resp.status_code == 429 or resp.status_code >= 500:
                if attempt == self.max_retries:
                    break
                delay = 60 if resp.status_code == 429 else 2**attempt
                log.warning("HTTP %s on %s; retrying in %ss", resp.status_code, url, delay)
                self._sleep(delay)
                continue
            raise DiscogsError(f"HTTP {resp.status_code} on {url}: {resp.text[:200]}")
        raise DiscogsError(f"Retries exhausted on {url}")

    def paginate(
        self, path: str, key: str, params: dict[str, Any] | None = None, max_pages: int | None = None
    ) -> Iterator[dict]:
        """Iterate the items of a paginated resource (the `key` field of each response)."""
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
