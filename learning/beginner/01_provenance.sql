-- Ocean Data Workshop: Beginner SQL - Provenance Tables
-- =========================================================
-- This file teaches: basic table creation, PRIMARY KEY constraints,
-- CHECK constraints, TEXT vs other data types
--
-- Design principle: provenance matters. Every measurement should be
-- traceable to its source for defensibility months later.
--
-- Access classes:
--   A = Anonymous HTTP (no account, no key)
--   B = Anonymous, other protocol (FTP, OPeNDAP)
--   C = Free account, password login
--   D = Free account + API key
--   E = Account + terms or approval
--   F = Manual request (email, form, person)
--   G = Licensed (free academic, commercial prohibited)
--   H = Unavailable

-- ============================================================================
-- Query 1: View all sources with their access class
-- ============================================================================

SELECT source_id, name, organisation, access_class, retrieval_url
FROM source
ORDER BY access_class;

-- ============================================================================
-- Query 2: Find all anonymous sources (A)
-- ============================================================================

SELECT name, retrieval_url, notes
FROM source
WHERE access_class = 'A'
ORDER BY name;

-- ============================================================================
-- Query 3: Get the most recent run
-- ============================================================================

SELECT run_id, description, site_name, window_start, window_end, created_utc
FROM run
ORDER BY created_utc DESC
LIMIT 1;

-- ============================================================================
-- Query 4: Get runs for a specific date range
-- ============================================================================

SELECT run_id, description, window_start, window_end
FROM run
WHERE window_start >= '2019-09-01'
  AND window_start < '2020-01-01'
ORDER BY window_start;

-- ============================================================================
-- Query 5: Count sources by access class
-- ============================================================================

SELECT access_class, COUNT(*) as count
FROM source
GROUP BY access_class
ORDER BY access_class;

-- ============================================================================
-- Learning concepts:
--   * SELECT with WHERE clause
--   * ORDER BY for sorting
--   * COUNT with GROUP BY
--   * DISTINCT values in CHECK constraint
--   * Aliasing columns (AS)
-- ============================================================================
