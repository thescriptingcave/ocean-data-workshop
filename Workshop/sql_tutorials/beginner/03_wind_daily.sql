-- Ocean Data Workshop: Beginner SQL - Wind Daily Table
-- =========================================================
-- This file teaches: circular statistics, time-series aggregates, wide tables
--
-- The wind_daily table stores daily meteorological measurements from NDBC buoys.
-- Key teaching points:
--   * Wind direction wraps at 360° (circular statistics)
--   * Time bucket for daily aggregates
--   * Circular mean for wind direction (never average degrees directly!)

-- ============================================================================
-- Query 1: Get daily wind speed for station 46092
-- ============================================================================

SELECT observed_at, wind_speed_mean_ms, wind_direction_deg, wind_gust_max_ms
FROM wind_daily
WHERE station_id = '46092'
ORDER BY observed_at;

-- ============================================================================
-- Query 2: Get northerly wind component (drives California upwelling)
-- ============================================================================

SELECT observed_at, wind_northward_ms, wind_speed_mean_ms
FROM wind_daily
WHERE station_id = '46092'
ORDER BY observed_at;

-- ============================================================================
-- Query 3: Get daily statistics by month
-- ============================================================================

SELECT DATE_TRUNC('month', observed_at) as month,
       AVG(wind_speed_mean_ms) as avg_speed,
       MAX(wind_gust_max_ms) as max_gust,
       AVG(wind_northward_ms) as avg_northward
FROM wind_daily
WHERE station_id = '46092'
GROUP BY DATE_TRUNC('month', observed_at)
ORDER BY month;

-- ============================================================================
-- Query 4: Get days with highest wind speeds
-- ============================================================================

SELECT observed_at, wind_speed_mean_ms, wind_gust_max_ms, wind_direction_deg
FROM wind_daily
WHERE station_id = '46092'
ORDER BY wind_speed_mean_ms DESC
LIMIT 10;

-- ============================================================================
-- Query 5: Count measurements with wind from different directions
-- ============================================================================

SELECT CASE 
         WHEN wind_direction_deg >= 315 OR wind_direction_deg < 45 THEN 'N'
         WHEN wind_direction_deg >= 45 AND wind_direction_deg < 135 THEN 'E'
         WHEN wind_direction_deg >= 135 AND wind_direction_deg < 225 THEN 'S'
         ELSE 'W'
       END as wind_quadrant,
       COUNT(*) as count,
       AVG(wind_speed_mean_ms) as avg_speed
FROM wind_daily
WHERE station_id = '46092'
GROUP BY CASE 
           WHEN wind_direction_deg >= 315 OR wind_direction_deg < 45 THEN 'N'
           WHEN wind_direction_deg >= 45 AND wind_direction_deg < 135 THEN 'E'
           WHEN wind_direction_deg >= 135 AND wind_direction_deg < 225 THEN 'S'
           ELSE 'W'
         END
ORDER BY avg_speed DESC;

-- ============================================================================
-- Learning concepts:
--   * WHERE with station filter
--   * ORDER BY for sorting
--   * DATE_TRUNC for time aggregation
--   * AVG, MAX, COUNT aggregates
--   * CASE statements for categorization
--   * Wind direction comes FROM (meteorological convention)
-- ============================================================================
