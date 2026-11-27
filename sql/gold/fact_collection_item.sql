-- Current state of each user's collection (latest collection). id_instance tells copies of the same record apart.
WITH latest AS (
    SELECT nm_username, MAX(dt) AS dt FROM silver_collection_items GROUP BY nm_username
)
SELECT c.nm_username, c.id_instance, c.id_release, c.id_folder, c.ts_added, c.nr_rating
FROM silver_collection_items c
JOIN latest USING (nm_username, dt)
