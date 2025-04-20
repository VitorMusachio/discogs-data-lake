# Discogs Data Pipeline

Este projeto implementa uma arquitetura **Data Lakehouse** baseada em dados extraídos da **API do Discogs**, organizada em uma arquitetura **medalhão** (Bronze → Silver → Gold). O pipeline é **orquestrado via Airflow**, utiliza **Apache Spark** para processamento, **MinIO** para armazenamento de dados, e disponibiliza a camada Gold via **Trino** para consumo no **Metabase**.

---

## Tecnologias Utilizadas

- **Python** (Coleta e orquestração)
- **Apache Spark** (Transformações de dados)
- **Apache Airflow** (Orquestração)
- **MinIO** (Data Lake)
- **Trino** (Motor de consulta SQL)
- **Metabase** (Visualização de dados)
- **Docker Compose** (Ambiente local)

---

## Endpoints da API do Discogs

Os seguintes endpoints da API oficial do [Discogs](https://www.discogs.com/developers/) foram integrados:

| Endpoint | Descrição |
|----------|-----------|
| `discovery`     | Endpoint base para identificar itens de interesse a serem coletados |
| `artists`       | Informações sobre artistas (nome, membros, aliases, etc) |
| `labels`        | Informações sobre gravadoras |
| `releases`      | Informações de lançamentos (álbuns, EPs, singles) |
| `users`         | Dados públicos de usuários da comunidade |
| `search`        | Resultados de pesquisa por termos diversos |
| `marketplace`   | Dados de venda e compra de mídias físicas |
| `collections`   | Itens presentes na coleção pessoal de um usuário |
| `wishlist`      | Lista de desejos de um usuário |

> ⚠️ Alguns endpoints requerem `id` para consulta. O processo de discovery auxilia a identificar esses ids antes da coleta detalhada.

---

## Arquitetura Medalhão

### Bronze
- **Objetivo:** Armazenar dados crus, diretamente da API, em formato `Parquet`.
- **Exemplo de estrutura:** `bronze/artists/yyyy-mm-dd/artists.parquet`

### Silver
- **Objetivo:** Padronização de nomenclatura e tipos:
  - Campos `id` viram `id_*`
  - Campos de data viram `dt_*`
  - Campos de timestamp viram `ts_*`
- **Formato:** `Parquet`
- **Processamento:** Feito com **Spark**

### Gold
- **Objetivo:** Construção de tabelas analíticas (fatos e dimensões)
- **Formato:** `Parquet`
- **Consultas SQL:** Localizadas na pasta `queries/gold/`
- **Processamento:** **Spark SQL**, com tabelas criadas automaticamente pela DAG

---

## Tabelas de Fatos e Dimensões (GOLD)

### Tabelas de Dimensão

| Tabela         | Descrição |
|----------------|-----------|
| `dim_artists`  | Informações padronizadas sobre artistas |
| `dim_labels`   | Dados sobre gravadoras |
| `dim_users`    | Dados públicos dos usuários do Discogs |

### Tabelas de Fato

| Tabela            | Descrição |
|-------------------|-----------|
| `fct_releases`    | Lançamentos de mídia musical com chaves para artistas, gravadoras e datas |
| `fct_marketplace` | Transações de compra e venda de mídia física |
| `fct_wishlist`    | Itens desejados por usuários (referencia `dim_users`, `dim_artists`, `fct_releases`) |
| `fct_collections` | Itens efetivamente presentes nas coleções dos usuários |

---

## Execução do Projeto

### 1. Inicialize o ambiente

```bash
docker-compose up -d --build
```

### 2. Instale as dependências

```bash
pip install -r requirements.txt
```

### 3. Acesse o Airflow

- http://localhost:8080
- Usuário: `airflow` | Senha: `airflow`

As DAGs disponíveis são:

- `dag_discovery`: Gera a lista de IDs a serem usados nos coletores
- `dag_bronze`: Realiza a coleta dos endpoints
- `dag_silver`: Padroniza os dados da bronze
- `dag_gold`: Executa as queries SQL e cria tabelas analíticas

### 4. Acesse o Metabase

- http://localhost:3000

> Apenas as tabelas da **camada gold** são visíveis via Trino.

---

## Considerações Finais

- Arquitetura extensível e modular
- Novo endpoint? Apenas crie um novo coletor e adicione à DAG bronze
- Nova query? Coloque na pasta `queries/gold/` e ela será automaticamente processada

---

**Desenvolvido por:** Vitor Musachio
