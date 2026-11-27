"""Airflow entry point: builds one DAG per file in pipelines/*.yml.

To change a DAG, edit its YAML (and the SQL under sql/<layer>/). Nothing needs to change here.
"""

from discogs_pipeline.dag_factory import build_all
from discogs_pipeline.settings import load_settings

_settings = load_settings()
globals().update(build_all(_settings.pipelines_dir, _settings.sql_dir))
