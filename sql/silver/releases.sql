-- Attributes and community counters of each release collected that day.
-- Genre, style, format and label keep the first value of their list.
SELECT data.id                       AS id_release,
       data.master_id                AS id_master,
       data.labels[0].id             AS id_label,
       data.title                    AS ds_title,
       data.year                     AS nr_year,
       data.country                  AS ds_country,
       data.genres[0]                AS ds_genre,
       data.styles[0]                AS ds_style,
       data.formats[0].name          AS ds_format,
       data.labels[0].catno          AS cd_catno,
       data.released                 AS ds_released,
       -- '1991-09-24' becomes a date; '1991' and '1991-00-00' become null
       CASE WHEN data.released RLIKE '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' AND data.released NOT LIKE '%-00%'
            THEN to_date(data.released) END AS dt_released,
       data.community.have           AS qt_have,
       data.community.want           AS qt_want,
       data.community.rating.average AS vl_rating_avg,
       data.community.rating.count   AS qt_rating,
       to_timestamp(data.date_changed) AS ts_changed
FROM bronze_releases
