FROM apache/airflow:2.9.3-python3.11

USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends default-jre-headless curl \
    && rm -rf /var/lib/apt/lists/*
ENV JAVA_HOME=/usr/lib/jvm/default-java

USER airflow
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir "apache-airflow==${AIRFLOW_VERSION}" -r /tmp/requirements.txt \
    --constraint "https://raw.githubusercontent.com/apache/airflow/constraints-2.9.3/constraints-3.11.txt"

# Conectores S3A para o Spark ler/gravar no MinIO (versões casadas com o Hadoop 3.3.4 do PySpark 3.5.1)
RUN JARS="$(python -c 'import os, pyspark; print(os.path.join(os.path.dirname(pyspark.__file__), "jars"))')" \
    && curl -fsSL -o "$JARS/hadoop-aws-3.3.4.jar" \
       https://repo1.maven.org/maven2/org/apache/hadoop/hadoop-aws/3.3.4/hadoop-aws-3.3.4.jar \
    && curl -fsSL -o "$JARS/aws-java-sdk-bundle-1.12.262.jar" \
       https://repo1.maven.org/maven2/com/amazonaws/aws-java-sdk-bundle/1.12.262/aws-java-sdk-bundle-1.12.262.jar
