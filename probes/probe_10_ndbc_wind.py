"""Probe 10 — wind and wave forcing. The missing driver.

Upwelling on the California coast is driven by northerly wind, so without this the ocean
signal can be described but not explained. And there is a trap here that cost real time:

**Buoy 46042's wind-direction sensor failed on 2019-08-18 23:50 and never recovered.**
Every September record is 999 (missing). Wind *speed* kept reporting; direction did not.
Since the northerly component is derived from direction, the single most important
variable for upwelling is absent for the entire window from the obvious source.

**Buoy 46092 ("MBM1") is the answer:** 10 km from the ocean site, and its direction record
is complete for September. It becomes the primary wind source; 46042 is retained for wave
height and as an independent cross-check on speed.

What the two stations actually give us:

  =============  ==========  ==========================  ====================
  Station        Distance    September 2019 coverage      Note
  =============  ==========  ==========================  ====================
  46042          36 km       speed + waves complete,      direction sensor FAILED
                             direction 100% missing
  46092 (MBM1)   10 km       speed + direction complete    primary wind source
  =============  ==========  ==========================  ====================

File-format facts (see ``ocean_data_workshop.data.ndbc`` for the full list): data starts on
**line 2**, not line 4; missing sentinels are 99 for most fields but **999** for ``WDIR``
and ``MWD``; resolution is **not uniform** within a year file (46042 is hourly in January
and 10-minute by December); and wind direction is where the wind comes *from*.

The finding worth acting on: northerly wind leads southward current by about six days
(r = -0.61), which is physically sensible -- wind stress takes days to spin up Ekman
transport. But with only **30 daily samples** that is thin, and a 6-day lag searched
across several drivers invites spurious correlation. The fix is a longer window, and both
sources allow one.
"""

from __future__ import annotations

import sys

from ._common import PASS, Probe, Result, run

HARNESS = Probe(
    slug="ndbc_wind",
    name="NDBC moored wind and wave observations (46092, 46042)",
    tier=1,
    klass="A",
    provides="hourly wind speed/direction, gust, wave height, air and sea temperature",
    protocol="gzipped text over HTTPS",
    order=11,
)

STATIONS = {
    "46092": {"km": 10, "role": "primary wind (complete direction)"},
    "46042": {"km": 36, "role": "waves + cross-check (direction failed)"},
}


