"""Silver e gold de ponta a ponta com Spark local, a partir dos YAML e SQL reais do projeto."""

from datetime import date
from pathlib import Path

import pytest

pytest.importorskip("pyspark")

from discogs_pipeline.spark_session import create_spark  # noqa: E402
from discogs_pipeline.spec import TaskSpec, load_specs  # noqa: E402
from discogs_pipeline.storage import LocalLake  # noqa: E402
from discogs_pipeline.transform import DataQualityError, run_checks, run_sql_task  # noqa: E402
from discogs_pipeline.trino_catalog import create_table_sql  # noqa: E402

from fakes import seed_bronze_day  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
SQL = ROOT / "sql"
D1, D2 = "2026-11-26", "2026-11-27"


@pytest.fixture(scope="module")
def spark():
    session = create_spark("tests", master="local[1]")
    yield session
    session.stop()


@pytest.fixture(scope="module")
def gold(spark, tmp_path_factory):
    specs = load_specs(ROOT / "pipelines", SQL)
    base = tmp_path_factory.mktemp("lake")
    lake, root = LocalLake(base), f"file://{base}"
    silver = specs["silver_discogs"]
    for ds, have in ((D1, 100), (D2, 120)):
        seed_bronze_day(lake, ds, have=have, first_day=ds == D1)
        for task in silver.tasks.values():
            run_sql_task(spark, root, SQL, silver, task, ds)
    gold_spec = specs["gold_discogs"]
    return {t.task_id: run_sql_task(spark, root, SQL, gold_spec, t, D2).df for t in gold_spec.tasks.values()}


def rows(df, *cols, order=None):
    return [tuple(r) for r in df.select(*cols).orderBy(*(order or cols)).collect()]


def test_snapshot_has_one_row_per_release_per_day(gold):
    snap = gold["fact_release_snapshot"]
    d1, d2 = date.fromisoformat(D1), date.fromisoformat(D2)
    assert rows(snap, "id_release", "qt_have", "dt_snapshot", order=["dt_snapshot", "id_release"]) == [
        (1, 100, d1), (2, 100, d1), (1, 120, d2), (2, 100, d2)]
    priced = {r.id_release: (r.vl_lowest_price_usd, r.qt_for_sale) for r in snap.where(f"dt_snapshot = '{D2}'").collect()}
    assert float(priced[1][0]) == 12.34 and priced[1][1] == 7
    assert priced[2] == (None, None)  # sem oferta fica nulo, não zero


def test_dimensions_keep_latest_version_and_first_values(gold):
    assert rows(gold["dim_release"], "id_release", "id_master", "id_label", "ds_genre", "ds_style", "ds_format") == [
        (1, 13814, 895, "Rock", "Grunge", "Vinyl"), (2, None, 0, "Rock", "Grunge", "Vinyl")]
    assert str(gold["dim_release"].where("id_release = 1").first().dt_released) == "1991-09-24"
    assert rows(gold["dim_label"], "id_label", "nm_label", "nm_parent_label") == [(895, "DGC", "UMG")]
    assert rows(gold["dim_artist"], "id_artist", "nm_artist") == [(1, "Nirvana")]
    assert rows(gold["dim_master"], "id_master", "ds_title") == [(13814, "Nevermind")]


def test_bridge_and_tracks(gold):
    assert rows(gold["bridge_release_artist"].where("id_release = 1"), "id_artist", "nr_position") == [(1, 1), (2, 2)]
    tracks = rows(gold["dim_track"].where("id_release = 1"), "cd_position", "nr_sequence", "nr_duration_sec")
    assert tracks == [("A1", 2, 301), ("A2", 3, 3855), ("B1", 4, None)]


def test_user_lists_reflect_latest_day(gold):
    assert rows(gold["fact_collection_item"], "id_instance", "id_release", "nr_rating") == [(11, 1, None)]
    assert rows(gold["fact_wantlist_item"], "nm_username", "id_release") == [("vitor", 2)]


def test_dim_date_and_tracked(gold):
    assert gold["dim_date"].count() == 2
    assert rows(gold["ctl_tracked_release"], "id_release", "ds_origin") == [(1, "discovery:1991"), (2, "collection:vitor")]


def test_checks_reject_bad_data(spark):
    df = spark.createDataFrame([(1, "a"), (1, None)], "id long, name string")
    with pytest.raises(DataQualityError, match="chaves repetidas"):
        run_checks("t", df, {"unique": ["id"]})
    with pytest.raises(DataQualityError, match="nulos"):
        run_checks("t", df, {"not_null": ["name"]})
    with pytest.raises(DataQualityError, match="mínimo"):
        run_checks("t", df, {"min_rows": 3})
    run_checks("t", df, {"not_null": ["id"], "min_rows": 2})


def test_trino_ddl_puts_partition_last(gold):
    ddl = create_table_sql("fact_release_snapshot", gold["fact_release_snapshot"].schema, "s3a://b/gold/x", "dt_snapshot")
    assert ddl.index("dt_snapshot date") > ddl.index("qt_for_sale integer")
    assert "partitioned_by = ARRAY['dt_snapshot']" in ddl
    assert "vl_lowest_price_usd decimal(12,2)" in ddl
    assert ddl.startswith("CREATE TABLE lakehouse.gold.fact_release_snapshot")


def test_unused_task_spec_defaults():
    assert TaskSpec("x", "spark_gold").partitioned
