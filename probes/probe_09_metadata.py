"""Probe 09 — SanctSound metadata index: which hydrophone is near our ocean site?

A *catalogue* rather than data, and the cheapest high-value fetch in the whole project.
The bucket contains ``big_query_metadata/`` with a row-per-file index of the entire
SanctSound collection -- 25,503 rows carrying coordinates, sensor depth, sample rate and
dates. That answers "which mooring is near Monterey, and what can it record?" without
walking the bucket tree by hand, which is how the anchor site got decided by evidence
rather than by my guesswork.

What it settled:

  * Anchor site 36.798 N, 121.976 W -- **16 km from the GLORYS ocean site**, moored at
    116.5 m and recording at **96 kHz**.
  * 96 kHz matters: bottlenose dolphin clicks peak at 30-50 kHz, so a 48 kHz hydrophone
    clips the top of that band off. The plan assumed 48 kHz.
  * 116.5 m depth means a deep mooring, so the sound-channel / ducting analysis has real
    structure rather than a shallow surface duct.
  * The index spans **Apr-Sep 2019**, which overlaps the GLORYS month but does not
    extend beyond it.

The second site (36.650 N, 121.908 W, 64.5 m, 48 kHz) is the fallback: shallower, and
its top band is cut off.
"""

from __future__ import annotations

import sys

from ._common import PASS, Probe, Result, cache_path, http_session, run

HARNESS = Probe(
    slug="ncei_metadata",
    name="SanctSound file-level metadata index (site catalogue)",
    tier=1,
    klass="A",
    provides="coordinates, sensor depth, sample rate, dates for 25,503 recording files",
    protocol="GCS JSON API -> CSV",
    order=10,
)

BUCKET = "https://storage.googleapis.com/noaa-passive-bioacoustic/big_query_metadata/"
CSV = "NCEI_SANCTSOUND_PAD_metadata.csv"

# the ocean site we are working with
OCEAN_SITE = (36.70, -122.10)
NEAR_KM = 60.0  # "close enough to describe the same water mass"
EARTH_R_KM = 6371.0

HTTP = http_session()


def check() -> Result:
    import numpy as np
    import pandas as pd

    detail: dict = {}
    problems: list[str] = []

    cp = cache_path(CSV, ".csv")
    if not cp.exists() or cp.stat().st_size == 0:
        r = HTTP.get(BUCKET + CSV, timeout=(30, 600))
        if r.status_code != 200:
            return Result(
                status="FAIL", note=f"metadata CSV returned HTTP {r.status_code}"
            )
        cp.write_bytes(r.content)
    detail["mb"] = round(cp.stat().st_size / 1024 / 1024, 1)

    df = pd.read_csv(cp, low_memory=False)
    detail["rows"] = len(df)
    detail["cols"] = len(df.columns)

    need = {"LAT", "LON", "SENSOR_DEPTH", "SAMPLE_RATE_Hz", "FILE_NAME"}
    missing = need - set(df.columns)
    if missing:
        return Result(
            status="FAIL", note=f"index missing columns: {sorted(missing)}", detail=detail
        )

    # --- what is in the collection overall ---
    detail["lat_range"] = f"{df.LAT.min():.1f}..{df.LAT.max():.1f}"
    detail["lon_range"] = f"{df.LON.min():.1f}..{df.LON.max():.1f}"
    rates = sorted(df.SAMPLE_RATE_Hz.dropna().unique())
    detail["sample_rates_hz"] = ",".join(str(int(r)) for r in rates)
    detail["depth_range_m"] = f"{df.SENSOR_DEPTH.min():.0f}..{df.SENSOR_DEPTH.max():.0f}"
    detail["date_range"] = f"{df.START_DATE.min()} .. {df.START_DATE.max()}"

    # --- distance to the ocean site (haversine) ---
    lat0 = np.radians(OCEAN_SITE[0])
    dlat = np.radians(df.LAT - OCEAN_SITE[0])
    dlon = np.radians(df.LON - OCEAN_SITE[1])
    a = np.sin(dlat / 2) ** 2 + np.cos(lat0) * np.cos(np.radians(df.LAT)) * np.sin(
        dlon / 2
    ) ** 2
    df = df.assign(km=2 * EARTH_R_KM * np.arcsin(np.sqrt(a)))

    sites = (
        df.groupby(["LAT", "LON"])
        .agg(km=("km", "first"), depth=("SENSOR_DEPTH", "max"),
             fs=("SAMPLE_RATE_Hz", "max"), n=("FILE_NAME", "count"))
        .reset_index()
        .sort_values("km")
    )
    near = sites[sites.km < NEAR_KM]
    detail["n_sites"] = len(sites)
    detail["sites_within_km"] = len(near)
    if near.empty:
        return Result(
            status="FAIL",
            note=f"no SanctSound site within {NEAR_KM:.0f} km of the ocean site -- "
            f"the acoustic anchor has to move",
            detail=detail,
        )

    detail["nearby_sites"] = "; ".join(
        f"{r.LAT:.3f}/{r.LON:.3f}@{r.km:.0f}km/{r.depth:.0f}m/{int(r.fs)}Hz"
        for _, r in near.head(4).iterrows()
    )

    # --- the anchor must be able to record what we care about ---
    anchor = near.iloc[0]
    detail["anchor"] = (
        f"{anchor.LAT:.3f}N {anchor.LON:.3f}E, {anchor.km:.0f} km, "
        f"{anchor.depth:.0f} m, {int(anchor.fs)} Hz, {int(anchor.n)} files"
    )
    if int(anchor.fs) < 96000:
        problems.append(
            f"anchor records at {int(anchor.fs)} Hz -- dolphin clicks peak at "
            f"30-50 kHz, so this clips the band we most want"
        )
    if anchor.depth < 80:
        problems.append(
            f"anchor moored at {anchor.depth:.0f} m -- too shallow for a real sound "
            f"channel, the ducting analysis would be trivial"
        )

    if problems:
        return Result(status="FAIL", note="; ".join(problems), detail=detail)

    return Result(
        status=PASS,
        note=(
            f"{len(df)} files catalogued. ANCHOR: {detail['anchor']}. "
            f"96 kHz captures the dolphin click band; 116 m depth gives a real sound "
            f"channel. Both sit in the same upwelling system as the GLORYS site, so "
            f"ocean and acoustic records describe the same water mass. "
            f"NOTE: index covers {detail['date_range']} only."
        ),
        detail=detail,
    )


if __name__ == "__main__":
    from ._common import append_verdict

    res = run(HARNESS, check)
    append_verdict(res)
    sys.exit(0 if res.status == "PASS" else 1)
