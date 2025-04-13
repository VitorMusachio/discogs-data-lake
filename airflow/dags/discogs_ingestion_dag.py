from airflow import DAG
from airflow.operators.bash import BashOperator
from datetime import datetime, timedelta

# Configurações da DAG
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=2),
}

with DAG(
    dag_id='discogs_ingestion_dag',
    default_args=default_args,
    description='Coleta dados da API do Discogs e salva no MinIO (camada bronze)',
    schedule_interval='@daily',
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['discogs', 'bronze'],
) as dag:

    collect_and_upload = BashOperator(
        task_id='collect_and_upload_discogs_data',
        bash_command='python /opt/airflow/scripts/collect_discogs_data.py',
    )

    collect_and_upload