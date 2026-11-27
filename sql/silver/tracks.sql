-- Tracks of each release. Side headings ("Side A", type_ = heading) are dropped; the original position is kept.
SELECT r.data.id                AS id_release,
       t.position               AS cd_position,
       pos + 1                  AS nr_sequence,
       t.title                  AS ds_title,
       NULLIF(t.duration, '')   AS ds_duration,
       CASE
         WHEN t.duration RLIKE '^[0-9]+:[0-9]{1,2}$'
           THEN CAST(split(t.duration, ':')[0] AS INT) * 60 + CAST(split(t.duration, ':')[1] AS INT)
         WHEN t.duration RLIKE '^[0-9]+:[0-9]{1,2}:[0-9]{1,2}$'
           THEN CAST(split(t.duration, ':')[0] AS INT) * 3600 + CAST(split(t.duration, ':')[1] AS INT) * 60
                + CAST(split(t.duration, ':')[2] AS INT)
       END                      AS nr_duration_sec
FROM bronze_releases r
LATERAL VIEW POSEXPLODE(r.data.tracklist) x AS pos, t
WHERE COALESCE(t.type_, 'track') = 'track'
