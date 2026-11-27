"""Integration tests: they run inside the Airflow container, with the stack up.

    docker compose exec airflow-scheduler python -m pytest -m integration tests/integration

Each run uses its own bucket (`lakehouse-it-<timestamp>`) and the `gold_it` schema in Trino,
kept apart from real data, and drops both at the end.
"""

import importlib.util
import os
import time

import pytest

if importlib.util.find_spec("airflow.models") is None:  # outside the container: nothing to collect here
    collect_ignore_glob = ["test_*.py"]

IT_BUCKET, IT_SCHEMA = f"lakehouse-it-{int(time.time())}", "gold_it"


def pytest_collection_modifyitems(items):
    for item in items:
        item.add_marker(pytest.mark.integration)


@pytest.fixture(scope="session")
def it_settings():
    from dataclasses import replace

    from discogs_pipeline.settings import load_settings

    os.environ.pop("LAKE_ROOT", None)
    return replace(load_settings(), bucket=IT_BUCKET, gold_schema=IT_SCHEMA)
