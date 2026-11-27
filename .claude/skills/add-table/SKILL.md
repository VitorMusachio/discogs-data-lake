---
name: add-table
description: Add or change a silver or gold table in the Discogs data lake (SQL file, YAML task, checks, tests, lineage). Use when asked for a new dimension, fact, column, or silver table.
---

# Add or change a silver/gold table

1. **Pin down the grain.** One row per what? Which columns are unique? Pick the name:
   gold `dim_`/`fact_`/`bridge_`/`ctl_` + singular noun; silver = plain entity name.
2. **Check the inputs exist** in `docs/lineage.md` (silver tables for gold; bronze sources for silver). If a field is
   missing from a silver table, add it there first (and to the silver `sources.<x>.data_schema` if it comes from the
   API payload).
3. **Write `sql/<layer>/<table>.sql`**: a single `SELECT`, starting with a `--` comment on grain and meaning.
   - Gold dims: latest version per key with `ROW_NUMBER() OVER (PARTITION BY <key> ORDER BY dt DESC) = 1`.
   - Column prefixes: `id_ dt_ ts_ qt_ vl_ nm_ ds_ nr_ cd_ fl_`; absent values are `NULL`.
4. **Declare the task** in `pipelines/<layer>_discogs.yml`:
   ```yaml
   dim_example:
     operator: spark_gold          # spark_silver for silver
     checks: {unique: [id_example], not_null: [id_example]}
     # partition_by: dt_snapshot   # gold facts with a date grain
     # partitioned: false          # silver current-state tables
   ```
5. **Test it** in `tests/unit/test_transform.py`: extend `tests/fakes.py:seed_bronze_day` if new input data is needed
   and assert on the output rows. `test_every_sql_file_belongs_to_a_task` already guards the YAML/SQL pairing.
6. **Lineage and checks:** `make format && make lineage && make check`.
7. **Docs:** add the table to the gold model table in `README.md`. In the PR, list downstream tables from
   `docs/lineage.md` and call out grain/column breaking changes.
