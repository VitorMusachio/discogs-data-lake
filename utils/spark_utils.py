from pyspark.sql import SparkSession

def create_spark_session(app_name='GoldLayerSQL'):
    """
    Cria uma sessão Spark.
    """
    return SparkSession.builder.appName(app_name).getOrCreate()

def execute_sql(spark, query):
    """
    Executa uma query SQL usando a sessão Spark.
    """
    return spark.sql(query)

def save_to_parquet(df, output_path):
    """
    Salva um DataFrame Spark no formato Parquet.
    """
    df.write.parquet(output_path, mode='overwrite')