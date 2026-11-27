"""Gera as DAGs do Airflow a partir de pipelines/*.yml.

- tarefas e dependências internas vêm de `tasks` / `upstream`
- `schedule: {after: [dag_x]}` agenda a DAG por dataset: ela roda quando as DAGs listadas terminam
- toda DAG termina numa tarefa `publish` que emite o dataset `lakehouse://<dag_id>`
"""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.datasets import Dataset
from airflow.operators.python import PythonOperator

from .operators import OPERATORS
from .spec import DagSpec, load_specs


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
        doc_md=f"Gerada de `{spec.path.name}`. {spec.description}",
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
    return {dag_id: build_dag(spec) for dag_id, spec in load_specs(pipelines_dir, sql_dir).items()}
