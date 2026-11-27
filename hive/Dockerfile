# Jars are downloaded in a separate stage: apt in apache/hive:4.0.0 points to archived repositories.
FROM curlimages/curl:8.10.1 AS jars
WORKDIR /jars
RUN curl -fsSLO https://repo1.maven.org/maven2/org/postgresql/postgresql/42.7.4/postgresql-42.7.4.jar \
    && curl -fsSLO https://repo1.maven.org/maven2/org/apache/hadoop/hadoop-aws/3.3.6/hadoop-aws-3.3.6.jar \
    && curl -fsSLO https://repo1.maven.org/maven2/com/amazonaws/aws-java-sdk-bundle/1.12.367/aws-java-sdk-bundle-1.12.367.jar

# Postgres driver (metastore database) and S3A connectors matching the image's Hadoop 3.3.6
FROM apache/hive:4.0.0
COPY --from=jars /jars/*.jar /opt/hive/lib/
