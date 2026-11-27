"""Operadores do Airflow, um por tipo de transformação. A chave é o valor de `operator:` nos YAML."""

from .ingestion import DiscogsApiOperator
from .spark import SparkGoldOperator, SparkSilverOperator

OPERATORS = {
    "discogs_api": DiscogsApiOperator,
    "spark_silver": SparkSilverOperator,
    "spark_gold": SparkGoldOperator,
}

__all__ = ["OPERATORS", "DiscogsApiOperator", "SparkSilverOperator", "SparkGoldOperator"]
