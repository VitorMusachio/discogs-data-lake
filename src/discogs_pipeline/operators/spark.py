"""Silver e gold: uma tabela por tarefa, gerada a partir de um arquivo SQL executado no Spark.

O operador base cuida da sessão Spark, da execução do SQL, da gravação e dos checks
(ver discogs_pipeline.transform). As subclasses mudam só o que é próprio da camada.
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
        """Gancho pós-gravação (a gold registra a tabela no Trino)."""

    def run(self, ds: str, settings: Settings):
        from ..spark_session import create_spark
        from ..transform import run_sql_task

        spark = create_spark(f"{self.layer}-{self.task_spec.task_id}", settings)
        try:
            result = run_sql_task(spark, settings.lake_root, settings.sql_dir, self.dag_spec, self.task_spec, ds)
            self.publish(result, settings)
            return {"table": result.table, "rows": result.rows, "location": result.location}
        finally:
            spark.stop()


class SparkSilverOperator(SparkSqlOperator):
    """Lê o JSON bruto do dia (fontes bronze_* do YAML) e grava silver/<tabela>/dt=<ds>/."""

    ui_color = "#eef3fa"


class SparkGoldOperator(SparkSqlOperator):
    """Lê as tabelas silver_*, reconstrói gold/<tabela>/ e publica a tabela no Trino."""

    ui_color = "#fbf6e6"

    def publish(self, result, settings: Settings) -> None:
        from ..trino_catalog import TrinoRegistrar

        registrar = TrinoRegistrar(settings.trino_host, settings.trino_port, settings.bucket, settings.gold_schema)
        registrar(result.table, result.df, result.location, self.task_spec.partition_by)
