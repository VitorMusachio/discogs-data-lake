-- Atributos de cada release na versão mais recente coletada.
SELECT id_release, id_master, id_label, ds_title, nr_year, ds_country, ds_genre, ds_style,
       ds_format, cd_catno, ds_released, dt_released, ts_changed
FROM (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY id_release ORDER BY dt DESC) AS rn
    FROM silver_releases
) r
WHERE rn = 1
