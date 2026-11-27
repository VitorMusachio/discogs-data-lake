"""Settings read from environment variables (see .env.example)."""

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
    pipelines_dir: str
    sql_dir: str
    gold_schema: str
    trino_host: str
    trino_port: int

    @property
    def lake_root(self) -> str:
        """Lake root in the form Spark understands."""
        return os.getenv("LAKE_ROOT", f"s3a://{self.bucket}")


def load_settings() -> Settings:
    return Settings(
        discogs_token=os.getenv("DISCOGS_TOKEN", ""),
        user_agent=os.getenv("DISCOGS_USER_AGENT", "DiscogsDataLake/2.0"),
        s3_endpoint=os.getenv("S3_ENDPOINT", "http://seaweedfs:8333"),
        s3_access_key=os.getenv("S3_ACCESS_KEY", "lake"),
        s3_secret_key=os.getenv("S3_SECRET_KEY", ""),
        bucket=os.getenv("LAKE_BUCKET", "lakehouse"),
        pipeline_config=os.getenv("PIPELINE_CONFIG", "config/tracking.yml"),
        pipelines_dir=os.getenv("PIPELINES_DIR", "pipelines"),
        sql_dir=os.getenv("SQL_DIR", "sql"),
        gold_schema=os.getenv("GOLD_SCHEMA", "gold"),
        trino_host=os.getenv("TRINO_HOST", "trino"),
        trino_port=int(os.getenv("TRINO_PORT", "8080")),
    )
