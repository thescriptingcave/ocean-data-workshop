-- Ocean Data Workshop: Complete SQL Curriculum
-- ==============================================
-- This file contains query examples from all SQL files combined for easy running in TablePlus
--
-- Instructions:
-- 1. Open this file in TablePlus (copy-paste or open)
-- 2. Click Run
-- 3. Examine results and comments to learn SQL concepts

-- ============================================================================
-- BEGINNER LEVEL
-- ============================================================================

-- ============================================================================
-- File 1: 01_provenance.sql
-- Basic tables, constraints, access classes
-- ============================================================================

-- Query 1: View all sources with their access class
SELECT source_id, name, organisation, access_class, retrieval_url
FROM source
ORDER BY access_class;

-- Query 2: Find all anonymous sources (A)
SELECT name, retrieval_url, notes
FROM source
WHERE access_class = 'A'
ORDER BY name;

-- Query 3: Get the most recent run
SELECT run_id, description, site_name, window_start, window_end, created_utc
FROM run
ORDER BY created_utc DESC
LIMIT 1;

-- ============================================================================
-- File 2: 02_ocean_profile.sql
-- Hypertables, time-series partitioning
-- ============================================================================

-- Query 1: Get surface temperature for all days
SELECT observed_at, raw_temperature_c 
FROM ocean_profile_daily 
WHERE depth_m = (SELECT MIN(depth_m) FROM ocean_profile_daily)
ORDER BY observed_at;

-- Query 2: Get all data for a specific day
SELECT * FROM ocean_profile_daily 
WHERE observed_at::date = '2019-09-15'
ORDER BY depth_m;

-- Query 3: Get temperature range for each day
SELECT observed_at::date as day,
       MIN(raw_temperature_c) as min_temp,
       MAX(raw_temperature_c) as max_temp
FROM ocean_profile_daily
GROUP BY observed_at::date
ORDER BY day;

-- ============================================================================
-- File 3: 03_wind_daily.sql
-- Circular statistics, daily aggregates
-- ============================================================================

-- Query 1: Get daily wind speed for station 46092
SELECT observed_at, wind_speed_mean_ms, wind_direction_deg, wind_gust_max_ms
FROM wind_daily
WHERE station_id = '46092'
ORDER BY observed_at;

-- Query 2: Get northerly wind component
SELECT observed_at, wind_northward_ms, wind_speed_mean_ms
FROM wind_daily
WHERE station_id = '46092'
ORDER BY observed_at;

-- ============================================================================
-- INTERMEDIATE LEVEL
-- ============================================================================

-- ============================================================================
-- File 4: 04_acoustic.sql
-- Wide tables, frequency bands (30 bands)
-- ============================================================================

-- Query 1: Select specific frequency bands
SELECT observed_at, site_id,
       band_160hz, band_500hz, band_2500hz, band_10000hz, band_20000hz
FROM acoustic_tol_hourly
WHERE site_id = 'mb01'
ORDER BY observed_at;

-- Query 2: Calculate average levels by band
SELECT 'band_160hz' as band, AVG(band_160hz) as avg_level
FROM acoustic_tol_hourly WHERE site_id = 'mb01'
UNION ALL
SELECT 'band_500hz', AVG(band_500hz)
FROM acoustic_tol_hourly WHERE site_id = 'mb01'
UNION ALL
SELECT 'band_2500hz', AVG(band_2500hz)
FROM acoustic_tol_hourly WHERE site_id = 'mb01'
ORDER BY avg_level DESC;

-- ============================================================================
-- File 5: 05_detections.sql
-- Event lists vs presence/absence
-- ============================================================================

-- Query 1: Get dolphin presence (0/1 time series)
SELECT observed_at, presence 
FROM detection_hourly
WHERE taxon = 'dolphin' AND is_event_list = FALSE
ORDER BY observed_at;

-- Query 2: Count daily dolphin detection rate
SELECT DATE(observed_at) as day, 
       COUNT(*) as hourly_count,
       CAST(SUM(presence) AS FLOAT) / COUNT(*) as detection_rate
FROM detection_hourly
WHERE taxon = 'dolphin' AND is_event_list = FALSE
GROUP BY DATE(observed_at)
ORDER BY day;

-- ============================================================================
-- ADVANCED LEVEL
-- ============================================================================

-- ============================================================================
-- File 6: 06_views.sql
-- Complex JOINs, window functions
-- ============================================================================

-- Query 1: Get hourly data from v_site_hourly
SELECT * FROM v_site_hourly
WHERE observed_at >= '2019-09-15' AND observed_at < '2019-09-16'
ORDER BY observed_at;

-- Query 2: Compare acoustic levels with dolphin presence
SELECT 
    CASE WHEN dolphin_presence = 1 THEN 'dolphin' ELSE 'no dolphin' END as condition,
    AVG(band_160hz) as avg_160hz,
    AVG(band_20000hz) as avg_20kHz
FROM v_site_hourly
GROUP BY dolphin_presence;

-- Query 3: Correlation between wind and ocean currents
SELECT corr(wind_northward_ms, v_northward_ms) as wind_current_corr
FROM v_daily_environment;

-- Query 4: Daily SST and wind relationship
SELECT day, sst_c, wind_speed_mean_ms,
       sst_c - LAG(sst_c) OVER (ORDER BY day) as sst_change,
       wind_speed_mean_ms - LAG(wind_speed_mean_ms) OVER (ORDER BY day) as wind_change
FROM v_daily_environment
ORDER BY day;

-- Query 5: Temperature anomaly analysis
SELECT day, sst_c,
       AVG(sst_c) OVER () as global_mean,
       sst_c - AVG(sst_c) OVER () as anomaly
FROM v_daily_environment
ORDER BY anomaly DESC;

