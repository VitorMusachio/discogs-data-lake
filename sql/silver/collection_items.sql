-- Each copy in the collection (instance_id tells copies of the same release apart). Rating 0 = no rating.
SELECT username                     AS nm_username,
       data.instance_id             AS id_instance,
       data.folder_id               AS id_folder,
       data.id                      AS id_release,
       to_timestamp(data.date_added) AS ts_added,
       NULLIF(data.rating, 0)       AS nr_rating
FROM bronze_collection
