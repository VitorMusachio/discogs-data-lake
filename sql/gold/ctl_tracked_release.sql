-- Releases in the daily snapshot, with their origin (discovery, collection or wantlist).
SELECT id_release, ds_origin, dt_first_seen
FROM silver_tracked_releases
