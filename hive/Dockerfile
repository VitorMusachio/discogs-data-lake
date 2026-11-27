FROM apache/hive:4.0.0

USER root
# Driver do Postgres (banco do metastore) e conectores S3A (Hadoop 3.3.6 da imagem)
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/* \
    && curl -fsSL -o /opt/hive/lib/postgresql-42.7.4.jar \
       https://repo1.maven.org/maven2/org/postgresql/postgresql/42.7.4/postgresql-42.7.4.jar \
    && curl -fsSL -o /opt/hive/lib/hadoop-aws-3.3.6.jar \
       https://repo1.maven.org/maven2/org/apache/hadoop/hadoop-aws/3.3.6/hadoop-aws-3.3.6.jar \
    && curl -fsSL -o /opt/hive/lib/aws-java-sdk-bundle-1.12.367.jar \
       https://repo1.maven.org/maven2/com/amazonaws/aws-java-sdk-bundle/1.12.367/aws-java-sdk-bundle-1.12.367.jar
USER hive
