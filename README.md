# Discogs Data Lake

Lakehouse local com dados da [API do Discogs](https://www.discogs.com/developers/), organizado em camadas
**Bronze → Silver → Gold**. A peça central é um **snapshot diário** de demanda (`have`/`want`) e preço
(menor oferta em USD) de um conjunto de releases acompanhados. Isso permite ver tendências ao longo do tempo,
além da sua coleção e da sua wantlist.

| Peça | Papel |
|---|---|
| **Airflow** (2.9) | Orquestração: DAGs `discogs_discovery` (manual) e `discogs_daily` |
| **Spark** (3.5, local no worker do Airflow) | Bronze → Silver → Gold |
| **MinIO** | Armazenamento S3 (bucket `lakehouse`) |
| **Hive Metastore** + Postgres | Catálogo das tabelas Gold |
| **Trino** | SQL sobre a Gold (catálogo `lakehouse`, schema `gold`) |
| **Metabase** | Visualização |

## Como funciona

```
tracking.yml ──► discogs_discovery ──► control/tracked_releases.json  (só cresce)
                                                 │
discogs_daily:                                   ▼
  bronze  user_lists ──► snapshot ──► new_entities         JSON cru: bronze/<entidade>/dt=AAAA-MM-DD/
  silver  Spark, schema explícito, nomes padronizados       Parquet:  silver/<tabela>/dt=AAAA-MM-DD/
  gold    Spark SQL (sql/gold/*.sql) + registro no Trino    Parquet:  gold/<tabela>/
```

- **Discovery**: a busca do Discogs só devolve IDs de *release* (o campo `label` é uma lista de nomes e não
  existe campo de artista). Artistas, gravadoras e masters saem do detalhe de cada release.
- **Conjunto acompanhado**: a discovery e as listas de usuários só *acrescentam* releases. Nenhum sai, para as
  séries históricas ficarem completas. O teto está em `limits.max_tracked_releases`.
- **Custo**: cada release acompanhado custa 2 chamadas por dia (`/releases/{id}` e `/marketplace/stats/{id}`).
  Com o limite de 60 req/min, 500 releases levam cerca de 17 min por dia. Artistas, gravadoras e masters são
  coletados uma única vez.
- **Falhas**: falhas pontuais são registradas no log e o item é tentado de novo no dia seguinte. Se mais de
  `max_failure_ratio` das chamadas falhar, a tarefa falha.
- **Reprocessar** um dia é seguro: cada camada sobrescreve só a partição daquele dia, e a Gold é reconstruída inteira.

## Modelo Gold

| Tabela | Grão | Origem |
|---|---|---|
| `fact_release_snapshot` | release × dia (partição `dt_snapshot`) | `community.have/want`, `rating`; `marketplace/stats` (`vl_lowest_price_usd`, `qt_for_sale`). Preço nulo = nada à venda |
| `dim_release` | release | atributos; gênero, estilo e formato = **primeiro valor** da lista |
| `dim_master` | master (agrupa edições) | `/masters/{id}`; nem todo release tem master: use `LEFT JOIN` |
| `dim_artist`, `dim_label` | artista, gravadora | `/artists/{id}`, `/labels/{id}` (com gravadora-mãe) |
| `bridge_release_artist` | release × artista | `artists[]` do release, com posição no crédito |
| `dim_track` | release × faixa | `tracklist[]`, duração em segundos; títulos de lado são removidos |
| `fact_collection_item` | cópia na coleção (`id_instance`) | estado atual por usuário |
| `fact_wantlist_item` | release na wantlist | estado atual por usuário |
| `ctl_tracked_release` | release acompanhado | origem (`discovery:…`, `collection:…`, `wantlist:…`) |
| `dim_date` | dia | calendário do período com snapshots |

Prefixos de coluna: `id_` chave, `dt_` data, `ts_` timestamp, `qt_` quantidade, `vl_` valor, `nm_` nome,
`ds_` descrição, `nr_` número, `cd_` código, `fl_` booleano.

Nova tabela? Crie `sql/gold/<nome>.sql`, consultando as views `silver_<tabela>`. Ela é construída e registrada
no Trino na próxima execução. Para particionar, comece o arquivo com `-- partition_by: <coluna>`.

## Executando

1. Configure o ambiente:
   ```bash
   cp .env.example .env
   ```
   Preencha `DISCOGS_TOKEN` (gerado em <https://www.discogs.com/settings/developers>), `DISCOGS_USER_AGENT` e as senhas.
2. Edite `config/tracking.yml`: seus usernames e as sementes de discovery.
3. Suba a stack (a primeira build baixa algumas imagens, ~5 GB):
   ```bash
   docker compose up -d --build
   ```
4. No Airflow (<http://localhost:8080>, com o usuário e a senha do `.env`):
   1. Despause e rode `discogs_discovery` uma vez.
   2. Despause `discogs_daily`, que passa a rodar todo dia (dá para disparar manualmente também).
5. Consulte:
   - **Trino**: `localhost:8081`, catálogo `lakehouse`, schema `gold`.
   - **Metabase**: <http://localhost:3000>. Adicione um banco do tipo **Starburst** com host `trino`,
     porta `8080`, catálogo `lakehouse`, schema `gold` e usuário `metabase` (sem senha).
   - **MinIO**: console em <http://localhost:9001>.

Exemplo de consulta no Trino:

```sql
-- Releases cuja demanda mais cresceu nos últimos 30 dias
SELECT r.ds_title, a.nm_artist_credit,
       MAX_BY(s.qt_want, s.dt_snapshot) - MIN_BY(s.qt_want, s.dt_snapshot) AS ganho_want
FROM lakehouse.gold.fact_release_snapshot s
JOIN lakehouse.gold.dim_release r USING (id_release)
LEFT JOIN lakehouse.gold.bridge_release_artist a ON a.id_release = s.id_release AND a.nr_position = 1
WHERE s.dt_snapshot >= current_date - INTERVAL '30' DAY
GROUP BY 1, 2
ORDER BY ganho_want DESC
LIMIT 20;
```

## Desenvolvimento

```bash
python3 -m venv .venv && .venv/bin/pip install pyspark==3.5.1 boto3 requests pyyaml pytest trino
```

```bash
.venv/bin/python -m pytest -q tests
```

Os testes cobrem o cliente da API (rate limit, novas tentativas, paginação), os coletores e um teste de ponta a
ponta Bronze → Silver → Gold em disco local, que precisa de Java 17+.

---

**Desenvolvido por:** Vitor Musachio
