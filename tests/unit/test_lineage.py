"""Lineage built from the YAML/SQL: dependency rules and the generated docs."""

from pathlib import Path

import yaml

from discogs_pipeline import lineage
from discogs_pipeline.spec import load_specs

ROOT = Path(__file__).resolve().parents[2]


def project_lineage():
    return lineage.build(load_specs(ROOT / "pipelines", ROOT / "sql"), ROOT / "sql")


def test_project_lineage_is_consistent():
    assert lineage.validate(project_lineage()) == []


def test_upstream_and_downstream_of_a_table():
    lin = project_lineage()
    assert lin.upstream_of("silver.releases") == ["bronze.releases"]
    assert lin.upstream_of("gold.fact_release_snapshot") == ["silver.marketplace_stats", "silver.releases"]
    assert "gold.dim_release" in lin.downstream_of("silver.releases")
    assert [p.key for p in lin.producers("bronze.releases")] == ["bronze_discogs_daily.snapshot"]
    assert {p.key for p in lin.producers("control.tracked_releases")} == {
        "bronze_discogs_daily.user_lists",
        "bronze_discogs_discovery.discovery",
    }


def test_committed_docs_are_up_to_date():
    """Same rule CI enforces: run `make lineage` after changing pipelines/ or sql/."""
    for name, content in lineage.render(project_lineage()).items():
        assert (ROOT / "docs" / name).read_text() == content, f"docs/{name} is stale; run `make lineage`"


def make_project(tmp_path, specs: dict[str, dict], sql: dict[str, str]):
    (tmp_path / "pipelines").mkdir()
    for name, body in specs.items():
        (tmp_path / "pipelines" / f"{name}.yml").write_text(yaml.safe_dump(body))
    for rel, text in sql.items():
        path = tmp_path / "sql" / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    specs_ = load_specs(tmp_path / "pipelines", tmp_path / "sql")
    return lineage.build(specs_, tmp_path / "sql")


BRONZE = {
    "layer": "bronze",
    "schedule": "@daily",
    "tasks": {"snapshot": {"operator": "discogs_api", "collector": "snapshot"}},
}
SOURCES = {"bronze_releases": {"path": "bronze/releases/dt={ds}", "data_schema": "id BIGINT"}}


def test_consumer_must_run_after_a_producer(tmp_path):
    silver = {
        "layer": "silver",
        "schedule": "@daily",
        "sources": SOURCES,
        "tasks": {"releases": {"operator": "spark_silver"}},
    }
    lin = make_project(
        tmp_path,
        {"bronze_x": BRONZE, "silver_x": silver},
        {"silver/releases.sql": "SELECT data.id FROM bronze_releases"},
    )
    [error] = lineage.validate(lin)
    assert "silver_x.releases reads bronze.releases" in error
    assert "add one of [bronze_x] to `schedule.after` of silver_x" in error


def test_upstream_through_after_chain_is_accepted(tmp_path):
    silver = {
        "layer": "silver",
        "schedule": {"after": ["bronze_x"]},
        "sources": SOURCES,
        "tasks": {"releases": {"operator": "spark_silver"}},
    }
    gold = {"layer": "gold", "schedule": {"after": ["silver_x"]}, "tasks": {"dim": {"operator": "spark_gold"}}}
    lin = make_project(
        tmp_path,
        {"bronze_x": BRONZE, "silver_x": silver, "gold_x": gold},
        {"silver/releases.sql": "SELECT data.id FROM bronze_releases", "gold/dim.sql": "SELECT * FROM silver_releases"},
    )
    assert lineage.validate(lin) == []
    assert lineage.upstream_dags(lin.specs, "gold_x") == {"silver_x", "bronze_x"}


def test_input_without_producer(tmp_path):
    sources = {"bronze_ghost": {"path": "bronze/ghost/dt={ds}", "data_schema": "id BIGINT"}}
    silver = {
        "layer": "silver",
        "schedule": {"after": ["bronze_x"]},
        "sources": sources,
        "tasks": {"ghost": {"operator": "spark_silver"}},
    }
    lin = make_project(
        tmp_path, {"bronze_x": BRONZE, "silver_x": silver}, {"silver/ghost.sql": "SELECT * FROM bronze_ghost"}
    )
    assert lineage.validate(lin) == ["silver_x.ghost reads bronze.ghost, which no task produces"]


def test_same_table_written_twice(tmp_path):
    silver = {
        "layer": "silver",
        "schedule": {"after": ["bronze_x"]},
        "sources": SOURCES,
        "tasks": {"releases": {"operator": "spark_silver"}},
    }
    lin = make_project(
        tmp_path,
        {"bronze_x": BRONZE, "silver_a": silver, "silver_b": silver},
        {"silver/releases.sql": "SELECT data.id FROM bronze_releases"},
    )
    errors = lineage.validate(lin)
    assert any("silver.releases is written by more than one task" in e for e in errors)


def test_check_command_detects_stale_docs(tmp_path, capsys):
    args = ["--pipelines", str(ROOT / "pipelines"), "--sql", str(ROOT / "sql"), "--out", str(tmp_path)]
    assert lineage.main(["check", *args]) == 1
    assert "out of date" in capsys.readouterr().err
    assert lineage.main(["generate", *args]) == 0
    assert lineage.main(["check", *args]) == 0
