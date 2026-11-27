"""Base comum aos operadores do lake: configuração e data de referência (ds) da execução."""

from __future__ import annotations

from airflow.models import BaseOperator

from ..settings import Settings, load_settings


def resolve_ds(context) -> str:
    """Data da partição a processar.

    1. `ds` no conf de uma execução manual ({"ds": "2026-11-27"})
    2. a data lógica da DAG upstream que disparou esta execução (DAGs agendadas por dataset)
    3. a data lógica desta execução
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
    """Operador base: subclasses implementam `run(ds, settings)` e devolvem um resumo (vai para o XCom)."""

    ui_color = "#e8f1fb"

    def __init__(self, *, layer: str, **kwargs):
        super().__init__(**kwargs)
        self.layer = layer

    def run(self, ds: str, settings: Settings):  # pragma: no cover - interface
        raise NotImplementedError

    def execute(self, context):
        ds = resolve_ds(context)
        self.log.info("Camada %s, partição ds=%s", self.layer, ds)
        return self.run(ds, load_settings())
