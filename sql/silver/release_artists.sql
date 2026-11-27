-- Artistas creditados em cada release, na ordem do crédito. id 0 é placeholder do Discogs ("Various").
SELECT r.data.id                              AS id_release,
       a.id                                   AS id_artist,
       pos + 1                                AS nr_position,
       COALESCE(NULLIF(a.anv, ''), a.name)    AS nm_artist_credit,
       NULLIF(a.`join`, '')                   AS ds_join
FROM bronze_releases r
LATERAL VIEW POSEXPLODE(r.data.artists) x AS pos, a
WHERE a.id > 0
