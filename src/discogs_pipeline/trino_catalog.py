"""Publica as tabelas Gold no Trino (catálogo `lakehouse`, schema `gold`) como tabelas externas no Hive Metastore.

O Spark só grava Parquet; o Trino registra a tabela com o schema do DataFrame.
Os caminhos usam s3a:// porque o Hive Metastore (Hadoop) só conhece esse esquema; o Trino aceita os dois.
Como são tabelas externas, DROP + CREATE apaga só o metadado, nunca os dados.
"""

from __future__ import annotations

from pyspark.sql import types as T

CATALOG, SCHEMA = "lakehouse", "gold"


def trino_type(dt: T.DataType) -> str:
    if isinstance(dt, T.StringType):
        return "varchar"
    if isinstance(dt, T.LongType):
        return "bigint"
    if isinstance(dt, T.IntegerType):
        return "integer"
    if isinstance(dt, T.DoubleType):
        return "double"
    if isinstance(dt, T.BooleanType):
        return "boolean"
    if isinstance(dt, T.DateType):
        return "date"
    if isinstance(dt, T.TimestampType):
        return "timestamp(6)"
    if isinstance(dt, T.DecimalType):
        return f"decimal({dt.precision},{dt.scale})"
    raise TypeError(f"Tipo sem mapeamento para o Trino: {dt}")


def create_table_sql(table: str, schema: T.StructType, location: str, partition_col: str | None) -> str:
    fields = [f for f in schema.fields if f.name != partition_col]
    if partition_col:
        fields.append(schema[partition_col])  # no Hive, colunas de partição vêm por último
    cols = ",\n  ".join(f"{f.name} {trino_type(f.dataType)}" for f in fields)
    props = [f"external_location = '{location}'", "format = 'PARQUET'"]
    if partition_col:
        props.append(f"partitioned_by = ARRAY['{partition_col}']")
    return f"CREATE TABLE {CATALOG}.{SCHEMA}.{table} (\n  {cols}\n)\nWITH ({', '.join(props)})"


class TrinoRegistrar:
    def __init__(self, host: str, port: int, bucket: str):
        import trino

        self.conn = trino.dbapi.connect(host=host, port=port, user="airflow", catalog=CATALOG)
        self._exec(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{SCHEMA} "
                   f"WITH (location = 's3a://{bucket}/gold/')")

    def _exec(self, sql: str) -> None:
        cur = self.conn.cursor()
        cur.execute(sql)
        cur.fetchall()

    def __call__(self, table: str, df, location: str, partition_col: str | None) -> None:
        self._exec(f"DROP TABLE IF EXISTS {CATALOG}.{SCHEMA}.{table}")
        self._exec(create_table_sql(table, df.schema, location, partition_col))
        if partition_col:
            self._exec(f"CALL {CATALOG}.system.sync_partition_metadata('{SCHEMA}', '{table}', 'FULL')")
