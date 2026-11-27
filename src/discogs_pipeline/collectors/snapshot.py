"""Daily snapshot of the tracked releases: release detail + marketplace stats in USD.

- /releases/{id}?curr_abbr=USD          attributes, artists[], labels[], tracklist[], community.have/want
- /marketplace/stats/{id}?curr_abbr=USD  lowest_price, num_for_sale, blocked_from_sale (no login needed)
"""

from __future__ import annotations

import logging

from ..api import DiscogsClient, DiscogsError
from ..storage import Lake, write_bronze
from ..tracking import TrackedReleases, TrackingConfig
from . import check_failures

log = logging.getLogger(__name__)

CURRENCY = "USD"


def run_snapshot(client: DiscogsClient, lake: Lake, config: TrackingConfig, ds: str) -> dict:
    ids = TrackedReleases(lake).ids()
    releases, stats, failed = [], [], 0
    for release_id in ids:
        try:
            release = client.get(f"/releases/{release_id}", {"curr_abbr": CURRENCY})
            if release is None:
                log.info("Release %s no longer exists (404).", release_id)
                continue
            releases.append({"id": release_id, "data": release})
            market = client.get(f"/marketplace/stats/{release_id}", {"curr_abbr": CURRENCY})
            if market is not None:
                stats.append({"id": release_id, "data": market})
        except DiscogsError as exc:
            failed += 1
            log.warning("Release %s: %s", release_id, exc)
    write_bronze(lake, "releases", ds, releases)
    write_bronze(lake, "marketplace_stats", ds, stats)
    check_failures("snapshot", failed, len(ids), config.max_failure_ratio)
    return {"tracked": len(ids), "releases": len(releases), "stats": len(stats), "failed": failed}
