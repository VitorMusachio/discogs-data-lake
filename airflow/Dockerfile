FROM apache/airflow:2.7.2-python3.10

USER root
RUN apt-get update && apt-get install -y gcc libpq-dev curl

USER airflow
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt