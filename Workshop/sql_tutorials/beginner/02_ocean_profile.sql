-- Ocean Data Workshop: Beginner SQL - Ocean Profile Table
-- =========================================================
-- This file teaches: hypertables, time-series data, multi-column primary keys
--
-- The ocean_profile_daily table stores depth-resolved oceanographic measurements.
-- Key teaching points:
--   * Stored LONG on depth (one row per day+depth)
--   * Hypertables for time-based partitioning
--   * Raw measurements alongside derived values (for verification)

-- ============================================================================
-- Query 1: Get surface temperature for all days
-- (using subquery to find minimum depth)
-- ============================================================================

SELECT observed_at, raw_temperature_c 
FROM ocean_profile_daily 
WHERE depth_m = (SELECT MIN(depth_m) FROM ocean_profile_daily)
ORDER BY observed_at;

-- ============================================================================
-- Query 2: Get all data for a specific day
-- ============================================================================

SELECT * FROM ocean_profile_daily 
WHERE observed_at::date = '2019-09-15'
ORDER BY depth_m;

-- ============================================================================
-- Query 3: Get temperature range for each day
-- ============================================================================

SELECT observed_at::date as day,
       MIN(raw_temperature_c) as min_temp,
       MAX(raw_temperature_c) as max_temp,
       MAX(raw_temperature_c) - MIN(raw_temperature_c) as temp_range
FROM ocean_profile_daily
GROUP BY observed_at::date
ORDER BY day;

-- ============================================================================
-- Query 4: Get the deepest temperature measurement
-- ============================================================================

SELECT observed_at, depth_m, raw_temperature_c 
FROM ocean_profile_daily 
WHERE depth_m = (SELECT MAX(depth_m) FROM ocean_profile_daily)
ORDER BY observed_at;

-- ============================================================================
-- Query 5: Get all measurements at a specific depth
-- ============================================================================

SELECT observed_at, raw_temperature_c, raw_salinity_psu
FROM ocean_profile_daily 
WHERE depth_m BETWEEN 10 AND 20
ORDER BY observed_at, depth_m;

-- ============================================================================
-- Learning concepts:
--   * Subqueries in WHERE clause
--   * Type casting (observed_at::date)
--   * Aggregation with GROUP BY
--   * MIN/MAX functions
--   * BETWEEN for range queries
--   * Aliasing columns (AS)
-- ============================================================================
