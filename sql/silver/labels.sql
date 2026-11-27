SELECT data.id                AS id_label,
       data.name              AS nm_label,
       data.parent_label.id   AS id_parent_label,
       data.parent_label.name AS nm_parent_label,
       data.profile           AS ds_profile
FROM bronze_labels
