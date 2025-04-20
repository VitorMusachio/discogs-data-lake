from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from datetime import datetime, timedelta
from pathlib import Path
from pyspark.sql import SparkSession
from utils.minio_client import upload_file_to_minio
import os

default_args = {
    'owner': 'airflow',
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
    'start_date': datetime(2025, 4, 20),
    'catchup': False,
}

BASE_DIR = "/opt/airflow/dags"
INPUT_DIR = f"{BASE_DIR}/bronze"
OUTPUT_DIR = f"{BASE_DIR}/silver"
MINIO_BUCKET = "silver"
EXECUTION_DATE = "{{ ds }}"

Path(INPUT_DIR).mkdir(parents=True, exist_ok=True)
Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

spark = SparkSession.builder \
    .appName("SilverLayerProcessing") \
    .getOrCreate()

def process_silver_data(file_path: str, output_path: str):
    """
    Função para processar e padronizar os dados da camada Bronze para a camada Silver.
    - Renomeia os campos de id_ e dt_
    - Converte os tipos de dados para o formato correto de data e id.
    """
    df = spark.read.option("header", "true").csv(file_path)

    # Padronização de colunas
    for column in df.columns:
        if 'id' in column.lower():
            df = df.withColumnRenamed(column, f"id_{column}")
        elif 'date' in column.lower() or 'timestamp' in column.lower():
            df = df.withColumnRenamed(column, f"dt_{column}")
    
    # Ajuste de datatype
    for column in df.columns:
        if column.startswith("dt_"):
            df = df.withColumn(column, df[column].cast("timestamp"))

    output_file_path = os.path.join(output_path, f"processed_{os.path.basename(file_path)}")
    df.write.mode("overwrite").parquet(output_file_path)

    upload_file_to_minio(output_file_path, MINIO_BUCKET)

with DAG(
    'dag_silver',
    default_args=default_args,
    description='DAG para processar dados da camada Bronze para a camada Silver com padronização de nomes e tipos',
    schedule_interval='@daily',
    tags=['discogs', 'data_processing', 'minio', 'silver'],
) as dag:

    # Artists
    task_process_artists = PythonOperator(
        task_id='process_artists_silver',
        python_callable=process_silver_data,
        op_args=[f"{INPUT_DIR}/artists.csv", OUTPUT_DIR],
        dag=dag,
    )

    # Releases
    task_process_releases = PythonOperator(
        task_id='process_releases_silver',
        python_callable=process_silver_data,
        op_args=[f"{INPUT_DIR}/releases.csv", OUTPUT_DIR],
        dag=dag,
    )

    # Labels
    task_process_labels = PythonOperator(
        task_id='process_labels_silver',
        python_callable=process_silver_data,
        op_args=[f"{INPUT_DIR}/labels.csv", OUTPUT_DIR],
        dag=dag,
    )

    # Users
    task_process_users = PythonOperator(
        task_id='process_users_silver',
        python_callable=process_silver_data,
        op_args=[f"{INPUT_DIR}/users.csv", OUTPUT_DIR],
        dag=dag,
    )

    # Marketplace
    task_process_marketplace = PythonOperator(
        task_id='process_marketplace_silver',
        python_callable=process_silver_data,
        op_args=[f"{INPUT_DIR}/marketplace.csv", OUTPUT_DIR],
        dag=dag,
    )

    # Collections
    task_process_collections = PythonOperator(
        task_id='process_collections_silver',
        python_callable=process_silver_data,
        op_args=[f"{INPUT_DIR}/collections.csv", OUTPUT_DIR],
        dag=dag,
    )

    # Wishlist
    task_process_wishlist = PythonOperator(
        task_id='process_wishlist_silver',
        python_callable=process_silver_data,
        op_args=[f"{INPUT_DIR}/wishlist.csv", OUTPUT_DIR],
        dag=dag,
    )

    # Execução das tasks paralelizada
    task_process_artists
    task_process_releases
    task_process_labels
    task_process_users
    task_process_marketplace
    task_process_collections
    task_process_wishlist