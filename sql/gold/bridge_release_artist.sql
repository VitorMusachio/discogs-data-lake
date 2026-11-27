-- Artists credited on each release (a release can have several), from the release's latest collection.
WITH latest AS (
    SELECT id_release, MAX(dt) AS dt FROM silver_release_artists GROUP BY id_release
)
SELECT ra.id_release, ra.id_artist, ra.nr_position, ra.nm_artist_credit, ra.ds_join
FROM silver_release_artists ra
JOIN latest USING (id_release, dt)
