"""Declarative DAG specification (pipelines/*.yml): parsing and validation, with no Airflow dependency.

One DAG per file. Minimal example:

    dag_id: silver_discogs
    layer: silver
    schedule: {after: [bronze_discogs_daily]}   # cron, "@daily", null or {after: [dag_ids]}
    sources:                                    # raw inputs (silver only)
      bronze_releases:
        path: bronze/releases/dt={ds}
        data_schema: id BIGINT, title STRING
    tasks:
      releases:
        operator: spark_silver                  # see OPERATOR_KINDS
        sql: silver/releases.sql                # default: <layer>/<task>.sql
        upstream: []                            # tasks in the same DAG
        checks: {unique: [id_release], not_null: [id_release], min_rows: 1}

Checks performed here: known operator and its required parameters, existing and acyclic upstream tasks,
existing `after` DAGs, existing SQL file, and every view the SQL reads (bronze_* / silver_*) is declared.
Cross-DAG data dependencies are checked by discogs_pipeline.lineage.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import yaml

LAYERS = ("bronze", "silver", "gold")

# Operators available to each layer and the parameters they require.
OPERATOR_KINDS: dict[str, dict[str, Any]] = {
    "discogs_api": {"layers": ("bronze",), "required": ("collector",), "sql": False},
    "spark_silver": {"layers": ("silver",), "required": (), "sql": True},
    "spark_gold": {"layers": ("gold",), "required": (), "sql": True},
}

# Bronze collectors and the lake datasets each one writes (used for lineage).
COLLECTOR_OUTPUTS: dict[str, tuple[str, ...]] = {
    "discovery": ("bronze.search", "control.tracked_releases"),
    "user_lists": ("bronze.collection", "bronze.wantlist", "control.tracked_releases"),
    "snapshot": ("bronze.releases", "bronze.marketplace_stats"),
    "new_entities": ("bronze.artists", "bronze.labels", "bronze.masters"),
}
COLLECTORS = tuple(COLLECTOR_OUTPUTS)
CHECK_KINDS = ("unique", "not_null", "min_rows")

VIEW_RE = re.compile(r"\b(bronze|silver)_([a-z0-9_]+)\b")
ENVELOPE = "ingested_at STRING, id BIGINT, username STRING, seed STRING"


class SpecError(ValueError):
    pass


@dataclass(frozen=True)
class SourceSpec:
    name: str
    path: str
    schema: str
    partitioned: bool

    def resolve_path(self, ds: str) -> str:
        return self.path.format(ds=ds)

    @property
    def dataset(self) -> str:
        """Lake dataset id: 'bronze/releases/dt={ds}' -> 'bronze.releases'."""
        area, name = self.path.split("/")[:2]
        return f"{area}.{name.split('.')[0]}"


@dataclass(frozen=True)
class TaskSpec:
    task_id: str
    operator: str
    upstream: tuple[str, ...] = ()
    sql: str | None = None
    collector: str | None = None
    partition_by: str | None = None
    partitioned: bool = True
    checks: dict = field(default_factory=dict)
    execution_timeout_minutes: int | None = None


@dataclass(frozen=True)
class DagSpec:
    dag_id: str
    layer: str
    description: str
    schedule: str | None
    after: tuple[str, ...]
    start_date: date
    tags: tuple[str, ...]
    retries: int
    retry_delay_minutes: int
    max_active_tasks: int
    sources: dict[str, SourceSpec]
    tasks: dict[str, TaskSpec]
    path: Path

    def leaves(self) -> list[str]:
        """Tasks that are nobody's upstream (the end of the DAG)."""
        used = {u for t in self.tasks.values() for u in t.upstream}
        return [t for t in self.tasks if t not in used]

    def ancestors(self, task_id: str) -> set[str]:
        """Every task that runs before `task_id` in this DAG."""
        seen: set[str] = set()
        stack = list(self.tasks[task_id].upstream)
        while stack:
            t = stack.pop()
            if t not in seen:
                seen.add(t)
                stack.extend(self.tasks[t].upstream)
        return seen


def _require(cond: bool, where: str, msg: str) -> None:
    if not cond:
        raise SpecError(f"{where}: {msg}")


def _parse_source(dag_id: str, name: str, raw: dict) -> SourceSpec:
    where = f"{dag_id}.sources.{name}"
    _require(name.startswith("bronze_"), where, "sources must be named bronze_<entity>")
    _require(isinstance(raw, dict) and "path" in raw, where, "`path` is required")
    has_data, has_full = "data_schema" in raw, "schema" in raw
    _require(has_data != has_full, where, "give exactly one of `data_schema` (API envelope) and `schema`")
    schema = f"{ENVELOPE}, data STRUCT<{raw['data_schema']}>" if has_data else raw["schema"]
    return SourceSpec(name, raw["path"], " ".join(schema.split()), "{ds}" in raw["path"])


def _parse_task(dag_id: str, layer: str, task_id: str, raw: dict) -> TaskSpec:
    where = f"{dag_id}.tasks.{task_id}"
    raw = raw or {}
    operator = raw.get("operator")
    _require(operator in OPERATOR_KINDS, where, f"unknown operator {operator!r}; use one of {sorted(OPERATOR_KINDS)}")
    kind = OPERATOR_KINDS[operator]
    _require(layer in kind["layers"], where, f"operator {operator} does not fit the {layer} layer")
    for param in kind["required"]:
        _require(raw.get(param), where, f"operator {operator} requires `{param}`")
    if operator == "discogs_api":
        _require(raw["collector"] in COLLECTORS, where, f"unknown collector; use one of {list(COLLECTORS)}")
    checks = raw.get("checks") or {}
    unknown = set(checks) - set(CHECK_KINDS)
    _require(not unknown, where, f"unknown checks: {sorted(unknown)}")
    upstream = raw.get("upstream") or []
    _require(isinstance(upstream, list), where, "`upstream` must be a list")
    return TaskSpec(
        task_id=task_id,
        operator=operator,
        upstream=tuple(upstream),
        sql=raw.get("sql", f"{layer}/{task_id}.sql") if kind["sql"] else None,
        collector=raw.get("collector"),
        partition_by=raw.get("partition_by"),
        partitioned=bool(raw.get("partitioned", True)),
        checks=checks,
        execution_timeout_minutes=raw.get("execution_timeout_minutes"),
    )


def _check_acyclic(spec_id: str, tasks: dict[str, TaskSpec]) -> None:
    state: dict[str, int] = {}

    def visit(t: str, chain: list[str]) -> None:
        if state.get(t) == 2:
            return
        _require(state.get(t) != 1, spec_id, f"task cycle: {' -> '.join(chain + [t])}")
        state[t] = 1
        for u in tasks[t].upstream:
            visit(u, chain + [t])
        state[t] = 2

    for t in tasks:
        visit(t, [])


def parse_dag(path: Path, raw: dict) -> DagSpec:
    _require(isinstance(raw, dict), str(path), "the file must be a YAML mapping")
    dag_id = raw.get("dag_id") or path.stem
    layer = raw.get("layer")
    _require(layer in LAYERS, dag_id, f"`layer` must be one of {LAYERS}")
    schedule, after = raw.get("schedule"), ()
    if isinstance(schedule, dict):
        _require(list(schedule) == ["after"], dag_id, "a schedule mapping only accepts the `after` key")
        after, schedule = tuple(schedule["after"]), None
        _require(after, dag_id, "`after` needs at least one DAG")
    sources = {n: _parse_source(dag_id, n, s) for n, s in (raw.get("sources") or {}).items()}
    _require(raw.get("tasks"), dag_id, "declare at least one task")
    tasks = {t: _parse_task(dag_id, layer, t, r) for t, r in raw["tasks"].items()}
    for t in tasks.values():
        for u in t.upstream:
            _require(u in tasks, f"{dag_id}.tasks.{t.task_id}", f"upstream {u!r} does not exist in this DAG")
    _check_acyclic(dag_id, tasks)
    start = raw.get("start_date", date(2026, 11, 1))
    return DagSpec(
        dag_id=dag_id,
        layer=layer,
        description=raw.get("description", ""),
        schedule=schedule,
        after=after,
        start_date=start if isinstance(start, date) else date.fromisoformat(str(start)),
        tags=tuple(raw.get("tags") or ["discogs", layer]),
        retries=int(raw.get("retries", 1)),
        retry_delay_minutes=int(raw.get("retry_delay_minutes", 10)),
        max_active_tasks=int(raw.get("max_active_tasks", 4)),
        sources=sources,
        tasks=tasks,
        path=path,
    )


def referenced_views(sql: str) -> dict[str, set[str]]:
    """Views a SQL reads, by layer: {'bronze': {'bronze_releases'}, 'silver': {...}}."""
    out: dict[str, set[str]] = {"bronze": set(), "silver": set()}
    for layer, name in VIEW_RE.findall(sql):
        out[layer].add(f"{layer}_{name}")
    return out


def load_specs(pipelines_dir: str | Path, sql_dir: str | Path) -> dict[str, DagSpec]:
    """Parse and validate every YAML, including references between DAGs and between SQL and views."""
    pipelines_dir, sql_dir = Path(pipelines_dir), Path(sql_dir)
    specs: dict[str, DagSpec] = {}
    for path in sorted(pipelines_dir.glob("*.yml")):
        spec = parse_dag(path, yaml.safe_load(path.read_text()))
        _require(spec.dag_id not in specs, str(path), f"duplicate dag_id {spec.dag_id}")
        specs[spec.dag_id] = spec

    silver_tables = {f"silver_{t}" for s in specs.values() if s.layer == "silver" for t in s.tasks}
    for spec in specs.values():
        for dep in spec.after:
            _require(dep in specs, spec.dag_id, f"upstream DAG {dep!r} does not exist")
        for task in spec.tasks.values():
            if not task.sql:
                continue
            where = f"{spec.dag_id}.tasks.{task.task_id}"
            sql_path = sql_dir / task.sql
            _require(sql_path.exists(), where, f"SQL file {sql_path} not found")
            views = referenced_views(sql_path.read_text())
            if spec.layer == "silver":
                missing = views["bronze"] - set(spec.sources)
                _require(not missing, where, f"sources not declared under `sources`: {sorted(missing)}")
                _require(views["bronze"], where, "the SQL reads no bronze_* source")
            if spec.layer == "gold":
                missing = views["silver"] - silver_tables
                _require(not missing, where, f"unknown silver tables: {sorted(missing)}")
                _require(views["silver"], where, "the SQL reads no silver_* table")
    return specs


def silver_tables(specs: dict[str, DagSpec]) -> dict[str, TaskSpec]:
    return {t.task_id: t for s in specs.values() if s.layer == "silver" for t in s.tasks.values()}
