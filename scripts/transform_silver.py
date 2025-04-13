from pyspark.sql import SparkSession
from pyspark.sql.functions import col
import re

# Inicia sessão Spark
spark = SparkSession.builder \
    .appName("DiscogsSilverTransform") \
    .getOrCreate()

# Lê os dados da camada bronze
df = spark.read.json("s3a://bronze/bronze/artists/")

# Função para renomear colunas
def rename_columns(df):
    new_columns = []
    for column in df.columns:
        col_lower = column.lower()

        if "timestamp" in col_lower or col_lower.startswith("created_at") or col_lower.endswith("_ts"):
            new_columns.append((column, f"ts_{column}"))
        elif "date" in col_lower or col_lower.startswith("released") or col_lower.endswith("_date"):
            new_columns.append((column, f"dt_{column}"))
        elif column.lower() in ["id", "artist_id", "release_id"] or column.lower().endswith("_id"):
            new_columns.append((column, f"id_{column}"))
        else:
            new_columns.append((column, column))

    for old, new in new_columns:
        if old != new:
            df = df.withColumnRenamed(old, new)

    return df

# Renomeia as colunas
df_transformed = rename_columns(df)

# Salva no bucket Silver em formato Parquet
df_transformed.write.mode("overwrite").parquet("s3a://silver/silver/artists/")

spark.stop()