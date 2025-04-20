from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from datetime import datetime, timedelta
from pathlib import Path
from collectors.discovery import run_discovery_collector
from collectors.artists import run_artists_collector
from collectors.releases import run_releases_collector
from collectors.labels import run_labels_collector
from collectors.users import run_users_collector
from collectors.marketplace import run_marketplace_collector
from collectors.collections import run_collection_collector
from collectors.wishlist import run_wishlist_collector
from utils.minio_client import upload_file_to_minio
import os

default_args = {
    'owner': 'airflow',
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
    'start_date': datetime(2025, 4, 20),
}

BASE_DIR = "/opt/airflow/dags"
INPUT_DIR = f"{BASE_DIR}/input"
OUTPUT_DIR = f"{BASE_DIR}/output"
MINIO_BUCKET = "bronze"
EXECUTION_DATE = "{{ ds }}"

Path(INPUT_DIR).mkdir(parents=True, exist_ok=True)
Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

with DAG(
    'dag_bronze',
    default_args=default_args,
    description='DAG para coletar dados do Discogs e salvar na camada Bronze do MinIO',
    schedule_interval='@daily',
    catchup=False,
    tags=['discogs', 'data_collection', 'minio'],
) as dag:

    # Discovery
    task_discovery = PythonOperator(
        task_id='run_discovery',
        python_callable=run_discovery_collector,
        op_args=[INPUT_DIR, OUTPUT_DIR, EXECUTION_DATE],
        dag=dag,
    )

    # Artists
    task_artists = PythonOperator(
        task_id='run_artists',
        python_callable=run_artists_collector,
        op_args=[INPUT_DIR, OUTPUT_DIR, EXECUTION_DATE],
        dag=dag,
    )

    # Releases
    task_releases = PythonOperator(
        task_id='run_releases',
        python_callable=run_releases_collector,
        op_args=[INPUT_DIR, OUTPUT_DIR, EXECUTION_DATE],
        dag=dag,
    )

    # Labels
    task_labels = PythonOperator(
        task_id='run_labels',
        python_callable=run_labels_collector,
        op_args=[INPUT_DIR, OUTPUT_DIR, EXECUTION_DATE],
        dag=dag,
    )

    # Users
    task_users = PythonOperator(
        task_id='run_users',
        python_callable=run_users_collector,
        op_args=[INPUT_DIR, OUTPUT_DIR, EXECUTION_DATE],
        dag=dag,
    )

    # Marketplace
    task_marketplace = PythonOperator(
        task_id='run_marketplace',
        python_callable=run_marketplace_collector,
        op_args=[INPUT_DIR, OUTPUT_DIR, EXECUTION_DATE],
        dag=dag,
    )

    # Collections
    task_collections = PythonOperator(
        task_id='run_collections',
        python_callable=run_collection_collector,
        op_args=[INPUT_DIR, OUTPUT_DIR, EXECUTION_DATE],
        dag=dag,
    )

    # Wishlist
    task_wishlist = PythonOperator(
        task_id='run_wishlist',
        python_callable=run_wishlist_collector,
        op_args=[INPUT_DIR, OUTPUT_DIR, EXECUTION_DATE],
        dag=dag,
    )

    # Sequência de execução das tasks
    task_discovery >> [
        task_artists, 
        task_releases, 
        task_labels, 
        task_users, 
        task_marketplace, 
        task_collections, 
        task_wishlist
    ]