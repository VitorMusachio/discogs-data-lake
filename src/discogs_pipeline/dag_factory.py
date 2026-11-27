"""Build Airflow DAGs from pipelines/*.yml.

- tasks and in-DAG dependencies come from `tasks` / `upstream`
- `schedule: {after: [dag_x]}` schedules the DAG on datasets: it runs when the listed DAGs finish
- every DAG ends with a `publish` task that emits the dataset `lakehouse://<dag_id>`
- specs and lineage are validated first; an inconsistent pipeline shows up as an Airflow import error
"""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.datasets import Dataset
from airflow.operators.python import PythonOperator

from . import lineage
from .operators import OPERATORS
from .spec import DagSpec, SpecError, load_specs


def dag_dataset(dag_id: str) -> Dataset:
    return Dataset(f"lakehouse://{dag_id}")


def _done(**_):
    return None


def build_operator(spec: DagSpec, task, dag: DAG):
    cls = OPERATORS[task.operator]
    kwargs = {"task_id": task.task_id, "dag": dag}
    if task.execution_timeout_minutes:
        kwargs["execution_timeout"] = timedelta(minutes=task.execution_timeout_minutes)
    if task.operator == "discogs_api":
        return cls(layer=spec.layer, collector=task.collector, **kwargs)
    return cls(dag_spec=spec, task_spec=task, **kwargs)


def build_dag(spec: DagSpec) -> DAG:
    schedule = [dag_dataset(d) for d in spec.after] if spec.after else spec.schedule
    dag = DAG(
        dag_id=spec.dag_id,
        description=spec.description,
        schedule=schedule,
        start_date=datetime.combine(spec.start_date, datetime.min.time()),
        catchup=False,
        max_active_runs=1,
        max_active_tasks=spec.max_active_tasks,
        tags=list(spec.tags),
        default_args={"retries": spec.retries, "retry_delay": timedelta(minutes=spec.retry_delay_minutes)},
        doc_md=f"Generated from `{spec.path.name}`. {spec.description}",
    )
    ops = {t.task_id: build_operator(spec, t, dag) for t in spec.tasks.values()}
    for task in spec.tasks.values():
        for up in task.upstream:
            ops[up] >> ops[task.task_id]
    publish = PythonOperator(task_id="publish", python_callable=_done, outlets=[dag_dataset(spec.dag_id)], dag=dag)
    for leaf in spec.leaves():
        ops[leaf] >> publish
    return dag


def build_all(pipelines_dir: str, sql_dir: str) -> dict[str, DAG]:
    specs = load_specs(pipelines_dir, sql_dir)
    errors = lineage.validate(lineage.build(specs, sql_dir))
    if errors:
        raise SpecError("lineage is inconsistent:\n  - " + "\n  - ".join(errors))
    return {dag_id: build_dag(spec) for dag_id, spec in specs.items()}
