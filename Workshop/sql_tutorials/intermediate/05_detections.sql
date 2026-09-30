-- Ocean Data Workshop: Intermediate SQL - Detection Table
-- =========================================================
-- This file teaches: event lists vs presence/absence, composite primary keys
--
-- The detection_hourly table stores animal detection data from SanctSound.
-- Key teaching points:
--   * `ships` is an EVENT LIST (every row is a detection)
--   * `dolphin` is presence/absence (hourly 0/1 series)
--   * Different problem shapes, NOT two versions of one task
--   * is_event_list flag to distinguish the two

-- ============================================================================
-- Query 1: Get dolphin presence (0/1 time series)
-- ============================================================================

SELECT observed_at, presence 
FROM detection_hourly
WHERE taxon = 'dolphin' AND is_event_list = FALSE
ORDER BY observed_at;

-- ============================================================================
-- Query 2: Get ship detections (event list - one row per detection)
-- ============================================================================

SELECT observed_at, site_id, deployment
FROM detection_hourly
WHERE taxon = 'ships' AND is_event_list = TRUE
ORDER BY observed_at;

-- ============================================================================
-- Query 3: Count daily dolphin presence
-- ============================================================================

SELECT DATE(observed_at) as day, 
       COUNT(*) as hourly_count,
       SUM(presence) as positive_hours,
       CAST(SUM(presence) AS FLOAT) / COUNT(*) as detection_rate
FROM detection_hourly
WHERE taxon = 'dolphin' AND is_event_list = FALSE
GROUP BY DATE(observed_at)
ORDER BY day;

-- ============================================================================
-- Query 4: Count daily ship events
-- ============================================================================

SELECT DATE(observed_at) as day, COUNT(*) as ship_events
FROM detection_hourly
WHERE taxon = 'ships' AND is_event_list = TRUE
GROUP BY DATE(observed_at)
ORDER BY day;

-- ============================================================================
-- Query 5: Get detections by taxon
-- ============================================================================

SELECT taxon, COUNT(*) as total_count, MAX(presence) as max_presence
FROM detection_hourly
GROUP BY taxon
ORDER BY total_count DESC;

-- ============================================================================
-- Query 6: Get dolphin detection by detector type
-- ============================================================================

SELECT detector, COUNT(*) as count, 
       CAST(SUM(presence) AS FLOAT) / COUNT(*) as detection_rate
FROM detection_hourly
WHERE taxon = 'dolphin' AND is_event_list = FALSE
GROUP BY detector
ORDER BY detection_rate DESC;

-- ============================================================================
-- CAUTION: Do NOT aggregate ships like dolphin!
-- ships is an event list - each row IS an event, not a presence record
-- ============================================================================
