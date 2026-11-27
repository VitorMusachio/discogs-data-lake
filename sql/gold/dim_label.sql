SELECT id_label, nm_label, id_parent_label, nm_parent_label, ds_profile
FROM (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY id_label ORDER BY dt DESC) AS rn
    FROM silver_labels
) AS l
WHERE rn = 1
