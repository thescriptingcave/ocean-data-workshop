-- ocean-sim: teaching schema
-- ============================================================================
-- This file is the SOURCE OF TRUTH for the database design. docs/schema.md is
-- generated from it, so the two cannot drift.
--
-- Design intent (ADR 0011): **denormalise first, normalise later.** These tables
-- are deliberately teaching-shaped rather than storage-optimal:
--
--   * units live in the COLUMN NAMES (temperature_c, wind_speed_ms), because
--     a name is the only place a unit is always enforced;
--   * raw measurements sit BESIDE the values derived from them, so you can
--     check the derivation rather than trust it;
--   * quality flags are kept, never dropped -- "why is this row NULL?" should
--     have an answer that is a column, not an absence;
--   * the acoustic table is WIDE (one column per third-octave band) because
--     that is the form both teaching and the ML feature matrix want.
--
-- Normalising any of this is an exercise, not something the schema does for you.
--
-- TimescaleDB: high-volume, append-only time series become hypertables. Small
-- relational tables stay ordinary Postgres tables so learners see plain SQL.
-- The extension is optional in the sense that the core design works without it.
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS timescaledb;

-- ---------------------------------------------------------------------------
-- Provenance. Every measurement table can be traced to a source. This is what
-- makes a number defensible months later.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS source (
    source_id      TEXT PRIMARY KEY,
    name           TEXT NOT NULL,
    organisation   TEXT,
    access_class   TEXT NOT NULL
                  CHECK (access_class IN ('A','B','C','D','E','F','G','H')),
    retrieval_url  TEXT,
    notes          TEXT
);

CREATE TABLE IF NOT EXISTS run (
    run_id         TEXT PRIMARY KEY,
    description    TEXT,
    site_name      TEXT,
    site_lat       DOUBLE PRECISION,
    site_lon       DOUBLE PRECISION,
    window_start   TIMESTAMPTZ,
    window_end     TIMESTAMPTZ,
    created_utc    TIMESTAMPTZ NOT NULL DEFAULT now(),
    notes          TEXT
);

-- ---------------------------------------------------------------------------
-- OCEAN: daily, depth-resolved, bay-mean fields.
--
-- Stored LONG ON DEPTH, WIDE ON VARIABLES: one row per (day, depth) rather than
-- one column per depth. 19 depths x 4 variables as columns would be 76 columns
-- of mostly NULL; as rows it is 19 tidy rows per day.
--
-- `raw_` columns are what GLORYS reports; `sound_speed_ms` and `dc_dz_s` are
-- derived with TEOS-10 and are kept alongside so the derivation is auditable.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ocean_profile_daily (
    observed_at        TIMESTAMPTZ      NOT NULL,
    depth_m            DOUBLE PRECISION  NOT NULL,   -- positive down, CF convention
    raw_temperature_c  DOUBLE PRECISION,             -- GLORYS thetao
    raw_salinity_psu   DOUBLE PRECISION,             -- GLORYS so, practical
    u_eastward_ms      DOUBLE PRECISION,             -- GLORYS uo
    v_northward_ms     DOUBLE PRECISION,             -- GLORYS vo
    -- derived, TEOS-10 via gsw (which takes degrees C, not kelvin)
    conservative_temp_c      DOUBLE PRECISION,
    absolute_salinity_gkg    DOUBLE PRECISION,
    sound_speed_ms           DOUBLE PRECISION,
    dc_dz_s                  DOUBLE PRECISION,       -- ducting driver; <0 = duct
    potential_density_kgm3   DOUBLE PRECISION,
    qc_flag           SMALLINT NOT NULL DEFAULT 1,  -- 1 good, 0 not evaluated, 2 suspect
    PRIMARY KEY (observed_at, depth_m)
);

SELECT create_hypertable('ocean_profile_daily', 'observed_at',
                         chunk_time_interval => INTERVAL '30 days',
                         if_not_exists => TRUE);

