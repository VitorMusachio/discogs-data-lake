SELECT data.id                  AS id_master,
       data.main_release        AS id_main_release,
       data.most_recent_release AS id_most_recent_release,
       data.title               AS ds_title,
       data.year                AS nr_year
FROM bronze_masters
