-- Calendar from the first to the last day with a snapshot.
WITH bounds AS (SELECT MIN(dt) AS first_dt, MAX(dt) AS last_dt FROM silver_releases)
SELECT d                                AS dt,
       YEAR(d)                          AS nr_year,
       QUARTER(d)                       AS nr_quarter,
       MONTH(d)                         AS nr_month,
       DAYOFMONTH(d)                    AS nr_day,
       DATE_FORMAT(d, 'yyyy-MM')        AS cd_year_month,
       DAYOFWEEK(d) IN (1, 7)           AS fl_weekend
FROM bounds
LATERAL VIEW EXPLODE(SEQUENCE(first_dt, last_dt, INTERVAL 1 DAY)) days AS d
