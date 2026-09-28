"""Probe 08 — GLORYS12V1 via Copernicus Marine. The only Class C dataset.

This is the sole friction-gated source in the plan: it needs a free account. It matters
because nothing else probed supplies **currents** or a full 4D field -- ERDDAP gives
surface temperature only, and Argo gives profiles but no velocity.

Credentials come from ``.env`` (``COPERNICUSUSERNAME`` / ``COPERNICUSPASSWORD``) and
``copernicusmarine login`` caches them to ``~/.copernicusmarine/`` -- outside the repo.
Nothing credential-bearing is written here.

Catalogue facts that cost time to establish:

  * Product is ``GLOBAL_MULTIYEAR_PHY_001_030`` ("Global Ocean Physics Reanalysis"),
    which *is* GLORYS12V1: 1/12 deg (0.0833), 50 levels, daily, 1993-present.
  * Datasets: ``..._P1D-m`` (daily), ``..._P1M-m`` (monthly), ``..._climatology_P1M-m``,
    ``..._static``. Use ``P1D-m`` for daily, ``P1M-m`` for monthly.
  * ``copernicusmarine describe`` with no filter downloads a **170 MB** catalogue. Always
    pass ``--contains`` or ``--product-id``.
  * The CLI is ``--end-datetime``, not ``--stop-datetime``, and ``--file-format`` /
    ``--overwrite``, not ``--output-format`` / ``--overwrite-existing``.
  * The catalogue advertises 0 data variables; they are discovered from the netCDF.

What the data actually shows at our site, September 2019: a thermocline at ~13.5 m,
16.4 C at the surface over 10.9 C at 56 m. That is correct upwelling-season structure for
central California and it means the ducting work has something real to chew on.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from ._common import PROJECT, PASS, Probe, Result, run

HARNESS = Probe(
    slug="glorys",
    name="GLORYS12V1 global ocean reanalysis (Copernicus Marine)",
    tier=1,
    klass="C",
    provides="daily T/S/currents/SSH, 1/12 deg, 50 levels, 1993-present",
    protocol="copernicusmarine subset -> netCDF",
    setup="free account + `copernicusmarine login`",
    order=9,
)

DATASET = "cmems_mod_glo_phy_my_0.083deg_P1D-m"
OUT = PROJECT / "probes" / "_artifacts" / "glorys"

LAT0, LON0, LAT1, LON1 = 36.60, -122.20, 36.82, -121.98
D0, D1 = 0.0, 60.0
T0, T1 = "2019-09-01T00:00:00", "2019-10-01T00:00:00"


def _subset(variable: str) -> Path:
    """Fetch one variable for the month if not already cached. Returns the netCDF path."""
    OUT.mkdir(parents=True, exist_ok=True)
    cmd = [
        "copernicusmarine", "subset",
        "--dataset-id", DATASET,
        "--variable", variable,
        "--minimum-longitude", str(LON0), "--maximum-longitude", str(LON1),
        "--minimum-latitude", str(LAT0), "--maximum-latitude", str(LAT1),
        "--minimum-depth", str(D0), "--maximum-depth", str(D1),
        "--start-datetime", T0, "--end-datetime", T1,
        "--output-directory", str(OUT),
        "--file-format", "netcdf",
        "--overwrite",
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    if r.returncode != 0:
        tail = (r.stderr or r.stdout).strip().splitlines()[-3:]
        raise RuntimeError("copernicusmarine subset failed: " + " | ".join(tail))
    files = sorted(OUT.glob(f"*{variable}*.nc"))
    if not files:
        raise RuntimeError(f"no netCDF produced for {variable}")
    return files[0]


def check() -> Result:
    import numpy as np
    import xarray as xr

    detail: dict = {}
    problems: list[str] = []

    # credentials must be present, and must not be in the repo
    if not (Path.home() / ".copernicusmarine" / ".copernicusmarine-credentials").exists():
        problems.append("no cached credentials -- run `copernicusmarine login` first")
        return Result(status="FAIL", note="; ".join(problems), detail=detail)

    # --- thetao: the backbone, and the thing that must be physically right ---
    try:
        f_thetao = _subset("thetao")
        ds = xr.open_dataset(f_thetao)
        detail["thetao_kb"] = round(f_thetao.stat().st_size / 1024, 1)
        detail["dims"] = ",".join(f"{k}={v}" for k, v in ds.sizes.items())
        detail["n_depth"] = int(ds.sizes["depth"])
        detail["depth_range_m"] = f"{float(ds.depth.min()):.1f}-{float(ds.depth.max()):.1f}"
        detail["n_days"] = int(ds.sizes["time"])

        prof = ds.thetao.mean(dim=["time", "latitude", "longitude"]).values
        surf, deep = float(prof[0]), float(prof[-1])
        detail["thetao_surface"] = round(surf, 2)
        detail["thetao_deep"] = round(deep, 2)
        detail["thetao_range"] = f"{float(ds.thetao.min()):.2f}..{float(ds.thetao.max()):.2f}"

        if not 10.0 < surf < 22.0:
            problems.append(f"surface {surf:.2f} C implausible for Monterey in Sept")
        if not surf > deep:
            problems.append("surface must be warmer than depth (normal stratification)")

        # a thermocline must actually exist, or the ducting work has nothing to chew on
        grad = np.gradient(prof, ds.depth.values)
        i_tc = int(np.argmin(grad))
        detail["thermocline_m"] = round(float(ds.depth.values[i_tc]), 1)
        detail["thermocline_strength_c_per_m"] = round(float(grad[i_tc]), 4)
        if not 0.35 < float(ds.depth.values[i_tc]) < 45.0:
            problems.append(
                f"thermocline at {float(ds.depth.values[i_tc]):.1f} m is outside a "
                f"plausible 0.35-45 m band for a coastal upwelling site"
            )

        # the thermocline must MOVE over a month, or "when did it cross 40 m" is moot
        daily = ds.thetao.mean(dim=["latitude", "longitude"])  # (time, depth)
        tc_depths = []
        for k in range(daily.sizes["time"]):
            p = daily.isel(time=k).values
            gk = np.gradient(p, ds.depth.values)
            if np.isfinite(gk).all():
                tc_depths.append(float(ds.depth.values[int(np.argmin(gk))]))
        if tc_depths:
            tc = np.array(tc_depths)
            detail["thermocline_range_m"] = f"{tc.min():.1f}-{tc.max():.1f}"
            detail["thermocline_moves_m"] = round(float(tc.max() - tc.min()), 1)
            if tc.max() - tc.min() < 1.0:
                problems.append(
                    f"thermocline barely moves ({tc.max() - tc.min():.1f} m) -- the "
                    f"'when did it cross 40 m' question would have no answer"
                )
        ds.close()
    except Exception as exc:  # noqa: BLE001
        problems.append(f"thetao failed: {type(exc).__name__}: {exc}")

    # --- currents: nothing else probed supplies these ---
    try:
        f_u = _subset("uo")
        f_v = _subset("vo")
        du = xr.open_dataset(f_u)
        dv = xr.open_dataset(f_v)
        u = float(du.uo.mean())
        v = float(dv.vo.mean())
        umax = float(du.uo.max())
        vmax = float(dv.vo.max())
        sp = (u * u + v * v) ** 0.5
        detail.update(
            u_mean=round(u, 4),
            v_mean=round(v, 4),
            speed_mean=round(sp, 4),
            u_range=f"{umax:.3f}",
            v_range=f"{vmax:.3f}",
        )
        # open-ocean currents are ~0-1 m/s; a mean above 2 m/s would mean bad units
        if not 0.0 < sp < 2.0:
            problems.append(f"mean current speed {sp:.3f} m/s implausible")
        du.close()
        dv.close()
    except Exception as exc:  # noqa: BLE001
        problems.append(f"currents failed: {type(exc).__name__}: {exc}")

    if problems:
        return Result(status="FAIL", note="; ".join(problems), detail=detail)

    return Result(
        status=PASS,
        note=(
            f"Class C confirmed. 30 days x {detail['n_depth']} levels over "
            f"{detail['depth_range_m']} m. Surface {detail['thetao_surface']} C over "
            f"deep {detail['thetao_deep']} C. THERMOCLINE at "
            f"{detail['thermocline_m']} m, moving {detail['thermocline_moves_m']} m over "
            f"the month ({detail['thermocline_range_m']} m). Currents present: "
            f"mean |u,v| = {detail['speed_mean']} m/s. The ducting work has real "
            f"structure to work with."
        ),
        detail=detail,
    )


if __name__ == "__main__":
    from ._common import append_verdict

    res = run(HARNESS, check)
    append_verdict(res)
    sys.exit(0 if res.status == "PASS" else 1)
