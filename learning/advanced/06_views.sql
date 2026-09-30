-- Ocean Data Workshop: Advanced SQL - Views
-- ==========================================
-- This file teaches: complex joins, window functions, time-based joins
--
-- Views combine multiple data sources for analysis. The key challenges:
--   * LEFT JOINs so missing measurements don't drop rows
--   * Time-based joins (date_trunc for daily aggregation)
--   * Subqueries for specific values (e.g., surface temperature)

-- ============================================================================
-- Query 1: Get hourly data from v_site_hourly view
-- ============================================================================

SELECT * FROM v_site_hourly
WHERE observed_at >= '2019-09-15' AND observed_at < '2019-09-16'
ORDER BY observed_at;

-- ============================================================================
-- Query 2: Compare acoustic levels on days with vs without dolphins
-- ============================================================================

SELECT 
    CASE WHEN dolphin_presence = 1 THEN 'dolphin' ELSE 'no dolphin' END as condition,
    AVG(band_160hz) as avg_160hz,
    AVG(band_20000hz) as avg_20kHz,
    AVG(wind_speed_mean_ms) as avg_wind
FROM v_site_hourly
GROUP BY dolphin_presence;

-- ============================================================================
-- Query 3: Get daily environment data from v_daily_environment
-- ============================================================================

SELECT day, sst_c, wind_speed_mean_ms, wind_northward_ms
FROM v_daily_environment
ORDER BY day;

-- ============================================================================
-- Query 4: Correlation between northerly wind and ocean currents
-- ============================================================================

SELECT corr(wind_northward_ms, v_northward_ms) as wind_current_corr,
       corr(wind_northward_ms, u_eastward_ms) as wind_east_corr
FROM v_daily_environment;

-- ============================================================================
-- Query 5: Daily SST and wind relationship
-- ============================================================================

SELECT day, sst_c, wind_speed_mean_ms,
       sst_c - LAG(sst_c) OVER (ORDER BY day) as sst_change,
       wind_speed_mean_ms - LAG(wind_speed_mean_ms) OVER (ORDER BY day) as wind_change
FROM v_daily_environment
ORDER BY day;

-- ============================================================================
-- Query 6: Temperature anomaly analysis
-- ============================================================================

SELECT day, sst_c,
       AVG(sst_c) OVER () as global_mean,
       sst_c - AVG(sst_c) OVER () as anomaly
FROM v_daily_environment
ORDER BY anomaly DESC;

-- ============================================================================
-- Common patterns taught by these views:
--   1. LEFT JOIN preserves rows even when one side has missing data
--   2. date_trunc('day', ...) for daily aggregation of hourly data
--   3. Subqueries for specific values (min depth, latest detection)
--   4. FILTER clause for conditional aggregation
--   5. GROUP BY column positions (GROUP BY 1, 2, 3) for conciseness
--   6. Time-based joins with explicit date ranges
--   7. Window functions (LAG, AVG OVER) for time-series analysis
-- ============================================================================
