"""Load the three verified sources into PostgreSQL.

Ocean (GLORYS, daily, depth-resolved), wind (NDBC, daily), acoustic (SanctSound MB01
third-octave, hourly), and the SanctSound detections.

Design notes:

  * The DDL lives in ``learning/schema.sql``, which is the source of truth and a
    teaching artefact in its own right. This script only inserts.
  * Sound speed and ``dc/dz`` are computed here with TEOS-10 and stored *beside* the raw
    GLORYS values, so the derivation is auditable rather than trusted.
  * Idempotent: safe to re-run. Primary keys make inserts upserts.
  * ``ON CONFLICT DO NOTHING`` rather than DO UPDATE on purpose -- a re-run should not
    silently change history. To reload deliberately, drop the tables first.

Run:  uv run python scripts/load_db.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ocean_sim.config import OCEAN_BOX
from ocean_sim.data import glorys, ncei, ndbc
from ocean_sim.dsn import dsn

ROOT = Path(__file__).resolve().parent.parent
DSN = dsn()
WIND_STATION = "46092"
ACOUSTIC_SITE = "mb01"
ACOUSTIC_DEPLOYMENTS = ["01", "02", "03", "04", "05", "06", "07"]
SITE_LAT, SITE_LON = 36.70, -122.10

# The acoustic window, set by the deployments above: 2018-11-15 .. 2021-04-23.
# Wind and ocean are clipped to the same range so the join has no dangling edges.
WINDOW_START = "2019-01-01"
WINDOW_END = "2021-05-01"


def apply_schema() -> None:
    sql = (ROOT / "learning" / "schema.sql").read_text()
    with psycopg.connect(DSN, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
    print(f"  schema applied ({len(sql.splitlines())} lines from learning/schema.sql)")


def load_sources() -> None:
    rows = [
        ("glorys12v1", "GLORYS12V1 global ocean reanalysis", "Mercator Ocean International / Copernicus",
         "C", "https://marine.copernicus.eu", "1/12 deg, 50 levels, daily 1993-"),
        ("ndbc_46092", "NDBC moored met-ocean observations, station 46092 (MBM1)", "NOAA NDBC",
         "A", "https://www.ndbc.noaa.gov", "10 km from site; direction sensor complete 2019-2025"),
        ("sanctsound_mb01", "NOAA-Navy SanctSound passive acoustic, site MB01", "NOAA / US Navy",
         "A", "https://www.ncei.noaa.gov/products/passive-acoustic-data",
         "Third-octave hourly band levels, 115.5/116.5 m, 48/96 kHz"),
    ]
    with psycopg.connect(DSN, autocommit=True) as conn:
        with conn.cursor() as cur:
            for r in rows:
                cur.execute(
                    "INSERT INTO source (source_id, name, organisation, access_class,"
                    " retrieval_url, notes) VALUES (%s,%s,%s,%s,%s,%s)"
                    " ON CONFLICT (source_id) DO NOTHING",
                    r,
                )
    print(f"  {len(rows)} sources registered")


def load_ocean() -> int:
    import gsw

    paths = glorys.fetch(
        ["temperature", "salinity", "u_eastward", "v_northward"],
        OCEAN_BOX, f"{WINDOW_START}T00:00:00", f"{WINDOW_END}T00:00:00",
        "data/glorys_db",
    )
    ds = glorys.load(paths, label="db-load")

    t = ds.temperature.mean(dim=["latitude", "longitude"])
    s = ds.salinity.mean(dim=["latitude", "longitude"])
    u = ds.u_eastward.mean(dim=["latitude", "longitude"])
    v = ds.v_northward.mean(dim=["latitude", "longitude"])
    depth = ds.depth.values
    p_dbar = depth * 1.0198  # roughly dbar from metres; fine for this column

    sa = gsw.SA_from_SP(s.values, p_dbar, SITE_LON, SITE_LAT)
    ct = gsw.CT_from_t(sa, t.values, p_dbar)
    c = gsw.sound_speed(sa, ct, p_dbar)
    sigma = gsw.sigma0(sa, ct)
    # axis=1 is required: c is (time, depth) and `depth` is 1-D, so numpy cannot infer
    # which axis the coordinates belong to
    dcdz = np.gradient(c, depth, axis=1)

    times = pd.to_datetime(ds.time.values)
    records = []
    for k, ts in enumerate(times):
        for j, d in enumerate(depth):
            records.append(
                (
                    ts.to_pydatetime(), float(d),
                    float(t.values[k, j]), float(s.values[k, j]),
                    float(u.values[k, j]), float(v.values[k, j]),
                    # gsw returns plain ndarrays here because it was handed .values
                    float(ct[k, j]), float(sa[k, j]),
                    float(c[k, j]), float(dcdz[k, j]), float(sigma[k, j]),
                    1,
                )
            )
    sql = """
        INSERT INTO ocean_profile_daily
        (observed_at, depth_m, raw_temperature_c, raw_salinity_psu,
         u_eastward_ms, v_northward_ms, conservative_temp_c, absolute_salinity_gkg,
         sound_speed_ms, dc_dz_s, potential_density_kgm3, qc_flag)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (observed_at, depth_m) DO NOTHING
    """
    with psycopg.connect(DSN) as conn:
        with conn.cursor() as cur:
            cur.executemany(sql, records)
    return len(records)


def load_wind() -> int:
    frames = []
    for year in (2019, 2020, 2021):
        f = ndbc.load(ndbc.fetch(WIND_STATION, year, "data/ndbc"))
        frames.append(ndbc.daily(f))
    daily = pd.concat(frames).sort_index()
    daily = daily.loc[WINDOW_START:WINDOW_END]

    # hourly direction -> a proper circular mean, never a plain average of degrees
    from ocean_sim.data.ndbc import circular_mean

    dir_mean = (
        ndbc.load(ndbc.fetch(WIND_STATION, 2019, "data/ndbc"))["wdir"]
        .loc[WINDOW_START:WINDOW_END]
        .resample("1D")
        .apply(circular_mean)
    )
    records = [
        (
            idx.to_pydatetime(), WIND_STATION,
            float(r.wind_speed_mean), float(r.wind_gust_max),
            float(dir_mean.get(idx, np.nan)),
            float(r.wind_u_mean), float(r.wind_v_mean), float(r.wind_northward_mean),
            float(r.wave_height_max), float(r.air_temp_mean), float(r.water_temp_mean),
            1,
        )
        for idx, r in daily.iterrows()
        if np.isfinite(r.wind_speed_mean)
    ]
    sql = """
        INSERT INTO wind_daily
        (observed_at, station_id, wind_speed_mean_ms, wind_gust_max_ms,
         wind_direction_deg, wind_u_east_ms, wind_v_north_ms, wind_northward_ms,
         wave_height_max_m, air_temp_mean_c, water_temp_mean_c, qc_flag)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (observed_at, station_id) DO NOTHING
    """
    with psycopg.connect(DSN) as conn:
        with conn.cursor() as cur:
            cur.executemany(sql, records)
    return len(records)


def _band_col(freq: float) -> str:
    """Column name for a third-octave band centre.

    ``round`` rather than ``int``: the ISO centre is 31.5 Hz, and ``int`` truncates to 31
    while the schema column is ``band_32hz``. Note ``round`` is banker's rounding, which
    is fine here -- the only .5 centre in the series is 31.5, and 32 is even.
    """
    return f"band_{round(float(freq))}hz"


def load_acoustic() -> int:
    records = []
    for dep in ACOUSTIC_DEPLOYMENTS:
        try:
            ds = ncei.load_sound_levels(ACOUSTIC_SITE, f"{dep}_tol_1h")
        except FileNotFoundError:
            continue
        freqs = ds.frequency.values
        levels = ds.sound_pressure_levels.values
        times = pd.to_datetime(ds.time.values)
        for k, ts in enumerate(times):
            if not (WINDOW_START <= str(ts.date()) < WINDOW_END):
                continue
            levels_row = {_band_col(f): float(levels[k, j])
                          for j, f in enumerate(freqs)}
            records.append((ts.to_pydatetime(), ACOUSTIC_SITE, 116.5, *levels_row.values(), 1))
    if not records:
        return 0
    keys = [_band_col(f) for f in freqs]

    # Fail loudly here rather than as a SQL syntax error part-way through an insert.
    with psycopg.connect(DSN) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT column_name FROM information_schema.columns"
                " WHERE table_name = 'acoustic_tol_hourly'"
            )
            have = {r[0] for r in cur.fetchall()}
    missing = [k for k in keys if k not in have]
    if missing:
        raise RuntimeError(
            f"schema is missing band columns: {missing}. Add them to "
            f"learning/schema.sql -- the schema is the source of truth, not this script."
        )

    cols = ", ".join(("observed_at", "site_id", "sensor_depth_m", *keys, "qc_flag"))
    ph = ", ".join(["%s"] * (len(keys) + 4))
    sql = (
        f"INSERT INTO acoustic_tol_hourly ({cols}) VALUES ({ph})"
        " ON CONFLICT (observed_at, site_id) DO NOTHING"
    )
    with psycopg.connect(DSN) as conn:
        with conn.cursor() as cur:
            cur.executemany(sql, records)
    return len(records)


def load_detections() -> int:
    sys.path.insert(0, str(ROOT / "scripts"))
    from ml_triviality import load_labels  # reuse, not duplicate

    records = []
    for dep in ACOUSTIC_DEPLOYMENTS:
        labels = load_labels(dep)
        for taxon, s in labels.items():
            is_events = bool((s == 1).all())
            detector = "LTSA analysis" if taxon == "ships" else "PamGuard"
            for ts, v in s.items():
                if WINDOW_START <= str(ts.date()) < WINDOW_END:
                    records.append(
                        (ts.to_pydatetime(), ACOUSTIC_SITE, f"mb01_{dep}", taxon,
                         int(v), detector, is_events)
                    )
    if not records:
        return 0
    sql = """
        INSERT INTO detection_hourly
        (observed_at, site_id, deployment, taxon, presence, detector, is_event_list)
        VALUES (%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (observed_at, site_id, deployment, taxon) DO NOTHING
    """
    with psycopg.connect(DSN) as conn:
        with conn.cursor() as cur:
            cur.executemany(sql, records)
    return len(records)


def main() -> int:
    print(f"DSN: {DSN.split('@')[-1]}")
    print("\napplying schema ...")
    apply_schema()
    print("registering sources ...")
    load_sources()

    print("\nloading ...")
    for name, fn in (
        ("ocean_profile_daily", load_ocean),
        ("wind_daily", load_wind),
        ("acoustic_tol_hourly", load_acoustic),
        ("detection_hourly", load_detections),
    ):
        n = fn()
        print(f"  {name:24} {n:>9,} rows")

    with psycopg.connect(DSN) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT relname, n_live_tup FROM pg_stat_user_tables"
                " WHERE relname IN ('ocean_profile_daily','wind_daily',"
                "'acoustic_tol_hourly','detection_hourly','source') ORDER BY relname"
            )
            print("\n  table                 estimated rows")
            for name, _est in cur.fetchall():
                cur.execute(f"SELECT count(*) FROM {name}")
                print(f"  {name:22} {cur.fetchone()[0]:>9,}")
    print(f"\nwindow: {WINDOW_START} .. {WINDOW_END}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
