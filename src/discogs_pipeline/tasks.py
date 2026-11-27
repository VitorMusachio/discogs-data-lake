"""Pontos de entrada chamados pelas DAGs. Imports pesados (Spark, boto3) ficam dentro das funções
para o scheduler do Airflow não pagar esse custo ao ler as DAGs."""

from __future__ import annotations

import logging

from .settings import load_settings

log = logging.getLogger(__name__)


def _context():
    from .api import DiscogsClient
    from .storage import lake_from_settings
    from .tracking import load_config

    settings = load_settings()
    client = DiscogsClient(settings.discogs_token, settings.user_agent)
    return client, lake_from_settings(settings), load_config(settings.pipeline_config)


def discovery(ds: str) -> dict:
    from .collectors.discovery import run_discovery

    return run_discovery(*_context(), ds)


def user_lists(ds: str) -> dict:
    from .collectors.users import run_user_lists

    return run_user_lists(*_context(), ds)


def snapshot(ds: str) -> dict:
    from .collectors.snapshot import run_snapshot

    return run_snapshot(*_context(), ds)


def new_entities(ds: str) -> dict:
    from .collectors.entities import run_new_entities

    return run_new_entities(*_context(), ds)


def silver(ds: str) -> dict:
    from .spark.session import create_spark
    from .spark.silver import build_silver
    from .storage import lake_from_settings
    from .tracking import TrackedReleases

    settings = load_settings()
    tracked = TrackedReleases(lake_from_settings(settings)).data
    spark = create_spark("discogs-silver", settings)
    try:
        return build_silver(spark, settings.lake_root, ds, tracked)
    finally:
        spark.stop()


def gold() -> dict:
    from .spark.gold import build_gold
    from .spark.session import create_spark
    from .trino_catalog import TrinoRegistrar

    settings = load_settings()
    spark = create_spark("discogs-gold", settings)
    try:
        registrar = TrinoRegistrar(settings.trino_host, settings.trino_port, settings.bucket)
        return build_gold(spark, settings.lake_root, settings.gold_sql_dir, register=registrar)
    finally:
        spark.stop()
