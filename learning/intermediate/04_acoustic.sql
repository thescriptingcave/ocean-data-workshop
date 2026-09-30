-- Ocean Data Workshop: Intermediate SQL - Acoustic Table
-- =========================================================
-- This file teaches: wide tables, many columns with pattern naming,
-- frequency band analysis
--
-- The acoustic_tol_hourly table stores hourly sound pressure levels in 30 third-octave bands.
-- Key teaching points:
--   * Wide table (one column per band) for ML feature matrix
--   * Pattern-based column naming (band_XXhz)
--   * 25 Hz to 20 kHz range, 30 frequency bands

-- ============================================================================
-- Query 1: Select specific frequency bands for analysis
-- ============================================================================

SELECT observed_at, site_id,
       band_160hz, band_500hz, band_2500hz, band_10000hz, band_20000hz
FROM acoustic_tol_hourly
WHERE site_id = 'mb01'
ORDER BY observed_at;

-- ============================================================================
-- Query 2: Get all bands for a specific hour (wide table advantage)
-- ============================================================================

SELECT * FROM acoustic_tol_hourly
WHERE observed_at = '2019-09-15 12:00:00' AND site_id = 'mb01';

-- ============================================================================
-- Query 3: Get all bands for multiple samples (unpivot concept)
-- ============================================================================

SELECT observed_at, site_id, band_160hz as level_dB
FROM acoustic_tol_hourly
WHERE site_id = 'mb01' AND band_160hz IS NOT NULL
UNION ALL
SELECT observed_at, site_id, band_500hz as level_dB
FROM acoustic_tol_hourly
WHERE site_id = 'mb01' AND band_500hz IS NOT NULL
ORDER BY observed_at, level_dB DESC;

-- ============================================================================
-- Query 4: Calculate average levels by band
-- ============================================================================

SELECT 
    'band_160hz' as band, AVG(band_160hz) as avg_level
FROM acoustic_tol_hourly WHERE site_id = 'mb01'
UNION ALL
SELECT 'band_500hz', AVG(band_500hz)
FROM acoustic_tol_hourly WHERE site_id = 'mb01'
UNION ALL
SELECT 'band_2500hz', AVG(band_2500hz)
FROM acoustic_tol_hourly WHERE site_id = 'mb01'
UNION ALL
SELECT 'band_20000hz', AVG(band_20000hz)
FROM acoustic_tol_hourly WHERE site_id = 'mb01'
ORDER BY avg_level DESC;

-- ============================================================================
-- Query 5: Get band levels with wave height for correlation
-- ============================================================================

SELECT a.band_160hz, a.band_2500hz, w.wind_speed_mean_ms, w.wave_height_max_m
FROM acoustic_tol_hourly a
JOIN wind_daily w ON w.observed_at = DATE_TRUNC('day', a.observed_at)::timestamp
WHERE a.site_id = 'mb01' AND w.station_id = '46092'
ORDER BY a.observed_at;

-- ============================================================================
-- Band frequency ranges (hertz):
--   25-32 Hz: Very low frequency, shipping noise
--   160-500 Hz: Shipping band
--   1-10 kHz: Dolphin click band
--   10-20 kHz: High frequency, wind noise
-- ============================================================================
