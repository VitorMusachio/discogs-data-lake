@AGENTS.md

## Claude Code specifics

- Area rules in `.claude/rules/` load automatically when you touch matching files.
- Skills in `.claude/skills/` cover the recurring tasks: `add-table`, `add-collector`, `add-dag`, `impact-analysis`,
  `backfill`, `run-tests`, `review-pr`. Use them instead of improvising the steps.
- After editing anything under `pipelines/` or `sql/`, run `make lineage` and `make check` before reporting done.
