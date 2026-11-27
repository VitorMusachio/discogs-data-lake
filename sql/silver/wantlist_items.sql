SELECT username                     AS nm_username,
       data.id                      AS id_release,
       TO_TIMESTAMP(data.date_added) AS ts_added,
       NULLIF(data.rating, 0)       AS nr_rating
FROM bronze_wantlist
