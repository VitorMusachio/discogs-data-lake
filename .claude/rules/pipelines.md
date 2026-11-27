---
paths:
  - "pipelines/**"
  - "src/discogs_pipeline/spec.py"
  - "src/discogs_pipeline/dag_factory.py"
  - "src/discogs_pipeline/lineage.py"
---

# Pipeline YAML rules

- One DAG per file; the file name equals `dag_id`. Required keys: `dag_id`, `layer`, `description`, `schedule`, `tasks`.
- `schedule`: a cron/preset string (`"@daily"`), `null` (manual), or `{after: [dag_ids]}` (dataset-triggered when those
  DAGs finish). Downstream layers use `after`, never a cron of their own, so they process the upstream run's date.
- Tasks: `operator` is required (`discogs_api` for bronze with `collector`; `spark_silver`; `spark_gold`).
  `sql` defaults to `<layer>/<task>.sql` — only set it when the file name differs (avoid that).
- Use `upstream` only for dependencies inside the same DAG; cross-DAG data dependencies go in `schedule.after`.
- Silver `sources` declare every `bronze_<entity>` the SQL reads, with `data_schema` (API payload; the envelope is added)
  or `schema` (full schema, for control files). List only the fields you use; others are ignored.
- Every task declares `checks` (`unique`, `not_null`, optionally `min_rows`). Gold facts partitioned by date set
  `partition_by`.
- Keep `max_active_tasks: 2` for Spark DAGs.
- After any change here, run `make lineage` and commit `docs/lineage.*`; `make lineage-check` must pass.
- Changing `spec.py` or `lineage.py` rules requires updating `tests/unit/test_spec.py` / `tests/unit/test_lineage.py`.
