"""Silver and gold: one table per task, built from a SQL file run in Spark.

The base operator handles the Spark session, running the SQL, writing and the checks
(see discogs_pipeline.transform). Subclasses only change what is specific to their layer.
"""

from __future__ import annotations

from ..settings import Settings
from ..spec import DagSpec, TaskSpec
from .base import LakeOperator


class SparkSqlOperator(LakeOperator):
    template_fields = ()

    def __init__(self, *, dag_spec: DagSpec, task_spec: TaskSpec, **kwargs):
        super().__init__(layer=dag_spec.layer, **kwargs)
        self.dag_spec = dag_spec
        self.task_spec = task_spec

    def publish(self, result, settings: Settings) -> None:
        """Post-write hook (gold registers the table in Trino)."""

    @staticmethod
    def _clearer(settings: Settings):
        """Empty the destination through the S3 API before Spark overwrites it (see S3Lake.delete_prefix)."""
        root = settings.lake_root
        if not root.startswith("s3a://"):
            return None
        from ..storage import lake_from_settings

        lake = lake_from_settings(settings)
        return lambda location: lake.delete_prefix(location.removeprefix(root).lstrip("/"))

    def run(self, ds: str, settings: Settings):
        from ..spark_session import create_spark
        from ..transform import run_sql_task

        spark = create_spark(f"{self.layer}-{self.task_spec.task_id}", settings)
        try:
            result = run_sql_task(
                spark,
                settings.lake_root,
                settings.sql_dir,
                self.dag_spec,
                self.task_spec,
                ds,
                clear_location=self._clearer(settings),
            )
            self.publish(result, settings)
            return {"table": result.table, "rows": result.rows, "location": result.location}
        finally:
            spark.stop()


class SparkSilverOperator(SparkSqlOperator):
    """Read the day's raw JSON (bronze_* sources from the YAML) and write silver/<table>/dt=<ds>/."""

    ui_color = "#eef3fa"


class SparkGoldOperator(SparkSqlOperator):
    """Read silver_* tables, rebuild gold/<table>/ and publish the table in Trino."""

    ui_color = "#fbf6e6"

    def publish(self, result, settings: Settings) -> None:
        from ..trino_catalog import TrinoRegistrar

        registrar = TrinoRegistrar(settings.trino_host, settings.trino_port, settings.bucket, settings.gold_schema)
        registrar(result.table, result.df, result.location, self.task_spec.partition_by)
