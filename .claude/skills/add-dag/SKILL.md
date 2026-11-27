---
name: add-dag
description: Create a new declarative Airflow DAG from a YAML file in pipelines/ (schedule or upstream DAGs, tasks, validation). Use when asked for a new pipeline, a new schedule, or a new layer DAG.
---

# Add a declarative DAG

1. Choose the id `<layer>_<source>[_<cadence>]` and create `pipelines/<dag_id>.yml`:
   ```yaml
   dag_id: gold_discogs_weekly
   layer: gold                    # bronze | silver | gold
   description: One sentence on what it builds.
   schedule: {after: [silver_discogs]}   # or "@weekly", or null for manual
   max_active_tasks: 2
   tasks:
     some_table:
       operator: spark_gold
       checks: {unique: [id_x]}
   ```
2. Cross-DAG data dependencies go in `schedule.after` (dataset scheduling); `upstream` is only for tasks inside the
   same DAG. Do not add Python files to `dags/` — `dags/pipelines.py` builds every YAML automatically.
3. A table must have exactly one writer: if the new DAG rebuilds a table another DAG owns, move it instead.
4. Validate: `make lineage-check` explains missing producers (e.g. "add one of [...] to `schedule.after`").
   Then `make lineage && make check`.
5. With the stack up, `make test-integration` confirms Airflow loads it (`test_one_dag_per_yaml`,
   `test_tasks_and_dependencies_follow_yaml`). Mention the new DAG and its trigger in the README.
