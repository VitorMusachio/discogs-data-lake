-- Releases acompanhados no snapshot diário, com a origem (discovery, coleção ou wantlist).
SELECT id_release, ds_origin, dt_first_seen
FROM silver_tracked_releases
