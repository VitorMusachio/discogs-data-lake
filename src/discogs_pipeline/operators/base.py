"""Common base for lake operators: settings and the partition date (ds) of the run."""

from __future__ import annotations

from airflow.models import BaseOperator

from ..settings import Settings, load_settings


def resolve_ds(context) -> str:
    """Partition date to process.

    1. `ds` in the conf of a manual run ({"ds": "2026-11-27"})
    2. the logical date of the upstream DAG run that triggered this one (dataset-scheduled DAGs)
    3. the logical date of this run
    """
    dag_run = context.get("dag_run")
    conf = getattr(dag_run, "conf", None) or {}
    if conf.get("ds"):
        return conf["ds"]
    for events in (context.get("triggering_dataset_events") or {}).values():
        for event in events:
            source = getattr(event, "source_dag_run", None)
            if source is not None and source.logical_date is not None:
                return source.logical_date.strftime("%Y-%m-%d")
    return context["ds"]


class LakeOperator(BaseOperator):
    """Base operator: subclasses implement `run(ds, settings)` and return a summary (pushed to XCom)."""

    ui_color = "#e8f1fb"

    def __init__(self, *, layer: str, **kwargs):
        super().__init__(**kwargs)
        self.layer = layer

    def run(self, ds: str, settings: Settings):  # pragma: no cover - interface
        raise NotImplementedError

    def execute(self, context):
        ds = resolve_ds(context)
        self.log.info("Layer %s, partition ds=%s", self.layer, ds)
        return self.run(ds, load_settings())
