"""Testes de integração: rodam dentro do container do Airflow, com a stack no ar.

    docker compose exec airflow-scheduler python -m pytest -m integration tests/integration

Usam um bucket (`lakehouse-it`) e um schema no Trino (`gold_it`) separados dos dados reais.
"""

import importlib.util
import os

import pytest

if importlib.util.find_spec("airflow.models") is None:  # fora do container: nada a coletar aqui
    collect_ignore_glob = ["test_*.py"]

IT_BUCKET, IT_SCHEMA = "lakehouse-it", "gold_it"


def pytest_collection_modifyitems(items):
    for item in items:
        item.add_marker(pytest.mark.integration)


@pytest.fixture(scope="session")
def it_settings():
    from dataclasses import replace

    from discogs_pipeline.settings import load_settings

    os.environ.pop("LAKE_ROOT", None)
    return replace(load_settings(), bucket=IT_BUCKET, gold_schema=IT_SCHEMA)
