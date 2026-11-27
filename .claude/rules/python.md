---
paths:
  - "src/**"
  - "dags/**"
---

# Python rules

- `spec.py`, `lineage.py`, `transform.py`, `collectors/` and `api.py` must not import Airflow, so unit tests and CI run
  without it. Airflow imports live in `operators/` and `dag_factory.py` only.
- Heavy imports (pyspark, boto3, trino) go inside functions in operators, so DAG parsing stays fast.
- Operators stay thin: parse context → `resolve_ds` → call `transform` / a collector. Business logic belongs in
  `transform.py` or `collectors/`, where it is unit-tested.
- New collectors: function `run_<name>(client, lake, config, ds) -> dict`, registered in
  `operators/ingestion.py:COLLECTORS` and `spec.py:COLLECTOR_OUTPUTS` (with the datasets it writes). Write raw payloads
  with `write_bronze`; tolerate per-item failures with `check_failures`.
- Lake writes go through `Lake` (`S3Lake` / `LocalLake`); never call boto3 directly elsewhere.
- Ruff config is in `pyproject.toml` (line length 120). Run `make format`.
