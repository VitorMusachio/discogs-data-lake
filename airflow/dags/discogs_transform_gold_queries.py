from airflow import DAG
from airflow.operators.bash import BashOperator
from datetime import datetime, timedelta

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=2),
}

with DAG(
    dag_id='discogs_transform_gold_dag',
    default_args=default_args,
    description='Executa consultas SQL salvas como modelos da camada Gold com Spark SQL',
    schedule_interval='@daily',
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['discogs', 'gold'],
) as dag:

    execute_gold_models = BashOperator(
        task_id='run_gold_queries',
        bash_command='/opt/spark/bin/spark-submit /opt/airflow/scripts/run_gold_queries.py',
    )

    execute_gold_models