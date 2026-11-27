"""Bronze -> Silver: lê o JSON cru de um dia, extrai os campos com schema explícito e grava Parquet tipado.

Convenções de nome: id_ (chaves), dt_ (datas), ts_ (timestamps), qt_ (quantidades), vl_ (valores),
nm_ (nomes), ds_ (descrições/textos), nr_ (números), cd_ (códigos), fl_ (booleanos).

Cada tabela é gravada em silver/<tabela>/dt=<ds>/, sobrescrevendo só aquele dia (reprocessar é seguro).
"""

from __future__ import annotations

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql import types as T

S, L, I, D, B = T.StringType(), T.LongType(), T.IntegerType(), T.DoubleType(), T.BooleanType()


def _struct(**fields) -> T.StructType:
    return T.StructType([T.StructField(k, v) for k, v in fields.items()])


RELEASE = _struct(
    id=L, title=S, year=I, country=S, released=S, master_id=L, date_changed=S,
    genres=T.ArrayType(S), styles=T.ArrayType(S),
    formats=T.ArrayType(_struct(name=S, qty=S)),
    labels=T.ArrayType(_struct(id=L, name=S, catno=S)),
    artists=T.ArrayType(_struct(id=L, name=S, anv=S, join=S, role=S)),
    tracklist=T.ArrayType(_struct(position=S, type_=S, title=S, duration=S)),
    community=_struct(have=I, want=I, rating=_struct(average=D, count=I)),
)
STATS = _struct(lowest_price=_struct(value=D, currency=S), num_for_sale=I, blocked_from_sale=B)
MASTER = _struct(id=L, title=S, year=I, main_release=L, most_recent_release=L)
ARTIST = _struct(id=L, name=S, realname=S, profile=S)
LABEL = _struct(id=L, name=S, profile=S, parent_label=_struct(id=L, name=S))
COLLECTION_ITEM = _struct(id=L, instance_id=L, folder_id=L, rating=I, date_added=S)
WANT = _struct(id=L, rating=I, date_added=S)


def read_bronze(spark: SparkSession, root: str, entity: str, ds: str, data_schema: T.StructType) -> DataFrame:
    envelope = _struct(ingested_at=S, id=L, username=S, seed=S, data=data_schema)
    return spark.read.schema(envelope).json(f"{root}/bronze/{entity}/dt={ds}/")


def _write(df: DataFrame, root: str, table: str, ds: str) -> int:
    df.write.mode("overwrite").parquet(f"{root}/silver/{table}/dt={ds}")
    return df.count()


def _valid_date(col: str):
    """'1991-09-24' vira data; '1991', '1991-00-00' e vazios viram null."""
    c = F.col(col)
    return F.when(c.rlike(r"^\d{4}-\d{2}-\d{2}$") & ~c.contains("-00"), F.to_date(c))


def _duration_seconds(col: str):
    """'3:45' -> 225, '1:02:03' -> 3723, vazio -> null."""
    parts = F.split(F.col(col), ":")
    n = F.size(parts)
    as_int = lambda i: parts.getItem(i).cast("int")  # noqa: E731
    return (
        F.when(~F.col(col).rlike(r"^\d+(:\d{1,2}){1,2}$"), F.lit(None).cast("int"))
        .when(n == 2, as_int(0) * 60 + as_int(1))
        .otherwise(as_int(0) * 3600 + as_int(1) * 60 + as_int(2))
    )


def build_releases(spark, root, ds) -> dict[str, int]:
    df = read_bronze(spark, root, "releases", ds, RELEASE).select("data.*")
    df.cache()
    releases = df.select(
        F.col("id").alias("id_release"),
        F.col("master_id").alias("id_master"),
        F.col("labels")[0]["id"].alias("id_label"),
        F.col("title").alias("ds_title"),
        F.col("year").alias("nr_year"),
        F.col("country").alias("ds_country"),
        F.col("genres")[0].alias("ds_genre"),
        F.col("styles")[0].alias("ds_style"),
        F.col("formats")[0]["name"].alias("ds_format"),
        F.col("labels")[0]["catno"].alias("cd_catno"),
        F.col("released").alias("ds_released"),
        _valid_date("released").alias("dt_released"),
        F.col("community.have").alias("qt_have"),
        F.col("community.want").alias("qt_want"),
        F.col("community.rating.average").alias("vl_rating_avg"),
        F.col("community.rating.count").alias("qt_rating"),
        F.to_timestamp("date_changed").alias("ts_changed"),
    )
    artists = df.select(F.col("id").alias("id_release"), F.posexplode("artists").alias("pos", "a")).select(
        "id_release",
        F.col("a.id").alias("id_artist"),
        (F.col("pos") + 1).alias("nr_position"),
        F.coalesce(F.nullif(F.col("a.anv"), F.lit("")), F.col("a.name")).alias("nm_artist_credit"),
        F.nullif(F.col("a.join"), F.lit("")).alias("ds_join"),
    ).where(F.col("id_artist") > 0)
    tracks = (
        df.select(F.col("id").alias("id_release"), F.posexplode("tracklist").alias("pos", "t"))
        .where(F.coalesce(F.col("t.type_"), F.lit("track")) == "track")
        .select(
            "id_release",
            F.col("t.position").alias("cd_position"),
            (F.col("pos") + 1).alias("nr_sequence"),
            F.col("t.title").alias("ds_title"),
            F.nullif(F.col("t.duration"), F.lit("")).alias("ds_duration"),
            _duration_seconds("t.duration").alias("nr_duration_sec"),
        )
    )
    counts = {
        "releases": _write(releases, root, "releases", ds),
        "release_artists": _write(artists, root, "release_artists", ds),
        "tracks": _write(tracks, root, "tracks", ds),
    }
    df.unpersist()
    return counts


