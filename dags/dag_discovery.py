from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
from collectors.discovery import run_discovery

default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "email_on_failure": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5)
}

with DAG(
    dag_id="discogs_discovery",
    description="Faz a descoberta diária de IDs no Discogs",
    default_args=default_args,
    schedule_interval="@daily",
    start_date=datetime(2023, 1, 1),
    catchup=False,
    tags=["discogs", "discovery", "bronze"]
) as dag:

    def discovery_task(**context):
        execution_date = context["execution_date"]
        year = execution_date.year

        # parâmetros opcionais, podem ser configurados através da UI do Airflow
        genre = context["dag_run"].conf.get("genre") if context.get("dag_run") else None
        pages = context["dag_run"].conf.get("pages", 3) if context.get("dag_run") else 3

        run_discovery(year=year, genre=genre, pages=pages)

    run_discovery_op = PythonOperator(
        task_id="run_discogs_discovery",
        python_callable=discovery_task,
        provide_context=True,
    )

    run_discovery_op