"""Pipeline diário: bronze (API) -> silver (Spark) -> gold (Spark SQL + Trino).

Ordem da bronze: as listas de usuários vêm primeiro porque acrescentam releases ao conjunto
acompanhado; o snapshot usa esse conjunto; as entidades novas saem dos releases do snapshot.
"""

from datetime import datetime, timedelta

from airflow.decorators import dag, task, task_group


@dag(
    dag_id="discogs_daily",
    schedule="@daily",
    start_date=datetime(2026, 11, 1),
    catchup=False,
    max_active_runs=1,
    default_args={"retries": 1, "retry_delay": timedelta(minutes=10)},
    tags=["discogs"],
)
def discogs_daily():
    @task_group(group_id="bronze")
    def bronze():
        @task
        def user_lists(ds=None):
            from discogs_pipeline import tasks

            return tasks.user_lists(ds)

        @task(execution_timeout=timedelta(hours=1))
        def snapshot(ds=None):
            from discogs_pipeline import tasks

            return tasks.snapshot(ds)

        @task
        def new_entities(ds=None):
            from discogs_pipeline import tasks

            return tasks.new_entities(ds)

        user_lists() >> snapshot() >> new_entities()

    @task
    def silver(ds=None):
        from discogs_pipeline import tasks

        return tasks.silver(ds)

    @task
    def gold():
        from discogs_pipeline import tasks

        return tasks.gold()

    bronze() >> silver() >> gold()


discogs_daily()
