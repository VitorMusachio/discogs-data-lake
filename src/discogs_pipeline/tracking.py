"""Configuração de acompanhamento (config/tracking.yml) e estado de controle no lake.

control/tracked_releases.json: {"<id_release>": {"origin": "...", "first_seen": "YYYY-MM-DD"}}
  Releases acompanhados no snapshot diário. Só recebe inclusões: nada sai, para as séries ficarem completas.
control/known_entities.json: {"artists": [...], "labels": [...], "masters": [...]}
  Entidades já coletadas; só IDs novos geram chamadas à API.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .storage import Lake, read_json, write_json

TRACKED_KEY = "control/tracked_releases.json"
KNOWN_KEY = "control/known_entities.json"
ENTITY_TYPES = ("artists", "labels", "masters")


@dataclass
class TrackingConfig:
    usernames: list[str] = field(default_factory=list)
    discovery: list[dict] = field(default_factory=list)
    max_tracked_releases: int = 500
    max_failure_ratio: float = 0.2


def load_config(path: str | Path) -> TrackingConfig:
    raw = yaml.safe_load(Path(path).read_text()) or {}
    limits = raw.get("limits") or {}
    usernames = [u for u in (raw.get("usernames") or []) if u and u != "seu_username_aqui"]
    return TrackingConfig(
        usernames=usernames,
        discovery=list(raw.get("discovery") or []),
        max_tracked_releases=int(limits.get("max_tracked_releases", 500)),
        max_failure_ratio=float(limits.get("max_failure_ratio", 0.2)),
    )


class TrackedReleases:
    def __init__(self, lake: Lake):
        self.lake = lake
        self.data: dict[str, dict] = read_json(lake, TRACKED_KEY, {})

    def __len__(self) -> int:
        return len(self.data)

    def ids(self) -> list[int]:
        return sorted(int(k) for k in self.data)

    def add(self, release_id: int, origin: str, ds: str) -> bool:
        key = str(release_id)
        if key in self.data:
            return False
        self.data[key] = {"origin": origin, "first_seen": ds}
        return True

    def save(self) -> None:
        write_json(self.lake, TRACKED_KEY, self.data)


class KnownEntities:
    def __init__(self, lake: Lake):
        self.lake = lake
        raw = read_json(lake, KNOWN_KEY, {})
        self.data: dict[str, set[int]] = {t: set(raw.get(t, [])) for t in ENTITY_TYPES}

    def unknown(self, entity_type: str, ids) -> list[int]:
        return sorted(set(ids) - self.data[entity_type])

    def mark(self, entity_type: str, entity_id: int) -> None:
        self.data[entity_type].add(entity_id)

    def save(self) -> None:
        write_json(self.lake, KNOWN_KEY, {t: sorted(v) for t, v in self.data.items()})
