"""Discovery manual: lê as sementes de config/tracking.yml e acrescenta releases ao conjunto acompanhado.

Rode uma vez antes da primeira execução diária e de novo sempre que mudar as sementes.
Releases já acompanhados nunca saem, então rodar de novo não apaga histórico.
"""

from datetime import datetime

from airflow.decorators import dag, task


@dag(
    dag_id="discogs_discovery",
    schedule=None,
    start_date=datetime(2026, 11, 1),
    catchup=False,
    tags=["discogs"],
)
def discogs_discovery():
    @task
    def discovery(ds=None):
        from discogs_pipeline import tasks

        return tasks.discovery(ds)

    discovery()


discogs_discovery()
