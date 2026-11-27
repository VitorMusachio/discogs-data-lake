-- Tracks of each release (side headings such as "Side A" excluded), from the latest collection.
WITH latest AS (
    SELECT id_release, MAX(dt) AS dt FROM silver_tracks GROUP BY id_release
)
SELECT t.id_release, t.cd_position, t.nr_sequence, t.ds_title, t.ds_duration, t.nr_duration_sec
FROM silver_tracks t
JOIN latest USING (id_release, dt)
