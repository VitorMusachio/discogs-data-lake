-- Releases in the daily snapshot and where they came from (discovery, collection or wantlist).
SELECT id_release,
       origin              AS ds_origin,
       to_date(first_seen) AS dt_first_seen
FROM bronze_tracked_releases
