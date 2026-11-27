---
name: impact-analysis
description: Find what is upstream and downstream of a table, column, collector or DAG before changing it, using the generated lineage. Use when asked "what breaks if...", before renames/removals, or when describing a PR's impact.
---

# Impact analysis

1. `make lineage` so `docs/lineage.json` reflects the working tree.
2. For a dataset (e.g. `silver.releases`), read `datasets["silver.releases"]` in `docs/lineage.json`:
   `producers`, `consumers`, `upstream`, `downstream`. Walk `downstream` recursively to reach every gold table.
3. For a column, `grep -n "<column>" sql/**/*.sql` limited to the downstream SQL files found above, plus Trino/Metabase
   usage the user mentions.
4. Classify the change: additive (new column/table) vs breaking (rename, type change, grain change, removal).
   Breaking gold changes need a call-out in the PR.
5. Report a short table: dataset → impacted downstream tables → what to update (SQL, checks, tests, README).
