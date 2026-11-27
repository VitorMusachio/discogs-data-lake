"""Collections and wantlists of the configured usernames.

Endpoints: /users/{username}/collection/folders/0/releases (folder 0 = "All") and /users/{username}/wants.
Each run writes the full state for the day; gold uses each user's latest day.
Releases found here are added to control/tracked_releases.jsonl.
"""

from __future__ import annotations

import logging

from ..api import DiscogsClient
from ..storage import Lake, write_bronze
from ..tracking import TrackedReleases, TrackingConfig

log = logging.getLogger(__name__)

LISTS = {
    "collection": ("/users/{u}/collection/folders/0/releases", "releases"),
    "wantlist": ("/users/{u}/wants", "wants"),
}


def run_user_lists(client: DiscogsClient, lake: Lake, config: TrackingConfig, ds: str) -> dict:
    if not config.usernames:
        log.warning("No usernames in tracking.yml; collection and wantlist stay empty.")
    tracked = TrackedReleases(lake)
    counts = {}
    for entity, (path, key) in LISTS.items():
        records = []
        for username in config.usernames:
            items = list(client.paginate(path.format(u=username), key))
            records.extend({"username": username, "data": item} for item in items)
            for item in items:
                tracked.add(item["id"], f"{entity}:{username}", ds)
        counts[entity] = write_bronze(lake, entity, ds, records)
    tracked.save()
    log.info("User lists: %s", counts)
    return counts
