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
    dag_id='discogs_transform_silver_dag',
    default_args=default_args,
    description='Transforma dados da camada bronze e salva na camada silver com Spark',
    schedule_interval='@daily',
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['discogs', 'silver'],
) as dag:

    transform_silver = BashOperator(
        task_id='transform_bronze_to_silver',
        bash_command='/opt/spark/bin/spark-submit /opt/airflow/scripts/transform_silver.py',
    )

    transform_silver