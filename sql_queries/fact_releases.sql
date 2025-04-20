SELECT 
    id_release,
    id_label,
    COUNT(id_release) AS quantidade_lancada,
    MIN(dt_lancamento) AS dt_lancamento
FROM silver.releases
GROUP BY id_release, id_label