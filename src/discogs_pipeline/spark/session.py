"""SparkSession local (dentro do worker do Airflow) configurada para o MinIO via S3A."""

from __future__ import annotations

from pyspark.sql import SparkSession


def create_spark(app_name: str, settings=None, master: str = "local[*]") -> SparkSession:
    builder = (
        SparkSession.builder.appName(app_name)
        .master(master)
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.parquet.outputTimestampType", "TIMESTAMP_MICROS")
        .config("spark.sql.shuffle.partitions", "4")
        .config("spark.ui.enabled", "false")
    )
    if settings is not None:
        builder = (
            builder.config("spark.hadoop.fs.s3a.endpoint", settings.s3_endpoint)
            .config("spark.hadoop.fs.s3a.access.key", settings.s3_access_key)
            .config("spark.hadoop.fs.s3a.secret.key", settings.s3_secret_key)
            .config("spark.hadoop.fs.s3a.path.style.access", "true")
            .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")
            .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
        )
    return builder.getOrCreate()
