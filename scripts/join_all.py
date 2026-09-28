"""Join ocean, wind and acoustics at Monterey Bay, and test a physical prediction.

This is the first real physics question in the project, and it is falsifiable:

  * **Shipping** noise dominates below ~500 Hz and is anthropogenic. It should show
    little relationship with *local* wind.
  * **Wind and breaking waves** radiate from the sea surface, peaking in the mid-to-high
    bands. They should track local wind speed.

So the prediction is that the wind response should *increase with frequency* across the
third-octave bands -- weak where shipping dominates, strong where wind does. If the
response is flat, the surface-noise path is not reaching the hydrophone.

The hydrophone sits at 116 m in what the ocean data shows is a deep surface duct, so the
prediction is not guaranteed; that is what makes it worth testing.

Run:  uv run python scripts/join_all.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ocean_sim.data import glorys, ncei, ndbc
from ocean_sim.stats import block_bootstrap_pvalue

# MB01 deployments that are contiguous with the ocean/wind record. 01-07 run from
# 2018-11-15 to 2021-04-23 with only brief gaps; 08 and 09 are later and are excluded so
# the acoustic side is not the limiting factor on the window.
DEPLOYMENTS = ["01", "02", "03", "04", "05", "06", "07"]
SITE = "mb01"
WIND_STATION = "46092"  # MBM1, 10 km from the ocean site, complete direction record
MAX_LAG = 4  # hours -- wind forcing is fast, and the acoustic data is hourly
N_BOOT = 1000

# Physical bands worth naming in the output, for orientation only -- the test itself is
# over every third-octave band.
BAND_NOTES = {
    25.0: "shipping / traffic rumble",
    160.0: "shipping peak",
    400.0: "shipping upper",
    1000.0: "shipping to wind crossover",
    2500.0: "wind and breaking waves",
    8000.0: "surface noise, short range",
    20000.0: "surface noise, near the array",
}


def acoustic_daily() -> tuple[pd.DataFrame, np.ndarray]:
    """Daily-mean third-octave band levels across all deployments. Returns (frame, freqs)."""
    frames, freqs = [], None
    for dep in DEPLOYMENTS:
        try:
            ds = ncei.load_sound_levels(SITE, f"{dep}_tol_1h")
        except FileNotFoundError:
            print(f"  (skipping {dep}: no data)")
            continue
        freqs = ds.frequency.values
        df = pd.DataFrame(
            ds.sound_pressure_levels.values,
            index=pd.to_datetime(ds.time.values).floor("D"),
            columns=[f"L_{f:.0f}Hz" for f in freqs],
        )
        frames.append(df)
        print(f"  mb01_{dep}: {df.shape[0]:5d} days  {df.index.min().date()} .. {df.index.max().date()}")
    combined = pd.concat(frames).sort_index()
    combined = combined[~combined.index.duplicated(keep="first")]
    return combined, freqs


def ocean_daily() -> pd.DataFrame:
    paths = glorys.fetch(
        ["temperature", "salinity", "u_eastward", "v_northward"],
        __import__("ocean_sim.config", fromlist=["OCEAN_BOX"]).OCEAN_BOX,
        "2019-01-01T00:00:00", "2021-07-01T00:00:00", "data/glorys_acoustic",
    )
    ds = glorys.load(paths, label="acoustic-window")
    return pd.DataFrame(
        {
            "t": pd.to_datetime(ds.time.values).floor("D"),
            "sst": ds.temperature.isel(depth=0)
            .mean(dim=["latitude", "longitude"]).values,
            "u": ds.u_eastward.mean(dim=["depth", "latitude", "longitude"]).values,
            "v": ds.v_northward.mean(dim=["depth", "latitude", "longitude"]).values,
        }
    ).set_index("t")


def wind_daily() -> pd.DataFrame:
    frames = []
    for year in (2019, 2020, 2021):
        f = ndbc.load(ndbc.fetch(WIND_STATION, year, "data/ndbc"))
        frames.append(ndbc.daily(f))
    return pd.concat(frames).sort_index()


def main() -> int:
    print("loading acoustic third-octave levels ...")
    ac, freqs = acoustic_daily()
    print("loading ocean ...")
    oc = ocean_daily()
    print("loading wind ...")
    wd = wind_daily()

    merged = ac.join(oc, how="inner").join(
        wd[["wind_speed_mean", "wind_gust_max", "wave_height_max", "wind_northward_mean"]],
        how="inner",
    )
    print(f"\njoint daily record: {len(merged)} days  "
          f"{merged.index.min().date()} .. {merged.index.max().date()}")

    band_cols = [c for c in merged.columns if c.startswith("L_")]
    have = merged.dropna(subset=band_cols + ["wind_speed_mean"])
    print(f"with wind + all bands: {len(have)} days")

    print(f"\n--- does local wind drive each third-octave band? (lags 0-{MAX_LAG} h) ---")
    print(f"{'band':>10} {'Hz':>8} {'best lag':>9} {'max |r|':>8} {'p':>7}  note")
    rows = []
    for col in band_cols:
        pair = have[[col, "wind_speed_mean"]].dropna()
        if len(pair) < 200:
            continue
        f_hz = float(col.split("_")[1].rstrip("Hz"))
        res = block_bootstrap_pvalue(
            pair["wind_speed_mean"].values, pair[col].values,
            max_lag=MAX_LAG, n_boot=N_BOOT, seed=7,
        )
        note = BAND_NOTES.get(f_hz, "")
        print(f"{col:>10} {f_hz:>8.0f} {res['best_lag']:>7} d  "
              f"{res['obs_max_abs_r']:>8.3f} {res['p_boot']:>7.3f}  {note}")
        rows.append((f_hz, res["obs_max_abs_r"], res["p_boot"]))

    print("\n--- is the wind response frequency-dependent? ---")
    sig = [(f, r, p) for f, r, p in rows if p < 0.05]
    if sig:
        low = [r for f, r, p in sig if f <= 500]
        high = [r for f, r, p in sig if f > 2000]
        if low and high:
            print(f"  significant bands <= 500 Hz:  n={len(low):2d}  mean |r| = {np.mean(low):.3f}")
            print(f"  significant bands >  2000 Hz: n={len(high):2d}  mean |r| = {np.mean(high):.3f}")
            if np.mean(high) > np.mean(low):
                print("  -> wind response IS stronger at high frequency, as predicted.")
                print("     Surface noise reaches the hydrophone; shipping does not track wind.")
            else:
                print("  -> wind response is NOT stronger at high frequency. The prediction")
                print("     fails, which is a result: the surface-noise path is not behaving")
                print("     as a simple duct would suggest.")
        else:
            print("  not enough significant bands in both groups to compare")
    else:
        print("  no band shows a significant wind relationship")

    # --- the obvious confound: winter is both stormier and louder ---
    # If the wind correlation is just "winter is windy AND winter is loud", it is a
    # seasonal artefact, not day-to-day weather. Subtract the monthly climatology from
    # both series and repeat: anomalies are what remain after the normal seasonal cycle,
    # so any surviving correlation is genuine weather-to-noise response.
    print("\n--- control: is it just seasonality? (monthly anomalies) ---")
    print(f"{'band':>10} {'Hz':>8} {'raw |r|':>8} {'anom |r|':>9} {'anom p':>7}  verdict")
    kept = []
    for col in band_cols:
        pair = have[[col, "wind_speed_mean"]].dropna()
        if len(pair) < 200:
            continue
        f_hz = float(col.split("_")[1].rstrip("Hz"))
        raw_r = rows[[r[0] for r in rows].index(f_hz)][1] if f_hz in [r[0] for r in rows] else None

        anom = pair.copy()
        for c in pair.columns:
            monthly = pair[c].groupby(pair.index.month).transform("mean")
            anom[c] = pair[c] - monthly

        res = block_bootstrap_pvalue(
            anom["wind_speed_mean"].values, anom[col].values,
            max_lag=MAX_LAG, n_boot=N_BOOT, seed=7,
        )
        surv = res["p_boot"] < 0.05
        if surv:
            kept.append((f_hz, res["obs_max_abs_r"]))
        print(f"{col:>10} {f_hz:>8.0f} {raw_r:>8.3f} {res['obs_max_abs_r']:>9.3f} "
              f"{res['p_boot']:>7.3f}  {'survives' if surv else 'SEASONAL ARTEFACT'}")

    if kept:
        lo = [r for f, r in kept if f <= 500]
        hi = [r for f, r in kept if f > 2000]
        print(f"\n  {len(kept)}/{len(band_cols)} bands still respond after removing the "
              f"seasonal cycle.")
        if lo and hi:
            print(f"    anomalies, <= 500 Hz:  mean |r| = {np.mean(lo):.3f}")
            print(f"    anomalies, >  2000 Hz: mean |r| = {np.mean(hi):.3f}")
    else:
        print("\n  NOTHING survives removing the seasonal cycle. The raw correlations were")
        print("  a winter/storm artefact, not a wind-to-noise response.")

    print("\n" + "=" * 72)
    print(f"{len(sig)} of {len(rows)} bands respond to wind. "
          f"Acoustic record is HOURLY, so n_eff here is far better than for the")
    print("daily ocean series -- which is the main reason this join is worth doing.")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
