"""Airflow operators, one per kind of transformation. Keys are the `operator:` values used in the YAML."""

from .ingestion import DiscogsApiOperator
from .spark import SparkGoldOperator, SparkSilverOperator

OPERATORS = {
    "discogs_api": DiscogsApiOperator,
    "spark_silver": SparkSilverOperator,
    "spark_gold": SparkGoldOperator,
}

__all__ = ["OPERATORS", "DiscogsApiOperator", "SparkSilverOperator", "SparkGoldOperator"]
