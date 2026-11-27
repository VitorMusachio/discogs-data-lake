"""Coleções e wantlists dos usernames configurados.

Endpoints: /users/{username}/collection/folders/0/releases (pasta 0 = "All") e /users/{username}/wants.
Cada execução grava o estado completo do dia; a Gold usa o dia mais recente de cada usuário.
Os releases encontrados entram em control/tracked_releases.json.
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
        log.warning("Nenhum username em tracking.yml; coleção e wantlist ficam vazias.")
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
    log.info("Listas de usuários: %s", counts)
    return counts