-- ============================================================================
-- File 7: 07_comments.sql
-- Column documentation
-- ============================================================================

-- Query 1: View column comments for acoustic table
SELECT column_name, 
       pg_catalog.col_description(
           'acoustic_tol_hourly'::regclass, 
           ordinal_position
       ) as comment
FROM information_schema.columns
WHERE table_name = 'acoustic_tol_hourly'
ORDER BY ordinal_position;

-- ============================================================================
-- File 8: 08_ctes.sql
-- Common Table Expressions (CTEs)
-- ============================================================================

-- Query 1: Simple CTE - Temperature anomalies
WITH monthly_stats AS (
    SELECT 
        observed_at::date as day,
        AVG(raw_temperature_c) OVER (PARTITION BY observed_at::date) as daily_mean_temp
    FROM ocean_profile_daily
)
SELECT 
    day,
    daily_mean_temp,
    daily_mean_temp - AVG(daily_mean_temp) OVER () as temp_anomaly
FROM monthly_stats
GROUP BY day, daily_mean_temp
ORDER BY temp_anomaly DESC;

-- Query 2: Multiple CTEs - Joining data sources
WITH wind_days AS (
    SELECT DISTINCT observed_at::date as day
    FROM wind_daily
    WHERE station_id = '46092'
),
ocean_days AS (
    SELECT DISTINCT observed_at::date as day
    FROM ocean_profile_daily
),
acoustic_days AS (
    SELECT DISTINCT observed_at::date as day
    FROM acoustic_tol_hourly
    WHERE site_id = 'mb01'
),
all_days AS (
    SELECT day FROM wind_days
    INTERSECT
    SELECT day FROM ocean_days
    INTERSECT
    SELECT day FROM acoustic_days
)
SELECT 
    d.day,
    (SELECT AVG(wind_speed_mean_ms) FROM wind_daily WHERE observed_at::date = d.day) as wind_speed,
    (SELECT AVG(raw_temperature_c) FROM ocean_profile_daily WHERE observed_at::date = d.day) as ocean_temp,
    (SELECT AVG(band_160hz) FROM acoustic_tol_hourly WHERE observed_at::date = d.day AND site_id = 'mb01') as acoustic_160hz
FROM all_days d
ORDER BY d.day;

-- Query 3: Recursive CTE - Number days from start
WITH RECURSIVE day_numbers AS (
    SELECT CAST(MIN(observed_at) AS date) as day, 1::int as day_number
    FROM ocean_profile_daily
    UNION ALL
    SELECT (day + INTERVAL '1 day')::date, day_number + 1
    FROM day_numbers
    WHERE day < (SELECT CAST(MAX(observed_at) AS date) FROM ocean_profile_daily)
)
SELECT day, day_number
FROM day_numbers
ORDER BY day_number
LIMIT 30;

-- Query 4: CTE with window function - Top hottest days
WITH daily_temps AS (
    SELECT 
        observed_at::date as day,
        MAX(raw_temperature_c) as max_temp
    FROM ocean_profile_daily
    GROUP BY observed_at::date
),
ranked_days AS (
    SELECT 
        day,
        max_temp,
        RANK() OVER (ORDER BY max_temp DESC) as rank
    FROM daily_temps
)
SELECT day, max_temp, rank
FROM ranked_days
WHERE rank <= 5
ORDER BY max_temp DESC;

-- Query 5: CTE for filtering with aggregated values
WITH daily_stats AS (
    SELECT 
        observed_at::date as day,
        AVG(raw_temperature_c) as daily_avg,
        MAX(raw_temperature_c) as daily_max
    FROM ocean_profile_daily
    GROUP BY observed_at::date
),
overall_avg AS (
    SELECT AVG(daily_avg) as avg_temp
    FROM daily_stats
)
SELECT 
    d.day,
    d.daily_avg,
    d.daily_max,
    d.daily_max - o.avg_temp as excess_above_avg
FROM daily_stats d
CROSS JOIN overall_avg o
WHERE d.daily_max > o.avg_temp
ORDER BY excess_above_avg DESC;

-- Query 6: Multiple CTEs for correlation analysis
WITH monthly_wind AS (
    SELECT 
        DATE_TRUNC('month', observed_at) as month,
        AVG(wind_speed_mean_ms) as avg_wind,
        AVG(wind_northward_ms) as avg_northward
    FROM wind_daily
    WHERE station_id = '46092'
    GROUP BY DATE_TRUNC('month', observed_at)
),
monthly_ocean AS (
    SELECT 
        DATE_TRUNC('month', observed_at) as month,
        AVG(raw_temperature_c) as avg_temp,
        AVG(sound_speed_ms) as avg_sound_speed
    FROM ocean_profile_daily
    GROUP BY DATE_TRUNC('month', observed_at)
),
joined_data AS (
    SELECT 
        w.month,
        w.avg_wind,
        w.avg_northward,
        o.avg_temp,
        o.avg_sound_speed
    FROM monthly_wind w
    JOIN monthly_ocean o ON w.month = o.month
)
SELECT 
    'wind_temp_corr' as metric,
    corr(avg_wind, avg_temp) as correlation
FROM joined_data

UNION ALL

SELECT 
    'wind_sound_corr' as metric,
    corr(avg_wind, avg_sound_speed) as correlation
FROM joined_data;

-- ============================================================================
-- Summary:
-- This file demonstrates:
--   * Basic queries with SELECT, WHERE, ORDER BY
--   * Subqueries and aggregation
--   * Time-series analysis with DATE_TRUNC
--   * JOINs across multiple tables
--   * Window functions (LAG, AVG OVER)
--   * Column comments for documentation
--   * Common Table Expressions (CTEs) - simple, multiple, recursive
--   * CROSS JOIN, INTERSECT with CTEs
-- ============================================================================
