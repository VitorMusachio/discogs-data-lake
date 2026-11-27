"""As DAGs geradas pelo Airflow a partir dos YAML: carregam sem erro e refletem a declaração."""

from types import SimpleNamespace

import pendulum
import pytest
from airflow.models import DagBag

from discogs_pipeline.dag_factory import dag_dataset
from discogs_pipeline.operators import OPERATORS, DiscogsApiOperator, SparkGoldOperator, SparkSilverOperator
from discogs_pipeline.operators.base import resolve_ds
from discogs_pipeline.settings import load_settings
from discogs_pipeline.spec import OPERATOR_KINDS, load_specs


@pytest.fixture(scope="module")
def dagbag():
    return DagBag(dag_folder="/opt/airflow/dags", include_examples=False)


@pytest.fixture(scope="module")
def specs():
    s = load_settings()
    return load_specs(s.pipelines_dir, s.sql_dir)


def test_no_import_errors(dagbag):
    assert dagbag.import_errors == {}


def test_one_dag_per_yaml(dagbag, specs):
    assert set(dagbag.dag_ids) == set(specs)


def test_operator_registry_matches_spec_kinds():
    assert set(OPERATORS) == set(OPERATOR_KINDS)


def test_tasks_and_dependencies_follow_yaml(dagbag, specs):
    for dag_id, spec in specs.items():
        dag = dagbag.get_dag(dag_id)
        assert set(dag.task_ids) == set(spec.tasks) | {"publish"}
        for task in spec.tasks.values():
            assert dag.get_task(task.task_id).upstream_task_ids == set(task.upstream)
        assert dag.get_task("publish").upstream_task_ids == set(spec.leaves())
        assert dag.get_task("publish").outlets == [dag_dataset(dag_id)]


def test_layers_use_their_operators(dagbag):
    assert isinstance(dagbag.get_dag("bronze_discogs_daily").get_task("snapshot"), DiscogsApiOperator)
    assert isinstance(dagbag.get_dag("silver_discogs").get_task("releases"), SparkSilverOperator)
    assert isinstance(dagbag.get_dag("gold_discogs").get_task("dim_release"), SparkGoldOperator)


def test_layers_are_chained_by_datasets(dagbag):
    assert dagbag.get_dag("bronze_discogs_daily").schedule_interval == "@daily"
    silver = dagbag.get_dag("silver_discogs").dataset_triggers
    gold = dagbag.get_dag("gold_discogs").dataset_triggers
    assert list(silver) == [dag_dataset("bronze_discogs_daily")]
    assert list(gold) == [dag_dataset("silver_discogs")]


def test_resolve_ds_prefers_conf_then_upstream_run():
    run = SimpleNamespace(conf={"ds": "2026-01-02"})
    assert resolve_ds({"dag_run": run, "ds": "2026-12-31"}) == "2026-01-02"

    upstream = SimpleNamespace(logical_date=pendulum.datetime(2026, 11, 26, tz="UTC"))
    events = {"lakehouse://bronze_discogs_daily": [SimpleNamespace(source_dag_run=upstream)]}
    ctx = {"dag_run": SimpleNamespace(conf={}), "triggering_dataset_events": events, "ds": "2026-11-27"}
    assert resolve_ds(ctx) == "2026-11-26"

    assert resolve_ds({"dag_run": None, "ds": "2026-11-27"}) == "2026-11-27"
