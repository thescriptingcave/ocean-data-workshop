-- Ocean Data Workshop: Advanced SQL - Column Comments
-- =====================================================
-- This file contains column comments for documentation.
-- 
-- Comments make queries self-documenting and show up in:
--   * psql \d+ commands
--   * SQL browser tools
--   * Database documentation

-- ============================================================================
-- Query 1: View column comments for acoustic table
-- ============================================================================

SELECT column_name, 
       pg_catalog.col_description(
           'acoustic_tol_hourly'::regclass, 
           ordinal_position
       ) as comment
FROM information_schema.columns
WHERE table_name = 'acoustic_tol_hourly'
ORDER BY ordinal_position;

-- ============================================================================
-- Query 2: View column comments for wind table
-- ============================================================================

SELECT column_name, 
       pg_catalog.col_description(
           'wind_daily'::regclass, 
           ordinal_position
       ) as comment
FROM information_schema.columns
WHERE table_name = 'wind_daily'
ORDER BY ordinal_position;

-- ============================================================================
-- Query 3: Get all comments for a table
-- ============================================================================

SELECT 
    c.column_name,
    c.data_type,
    pg_catalog.col_description('ocean_profile_daily'::regclass, c.ordinal_position) as comment
FROM information_schema.columns c
WHERE c.table_name = 'ocean_profile_daily'
ORDER BY c.ordinal_position;

-- ============================================================================
-- Column meanings (from comments):
-- 
-- acoustic_tol_hourly:
--   * band_160hz: 1/3-octave band at 160 Hz, 160-500 Hz is shipping band
-- 
-- wind_daily:
--   * wind_direction_deg: Direction wind comes FROM (not where it goes to)
--   * wind_northward_ms: Northerly component, positive = upwelling
-- 
-- ocean_profile_daily:
--   * sound_speed_ms: TEOS-10 via gsw, takes DEGREES C not kelvin
--   * dc_dz_s: Vertical gradient of sound speed, <0 = ducting
-- ============================================================================
