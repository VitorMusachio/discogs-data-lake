"""Silver -> Gold: executa cada sql/gold/*.sql no Spark e grava o resultado em gold/<tabela>/.

Cada arquivo SQL vira uma tabela com o mesmo nome. As tabelas da Silver ficam disponíveis como
views `silver_<tabela>`. Um comentário `-- partition_by: coluna` no SQL particiona a saída.
A Gold é reconstruída inteira a cada execução (o volume é pequeno e isso mantém tudo idempotente).
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from pyspark.sql import SparkSession

log = logging.getLogger(__name__)

SILVER_TABLES = (
    "releases", "release_artists", "tracks", "marketplace_stats", "masters", "artists", "labels",
    "collection_items", "wantlist_items", "tracked_releases",
)
PARTITION_RE = re.compile(r"^--\s*partition_by:\s*(\w+)", re.MULTILINE)


def register_silver_views(spark: SparkSession, root: str) -> None:
    for table in SILVER_TABLES:
        spark.read.parquet(f"{root}/silver/{table}").createOrReplaceTempView(f"silver_{table}")


def gold_queries(sql_dir: str | Path) -> list[tuple[str, str, str | None]]:
    out = []
    for path in sorted(Path(sql_dir).glob("*.sql")):
        sql = path.read_text()
        match = PARTITION_RE.search(sql)
        out.append((path.stem, sql.strip().rstrip(";"), match.group(1) if match else None))
    return out


def build_gold(spark: SparkSession, root: str, sql_dir: str | Path, register=None) -> dict[str, int]:
    """`register(table, df, location, partition_col)` publica a tabela no catálogo (Trino); opcional."""
    register_silver_views(spark, root)
    counts = {}
    for table, sql, partition_col in gold_queries(sql_dir):
        df = spark.sql(sql)
        location = f"{root}/gold/{table}"
        writer = df.write.mode("overwrite")
        if partition_col:
            writer = writer.partitionBy(partition_col)
        writer.parquet(location)
        counts[table] = spark.read.parquet(location).count()
        if register:
            register(table, df, location, partition_col)
        log.info("gold.%s: %s linhas", table, counts[table])
    return counts
