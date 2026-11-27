---
name: review-pr
description: Review a pull request in this repo against its checklist and conventions (declarative DAGs, naming, checks, lineage, tests, English). Use when asked to review a PR or before opening one.
---

# Review a PR against the repo rules

1. Get the diff (`gh pr diff <n>` or `git diff main...HEAD`) and the PR body.
2. The body must follow `.github/pull_request_template.md` (Why? / What? / Tests + checklist). Flag missing sections.
3. Walk the checklist with evidence:
   - DAG changes only in `pipelines/` + `sql/`; no new Python files in `dags/`.
   - Names follow AGENTS.md (tables `dim_/fact_/bridge_/ctl_`, column prefixes, DAG ids).
   - Every new/changed task has `checks`.
   - `make lineage-check` passes; `docs/lineage.*` changed together with pipelines/SQL. Use the `impact-analysis` skill
     to list downstream effects and confirm the PR mentions breaking ones.
   - Tests: new logic covered in `tests/unit`; integration run reported when operators/infra changed.
   - API: calls through `DiscogsClient`; daily budget still fits.
   - No secrets; new settings in `.env.example`; English everywhere.
4. Run `make check` locally and report the result.
5. Report findings ordered by severity, each with file:line and a concrete fix.
