# Agent guide: Discogs Data Lake

Local lakehouse with Discogs API data. Airflow DAGs are **declared in YAML**; silver and gold tables are **SQL files**
run by Spark; gold is published in Trino. Read this before changing anything. Area rules live in `.claude/rules/`.

## Layout

| Path | What lives there |
|---|---|
| `pipelines/*.yml` | One DAG per file: schedule or upstream DAGs (`schedule.after`), tasks, operator, `upstream`, `checks` |
| `sql/silver/<table>.sql`, `sql/gold/<table>.sql` | One table per file; file name = task id = table name |
| `src/discogs_pipeline/spec.py` | YAML parsing/validation, operator kinds, collector outputs (no Airflow import) |
| `src/discogs_pipeline/lineage.py` | Table-level lineage + dependency rules; renders `docs/lineage.*` |
| `src/discogs_pipeline/dag_factory.py`, `dags/pipelines.py` | YAML → Airflow DAGs (never edit `dags/` to add a DAG) |
| `src/discogs_pipeline/operators/` | `DiscogsApiOperator` (bronze), `SparkSqlOperator` → `SparkSilverOperator` / `SparkGoldOperator` |
| `src/discogs_pipeline/transform.py` | Spark core shared by operators and tests: views, SQL, write, checks |
| `src/discogs_pipeline/collectors/` | Bronze API collectors (`discovery`, `user_lists`, `snapshot`, `new_entities`) |
| `config/tracking.yml` | Usernames, discovery seeds, call budget limits |
| `tests/unit`, `tests/integration` | Unit (local Spark) and integration (inside the Airflow container) |
| `docs/lineage.md`, `docs/lineage.json` | Generated lineage — never edit by hand |

## Commands

```bash
make install           # .venv + dev deps + git hooks
make check             # lint + lineage-check + unit tests (what CI runs)
make lineage           # regenerate docs/lineage.* after touching pipelines/ or sql/
make up                # start the stack (Airflow on AIRFLOW_PORT, Trino 8081, Metabase 3000, S3 8333)
make test-integration  # integration tests inside the Airflow container
```

## Rules that always apply

1. **DAGs are declarative.** Add or change DAGs only in `pipelines/*.yml` and `sql/**`. A new kind of step means a new
   operator in `operators/` plus an entry in `OPERATOR_KINDS` (`spec.py`) and `OPERATORS` (`operators/__init__.py`).
2. **Lineage must stay consistent and committed.** Every task input needs a producer that runs before it (an upstream
   DAG in `schedule.after`, or an upstream task in the same DAG); one writer per silver/gold table. Run `make lineage`
   and commit `docs/lineage.*` with the change — CI fails otherwise.
3. **Naming.**
   - DAG ids: `<layer>_<source>[_<cadence>]` (e.g. `bronze_discogs_daily`, `silver_discogs`, `gold_discogs`).
   - Views inside SQL: `bronze_<entity>` (declared in the silver YAML `sources`) and `silver_<table>`.
   - Gold tables: `dim_<entity>`, `fact_<event_or_snapshot>`, `bridge_<a>_<b>`, `ctl_<thing>` (singular nouns).
   - Columns: `id_` key, `dt_` date, `ts_` timestamp, `qt_` quantity, `vl_` value (currency in the name, e.g.
     `vl_lowest_price_usd`), `nm_` name, `ds_` description/text, `nr_` number, `cd_` code, `fl_` boolean.
4. **Every table declares `checks`** in its YAML (at least its key as `unique` + `not_null`).
5. **Layers.** Bronze = raw JSON per day (`bronze/<entity>/dt=<ds>/`), never transformed. Silver = typed and renamed,
   one `dt` partition per day (or `partitioned: false` for current-state tables). Gold = rebuilt fully every run from
   silver and registered in Trino. Gold never reads bronze; silver never reads silver.
6. **API calls** go through `DiscogsClient` (60 req/min, retries). Keep the daily budget in `config/tracking.yml` in
   mind: each tracked release costs 2 calls a day. New collectors must declare their outputs in `COLLECTOR_OUTPUTS`.
7. **Tests.** New logic gets unit tests (`tests/fakes.py` for API payloads; SQL through `tests/unit/test_transform.py`).
   Changes to operators, Spark/Trino/S3 config or the factory also need `make test-integration`.
8. **English** for code, comments, logs, docs and commit messages. **No secrets** in git (`.env` is local; add new
   settings to `.env.example`).

## Known environment quirks

- S3 is **SeaweedFS** (MinIO stopped publishing images). Spark uses the S3A `directory` committer and the operators
  empty the destination through the S3 API before overwriting (`S3Lake.delete_prefix`), because SeaweedFS refuses to
  delete non-empty folders. Do not remove either.
- Trino's Hive catalog uses `hive.timestamp-precision=MICROSECONDS` to match Spark's `TIMESTAMP_MICROS`.
- Each Spark task starts its own JVM; keep `max_active_tasks` low (2) on 8 GB machines.

## Pull requests

Use `.github/pull_request_template.md` (Why? / What? / Tests + checklist). Describe downstream impact using
`docs/lineage.md` when tables or columns change.
