-- Ocean Data Workshop: Advanced SQL - Common Table Expressions (CTEs)
-- ====================================================================
-- This file teaches: CTEs (WITH clauses), recursive CTEs, multiple CTEs
--
-- CTEs (Common Table Expressions) allow you to define temporary result sets
-- that can be referenced within a query. They're like inline views.
--
-- Benefits:
--   * Improves readability for complex queries
--   * Allows reference to the same subquery multiple times
--   * Enables recursive queries for hierarchical data
--   * Can replace subqueries in WHERE clauses for cleaner code

-- ============================================================================
-- Query 1: Simple CTE - Temperature anomalies with pre-calculated mean
-- ============================================================================
-- Compare each day's temperature to the monthly average using a CTE

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

-- ============================================================================
-- Query 2: Multiple CTEs - Joining wind, ocean, and acoustic data
-- ============================================================================
-- Find days when all three data sources have measurements

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

-- ============================================================================
-- Query 3: Recursive CTE - Number days from start of dataset
-- ============================================================================
-- Assign sequential day numbers to each date in ocean_profile_daily

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

-- ============================================================================
-- Query 4: CTE with window function - Top 5 hottest days
-- ============================================================================

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

-- ============================================================================
-- Query 5: CTE for filtering with aggregated values
-- ============================================================================
-- Find days where temperature exceeded the monthly average

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

-- ============================================================================
-- Query 6: Multiple CTEs for correlation analysis
-- ============================================================================
-- Calculate correlation between wind and ocean variables by month

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
-- CTE Patterns taught:
--   1. Simple CTE for readability (Query 1)
--   2. Multiple CTEs in one query (Queries 2, 6)
--   3. Recursive CTEs for sequences (Query 3)
--   4. CTEs with window functions (Query 4)
--   5. CTEs for pre-filtering aggregated data (Query 5)
--   6. CTEs for correlation analysis (Query 6)
--   7. CROSS JOIN with CTEs
--   8. INTERSECT with CTEs
--   9. CTEs as building blocks for complex queries
-- ============================================================================
