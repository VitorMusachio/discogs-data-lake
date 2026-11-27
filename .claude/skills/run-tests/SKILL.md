---
name: run-tests
description: Run and debug the Discogs data lake tests (unit with local Spark, integration inside the Airflow container) and fix common failures. Use when tests fail or before reporting a change as done.
---

# Run and debug tests

## Unit (no Docker)
```bash
make install      # once: .venv with pyspark, ruff, sqlfluff, pre-commit
make check        # lint + lineage-check + unit tests
```
Needs Java 17+ for Spark. `make test` alone runs only `tests/unit`.

## Integration (stack up)
```bash
make up
make test-integration
```
Runs inside `airflow-scheduler` with `tests/` and `pytest.ini` mounted. Uses a per-run bucket and the `gold_it` schema.

## Known failures and fixes
| Symptom | Cause / fix |
|---|---|
| `docs/lineage.* out of date` | run `make lineage` and commit the files |
| `reads X, but none of its producers runs before it` | add the producing DAG to `schedule.after` |
| `Could not rename s3a://...` | S3A directory committer not configured — check `spark_session.py` and the `spark-hadoop-cloud` jar |
| S3 `InternalError` on delete of a folder | SeaweedFS refuses non-empty folder deletes; the operator must pass `clear_location` |
| `Incorrect timestamp precision for timestamp(6)` | Trino catalog needs `hive.timestamp-precision=MICROSECONDS` |
| `port is already allocated` on 8080 | set `AIRFLOW_PORT` in `.env` |
| Spark task killed / hangs | lower `max_active_tasks`; Trino keeps `mem_limit: 2g` |
| a test hangs | rerun with `-o faulthandler_timeout=120` to dump the stack |

Inspect the lake with the S3 API on `localhost:8333` or the filer UI at `http://localhost:8888/buckets/`.
