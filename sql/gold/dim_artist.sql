SELECT id_artist, nm_artist, nm_real_name, ds_profile
FROM (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY id_artist ORDER BY dt DESC) AS rn
    FROM silver_artists
) AS a
WHERE rn = 1
