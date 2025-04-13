from pyspark.sql import SparkSession
import os

spark = SparkSession.builder \
    .appName("DiscogsGoldModels") \
    .getOrCreate()

queries_path = "/opt/airflow/gold_queries/"
output_path = "s3a://gold/gold/"

for filename in os.listdir(queries_path):
    if filename.endswith(".sql"):
        model_name = filename.replace(".sql", "")
        with open(os.path.join(queries_path, filename), "r") as f:
            query = f.read()

        print(f"Executando modelo: {model_name}")
        df = spark.sql(query)
        df.write.mode("overwrite").parquet(f"{output_path}{model_name}/")

spark.stop()