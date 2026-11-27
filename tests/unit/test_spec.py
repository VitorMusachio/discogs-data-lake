"""Validação dos YAML de pipeline (sem Airflow)."""

from pathlib import Path

import pytest
import yaml

from discogs_pipeline.spec import SpecError, load_specs, parse_dag, referenced_views, silver_tables

ROOT = Path(__file__).resolve().parents[2]
PIPELINES, SQL = ROOT / "pipelines", ROOT / "sql"


def test_project_pipelines_are_valid():
    specs = load_specs(PIPELINES, SQL)
    assert set(specs) == {"bronze_discogs_discovery", "bronze_discogs_daily", "silver_discogs", "gold_discogs"}
    assert specs["silver_discogs"].after == ("bronze_discogs_daily",)
    assert specs["gold_discogs"].after == ("silver_discogs",)
    assert specs["bronze_discogs_daily"].schedule == "@daily"
    assert specs["bronze_discogs_daily"].leaves() == ["new_entities"]


def test_every_sql_file_belongs_to_a_task():
    specs = load_specs(PIPELINES, SQL)
    declared = {t.sql for s in specs.values() for t in s.tasks.values() if t.sql}
    on_disk = {str(p.relative_to(SQL)) for p in SQL.rglob("*.sql")}
    assert declared == on_disk


def test_sql_defaults_to_layer_and_task_name():
    specs = load_specs(PIPELINES, SQL)
    assert specs["gold_discogs"].tasks["dim_release"].sql == "gold/dim_release.sql"
    assert specs["gold_discogs"].tasks["fact_release_snapshot"].partition_by == "dt_snapshot"
    assert not silver_tables(specs)["tracked_releases"].partitioned


def test_data_schema_gets_the_api_envelope():
    src = load_specs(PIPELINES, SQL)["silver_discogs"].sources["bronze_releases"]
    assert src.schema.startswith("ingested_at STRING, id BIGINT, username STRING, seed STRING, data STRUCT<id BIGINT")
    assert src.resolve_path("2026-11-27") == "bronze/releases/dt=2026-11-27"


def test_referenced_views():
    sql = "SELECT * FROM silver_releases r JOIN silver_marketplace_stats s ON 1=1 -- bronze_x"
    assert referenced_views(sql) == {"bronze": {"bronze_x"}, "silver": {"silver_releases", "silver_marketplace_stats"}}


def write(tmp_path, name, body):
    (tmp_path / "pipelines").mkdir(exist_ok=True)
    (tmp_path / "pipelines" / f"{name}.yml").write_text(yaml.safe_dump(body))


def sql(tmp_path, rel, text):
    path = tmp_path / "sql" / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def bronze(tasks):
    return {"layer": "bronze", "schedule": "@daily", "tasks": tasks}


@pytest.mark.parametrize("body, message", [
    (bronze({"a": {"operator": "nope"}}), "operador 'nope' desconhecido"),
    (bronze({"a": {"operator": "discogs_api"}}), "exige `collector`"),
    (bronze({"a": {"operator": "discogs_api", "collector": "xyz"}}), "coletor desconhecido"),
    (bronze({"a": {"operator": "spark_gold"}}), "não serve para a camada bronze"),
    (bronze({"a": {"operator": "discogs_api", "collector": "snapshot", "upstream": ["b"]}}), "upstream 'b' não existe"),
    (bronze({"a": {"operator": "discogs_api", "collector": "snapshot", "upstream": ["b"]},
             "b": {"operator": "discogs_api", "collector": "snapshot", "upstream": ["a"]}}), "ciclo"),
    (bronze({"a": {"operator": "discogs_api", "collector": "snapshot", "checks": {"foo": 1}}}), "checks desconhecidos"),
    ({"layer": "platinum", "tasks": {}}, "`layer` deve ser"),
])
def test_invalid_dag_specs(tmp_path, body, message):
    with pytest.raises(SpecError, match=message):
        parse_dag(tmp_path / "x.yml", body)


def test_upstream_dag_must_exist(tmp_path):
    write(tmp_path, "s", {"layer": "silver", "schedule": {"after": ["ghost"]},
                          "sources": {"bronze_a": {"path": "bronze/a/dt={ds}", "data_schema": "id BIGINT"}},
                          "tasks": {"t": {"operator": "spark_silver"}}})
    sql(tmp_path, "silver/t.sql", "SELECT data.id FROM bronze_a")
    with pytest.raises(SpecError, match="DAG upstream 'ghost' não existe"):
        load_specs(tmp_path / "pipelines", tmp_path / "sql")


def test_silver_sql_must_read_declared_sources(tmp_path):
    write(tmp_path, "s", {"layer": "silver", "schedule": None,
                          "sources": {"bronze_a": {"path": "bronze/a/dt={ds}", "data_schema": "id BIGINT"}},
                          "tasks": {"t": {"operator": "spark_silver"}}})
    sql(tmp_path, "silver/t.sql", "SELECT * FROM bronze_b")
    with pytest.raises(SpecError, match="fontes não declaradas"):
        load_specs(tmp_path / "pipelines", tmp_path / "sql")


def test_gold_sql_must_read_existing_silver_tables(tmp_path):
    write(tmp_path, "g", {"layer": "gold", "schedule": None, "tasks": {"t": {"operator": "spark_gold"}}})
    sql(tmp_path, "gold/t.sql", "SELECT * FROM silver_ghost")
    with pytest.raises(SpecError, match="tabelas silver inexistentes"):
        load_specs(tmp_path / "pipelines", tmp_path / "sql")


def test_missing_sql_file(tmp_path):
    write(tmp_path, "g", {"layer": "gold", "schedule": None, "tasks": {"t": {"operator": "spark_gold"}}})
    with pytest.raises(SpecError, match="não encontrado"):
        load_specs(tmp_path / "pipelines", tmp_path / "sql")


def test_source_needs_exactly_one_schema(tmp_path):
    body = {"layer": "silver", "tasks": {"t": {"operator": "spark_silver"}},
            "sources": {"bronze_a": {"path": "x", "schema": "a INT", "data_schema": "b INT"}}}
    with pytest.raises(SpecError, match="exatamente um"):
        parse_dag(tmp_path / "x.yml", body)
