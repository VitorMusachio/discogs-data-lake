---
paths:
  - "docker-compose.yml"
  - "airflow/**"
  - "hive/**"
  - "trino/**"
  - ".env.example"
---

# Infra rules

- Pin image tags (no `latest`). Check that a tag exists with `docker manifest inspect <image:tag>` before using it.
- Jar versions must match the Hadoop of each image: PySpark 3.5.1 → Hadoop 3.3.4 (`hadoop-aws-3.3.4`,
  `aws-java-sdk-bundle-1.12.262`, `spark-hadoop-cloud_2.12-3.5.1`); Hive 4.0.0 → Hadoop 3.3.6.
- `apache/hive:4.0.0` has archived apt sources: download extras in a separate build stage.
- Secrets only through `.env` (`env_file`); add every new variable to `.env.example` with a placeholder.
- Host ports: Airflow `${AIRFLOW_PORT:-8080}`, Trino 8081, Metabase 3000, S3 8333, filer 8888. Trino keeps
  `mem_limit: 2g`.
- After infra changes run `make up` and `make test-integration`.
