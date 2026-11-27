-- One row per release per day. Price and offer are null when nothing is for sale (not zero).
SELECT r.id_release,
       r.qt_have,
       r.qt_want,
       r.vl_rating_avg,
       r.qt_rating,
       s.vl_lowest_price_usd,
       s.qt_for_sale,
       s.fl_blocked_from_sale,
       r.dt AS dt_snapshot
FROM silver_releases AS r
LEFT JOIN silver_marketplace_stats AS s
  ON r.id_release = s.id_release AND r.dt = s.dt
