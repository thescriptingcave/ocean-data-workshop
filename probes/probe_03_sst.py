"""Probe 03 — real SST time series at Monterey Bay via ERDDAP.

First probe that fetches actual ocean data, and the first rung of the fallback ladder.
Purpose: prove we can pull a month of real values for our site and that they are
physically plausible. A plausible number at the right location in the right month is
already a strong signal -- ~16 C off central California in September is characteristic
of coastal upwelling, not a broken download.
"""

from __future__ import annotations

import io

import pandas as pd

from ._common import PASS, SITE, Probe, Result, cache_path, http_session, run

HARNESS = Probe(
    slug="sst_erddap",
    name="Sea surface temperature at Monterey Bay via ERDDAP (jplMURSST41)",
    tier=1,
    klass="A",
    provides="daily analysed SST, 0.045 deg, 2002-present",
    protocol="REST griddap -> CSV -> netCDF",
    order=3,
)

BASE = "https://coastwatch.pfeg.noaa.gov/erddap/griddap/jplMURSST41"
DS = "jplMURSST41"

# A probe must be TINY. The full site bbox is 2.5 deg square, which at 0.045 deg is
# ~90,000 cells per day and made the netCDF route hang. A tight box around the site
# point is enough to prove the route works and finishes instantly.
TINY_BOX = (
    SITE["lat"] - 0.1,
    SITE["lon"] - 0.1,
    SITE["lat"] + 0.1,
    SITE["lon"] + 0.1,
)


def _query(fmt: str = "csv") -> str:
    lat0, lon0, lat1, lon1 = TINY_BOX
    return (
        f"{BASE}.{fmt}?analysed_sst"
        f"%5B(2019-09-01T00:00:00Z):(2019-09-30T00:00:00Z)%5D"
        f"%5B({lat0}):({lat1})%5D%5B({lon0}):({lon1})%5D"
        + ("&.time=last&.lat=first&.lon=first" if fmt == "csv" else "")
    )


HTTP = http_session()


def check() -> Result:
    import xarray as xr

    detail: dict = {}
    problems: list[str] = []

    # --- CSV route: readable, small, enough for a sanity check ---
    r = HTTP.get(_query("csv"), timeout=HTTP.request_timeout)
    detail["csv_http"] = r.status_code
    if r.status_code != 200 or not r.text.startswith("time"):
        return Result(status="FAIL", note=f"CSV query returned {r.status_code}")
    detail["csv_kb"] = round(len(r.content) / 1024, 1)

    # ERDDAP CSV has TWO header rows: names, then units (UTC, degrees_north, ...).
    # pandas reads the units row as data, so skip it explicitly.
    df = pd.read_csv(io.StringIO(r.text), skiprows=[1])
    df["time"] = pd.to_datetime(df["time"].str.replace("Z", "", regex=False), utc=True)
    sst = df["analysed_sst"].astype(float)
    # _FillValue in ERDDAP is often -999 or NaN; drop non-physical values
    sst = sst.where(sst > -1.0)
    sst_clean = sst.dropna()

    detail.update(
        rows=len(df),
        valid=int(sst_clean.size),
        span_days=int(df["time"].dt.date.nunique()),
    )
    if sst_clean.empty:
        return Result(status="FAIL", note="every value came back as fill", detail=detail)

    detail.update(
        sst_min=round(float(sst_clean.min()), 2),
        sst_max=round(float(sst_clean.max()), 2),
        sst_mean=round(float(sst_clean.mean()), 2),
    )

    # --- physical plausibility for an upwelling coast in September ---
    if not 8.0 < float(sst_clean.mean()) < 22.0:
        problems.append(
            f"mean SST {float(sst_clean.mean()):.1f} C implausible for Monterey in Sept"
        )
    if not 1.0 < float(sst_clean.max() - sst_clean.min()) < 15.0:
        problems.append(
            f"SST range {float(sst_clean.max() - sst_clean.min()):.1f} C implausible"
        )
    if df["time"].dt.date.nunique() < 25:
        problems.append(f"only {df['time'].dt.date.nunique()} distinct days returned")

    # --- netCDF route: what the project will actually use ---
    cp = cache_path("jplMURSST41_monterey_201909.nc", ".nc")
    if not cp.exists():
        r2 = HTTP.get(_query("nc"), timeout=HTTP.request_timeout)
        if r2.status_code != 200:
            problems.append(f"netCDF query returned {r2.status_code}")
        else:
            cp.write_bytes(r2.content)
    detail["nc_kb"] = round(cp.stat().st_size / 1024, 1)
    try:
        ds = xr.open_dataset(cp)
        detail["nc_vars"] = ",".join(list(ds.data_vars)[:4])
        detail["nc_dims"] = ",".join(
            f"{k}={v}" for k, v in ds.sizes.items()
        )
        # Coordinates are stored as float32, so ERDDAP can return a grid centre a
        # few millionths of a degree outside the requested box. Use a tolerance.
        lat0, _, lat1, _ = TINY_BOX
        tol = 0.01
        if not (
            lat0 - tol <= float(ds.latitude.min())
            and float(ds.latitude.max()) <= lat1 + tol
        ):
            problems.append(
                f"netCDF latitude outside requested box: "
                f"{float(ds.latitude.min()):.4f}..{float(ds.latitude.max()):.4f}"
            )
        detail["lat_span"] = f"{float(ds.latitude.min()):.3f}..{float(ds.latitude.max()):.3f}"
        if "time" not in ds.coords and "time" not in ds.dims:
            problems.append("netCDF has no time coordinate")
        ds.close()
    except Exception as exc:
        problems.append(f"netCDF unreadable: {type(exc).__name__}: {exc}")

    if problems:
        return Result(status="FAIL", note="; ".join(problems), detail=detail)

    return Result(
        status=PASS,
        note=(
            f"real Monterey SST, {detail['span_days']} days in Sept 2019, "
            f"{detail['sst_min']}-{detail['sst_max']} C (mean {detail['sst_mean']}). "
            f"CSV and netCDF routes both work. Upwelling-consistent values."
        ),
        detail=detail,
    )


if __name__ == "__main__":
    import sys

    from ._common import append_verdict

    res = run(HARNESS, check)
    append_verdict(res)
    sys.exit(0 if res.status == "PASS" else 1)
