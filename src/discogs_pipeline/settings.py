"""Configuração lida de variáveis de ambiente (ver .env.example)."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    discogs_token: str
    user_agent: str
    s3_endpoint: str
    s3_access_key: str
    s3_secret_key: str
    bucket: str
    pipeline_config: str
    gold_sql_dir: str
    trino_host: str
    trino_port: int

    @property
    def lake_root(self) -> str:
        """Raiz do lake no formato que o Spark entende."""
        return os.getenv("LAKE_ROOT", f"s3a://{self.bucket}")


def load_settings() -> Settings:
    return Settings(
        discogs_token=os.getenv("DISCOGS_TOKEN", ""),
        user_agent=os.getenv("DISCOGS_USER_AGENT", "DiscogsDataLake/2.0"),
        s3_endpoint=os.getenv("S3_ENDPOINT", "http://minio:9000"),
        s3_access_key=os.getenv("MINIO_ROOT_USER", "minio"),
        s3_secret_key=os.getenv("MINIO_ROOT_PASSWORD", ""),
        bucket=os.getenv("LAKE_BUCKET", "lakehouse"),
        pipeline_config=os.getenv("PIPELINE_CONFIG", "config/tracking.yml"),
        gold_sql_dir=os.getenv("GOLD_SQL_DIR", "sql/gold"),
        trino_host=os.getenv("TRINO_HOST", "trino"),
        trino_port=int(os.getenv("TRINO_PORT", "8080")),
    )