-- ---------------------------------------------------------------------------
-- WIND: daily aggregates from NDBC moored observations.
--
-- `wind_direction_deg` is the direction the wind comes FROM. It WRAPS at 360,
-- so it must never be averaged in degrees -- see wind_bearing_deg, which is a
-- proper circular mean, and the `circular_*` helpers in the SQL curriculum.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS wind_daily (
    observed_at            TIMESTAMPTZ NOT NULL,
    station_id             TEXT NOT NULL,
    wind_speed_mean_ms     DOUBLE PRECISION,
    wind_gust_max_ms       DOUBLE PRECISION,
    wind_direction_deg     DOUBLE PRECISION,   -- from, meteorological
    wind_u_east_ms         DOUBLE PRECISION,   -- where the air is GOING
    wind_v_north_ms        DOUBLE PRECISION,
    wind_northward_ms      DOUBLE PRECISION,   -- + = northerly = upwelling-favourable
    wave_height_max_m      DOUBLE PRECISION,
    air_temp_mean_c        DOUBLE PRECISION,
    water_temp_mean_c      DOUBLE PRECISION,
    qc_flag                SMALLINT NOT NULL DEFAULT 1,
    PRIMARY KEY (observed_at, station_id)
);

SELECT create_hypertable('wind_daily', 'observed_at',
                         chunk_time_interval => INTERVAL '30 days',
                         if_not_exists => TRUE);

-- ---------------------------------------------------------------------------
-- ACOUSTIC: hourly third-octave band levels, moored at 116 m.
--
-- WIDE on purpose -- one column per band, 25 Hz to 20 kHz. This is the form the
-- ML feature matrix wants, and it makes band-vs-band comparison a SELECT rather
-- than a pivot. A tidy (time, frequency, level_dB) table is an exercise.
--
-- band levels are 1/3-octave, dB re 1 uPa^2/Hz, hourly medians.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS acoustic_tol_hourly (
    observed_at   TIMESTAMPTZ NOT NULL,
    site_id       TEXT NOT NULL,
    sensor_depth_m  DOUBLE PRECISION,
    -- third-octave band centres, Hz
    band_25hz   DOUBLE PRECISION,  band_32hz   DOUBLE PRECISION,
    band_40hz   DOUBLE PRECISION,  band_50hz   DOUBLE PRECISION,
    band_63hz   DOUBLE PRECISION,  band_80hz   DOUBLE PRECISION,
    band_100hz  DOUBLE PRECISION,  band_125hz  DOUBLE PRECISION,
    band_160hz  DOUBLE PRECISION,  band_200hz  DOUBLE PRECISION,
    band_250hz  DOUBLE PRECISION,  band_315hz  DOUBLE PRECISION,
    band_400hz  DOUBLE PRECISION,  band_500hz  DOUBLE PRECISION,
    band_630hz  DOUBLE PRECISION,  band_800hz  DOUBLE PRECISION,
    band_1000hz DOUBLE PRECISION,  band_1250hz DOUBLE PRECISION,
    band_1600hz DOUBLE PRECISION,  band_2000hz DOUBLE PRECISION,
    band_2500hz DOUBLE PRECISION,  band_3150hz DOUBLE PRECISION,
    band_4000hz DOUBLE PRECISION,  band_5000hz DOUBLE PRECISION,
    band_6300hz DOUBLE PRECISION,  band_8000hz DOUBLE PRECISION,
    band_10000hz DOUBLE PRECISION, band_12500hz DOUBLE PRECISION,
    band_16000hz DOUBLE PRECISION, band_20000hz DOUBLE PRECISION,
    qc_flag      SMALLINT NOT NULL DEFAULT 1,
    PRIMARY KEY (observed_at, site_id)
);

SELECT create_hypertable('acoustic_tol_hourly', 'observed_at',
                         chunk_time_interval => INTERVAL '7 days',
                         if_not_exists => TRUE);

