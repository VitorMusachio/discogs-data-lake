-- partition_by: dt_snapshot
-- Uma linha por release por dia. Preço e oferta ficam nulos quando não há nada à venda (não é zero).
SELECT r.id_release,
       r.qt_have,
       r.qt_want,
       r.vl_rating_avg,
       r.qt_rating,
       s.vl_lowest_price_usd,
       s.qt_for_sale,
       s.fl_blocked_from_sale,
       r.dt AS dt_snapshot
FROM silver_releases r
LEFT JOIN silver_marketplace_stats s
  ON s.id_release = r.id_release AND s.dt = r.dt
