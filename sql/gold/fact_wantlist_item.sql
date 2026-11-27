-- Estado atual da wantlist de cada usuário (última coleta).
WITH latest AS (
    SELECT nm_username, MAX(dt) AS dt FROM silver_wantlist_items GROUP BY nm_username
)
SELECT w.nm_username, w.id_release, w.ts_added, w.nr_rating
FROM silver_wantlist_items w
JOIN latest USING (nm_username, dt)
