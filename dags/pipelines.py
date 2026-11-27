"""Ponto de entrada do Airflow: cria uma DAG para cada arquivo em pipelines/*.yml.

Para mudar uma DAG, edite o YAML (e o SQL em sql/<camada>/). Nada precisa ser alterado aqui.
"""

from discogs_pipeline.dag_factory import build_all
from discogs_pipeline.settings import load_settings

_settings = load_settings()
globals().update(build_all(_settings.pipelines_dir, _settings.sql_dir))
