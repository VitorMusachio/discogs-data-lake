## Why?

<!-- The problem or need behind this change. Link the issue if there is one (Closes #...). -->

## What?

<!-- What changed, in reviewer terms: new/changed DAGs, tables, columns, collectors, infra. -->

## Tests

<!-- How this was verified. Paste the commands and their results. -->

- [ ] `make check` (lint + lineage + unit tests)
- [ ] `make test-integration` (needed when operators, Spark/Trino/S3 config, docker-compose or the DAG factory change)

## Checklist

**Pipelines and data**
- [ ] DAG changes are made in `pipelines/*.yml` and `sql/**`, not in Python DAG files
- [ ] New or changed tables follow the naming conventions (`dim_`/`fact_`/`bridge_`/`ctl_` tables; `id_`, `dt_`, `ts_`, `qt_`, `vl_`, `nm_`, `ds_`, `nr_`, `cd_`, `fl_` columns)
- [ ] Every new table declares `checks` (at least the key as `unique` / `not_null`)
- [ ] `docs/lineage.md` and `docs/lineage.json` are regenerated (`make lineage`), and the downstream impact is described above
- [ ] Breaking changes to gold columns or grain are called out (Metabase questions and Trino queries may depend on them)

**Code**
- [ ] Unit tests cover new logic (collectors with `tests/fakes.py`, SQL through `tests/unit/test_transform.py`)
- [ ] API calls go through `DiscogsClient` (rate limit, retries) and the daily call budget in `config/tracking.yml` still fits
- [ ] No secrets or tokens committed (`.env` stays local; new settings are added to `.env.example`)
- [ ] Code, comments and docs are in English

**Docs**
- [ ] README updated when behavior, setup or the gold model changed
- [ ] `CLAUDE.md` / `.claude/rules` / skills updated when a convention changed
