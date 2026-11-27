"""Read and write lake objects (S3: SeaweedFS), plus a local backend for tests.

Layout:
  bronze/<entity>/dt=YYYY-MM-DD/part-0000.jsonl   raw API responses
  silver/<table>/dt=YYYY-MM-DD/                    typed Parquet (Spark)
  gold/<table>/                                    analytical Parquet (Spark)
  control/*                                        pipeline state
"""

from __future__ import annotations

import contextlib
import json
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol


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

    def delete_prefix(self, prefix: str) -> int:
        """Delete everything under `prefix/`: files first, then the now-empty folders, deepest first.

        SeaweedFS stores folders as real directories and refuses to delete a non-empty one, while S3A's
        overwrite deletes the destination folder as a single object. Emptying it here first avoids that.
        """
        prefix = prefix.strip("/")
        keys = [
            o["Key"]
            for o in self.client.get_paginator("list_objects_v2")
            .paginate(Bucket=self.bucket, Prefix=prefix + "/")
            .search("Contents")
            if o
        ]
        for i in range(0, len(keys), 1000):
            self.client.delete_objects(
                Bucket=self.bucket, Delete={"Objects": [{"Key": k} for k in keys[i : i + 1000]], "Quiet": True}
            )
        folders = {prefix}
        for key in keys:
            parts = key.split("/")[:-1]
            folders.update("/".join(parts[:n]) for n in range(len(prefix.split("/")), len(parts) + 1))
        for folder in sorted(folders, key=lambda f: f.count("/"), reverse=True):
            for name in (folder + "/", folder):
                # a folder may already be gone or never have been materialized
                with contextlib.suppress(self.client.exceptions.ClientError):
                    self.client.delete_object(Bucket=self.bucket, Key=name)
        return len(keys)


class LocalLake:
    """Same contract as S3Lake, backed by a local folder (tests and runs without S3)."""

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
    """Write records (envelope + raw payload) as JSON Lines. Writing the same day again overwrites it."""
    ingested_at = datetime.now(UTC).isoformat()
    lines = [json.dumps({"ingested_at": ingested_at, **rec}, ensure_ascii=False) for rec in records]
    lake.put_bytes(bronze_key(entity, ds), ("\n".join(lines) + "\n" if lines else "").encode())
    return len(lines)


def read_json(lake: Lake, key: str, default: Any) -> Any:
    raw = lake.get_bytes(key)
    return json.loads(raw) if raw else default


def write_json(lake: Lake, key: str, value: Any) -> None:
    lake.put_bytes(key, json.dumps(value, ensure_ascii=False, indent=1, sort_keys=True).encode())