def build_marketplace_stats(spark, root, ds) -> int:
    df = read_bronze(spark, root, "marketplace_stats", ds, STATS).select(
        F.col("id").alias("id_release"),
        F.when(F.col("data.lowest_price.currency") == "USD", F.col("data.lowest_price.value"))
        .cast("decimal(12,2)").alias("vl_lowest_price_usd"),
        F.col("data.num_for_sale").alias("qt_for_sale"),
        F.col("data.blocked_from_sale").alias("fl_blocked_from_sale"),
    )
    return _write(df, root, "marketplace_stats", ds)


def build_entities(spark, root, ds) -> dict[str, int]:
    masters = read_bronze(spark, root, "masters", ds, MASTER).select(
        F.col("data.id").alias("id_master"),
        F.col("data.main_release").alias("id_main_release"),
        F.col("data.most_recent_release").alias("id_most_recent_release"),
        F.col("data.title").alias("ds_title"),
        F.col("data.year").alias("nr_year"),
    )
    artists = read_bronze(spark, root, "artists", ds, ARTIST).select(
        F.col("data.id").alias("id_artist"),
        F.col("data.name").alias("nm_artist"),
        F.col("data.realname").alias("nm_real_name"),
        F.col("data.profile").alias("ds_profile"),
    )
    labels = read_bronze(spark, root, "labels", ds, LABEL).select(
        F.col("data.id").alias("id_label"),
        F.col("data.name").alias("nm_label"),
        F.col("data.parent_label.id").alias("id_parent_label"),
        F.col("data.parent_label.name").alias("nm_parent_label"),
        F.col("data.profile").alias("ds_profile"),
    )
    return {
        "masters": _write(masters, root, "masters", ds),
        "artists": _write(artists, root, "artists", ds),
        "labels": _write(labels, root, "labels", ds),
    }


def build_user_lists(spark, root, ds) -> dict[str, int]:
    collection = read_bronze(spark, root, "collection", ds, COLLECTION_ITEM).select(
        F.col("username").alias("nm_username"),
        F.col("data.instance_id").alias("id_instance"),
        F.col("data.folder_id").alias("id_folder"),
        F.col("data.id").alias("id_release"),
        F.to_timestamp("data.date_added").alias("ts_added"),
        F.nullif(F.col("data.rating"), F.lit(0)).alias("nr_rating"),
    )
    wantlist = read_bronze(spark, root, "wantlist", ds, WANT).select(
        F.col("username").alias("nm_username"),
        F.col("data.id").alias("id_release"),
        F.to_timestamp("data.date_added").alias("ts_added"),
        F.nullif(F.col("data.rating"), F.lit(0)).alias("nr_rating"),
    )
    return {
        "collection_items": _write(collection, root, "collection_items", ds),
        "wantlist_items": _write(wantlist, root, "wantlist_items", ds),
    }


def build_tracked(spark, root, tracked: dict[str, dict]) -> int:
    rows = [(int(k), v["origin"], v["first_seen"]) for k, v in tracked.items()]
    df = spark.createDataFrame(rows, "id_release long, ds_origin string, first_seen string").select(
        "id_release", "ds_origin", F.to_date("first_seen").alias("dt_first_seen")
    )
    df.write.mode("overwrite").parquet(f"{root}/silver/tracked_releases")
    return len(rows)


def build_silver(spark: SparkSession, root: str, ds: str, tracked: dict[str, dict]) -> dict[str, int]:
    counts = {}
    counts.update(build_releases(spark, root, ds))
    counts["marketplace_stats"] = build_marketplace_stats(spark, root, ds)
    counts.update(build_entities(spark, root, ds))
    counts.update(build_user_lists(spark, root, ds))
    counts["tracked_releases"] = build_tracked(spark, root, tracked)
    return counts
