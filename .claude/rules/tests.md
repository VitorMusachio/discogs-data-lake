---
paths:
  - "tests/**"
---

# Test rules

- `tests/unit` runs with no Docker (local Spark, Java 17+): `make test`. `tests/integration` runs inside the Airflow
  container against SeaweedFS, Hive Metastore and Trino: `make test-integration` (stack up via `make up`).
- API payloads come from `tests/fakes.py` (`release(...)`, `FakeClient`, `seed_bronze_day`); keep them in the shape the
  Discogs docs show. Never call the real API from tests.
- SQL is tested through the real `pipelines/*.yml` and `sql/**` in `tests/unit/test_transform.py`: extend
  `seed_bronze_day` and assert on the gold table instead of re-implementing logic in Python.
- Integration tests must stay isolated: per-run bucket `lakehouse-it-<timestamp>` and Trino schema `gold_it`, cleaned
  up at the end. Do not write to the `lakehouse` bucket or the `gold` schema.
- Asserting on error messages: match a stable fragment, in English.
