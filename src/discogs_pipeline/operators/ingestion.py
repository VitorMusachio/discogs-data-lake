"""Bronze: ingestion from the Discogs API. No SQL; the YAML picks the collector by name."""

from __future__ import annotations

from importlib import import_module

from ..settings import Settings
from .base import LakeOperator

# YAML name -> (module, function) in discogs_pipeline.collectors
COLLECTORS = {
    "discovery": ("discovery", "run_discovery"),
    "user_lists": ("users", "run_user_lists"),
    "snapshot": ("snapshot", "run_snapshot"),
    "new_entities": ("entities", "run_new_entities"),
}


def get_collector(name: str):
    module, func = COLLECTORS[name]
    return getattr(import_module(f"discogs_pipeline.collectors.{module}"), func)


class DiscogsApiOperator(LakeOperator):
    ui_color = "#fdf0e1"

    def __init__(self, *, collector: str, **kwargs):
        super().__init__(**kwargs)
        if collector not in COLLECTORS:
            raise ValueError(f"Unknown collector: {collector}")
        self.collector = collector

    def run(self, ds: str, settings: Settings):
        from ..api import DiscogsClient
        from ..storage import lake_from_settings
        from ..tracking import load_config

        client = DiscogsClient(settings.discogs_token, settings.user_agent)
        return get_collector(self.collector)(client, lake_from_settings(settings), load_config(settings.pipeline_config), ds)
