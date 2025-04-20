SELECT 
    id_usuario,
    id_release,
    MIN(dt_adicao) AS dt_adicao
FROM silver.collections
GROUP BY id_usuario, id_release;