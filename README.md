
# Projeto Discogs Data Lakehouse

Este projeto implementa um pipeline completo de engenharia de dados para ingestão, transformação e disponibilização de dados do [Discogs](https://www.discogs.com/developers/) em uma arquitetura **data lakehouse**, utilizando a arquitetura **medalhão** (bronze, prata e ouro).

---

## Arquitetura

```mermaid
graph TD
    A[Discogs API] --> B[Coleta com Python]
    B --> C[Camada Bronze (Raw)]
    C --> D[Camada Silver (Tratada com Spark)]
    D --> E[Camada Gold (Modelos SQL)]
    E --> F[Trino]
    F --> G[Metabase]
```

---

## Tecnologias utilizadas

- **Airflow**: Orquestração dos pipelines
- **Apache Spark**: Processamento e transformações
- **MinIO (S3-like)**: Armazenamento dos dados (data lake)
- **Trino**: Engine de consulta SQL distribuída
- **Metabase**: Visualização de dados
- **Docker Compose**: Empacotamento da arquitetura
- **Python**: Scripts de coleta e transformação

---

##  Organização das camadas

| Camada | Descrição | Ferramenta |
|--------|-----------|------------|
| **Bronze** | Dados crus extraídos da API do Discogs | Python + Airflow |
| **Silver** | Dados limpos com padronização de nomenclatura (ex: `ts_created`, `dt_birth`, `id_release`) | Spark |
| **Gold** | Modelos analíticos em SQL (ex: top artistas, lançamentos por ano) | Spark SQL |

---

## Estrutura do Projeto

```
.
├── airflow/
│   ├── dags/
│   │   ├── discogs_bronze_dag.py
│   │   ├── discogs_silver_dag.py
│   │   └── discogs_gold_dag.py
│   └── scripts/
│       ├── collect_bronze.py
│       ├── transform_silver.py
│       └── run_gold_queries.py
├── gold_queries/
│   ├── top_artists.sql
│   └── releases_by_year.sql
├── docker-compose.yml
└── README.md
```

---

## Como executar o projeto

1. **Clone o repositório**
```bash
git clone https://github.com/seu-usuario/discogs-lakehouse.git
cd discogs-lakehouse
```

2. **Suba os containers com Docker Compose**
```bash
docker-compose up -d
```

3. **Acesse os serviços**

| Serviço | URL | Usuário / Senha |
|--------|-----|------------------|
| Airflow | [localhost:8081](http://localhost:8081) | airflow / airflow |
| MinIO | [localhost:9000](http://localhost:9000) | minio / minio123 |
| Trino | [localhost:8080](http://localhost:8080) | trino / *sem senha* |
| Metabase | [localhost:3000](http://localhost:3000) | admin / admin123 (definir no 1º uso) |

---

## Visualizações

Os dados da camada Gold podem ser acessados pelo Metabase via Trino. Exemplos de visualizações disponíveis:
-  Artistas mais populares
-  Número de lançamentos por ano
-  Gêneros mais presentes por década

---

##  Como criar novos modelos Gold

1. Crie uma nova query no diretório `gold_queries/` com extensão `.sql`
2. Ela será automaticamente executada pela DAG `discogs_gold_dag`
3. O resultado será salvo em `/gold/{nome_do_modelo}/`

Exemplo:

```sql
-- gold_queries/releases_by_genre.sql
SELECT genre, COUNT(*) AS total
FROM parquet.`s3a://silver/silver/releases/`
GROUP BY genre
```

---

## Possíveis melhorias

-  Adicionar validações com Great Expectations
-  Testes unitários com Pytest para os scripts
-  Monitoramento dos pipelines com alertas
-  Aplicar dbt como camada de transformação SQL

---

## Autor

Desenvolvido por Vitor Musachio

---

## Licença

MIT
