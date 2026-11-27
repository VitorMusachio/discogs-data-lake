"""Especificação declarativa das DAGs (pipelines/*.yml): leitura e validação, sem depender do Airflow.

Uma DAG por arquivo. Exemplo mínimo:

    dag_id: silver_discogs
    layer: silver
    schedule: {after: [bronze_discogs_daily]}   # cron, "@daily", null ou {after: [dag_ids]}
    sources:                                    # entradas brutas (só na silver)
      bronze_releases:
        path: bronze/releases/dt={ds}
        data_schema: id BIGINT, title STRING
    tasks:
      releases:
        operator: spark_silver                  # ver OPERATOR_KINDS
        sql: silver/releases.sql                # padrão: <layer>/<task>.sql
        upstream: []                            # tarefas da mesma DAG
        checks: {unique: [id_release], not_null: [id_release], min_rows: 1}

Validações: operador conhecido e parâmetros obrigatórios, upstream existente e sem ciclos, DAG de
`after` existente, arquivo SQL existente, e toda view citada no SQL (bronze_* / silver_*) declarada.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import yaml

LAYERS = ("bronze", "silver", "gold")

# Operadores disponíveis em cada camada e os parâmetros que exigem.
OPERATOR_KINDS: dict[str, dict[str, Any]] = {
    "discogs_api": {"layers": ("bronze",), "required": ("collector",), "sql": False},
    "spark_silver": {"layers": ("silver",), "required": (), "sql": True},
    "spark_gold": {"layers": ("gold",), "required": (), "sql": True},
}
COLLECTORS = ("discovery", "user_lists", "snapshot", "new_entities")
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
        """Tarefas que não são upstream de ninguém (o fim da DAG)."""
        used = {u for t in self.tasks.values() for u in t.upstream}
        return [t for t in self.tasks if t not in used]


def _require(cond: bool, where: str, msg: str) -> None:
    if not cond:
        raise SpecError(f"{where}: {msg}")


def _parse_source(dag_id: str, name: str, raw: dict) -> SourceSpec:
    where = f"{dag_id}.sources.{name}"
    _require(name.startswith("bronze_"), where, "fontes devem se chamar bronze_<entidade>")
    _require(isinstance(raw, dict) and "path" in raw, where, "informe `path`")
    has_data, has_full = "data_schema" in raw, "schema" in raw
    _require(has_data != has_full, where, "informe exatamente um entre `data_schema` (envelope da API) e `schema`")
    schema = f"{ENVELOPE}, data STRUCT<{raw['data_schema']}>" if has_data else raw["schema"]
    return SourceSpec(name, raw["path"], " ".join(schema.split()), "{ds}" in raw["path"])


def _parse_task(dag_id: str, layer: str, task_id: str, raw: dict) -> TaskSpec:
    where = f"{dag_id}.tasks.{task_id}"
    raw = raw or {}
    operator = raw.get("operator")
    _require(operator in OPERATOR_KINDS, where, f"operador {operator!r} desconhecido; use um de {sorted(OPERATOR_KINDS)}")
    kind = OPERATOR_KINDS[operator]
    _require(layer in kind["layers"], where, f"operador {operator} não serve para a camada {layer}")
    for param in kind["required"]:
        _require(raw.get(param), where, f"o operador {operator} exige `{param}`")
    if operator == "discogs_api":
        _require(raw["collector"] in COLLECTORS, where, f"coletor desconhecido; use um de {list(COLLECTORS)}")
    checks = raw.get("checks") or {}
    unknown = set(checks) - set(CHECK_KINDS)
    _require(not unknown, where, f"checks desconhecidos: {sorted(unknown)}")
    upstream = raw.get("upstream") or []
    _require(isinstance(upstream, list), where, "`upstream` deve ser uma lista")
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
        _require(state.get(t) != 1, spec_id, f"ciclo entre tarefas: {' -> '.join(chain + [t])}")
        state[t] = 1
        for u in tasks[t].upstream:
            visit(u, chain + [t])
        state[t] = 2

    for t in tasks:
        visit(t, [])


def parse_dag(path: Path, raw: dict) -> DagSpec:
    _require(isinstance(raw, dict), str(path), "o arquivo deve ser um mapeamento YAML")
    dag_id = raw.get("dag_id") or path.stem
    layer = raw.get("layer")
    _require(layer in LAYERS, dag_id, f"`layer` deve ser um de {LAYERS}")
    schedule, after = raw.get("schedule"), ()
    if isinstance(schedule, dict):
        _require(list(schedule) == ["after"], dag_id, "schedule em mapa só aceita a chave `after`")
        after, schedule = tuple(schedule["after"]), None
        _require(after, dag_id, "`after` precisa de ao menos uma DAG")
    sources = {n: _parse_source(dag_id, n, s) for n, s in (raw.get("sources") or {}).items()}
    _require(raw.get("tasks"), dag_id, "declare ao menos uma tarefa")
    tasks = {t: _parse_task(dag_id, layer, t, r) for t, r in raw["tasks"].items()}
    for t in tasks.values():
        for u in t.upstream:
            _require(u in tasks, f"{dag_id}.tasks.{t.task_id}", f"upstream {u!r} não existe nesta DAG")
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
    """Views citadas num SQL, por camada: {'bronze': {'bronze_releases'}, 'silver': {...}}."""
    out: dict[str, set[str]] = {"bronze": set(), "silver": set()}
    for layer, name in VIEW_RE.findall(sql):
        out[layer].add(f"{layer}_{name}")
    return out


def load_specs(pipelines_dir: str | Path, sql_dir: str | Path) -> dict[str, DagSpec]:
    """Lê e valida todos os YAML, incluindo as referências entre DAGs e entre SQL e views."""
    pipelines_dir, sql_dir = Path(pipelines_dir), Path(sql_dir)
    specs: dict[str, DagSpec] = {}
    for path in sorted(pipelines_dir.glob("*.yml")):
        spec = parse_dag(path, yaml.safe_load(path.read_text()))
        _require(spec.dag_id not in specs, str(path), f"dag_id {spec.dag_id} duplicado")
        specs[spec.dag_id] = spec

    silver_tables = {f"silver_{t}" for s in specs.values() if s.layer == "silver" for t in s.tasks}
    for spec in specs.values():
        for dep in spec.after:
            _require(dep in specs, spec.dag_id, f"DAG upstream {dep!r} não existe")
        for task in spec.tasks.values():
            if not task.sql:
                continue
            where = f"{spec.dag_id}.tasks.{task.task_id}"
            sql_path = sql_dir / task.sql
            _require(sql_path.exists(), where, f"SQL {sql_path} não encontrado")
            views = referenced_views(sql_path.read_text())
            if spec.layer == "silver":
                missing = views["bronze"] - set(spec.sources)
                _require(not missing, where, f"fontes não declaradas em `sources`: {sorted(missing)}")
                _require(views["bronze"], where, "o SQL não lê nenhuma fonte bronze_*")
            if spec.layer == "gold":
                missing = views["silver"] - silver_tables
                _require(not missing, where, f"tabelas silver inexistentes: {sorted(missing)}")
                _require(views["silver"], where, "o SQL não lê nenhuma tabela silver_*")
    return specs


def silver_tables(specs: dict[str, DagSpec]) -> dict[str, TaskSpec]:
    return {t.task_id: t for s in specs.values() if s.layer == "silver" for t in s.tasks.values()}
