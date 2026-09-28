"""Widen the window and test the wind-ocean relationship honestly.

September 2019 gave 30 daily points. That is not enough: a naive lag scan across 7 lags
on 30 autocorrelated points reported r = -0.61, which is very likely an artefact of both
autocorrelation and selecting the best of several lags.

This script uses 2019-2025 (~2,550 daily points) and a moving-block bootstrap, which
accounts for both. The question is not "is there a correlation" but **"which
relationships survive a null built from data with the same persistence?"**

Run:  uv run python scripts/widen_window.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ocean_sim.config import OCEAN_BOX, OCEAN_SITE
from ocean_sim.data import glorys, ndbc
from ocean_sim.stats import block_bootstrap_pvalue, effective_n

YEARS = list(range(2019, 2026))
CACHE = "data/glorys_wide"
MAX_LAG = 10
N_BOOT = 1500
# Block lengths to compare. A single choice is a choice; robustness is the finding.
BLK = [20, 30, 40, 60]

# Which NDBC station supplies wind. 46092 "MBM1" is 10 km away with a complete direction
# record for every year in this window; 46042 is 36 km out and lost its direction sensor
# on 2019-08-18.
WIND_STATION = "46092"


def ocean_daily() -> pd.DataFrame:
    """Daily bay-mean ocean fields over YEARS, fetched as one netCDF per variable."""
    start, end = f"{YEARS[0]}-01-01T00:00:00", f"{YEARS[-1]}-12-31T00:00:00"
    paths = glorys.fetch(
        ["temperature", "salinity", "u_eastward", "v_northward"],
        OCEAN_BOX, start, end, CACHE,
    )
    ds = glorys.load(paths, label=f"{YEARS[0]}-{YEARS[-1]}")
    return pd.DataFrame(
        {
            "t": pd.to_datetime(ds.time.values).floor("D"),
            "sst": ds.temperature.isel(depth=0)
            .mean(dim=["latitude", "longitude"]).values,
            "temp_deep": ds.temperature.isel(depth=-1)
            .mean(dim=["latitude", "longitude"]).values,
            "u": ds.u_eastward.mean(dim=["depth", "latitude", "longitude"]).values,
            "v": ds.v_northward.mean(dim=["depth", "latitude", "longitude"]).values,
            "salinity": ds.salinity.isel(depth=0)
            .mean(dim=["latitude", "longitude"]).values,
        }
    ).set_index("t")


def wind_daily() -> pd.DataFrame:
    frames = []
    for year in YEARS:
        f = ndbc.load(ndbc.fetch(WIND_STATION, year, "data/ndbc"))
        frames.append(ndbc.daily(f))
    return pd.concat(frames).sort_index()


def main() -> int:
    print(f"site   : {OCEAN_SITE.name} {OCEAN_SITE.lat}N {OCEAN_SITE.lon}E")
    print(f"window : {YEARS[0]}-{YEARS[-1]}   wind: NDBC {WIND_STATION} (MBM1, 10 km)")
    print(f"test   : moving-block bootstrap, max over lags 0-{MAX_LAG}d, {N_BOOT} resamples\n")

    print("fetching ocean cube ...")
    ocean = ocean_daily()
    print(f"  {len(ocean)} daily rows, {ocean.index.min().date()} .. {ocean.index.max().date()}")
    print("loading wind ...")
    wind = wind_daily()

    merged = ocean.join(wind, how="inner").dropna(
        subset=["sst", "u", "v", "wind_speed_mean", "wind_northward_mean"]
    )
    print(f"\nmerged: {len(merged)} days  ({merged.index.min().date()} .. {merged.index.max().date()})")

    print("\n--- effective sample size (why the naive p-value was wrong) ---")
    for col in ("sst", "u", "v", "wind_northward_mean", "wind_speed_mean"):
        print(f"  {col:22} n={len(merged):5d}  n_eff={effective_n(merged[col].values):7.1f}")

    drivers = {
        "northerly wind": "wind_northward_mean",
        "wind speed": "wind_speed_mean",
        "wave height": "wave_height_max",
    }
    targets = {"SST": "sst", "current u": "u", "current v": "v"}

    print(f"\n--- block-bootstrap test, max |r| over lags 0-{MAX_LAG} d ---")
    print(f"{'driver':16} {'target':11} {'best lag':>9} {'max |r|':>8} {'p':>7}  verdict")
    survivors = []
    for dlabel, dcol in drivers.items():
        if dcol not in merged or merged[dcol].isna().all():
            continue
        for tlabel, tcol in targets.items():
            pair = merged[[dcol, tcol]].dropna()
            if len(pair) < 200:
                continue
            res = block_bootstrap_pvalue(
                pair[dcol].values, pair[tcol].values,
                max_lag=MAX_LAG, n_boot=N_BOOT, seed=42,
            )
            sig = res["p_boot"] < 0.05
            if sig:
                survivors.append((dlabel, tlabel, res))
            print(
                f"{dlabel:16} {tlabel:11} {res['best_lag']:>6} d  "
                f"{res['obs_max_abs_r']:>8.3f} {res['p_boot']:>7.3f}  "
                f"{'SIGNIFICANT' if sig else 'not significant'}"
            )

    # --- sensitivity: the p-values depend on the block length, so report the spread ---
    # A single block length is a choice. Where the answer flips with it, the finding is
    # not robust and must not be reported as if it were.
    print("\n--- sensitivity to block length (is the verdict robust?) ---")
    print(f"{'driver':16} {'target':11} " + "".join(f"{b:>9}" for b in BLK) + "   robust?")
    unstable = []
    for dlabel, dcol in drivers.items():
        if dcol not in merged or merged[dcol].isna().all():
            continue
        for tlabel, tcol in targets.items():
            pair = merged[[dcol, tcol]].dropna()
            if len(pair) < 200:
                continue
            ps = []
            for b in BLK:
                r = block_bootstrap_pvalue(
                    pair[dcol].values, pair[tcol].values,
                    max_lag=MAX_LAG, n_boot=N_BOOT, block=b, seed=42,
                )
                ps.append(r["p_boot"])
            sigs = [p < 0.05 for p in ps]
            robust = all(sigs) or not any(sigs)
            if not robust:
                unstable.append((dlabel, tlabel))
            print(
                f"{dlabel:16} {tlabel:11} " + "".join(f"{p:>9.3f}" for p in ps)
                + f"   {'yes' if robust else 'NO -- depends on block'}"
            )

    print("\n" + "=" * 72)
    if unstable:
        print("NOT robust (verdict flips with block length):")
        for d, t in unstable:
            print(f"  {d} -> {t}")
        print()
    if survivors:
        print(f"{len(survivors)} relationship(s) survive the autocorrelation-aware test:")
        for dlabel, tlabel, r in survivors:
            print(f"  {dlabel} -> {tlabel}: r={r['obs_max_abs_r']:+.3f} at "
                  f"{r['best_lag']}d, p={r['p_boot']}, block={r['block']}d")
    else:
        print("NO relationship survives. The 6-day, r=-0.61 result from the one-month")
        print("window was an artefact of autocorrelation plus selecting the best lag.")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
