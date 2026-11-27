"""Leitura e escrita de objetos no lake (MinIO/S3), mais um backend local para testes.

Layout:
  bronze/<entidade>/dt=YYYY-MM-DD/part-0000.jsonl   respostas cruas da API
  silver/<tabela>/dt=YYYY-MM-DD/                     Parquet tipado (Spark)
  gold/<tabela>/                                     Parquet analítico (Spark)
  control/*.json                                     estado do pipeline
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Protocol


class Lake(Protocol):
    def put_bytes(self, key: str, data: bytes) -> None: ...
    def get_bytes(self, key: str) -> bytes | None: ...


class S3Lake:
    def __init__(self, endpoint: str, access_key: str, secret_key: str, bucket: str):
        import boto3

        self.bucket = bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name="us-east-1",
        )

    def put_bytes(self, key: str, data: bytes) -> None:
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data)

    def get_bytes(self, key: str) -> bytes | None:
        try:
            return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()
        except self.client.exceptions.NoSuchKey:
            return None


class LocalLake:
    """Mesmo contrato do S3Lake gravando numa pasta local (testes e execução sem MinIO)."""

    def __init__(self, root: str | Path):
        self.root = Path(root)

    def put_bytes(self, key: str, data: bytes) -> None:
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def get_bytes(self, key: str) -> bytes | None:
        path = self.root / key
        return path.read_bytes() if path.exists() else None


def lake_from_settings(settings) -> Lake:
    return S3Lake(settings.s3_endpoint, settings.s3_access_key, settings.s3_secret_key, settings.bucket)


def bronze_key(entity: str, ds: str) -> str:
    return f"bronze/{entity}/dt={ds}/part-0000.jsonl"


def write_bronze(lake: Lake, entity: str, ds: str, records: Iterable[dict[str, Any]]) -> int:
    """Grava os registros (envelope + payload cru) como JSON Lines. Regravar o mesmo dia sobrescreve."""
    ingested_at = datetime.now(timezone.utc).isoformat()
    lines = [json.dumps({"ingested_at": ingested_at, **rec}, ensure_ascii=False) for rec in records]
    lake.put_bytes(bronze_key(entity, ds), ("\n".join(lines) + "\n" if lines else "").encode())
    return len(lines)


def read_json(lake: Lake, key: str, default: Any) -> Any:
    raw = lake.get_bytes(key)
    return json.loads(raw) if raw else default


def write_json(lake: Lake, key: str, value: Any) -> None:
    lake.put_bytes(key, json.dumps(value, ensure_ascii=False, indent=1, sort_keys=True).encode())
