-- Master SQL script to run all SQL files in the curriculum
-- Run this in TablePlus to set up the complete database

-- ============================================================================
-- BEGINNER LEVEL
-- ============================================================================

-- File 1: Basic tables, constraints
\i learning/beginner/01_provenance.sql

-- File 2: Hypertables, time-series data
\i learning/beginner/02_ocean_profile.sql

-- File 3: Circular statistics, daily aggregates
\i learning/beginner/03_wind_daily.sql

-- ============================================================================
-- INTERMEDIATE LEVEL
-- ============================================================================

-- File 4: Wide tables, frequency bands
\i learning/intermediate/04_acoustic.sql

-- File 5: Event lists vs presence/absence
\i learning/intermediate/05_detections.sql

-- ============================================================================
-- ADVANCED LEVEL
-- ============================================================================

-- File 6: Complex joins, views
\i learning/advanced/06_views.sql

-- File 7: Column comments
\i learning/advanced/07_comments.sql
