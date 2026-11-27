"""Table-level lineage derived from pipelines/*.yml and sql/**, plus the rules that keep it consistent.

Every task produces datasets and consumes datasets:
  - bronze (discogs_api): writes what its collector writes (spec.COLLECTOR_OUTPUTS), reads nothing
  - silver (spark_silver): reads the bronze_* sources its SQL cites, writes silver.<task>
  - gold   (spark_gold):   reads the silver_* tables its SQL cites, writes gold.<task>

Rules (any violation fails `check`, the DAG factory and CI):
  1. every consumed dataset has a producer
  2. a silver/gold dataset has exactly one producing task
  3. at least one producer of each input runs before the consumer: in an upstream DAG reachable through
     `schedule.after`, or in the same DAG as an upstream task
Datasets that nothing consumes are reported, not rejected.

The generated files (docs/lineage.json and docs/lineage.md) are committed. `check` regenerates them in memory and
fails when the committed copy is stale, so the lineage always follows the pipelines.

    python -m discogs_pipeline.lineage generate   # rewrite docs/lineage.*
    python -m discogs_pipeline.lineage check      # validate + fail if docs/lineage.* are out of date
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

from .spec import COLLECTOR_OUTPUTS, DagSpec, SpecError, load_specs, referenced_views

LAYER_ORDER = ("control", "bronze", "silver", "gold")


@dataclass
class TaskNode:
    dag_id: str
    task_id: str
    layer: str
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)

    @property
    def key(self) -> str:
        return f"{self.dag_id}.{self.task_id}"


@dataclass
class Lineage:
    specs: dict[str, DagSpec]
    tasks: list[TaskNode]

    def producers(self, dataset: str) -> list[TaskNode]:
        return [t for t in self.tasks if dataset in t.outputs]

    def consumers(self, dataset: str) -> list[TaskNode]:
        return [t for t in self.tasks if dataset in t.inputs]

    def datasets(self) -> list[str]:
        names = {d for t in self.tasks for d in t.inputs + t.outputs}
        return sorted(names, key=lambda d: (LAYER_ORDER.index(d.split(".")[0]), d))

    def upstream_of(self, dataset: str) -> list[str]:
        return sorted({i for p in self.producers(dataset) for i in p.inputs})

    def downstream_of(self, dataset: str) -> list[str]:
        return sorted({o for c in self.consumers(dataset) for o in c.outputs})

    def unconsumed(self) -> list[str]:
        return [d for d in self.datasets() if not self.consumers(d)]


def build(specs: dict[str, DagSpec], sql_dir: str | Path) -> Lineage:
    sql_dir = Path(sql_dir)
    tasks = []
    for spec in specs.values():
        for task in spec.tasks.values():
            node = TaskNode(spec.dag_id, task.task_id, spec.layer)
            if task.operator == "discogs_api":
                node.outputs = list(COLLECTOR_OUTPUTS[task.collector])
            else:
                views = referenced_views((sql_dir / task.sql).read_text())
                if spec.layer == "silver":
                    node.inputs = sorted(spec.sources[v].dataset for v in views["bronze"])
                else:
                    node.inputs = sorted("silver." + v.removeprefix("silver_") for v in views["silver"])
                node.outputs = [f"{spec.layer}.{task.task_id}"]
            tasks.append(node)
    return Lineage(specs, tasks)


def upstream_dags(specs: dict[str, DagSpec], dag_id: str) -> set[str]:
    """Every DAG that runs before `dag_id` through `schedule.after` (transitively)."""
    seen: set[str] = set()
    stack = list(specs[dag_id].after)
    while stack:
        d = stack.pop()
        if d not in seen:
            seen.add(d)
            stack.extend(specs[d].after)
    return seen


def validate(lineage: Lineage) -> list[str]:
    """Rule violations, as readable messages (empty list = consistent)."""
    errors = []
    for dataset in lineage.datasets():
        producers = lineage.producers(dataset)
        if dataset.split(".")[0] in ("silver", "gold") and len(producers) > 1:
            errors.append(f"{dataset} is written by more than one task: {[p.key for p in producers]}")
    for task in lineage.tasks:
        before_dags = upstream_dags(lineage.specs, task.dag_id)
        before_tasks = lineage.specs[task.dag_id].ancestors(task.task_id)
        for dataset in task.inputs:
            producers = lineage.producers(dataset)
            if not producers:
                errors.append(f"{task.key} reads {dataset}, which no task produces")
                continue
            if not any(
                p.dag_id in before_dags or (p.dag_id == task.dag_id and p.task_id in before_tasks) for p in producers
            ):
                options = ", ".join(sorted({p.dag_id for p in producers}))
                errors.append(
                    f"{task.key} reads {dataset}, but none of its producers runs before it; "
                    f"add one of [{options}] to `schedule.after` of {task.dag_id}"
                )
    return errors


def to_json(lineage: Lineage) -> str:
    doc = {
        "dags": {
            d: {"layer": s.layer, "after": list(s.after), "schedule": s.schedule}
            for d, s in sorted(lineage.specs.items())
        },
        "datasets": {
            d: {
                "producers": sorted(p.key for p in lineage.producers(d)),
                "consumers": sorted(c.key for c in lineage.consumers(d)),
                "upstream": lineage.upstream_of(d),
                "downstream": lineage.downstream_of(d),
            }
            for d in lineage.datasets()
        },
    }
    return json.dumps(doc, indent=2, sort_keys=False) + "\n"


def _node_id(dataset: str) -> str:
    return dataset.replace(".", "_")


def to_markdown(lineage: Lineage) -> str:
    lines = [
        "# Lineage",
        "",
        "<!-- Generated by `make lineage` from pipelines/*.yml and sql/**. Do not edit by hand. -->",
        "",
        "## DAGs",
        "",
        "```mermaid",
        "flowchart LR",
    ]
    for dag_id, spec in sorted(lineage.specs.items()):
        label = spec.schedule if spec.schedule else ("after upstream" if spec.after else "manual")
        lines.append(f'    {dag_id}["{dag_id}<br/>{label}"]')
    for dag_id, spec in sorted(lineage.specs.items()):
        for up in spec.after:
            lines.append(f"    {up} --> {dag_id}")
    lines += ["```", "", "## Datasets", "", "```mermaid", "flowchart LR"]
    for layer in LAYER_ORDER:
        members = [d for d in lineage.datasets() if d.startswith(layer + ".")]
        if members:
            lines.append(f"    subgraph {layer}")
            lines += [f'        {_node_id(d)}["{d.split(".", 1)[1]}"]' for d in members]
            lines.append("    end")
    edges = sorted({(i, o) for t in lineage.tasks for i in t.inputs for o in t.outputs})
    lines += [f"    {_node_id(i)} --> {_node_id(o)}" for i, o in edges]
    lines += [
        "```",
        "",
        "## Dependencies",
        "",
        "| Dataset | Produced by | Upstream | Downstream |",
        "|---|---|---|---|",
    ]
    for d in lineage.datasets():
        producers = ", ".join(f"`{p.key}`" for p in lineage.producers(d)) or "—"
        up = ", ".join(f"`{u}`" for u in lineage.upstream_of(d)) or "—"
        down = ", ".join(f"`{x}`" for x in lineage.downstream_of(d)) or "—"
        lines.append(f"| `{d}` | {producers} | {up} | {down} |")
    unconsumed = [d for d in lineage.unconsumed() if not d.startswith("gold.")]
    if unconsumed:
        lines += [
            "",
            "Written but not read by any task (kept for lineage and debugging): "
            + ", ".join(f"`{d}`" for d in unconsumed)
            + ".",
        ]
    return "\n".join(lines) + "\n"


def render(lineage: Lineage) -> dict[str, str]:
    return {"lineage.json": to_json(lineage), "lineage.md": to_markdown(lineage)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m discogs_pipeline.lineage", description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=("generate", "check"))
    parser.add_argument("--pipelines", default="pipelines")
    parser.add_argument("--sql", default="sql")
    parser.add_argument("--out", default="docs")
    args = parser.parse_args(argv)

    try:
        lineage = build(load_specs(args.pipelines, args.sql), args.sql)
    except SpecError as exc:
        print(f"invalid pipeline spec: {exc}", file=sys.stderr)
        return 1
    errors = validate(lineage)
    if errors:
        print("lineage is inconsistent:\n  - " + "\n  - ".join(errors), file=sys.stderr)
        return 1

    out = Path(args.out)
    files = render(lineage)
    if args.command == "generate":
        out.mkdir(parents=True, exist_ok=True)
        for name, content in files.items():
            (out / name).write_text(content)
        print(f"wrote {', '.join(str(out / n) for n in files)}")
        return 0
    stale = [
        name for name, content in files.items() if not (out / name).exists() or (out / name).read_text() != content
    ]
    if stale:
        print(f"{', '.join(stale)} out of date; run `make lineage` and commit the result", file=sys.stderr)
        return 1
    print("lineage OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