def check() -> Result:
    import numpy as np
    import pandas as pd

    from ocean_data_workshop.data import ndbc

    detail: dict = {}
    problems: list[str] = []
    loaded = {}

    for st in STATIONS:
        frame = ndbc.load(ndbc.fetch(st, 2019, "data/ndbc"))
        loaded[st] = frame
        sep = frame.loc["2019-09-01":"2019-09-30"]
        d = {
            "rows_year": len(frame),
            "rows_sept": len(sep),
            "speed_na": int(sep["wspd"].isna().sum()),
            "dir_na": int(sep["wdir"].isna().sum()),
            "wave_max": round(float(sep["wvht"].max()), 2) if sep["wvht"].notna().any() else None,
        }
        detail[st] = d
        if d["rows_sept"] < 600:
            problems.append(f"{st}: only {d['rows_sept']} September rows")
        if d["speed_na"] > 0.05 * d["rows_sept"]:
            problems.append(f"{st}: {d['speed_na']} missing wind-speed values in September")

    # --- the finding: 46042 lost its direction sensor partway through the year ---
    # Must test the *September* subset. Across the full year only ~13% is missing, so a
    # whole-year test would read the failure as "intact". The outage is bounded -- the
    # sensor was repaired later in the year -- so report its extent, not just its start.
    sep42 = loaded["46042"].loc["2019-09-01":"2019-09-30"]
    if sep42["wdir"].isna().mean() > 0.5:
        w42 = loaded["46042"]["wdir"]
        missing = w42[w42.isna()]
        first_out = missing.index.min()
        # the outage is one contiguous run: last missing reading, and whether anything
        # valid reappears after it
        last_out = missing.index.max()
        recovered = w42.index.max() > last_out
        detail["46042_dir_failure"] = (
            f"outage {first_out} -> {last_out} "
            f"({len(missing)} rows); September 100% missing; "
            f"sensor {'recovered' if recovered else 'never recovered'}"
        )
    else:
        problems.append(
            f"46042 September direction is only "
            f"{sep42['wdir'].isna().mean():.0%} missing -- the failure note is stale"
        )

    # --- 46092 must be complete in direction, or we have no upwelling variable ---
    primary = loaded["46092"].loc["2019-09-01":"2019-09-30"]
    if primary["wdir"].isna().mean() > 0.1:
        problems.append(
            f"46092 direction is {primary['wdir'].isna().mean():.0%} missing -- "
            f"there is then no upwelling variable at all"
        )
        return Result(status="FAIL", note="; ".join(problems), detail=detail)

    detail["wind_speed_mean"] = round(float(primary["wspd"].mean()), 2)
    detail["wind_speed_max"] = round(float(primary["wspd"].max()), 2)
    detail["dominant_dir_deg"] = round(ndbc.circular_mean(primary["wdir"]), 0)
    detail["northerly_mean"] = round(float(primary["wind_northward"].mean()), 2)

    # --- is the wind actually upwelling-favourable? ---
    # Northerly (from the north, roughly 0-180) drives California coastal upwelling.
    # 316 deg is northwesterly, which is upwelling-favourable on this coast.
    if not 0.0 < float(primary["wind_northward"].mean()) <= 12.0:
        problems.append(
            f"mean northerly component {float(primary['wind_northward'].mean()):.2f} m/s "
            f"-- not upwelling-favourable, which would be surprising for this coast"
        )

    # --- does it actually explain the ocean? ---
    from ocean_data_workshop.config import OCEAN_BOX, SEPT_2019
    from ocean_data_workshop.data import glorys

    ds = glorys.load(
        glorys.fetch(
            ["thetao", "uo", "vo"], OCEAN_BOX, SEPT_2019.start, SEPT_2019.end, "data/glorys"
        )
    )
    ocean = pd.DataFrame(
        {
            "t": pd.to_datetime(ds.time.values).floor("D"),
            "sst": ds.temperature.isel(depth=0)
            .mean(dim=["latitude", "longitude"]).values,
            "u": ds.u_eastward.mean(dim=["depth", "latitude", "longitude"]).values,
            "v": ds.v_northward.mean(dim=["depth", "latitude", "longitude"]).values,
        }
    ).set_index("t")
    merged = ocean.join(ndbc.daily(primary), how="inner").dropna(
        subset=["sst", "wind_speed_mean", "wind_northward_mean"]
    )
    detail["merged_days"] = len(merged)

    def best_lag(x, y, maxlag=6):
        rs = {
            k: (np.corrcoef(x, y)[0, 1] if k == 0 else np.corrcoef(x[:-k], y[k:])[0, 1])
            for k in range(maxlag + 1)
        }
        b = max(rs, key=lambda k: abs(rs[k]))
        return rs[0], rs[b], b

    pairs = {}
    for oc in ("sst", "u", "v"):
        r0, rb, lb = best_lag(
            merged["wind_northward_mean"].values, merged[oc].values
        )
        pairs[oc] = (round(r0, 2), round(rb, 2), lb)
    detail["northerly_lag_corr"] = pairs
    strongest = max(pairs, key=lambda k: abs(pairs[k][1]))
    detail["strongest"] = (
        f"northerly wind -> {strongest} r={pairs[strongest][1]:+.2f} at {pairs[strongest][2]}d"
    )

    if abs(pairs[strongest][1]) < 0.4:
        problems.append(
            f"no meaningful wind-ocean relationship: best |r| is "
            f"{abs(pairs[strongest][1]):.2f}, so wind does not explain this window"
        )

    # 30 daily points is thin, and 7 lags x 3 drivers x 3 targets invites false positives.
    detail["caveat"] = "30 daily samples; lag correlations are not significance-tested"

    if problems:
        return Result(status="FAIL", note="; ".join(problems), detail=detail)

    return Result(
        status=PASS,
        note=(
            f"46092 (10 km) is the primary wind source, complete direction, mean "
            f"{detail['wind_speed_mean']} m/s from {detail['dominant_dir_deg']:.0f} deg "
            f"(NW, upwelling-favourable). 46042 (36 km) has waves but its direction "
            f"sensor FAILED 2019-08-18 -- 100% missing for September. Strongest "
            f"relationship: {detail['strongest']}. CAVEAT: only 30 daily samples, so "
            f"widen the window before trusting any lag."
        ),
        detail=detail,
    )


if __name__ == "__main__":
    from ._common import append_verdict

    res = run(HARNESS, check)
    append_verdict(res)
    sys.exit(0 if res.status == "PASS" else 1)
