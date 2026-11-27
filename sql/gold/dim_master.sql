-- Agrupador das edições de um mesmo álbum. Nem todo release tem master: use LEFT JOIN.
SELECT id_master, id_main_release, id_most_recent_release, ds_title, nr_year
FROM (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY id_master ORDER BY dt DESC) AS rn
    FROM silver_masters
) m
WHERE rn = 1
