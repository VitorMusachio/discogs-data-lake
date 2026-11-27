-- Releases acompanhados no snapshot diário e de onde vieram (discovery, coleção ou wantlist).
SELECT id_release,
       origin              AS ds_origin,
       to_date(first_seen) AS dt_first_seen
FROM bronze_tracked_releases
