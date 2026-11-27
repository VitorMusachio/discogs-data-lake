---
paths:
  - "sql/**"
---

# SQL rules (Spark SQL)

- One `SELECT` per file producing exactly one table; no `CREATE`, `INSERT` or `;` — the operator writes the result.
- Read only views of the previous layer: silver reads `bronze_<entity>` (columns under `data.*` plus the envelope:
  `ingested_at`, `id`, `username`, `seed`); gold reads `silver_<table>` (each has a `dt` partition column unless the
  table is `partitioned: false`).
- Gold dimensions take the latest version per key: `ROW_NUMBER() OVER (PARTITION BY <key> ORDER BY dt DESC) = 1`.
  Current-state facts join on the latest `dt` per owner (see `fact_collection_item.sql`).
- Name every output column with the prefixes in AGENTS.md (`id_`, `dt_`, `ts_`, `qt_`, `vl_`, `nm_`, `ds_`, `nr_`,
  `cd_`, `fl_`). Currency goes in value names (`_usd`).
- Absent is `NULL`, not zero or empty string (`NULLIF(x, '')`, `NULLIF(rating, 0)`).
- Style is enforced by sqlfluff (`.sqlfluff`): uppercase keywords and functions, explicit `AS` for aliases,
  `INNER JOIN` spelled out. Run `make format` to fix. Start the file with a `--` comment stating grain and meaning.
- A new file needs a task in the layer's YAML (and checks), then `make lineage`.
