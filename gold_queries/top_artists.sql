SELECT
    id_artist,
    name,
    followers
FROM
    parquet.`s3a://silver/silver/artists/`
ORDER BY
    followers DESC
LIMIT 100