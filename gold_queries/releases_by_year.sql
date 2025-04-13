SELECT
    dt_release_date AS year, 
    COUNT(*) AS total_releases
FROM
    parquet.`s3a://silver/silver/releases/`
GROUP BY
    dt_release_date
ORDER BY
    year