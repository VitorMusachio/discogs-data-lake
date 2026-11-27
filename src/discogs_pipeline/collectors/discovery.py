"""Discovery: turn the seeds in tracking.yml into tracked releases.

Search (/database/search) only returns release IDs: `label` is a list of names and there is no
artist field. Artists, labels and masters come later, from each release's detail.
"""

from __future__ import annotations

import logging

from ..api import DiscogsClient
from ..storage import Lake, write_bronze
from ..tracking import TrackedReleases, TrackingConfig

log = logging.getLogger(__name__)

SEARCH_FIELDS = ("year", "genre", "style", "country", "format")


def seed_origin(seed: dict) -> str:
    parts = [str(seed[f]) for f in SEARCH_FIELDS if seed.get(f)]
    return "discovery:" + "-".join(parts or ["all"])


def search_params(seed: dict) -> dict:
    params = {f: seed[f] for f in SEARCH_FIELDS if seed.get(f)}
    params["type"] = "release"
    params["sort"] = seed.get("sort", "want")
    params["sort_order"] = "desc"
    return params


def release_ids_from_search(results: list[dict]) -> list[int]:
    return [r["id"] for r in results if r.get("type") == "release" and isinstance(r.get("id"), int)]


def run_discovery(client: DiscogsClient, lake: Lake, config: TrackingConfig, ds: str) -> dict:
    tracked = TrackedReleases(lake)
    raw, added = [], 0
    for seed in config.discovery:
        origin = seed_origin(seed)
        results = list(client.paginate("/database/search", "results", search_params(seed),
                                       max_pages=int(seed.get("pages", 1))))
        raw.extend({"seed": origin, "data": r} for r in results)
        for release_id in release_ids_from_search(results):
            if len(tracked) >= config.max_tracked_releases:
                log.warning("Reached the cap of %s tracked releases; skipping the remaining seeds.",
                            config.max_tracked_releases)
                break
            added += tracked.add(release_id, origin, ds)
    write_bronze(lake, "search", ds, raw)
    tracked.save()
    log.info("Discovery: %s results, %s new releases, %s tracked in total.", len(raw), added, len(tracked))
    return {"results": len(raw), "added": added, "tracked": len(tracked)}
