"""Bronze -> Silver -> Gold de ponta a ponta no sistema de arquivos local (sem MinIO nem Trino)."""

from datetime import date
from pathlib import Path

import pytest

pyspark = pytest.importorskip("pyspark")

from discogs_pipeline.spark.gold import build_gold, gold_queries  # noqa: E402
from discogs_pipeline.spark.session import create_spark  # noqa: E402
from discogs_pipeline.spark.silver import build_silver  # noqa: E402
from discogs_pipeline.storage import LocalLake, write_bronze  # noqa: E402
from discogs_pipeline.trino_catalog import create_table_sql  # noqa: E402

from fakes import release  # noqa: E402

SQL_DIR = Path(__file__).resolve().parents[1] / "sql" / "gold"
D1, D2 = "2026-11-26", "2026-11-27"


@pytest.fixture(scope="module")
def spark():
    session = create_spark("tests", master="local[1]")
    yield session
    session.stop()


def seed_day(lake, ds, have):
    write_bronze(lake, "releases", ds, [
        {"id": 1, "data": release(1, have=have, artists=((1, "Nirvana"), (2, "Guest")),
                                  tracks=(("A1", "Teen Spirit", "5:01"), ("A2", "In Bloom", "1:04:15"), ("B1", "Untitled", "")))},
        {"id": 2, "data": release(2, master=None, label=(0, "Not On Label", "none"))},
    ])
    write_bronze(lake, "marketplace_stats", ds, [
        {"id": 1, "data": {"lowest_price": {"value": 12.34, "currency": "USD"}, "num_for_sale": 7, "blocked_from_sale": False}},
        {"id": 2, "data": {"lowest_price": None, "num_for_sale": None, "blocked_from_sale": False}},
    ])
    first = ds == D1
    write_bronze(lake, "artists", ds, [{"id": 1, "data": {"id": 1, "name": "Nirvana"}}] if first else [])
    write_bronze(lake, "labels", ds, [{"id": 895, "data": {"id": 895, "name": "DGC", "parent_label": {"id": 1, "name": "UMG"}}}] if first else [])
    write_bronze(lake, "masters", ds, [{"id": 13814, "data": {"id": 13814, "title": "Nevermind", "year": 1991, "main_release": 1}}] if first else [])
    collection = [{"username": "vitor", "data": {"id": 1, "instance_id": 11, "folder_id": 1, "rating": 0,
                                                 "date_added": "2020-01-02T03:04:05-08:00"}}]
    if first:
        collection.append({"username": "vitor", "data": {"id": 2, "instance_id": 12, "folder_id": 1, "rating": 5,
                                                         "date_added": "2020-01-02T03:04:05-08:00"}})
    write_bronze(lake, "collection", ds, collection)
    write_bronze(lake, "wantlist", ds, [{"username": "vitor", "data": {"id": 2, "rating": 0, "date_added": "2021-01-01T00:00:00-00:00"}}])


@pytest.fixture(scope="module")
def gold(spark, tmp_path_factory):
    base = tmp_path_factory.mktemp("lake")
    lake, root = LocalLake(base), f"file://{base}"
    tracked = {"1": {"origin": "discovery:1991", "first_seen": D1}, "2": {"origin": "collection:vitor", "first_seen": D1}}
    for ds, have in ((D1, 100), (D2, 120)):
        seed_day(lake, ds, have)
        build_silver(spark, root, ds, tracked)
    counts = build_gold(spark, root, SQL_DIR)
    tables = {name: spark.read.parquet(f"{root}/gold/{name}") for name, _, _ in gold_queries(SQL_DIR)}
    return counts, tables


def rows(df, *cols, order=None):
    return [tuple(r) for r in df.select(*cols).orderBy(*(order or cols)).collect()]


def test_every_sql_file_builds_a_table(gold):
    counts, _ = gold
    assert set(counts) == {p.stem for p in SQL_DIR.glob("*.sql")}


def test_snapshot_has_one_row_per_release_per_day(gold):
    _, t = gold
    snap = t["fact_release_snapshot"]
    assert rows(snap, "id_release", "qt_have", "dt_snapshot", order=["dt_snapshot", "id_release"]) == [
        (1, 100, date.fromisoformat(D1)), (2, 100, date.fromisoformat(D1)),
        (1, 120, date.fromisoformat(D2)), (2, 100, date.fromisoformat(D2)),
    ]
    priced = {r.id_release: (r.vl_lowest_price_usd, r.qt_for_sale) for r in snap.where(f"dt_snapshot = '{D2}'").collect()}
    assert float(priced[1][0]) == 12.34 and priced[1][1] == 7
    assert priced[2] == (None, None)  # sem oferta fica nulo, não zero


def test_dimensions_keep_latest_version_and_first_values(gold):
    _, t = gold
    assert rows(t["dim_release"], "id_release", "id_master", "id_label", "ds_genre", "ds_style", "ds_format") == [
        (1, 13814, 895, "Rock", "Grunge", "Vinyl"),
        (2, None, 0, "Rock", "Grunge", "Vinyl"),
    ]
    assert str(t["dim_release"].where("id_release = 1").first().dt_released) == "1991-09-24"
    assert rows(t["dim_label"], "id_label", "nm_label", "nm_parent_label") == [(895, "DGC", "UMG")]
    assert rows(t["dim_artist"], "id_artist", "nm_artist") == [(1, "Nirvana")]
    assert rows(t["dim_master"], "id_master", "ds_title") == [(13814, "Nevermind")]


def test_bridge_and_tracks(gold):
    _, t = gold
    assert rows(t["bridge_release_artist"].where("id_release = 1"), "id_artist", "nr_position") == [(1, 1), (2, 2)]
    tracks = rows(t["dim_track"].where("id_release = 1"), "cd_position", "nr_sequence", "nr_duration_sec")
    # o título de lado ("Side A", heading) sai; a posição na lista original é mantida
    assert tracks == [("A1", 2, 301), ("A2", 3, 3855), ("B1", 4, None)]


def test_user_lists_reflect_latest_day(gold):
    _, t = gold
    assert rows(t["fact_collection_item"], "id_instance", "id_release", "nr_rating") == [(11, 1, None)]
    assert rows(t["fact_wantlist_item"], "nm_username", "id_release") == [("vitor", 2)]


def test_dim_date_and_tracked(gold):
    _, t = gold
    assert t["dim_date"].count() == 2
    assert rows(t["ctl_tracked_release"], "id_release", "ds_origin") == [(1, "discovery:1991"), (2, "collection:vitor")]


def test_trino_ddl_puts_partition_last(gold, spark):
    _, t = gold
    ddl = create_table_sql("fact_release_snapshot", t["fact_release_snapshot"].schema, "s3a://b/gold/x", "dt_snapshot")
    assert ddl.index("dt_snapshot date") > ddl.index("qt_for_sale integer")
    assert "partitioned_by = ARRAY['dt_snapshot']" in ddl
    assert "vl_lowest_price_usd decimal(12,2)" in ddl
