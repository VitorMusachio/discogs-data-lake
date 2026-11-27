"""Bronze no MinIO -> operadores silver e gold do Airflow -> tabelas consultáveis no Trino."""

from dataclasses import replace

import pytest

from discogs_pipeline.operators import SparkGoldOperator, SparkSilverOperator
from discogs_pipeline.spec import load_specs
from discogs_pipeline.storage import S3Lake
from discogs_pipeline.trino_catalog import TrinoRegistrar

from fakes import seed_bronze_day

D1, D2 = "2026-11-26", "2026-11-27"


@pytest.fixture(scope="module")
def lake(it_settings):
    s = it_settings
    lake = S3Lake(s.s3_endpoint, s.s3_access_key, s.s3_secret_key, s.bucket)
    existing = [b["Name"] for b in lake.client.list_buckets()["Buckets"]]
    if s.bucket in existing:  # recomeça do zero
        objs = lake.client.list_objects_v2(Bucket=s.bucket).get("Contents", [])
        while objs:
            lake.client.delete_objects(Bucket=s.bucket, Delete={"Objects": [{"Key": o["Key"]} for o in objs]})
            objs = lake.client.list_objects_v2(Bucket=s.bucket).get("Contents", [])
    else:
        lake.client.create_bucket(Bucket=s.bucket)
    return lake


@pytest.fixture(scope="module")
def trino(it_settings):
    return TrinoRegistrar(it_settings.trino_host, it_settings.trino_port, it_settings.bucket, it_settings.gold_schema)


@pytest.fixture(scope="module")
def pipeline(it_settings, lake, trino):
    specs = load_specs(it_settings.pipelines_dir, it_settings.sql_dir)
    silver, gold = specs["silver_discogs"], specs["gold_discogs"]
    results = {}
    for ds, have in ((D1, 100), (D2, 120)):
        seed_bronze_day(lake, ds, have=have, first_day=ds == D1)
        for task in silver.tasks.values():
            op = SparkSilverOperator(task_id=task.task_id, dag_spec=silver, task_spec=task)
            results[f"silver.{task.task_id}.{ds}"] = op.run(ds, it_settings)
    for task in gold.tasks.values():
        op = SparkGoldOperator(task_id=task.task_id, dag_spec=gold, task_spec=task)
        results[f"gold.{task.task_id}"] = op.run(D2, it_settings)
    return results


def q(trino, sql):
    return trino.query(sql.replace("{s}", f"lakehouse.{trino.schema}"))


def test_silver_writes_daily_partitions_in_minio(pipeline, lake, it_settings):
    keys = [o["Key"] for o in lake.client.list_objects_v2(Bucket=it_settings.bucket, Prefix="silver/releases/")["Contents"]]
    assert any(f"dt={D1}/" in k for k in keys) and any(f"dt={D2}/" in k for k in keys)
    assert pipeline[f"silver.releases.{D2}"]["rows"] == 2


def test_every_gold_table_is_queryable_in_trino(pipeline, trino, it_settings):
    tables = {r[0] for r in q(trino, "SHOW TABLES FROM {s}")}
    gold = load_specs(it_settings.pipelines_dir, it_settings.sql_dir)["gold_discogs"]
    assert tables == set(gold.tasks)
    for table in tables:
        assert q(trino, f"SELECT count(*) FROM {{s}}.{table}")[0][0] == pipeline[f"gold.{table}"]["rows"]


def test_snapshot_partitions_and_star_join(pipeline, trino):
    parts = q(trino, 'SELECT dt_snapshot FROM {s}."fact_release_snapshot$partitions" ORDER BY 1')
    assert [str(p[0]) for p in parts] == [D1, D2]
    joined = q(trino, """
        SELECT r.ds_title, a.nm_artist, l.nm_label, s.qt_have, s.vl_lowest_price_usd
        FROM {s}.fact_release_snapshot s
        JOIN {s}.dim_release r ON r.id_release = s.id_release
        JOIN {s}.bridge_release_artist b ON b.id_release = s.id_release AND b.nr_position = 1
        JOIN {s}.dim_artist a ON a.id_artist = b.id_artist
        JOIN {s}.dim_label l ON l.id_label = r.id_label
        WHERE s.dt_snapshot = DATE '2026-11-27'""")
    assert len(joined) == 1
    title, artist, label, have, price = joined[0]
    assert (title, artist, label, have) == ("Nevermind", "Nirvana", "DGC", 120)
    assert float(price) == 12.34


def test_gold_rebuild_is_idempotent(pipeline, it_settings, trino):
    gold = load_specs(it_settings.pipelines_dir, it_settings.sql_dir)["gold_discogs"]
    task = gold.tasks["fact_release_snapshot"]
    again = SparkGoldOperator(task_id=task.task_id, dag_spec=gold, task_spec=task).run(D2, it_settings)
    assert again["rows"] == pipeline["gold.fact_release_snapshot"]["rows"]
    assert q(trino, "SELECT count(*) FROM {s}.fact_release_snapshot")[0][0] == again["rows"]


def test_settings_point_to_isolated_bucket(it_settings):
    assert it_settings.bucket == "lakehouse-it" and it_settings.gold_schema == "gold_it"
    assert replace(it_settings).lake_root == "s3a://lakehouse-it"
