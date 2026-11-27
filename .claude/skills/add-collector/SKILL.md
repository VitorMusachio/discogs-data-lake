---
name: add-collector
description: Ingest a new Discogs API endpoint into bronze (collector, registration, YAML task, silver source, tests, call budget). Use when asked to collect new data from the Discogs API.
---

# Add a bronze collector for a new endpoint

1. **Read the endpoint docs** (https://www.discogs.com/developers/) in the browser: path, auth, pagination, payload
   fields. Note the calls per day it adds; the limit is 60/min and each tracked release already costs 2.
2. **Write `src/discogs_pipeline/collectors/<name>.py`** with `run_<name>(client, lake, config, ds) -> dict`:
   - call the API only through `client.get` / `client.paginate`;
   - write raw payloads with `write_bronze(lake, "<entity>", ds, [{"id": ..., "data": payload}])`;
   - tolerate item failures and finish with `check_failures(step, failed, total, config.max_failure_ratio)`.
3. **Register it** in `operators/ingestion.py:COLLECTORS` and in `spec.py:COLLECTOR_OUTPUTS` with every dataset it
   writes (`"bronze.<entity>"`, or `"control.<file>"`). Lineage depends on the outputs being right.
4. **Schedule it**: add a task to `pipelines/bronze_discogs_daily.yml` (`operator: discogs_api`, `collector: <name>`,
   `upstream` if it needs data from another task that day).
5. **Expose it to silver**: add `bronze_<entity>` to `sources` in `pipelines/silver_discogs.yml` with a `data_schema`
   listing only the fields you will use, then follow the `add-table` skill for the silver table.
6. **Unit tests** in `tests/unit/test_collectors.py` with `FakeClient` routes/pages shaped like the real payload,
   including a 404 and the failure-ratio path.
7. `make lineage && make check`; mention the extra daily calls in the PR.
