"""Núcleo das transformações SQL (silver e gold), sem depender do Airflow.

O mesmo caminho é usado pelos operadores e pelos testes:
  1. registra como views só as entradas citadas no SQL (bronze_* com schema explícito, ou silver_*)
  2. executa o SQL no Spark
  3. grava Parquet (silver: partição dt=<ds> sobrescrita; gold: tabela inteira, opcionalmente particionada)
  4. relê o que foi gravado e roda os checks de qualidade declarados no YAML
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

from .spec import DagSpec, SourceSpec, TaskSpec, referenced_views

log = logging.getLogger(__name__)


class DataQualityError(AssertionError):
    pass


@dataclass
class TableResult:
    table: str
    location: str
    rows: int
    df: DataFrame


def register_bronze(spark: SparkSession, root: str, sources: dict[str, SourceSpec], names: set[str], ds: str) -> None:
    for name in sorted(names):
        src = sources[name]
        spark.read.schema(src.schema).json(f"{root}/{src.resolve_path(ds)}").createOrReplaceTempView(name)


def register_silver(spark: SparkSession, root: str, names: set[str]) -> None:
    for name in sorted(names):
        table = name.removeprefix("silver_")
        spark.read.parquet(f"{root}/silver/{table}").createOrReplaceTempView(name)


def output_location(root: str, layer: str, task: TaskSpec, ds: str) -> str:
    base = f"{root}/{layer}/{task.task_id}"
    return f"{base}/dt={ds}" if layer == "silver" and task.partitioned else base


def run_checks(table: str, df: DataFrame, checks: dict) -> None:
    rows = df.count()
    if rows < int(checks.get("min_rows", 0)):
        raise DataQualityError(f"{table}: {rows} linhas, mínimo {checks['min_rows']}")
    for col in checks.get("not_null", []):
        nulls = df.where(F.col(col).isNull()).count()
        if nulls:
            raise DataQualityError(f"{table}.{col}: {nulls} nulos")
    unique = checks.get("unique")
    if unique:
        dupes = df.groupBy(*unique).count().where("count > 1").count()
        if dupes:
            raise DataQualityError(f"{table}: {dupes} chaves repetidas em {unique}")


def run_sql_task(spark: SparkSession, root: str, sql_dir: str | Path, dag: DagSpec, task: TaskSpec,
                 ds: str) -> TableResult:
    sql = (Path(sql_dir) / task.sql).read_text().strip().rstrip(";")
    views = referenced_views(sql)
    if dag.layer == "silver":
        register_bronze(spark, root, dag.sources, views["bronze"], ds)
    else:
        register_silver(spark, root, views["silver"])

    location = output_location(root, dag.layer, task, ds)
    writer = spark.sql(sql).write.mode("overwrite")
    if task.partition_by:
        writer = writer.partitionBy(task.partition_by)
    writer.parquet(location)

    stored = spark.read.parquet(location)
    run_checks(task.task_id, stored, task.checks)
    rows = stored.count()
    log.info("%s.%s: %s linhas em %s", dag.layer, task.task_id, rows, location)
    return TableResult(task.task_id, location, rows, stored)
