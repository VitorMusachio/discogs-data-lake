from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from datetime import datetime, timedelta
import os
from utils.spark_utils import create_spark_session, execute_sql, save_to_parquet

def process_sql_to_parquet(file_path: str, output_path: str):
    spark = create_spark_session('GoldLayerSQL')
    with open(file_path, 'r') as file:
        query = file.read()

    df = execute_sql(spark, query)

    save_to_parquet(df, output_path)

def get_sql_files_from_directory(directory: str):
    return [os.path.join(directory, f) for f in os.listdir(directory) if f.endswith('.sql')]

default_args = {
    'owner': 'airflow',
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
    'start_date': datetime(2025, 4, 20),
    'catchup': False,
}

with DAG(
    'dag_gold',
    default_args=default_args,
    description='DAG para processar dados e criar as tabelas de fato e dimensão',
    schedule_interval='@daily',
    tags=['discogs', 'data_processing', 'gold'],
) as dag:

    sql_folder_path = '/path/to/sql_queries'
    gold_output_path = '/path/to/gold_output/'

    # Lista todos os arquivos SQL na pasta
    sql_files = get_sql_files_from_directory(sql_folder_path)

    # Criação das tarefas para cada arquivo SQL
    for sql_file in sql_files:
        table_name = os.path.splitext(os.path.basename(sql_file))[0]
        
        output_path = os.path.join(gold_output_path, f'{table_name}.parquet')
        
        task = PythonOperator(
            task_id=f'process_{table_name}_to_parquet',
            python_callable=process_sql_to_parquet,
            op_args=[sql_file, output_path],
            dag=dag,
        )