-- ---------------------------------------------------------------------------
-- DETECTIONS: hourly presence/absence from the SanctSound detectors.
--
-- IMPORTANT and easy to get wrong: `ships` is an EVENT LIST -- every row is a
-- detection, so presence is always 1. It is not an hourly 0/1 series and cannot
-- be turned into one without the full hourly grid. `dolphins_1h` IS a full 0/1
-- series. Different problem shapes, not two versions of one task.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS detection_hourly (
    observed_at  TIMESTAMPTZ NOT NULL,
    site_id      TEXT NOT NULL,
    deployment   TEXT NOT NULL,
    taxon        TEXT NOT NULL,
    presence     SMALLINT NOT NULL CHECK (presence IN (0, 1)),
    detector     TEXT,        -- e.g. 'LTSA analysis' or 'PamGuard'
    is_event_list BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (observed_at, site_id, deployment, taxon)
);

-- ---------------------------------------------------------------------------
-- Views. These are the joins the curriculum starts from.
-- ---------------------------------------------------------------------------

-- Everything at one site on one timeline. LEFT JOINs throughout so that a missing
-- measurement never silently drops a row from a different instrument.
CREATE OR REPLACE VIEW v_site_hourly AS
SELECT
    a.observed_at,
    a.site_id,
    a.band_160hz, a.band_500hz, a.band_2500hz, a.band_10000hz, a.band_20000hz,
    (SELECT d.presence FROM detection_hourly d
      WHERE d.observed_at = a.observed_at AND d.site_id = a.site_id
        AND d.taxon = 'dolphin' AND NOT d.is_event_list
      ORDER BY d.observed_at DESC LIMIT 1) AS dolphin_presence,
    w.wind_speed_mean_ms,
    w.wind_northward_ms,
    w.wave_height_max_m
FROM acoustic_tol_hourly a
LEFT JOIN wind_daily w
       ON w.observed_at = date_trunc('day', a.observed_at)::timestamp
      AND w.station_id = '46092'
      AND w.observed_at >= date_trunc('day', a.observed_at)::timestamp
      AND w.observed_at <  (date_trunc('day', a.observed_at) + INTERVAL '1 day')::timestamp;

-- Daily surface summary: the join the wind-to-noise analysis used.
CREATE OR REPLACE VIEW v_daily_environment AS
SELECT
    o.observed_at::date                AS day,
    max(o.raw_temperature_c) FILTER (WHERE o.depth_m = (SELECT min(depth_m) FROM ocean_profile_daily)) AS sst_c,
    o.u_eastward_ms,
    o.v_northward_ms,
    w.wind_speed_mean_ms,
    w.wind_northward_ms,
    w.wave_height_max_m
FROM ocean_profile_daily o
LEFT JOIN wind_daily w ON w.observed_at = o.observed_at::date AND w.station_id = '46092'
GROUP BY 1, o.u_eastward_ms, o.v_northward_ms,
         w.wind_speed_mean_ms, w.wind_northward_ms, w.wave_height_max_m;

-- ---------------------------------------------------------------------------
-- Comments. Cheap, and they show up in \d+ in psql and in most SQL browsers.
-- ---------------------------------------------------------------------------
COMMENT ON COLUMN acoustic_tol_hourly.band_160hz IS
    '1/3-octave band level at 160 Hz, dB re 1 uPa^2/Hz, hourly median. 160-500 Hz is the shipping band.';
COMMENT ON COLUMN wind_daily.wind_direction_deg IS
    'Direction the wind comes FROM, degrees true. Wraps at 360: never average it in degrees.';
COMMENT ON COLUMN wind_daily.wind_northward_ms IS
    'Northerly component. Positive = wind from the north, which drives upwelling on the California coast.';
COMMENT ON COLUMN ocean_profile_daily.sound_speed_ms IS
    'TEOS-10 via gsw. gsw takes DEGREES C, not kelvin -- passing 293.15 returns NaN.';
COMMENT ON COLUMN ocean_profile_daily.dc_dz_s IS
    'Vertical gradient of sound speed. Negative = duct. The ducting analysis keys off this.';
