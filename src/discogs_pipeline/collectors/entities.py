"""Artists, labels and masters cited by the day's releases, collected only when the ID is new."""

from __future__ import annotations

import json
import logging

from ..api import DiscogsClient, DiscogsError
from ..storage import Lake, bronze_key, write_bronze
from ..tracking import ENTITY_TYPES, KnownEntities, TrackingConfig
from . import check_failures

log = logging.getLogger(__name__)


def entity_ids(release: dict) -> dict[str, set[int]]:
    """IDs referenced by a /releases/{id} payload.

    Artists and labels with id 0 are Discogs placeholders (e.g. "Various", "Not On Label").
    """
    ids = {t: set() for t in ENTITY_TYPES}
    for artist in release.get("artists") or []:
        if artist.get("id"):
            ids["artists"].add(artist["id"])
    for label in release.get("labels") or []:
        if label.get("id"):
            ids["labels"].add(label["id"])
    if release.get("master_id"):
        ids["masters"].add(release["master_id"])
    return ids


def read_bronze_releases(lake: Lake, ds: str) -> list[dict]:
    raw = lake.get_bytes(bronze_key("releases", ds)) or b""
    return [json.loads(line)["data"] for line in raw.decode().splitlines() if line.strip()]


def run_new_entities(client: DiscogsClient, lake: Lake, config: TrackingConfig, ds: str) -> dict:
    known = KnownEntities(lake)
    referenced = {t: set() for t in ENTITY_TYPES}
    for release in read_bronze_releases(lake, ds):
        for t, ids in entity_ids(release).items():
            referenced[t] |= ids

    counts, failed, total = {}, 0, 0
    for entity_type in ENTITY_TYPES:
        records = []
        for entity_id in known.unknown(entity_type, referenced[entity_type]):
            total += 1
            try:
                data = client.get(f"/{entity_type}/{entity_id}")
            except DiscogsError as exc:
                failed += 1
                log.warning("%s %s: %s", entity_type, entity_id, exc)
                continue
            if data is not None:
                records.append({"id": entity_id, "data": data})
            known.mark(entity_type, entity_id)
        counts[entity_type] = write_bronze(lake, entity_type, ds, records)
    known.save()
    check_failures("new entities", failed, total, config.max_failure_ratio)
    return counts
