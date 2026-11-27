---
name: backfill
description: Reprocess silver/gold for a past date or date range in the Discogs data lake. Use when asked to rerun, backfill, or fix data for specific days.
---

# Backfill / reprocess

- Bronze for a past day cannot be re-fetched: the API returns *today's* state. Backfills only rebuild silver/gold from
  bronze that already exists in `bronze/<entity>/dt=<ds>/`.
- Silver overwrites only the `dt=<ds>` partition, so reprocessing a day is safe. Trigger it with a conf date:
  ```bash
  docker compose exec airflow-scheduler airflow dags trigger silver_discogs --conf '{"ds": "2026-11-27"}'
  ```
  Gold then runs automatically (dataset trigger) and rebuilds every table from all silver partitions.
- For a range, trigger silver once per day (oldest first) and let gold run after the last one, or pause
  `gold_discogs` during the loop and trigger it once at the end.
- Check the result in Trino (`localhost:8081`): `SELECT dt_snapshot, count(*) FROM lakehouse.gold.fact_release_snapshot GROUP BY 1 ORDER BY 1`.
