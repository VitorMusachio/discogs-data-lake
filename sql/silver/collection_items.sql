-- Cada cópia na coleção (instance_id distingue cópias do mesmo release). Nota 0 = sem nota.
SELECT username                     AS nm_username,
       data.instance_id             AS id_instance,
       data.folder_id               AS id_folder,
       data.id                      AS id_release,
       to_timestamp(data.date_added) AS ts_added,
       NULLIF(data.rating, 0)       AS nr_rating
FROM bronze_collection
