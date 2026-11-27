-- Oferta no marketplace. Sem itens à venda, preço e quantidade ficam nulos (não zero).
SELECT id                                                       AS id_release,
       CAST(CASE WHEN data.lowest_price.currency = 'USD' THEN data.lowest_price.value END
            AS DECIMAL(12, 2))                                   AS vl_lowest_price_usd,
       data.num_for_sale                                        AS qt_for_sale,
       data.blocked_from_sale                                   AS fl_blocked_from_sale
FROM bronze_marketplace_stats
