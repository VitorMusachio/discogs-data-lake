-- Artistas creditados em cada release (um release pode ter vários), na coleta mais recente do release.
WITH latest AS (
    SELECT id_release, MAX(dt) AS dt FROM silver_release_artists GROUP BY id_release
)
SELECT ra.id_release, ra.id_artist, ra.nr_position, ra.nm_artist_credit, ra.ds_join
FROM silver_release_artists ra
JOIN latest USING (id_release, dt)
