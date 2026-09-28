"""Probe 07 — Argo in-situ profiles via GDAC (no ERDDAP, no argopy, no account).

Findings worth recording, because two of them cost real time:

1. **argopy is currently unusable.** argopy 1.3.1 *and* 1.4.0 both import
   ``erddapy.erddapy._quote_string_constraints``, a private symbol removed in
   erddapy 3.x. argopy 1.4.0 additionally caps ``xarray<=2025.9.0``. Making it work
   means pinning ``erddapy<3`` *and* downgrading xarray, which is a bad trade when
   ERDDAP already works. So: no argopy. Fetch GDAC files directly.

2. **GDAC is plain browsable HTTPS with no account.** Layout is
   ``/dac/<dac>/<wmo>/<wmo>_prof.nc``, where the ``_prof.nc`` file holds *every cycle*
   for that float as one N_PROF x N_LEVELS x N_PARAM array (98 cycles in 673 KB).
   One file per float is the right granularity -- far better than 98 separate files.

Argo is not on the ERDDAP hosts we checked (coastwatch, argo.ucsd.edu, data-argo), and
``argo.ucsd.edu/erddap`` has no griddap index. For geographic box queries, Copernicus
Marine ``INSITU_GLO_TS_OA`` is the better tool and needs the account the plan assumes.
"""

from __future__ import annotations

import numpy as np

from ._common import PASS, Probe, Result, cache_path, http_session, run

HARNESS = Probe(
    slug="argo_gdac",
    name="Argo in-situ profiles via GDAC",
    tier=1,
    klass="A",
    provides="T/S/pressure profiles to 2000 m, ~10-day cycles, with QC flags",
    protocol="browsable HTTPS directory + netCDF",
    order=7,
)

GDAC = "https://data-argo.ifremer.fr/dac/coriolis/1900063/1900063_prof.nc"
HTTP = None


def _decode_qc(arr) -> np.ndarray:
    """Argo QC flags arrive in two encodings depending on the file.

    The per-cycle ``_D``/``.nc`` byte files store flags as int8 (0..9). The
    aggregated ``_prof.nc`` multi-profile file stores them as *characters*, so
    xarray gives an object array of numpy bytes: b'1', b'2', b'4', b'nan'...

    Comparing bytes to an int silently yields all-False, which reads as "no good
    data" rather than raising. Handle both, and keep 'nan' as a fill value.
    """
    a = np.asarray(arr)
    if a.dtype.kind in "iu":
        return a.astype(int)
    out = np.full(a.shape, -1, dtype=int)  # -1 = fill / not evaluated
    flat = a.ravel()
    res = out.ravel()
    for i, v in enumerate(flat):
        if isinstance(v, (bytes, np.bytes_)):
            s = v.decode("ascii", "ignore")
        else:
            s = str(v)
        s = s.strip()
        if s and s not in ("nan", "NaN", ""):
            try:
                res[i] = int(s)
            except ValueError:
                res[i] = -1
        else:
            res[i] = -1
    return res.reshape(a.shape)


def check() -> Result:
    global HTTP
    HTTP = http_session()

    detail: dict = {}
    problems: list[str] = []

    cp = cache_path("argo_1900063_prof.nc", "")
    if not cp.exists() or cp.stat().st_size == 0:
        r = HTTP.get(GDAC, timeout=HTTP.request_timeout)
        if r.status_code != 200:
            return Result(
                status="FAIL", note=f"GDAC fetch returned HTTP {r.status_code}"
            )
        cp.write_bytes(r.content)
    detail["kb"] = round(cp.stat().st_size / 1024, 1)

    import xarray as xr

    ds = xr.open_dataset(cp, decode_timedelta=False)
    detail["n_profiles"] = int(ds.sizes["N_PROF"])
    detail["n_levels"] = int(ds.sizes["N_LEVELS"])
    detail["n_params"] = int(ds.sizes["N_PARAM"])
    if detail["n_profiles"] < 10:
        problems.append(f"only {detail['n_profiles']} cycles -- too few to be useful")

    # --- QC flags must be present, because the SQL work depends on them ---
    for v in ("PRES_ADJUSTED_QC", "TEMP_ADJUSTED_QC", "PSAL_ADJUSTED_QC"):
        if v not in ds:
            problems.append(f"missing QC variable {v}")
    detail["has_qc"] = all(
        v in ds for v in ("PRES_ADJUSTED_QC", "TEMP_ADJUSTED_QC", "PSAL_ADJUSTED_QC")
    )
    detail["qc_encoding"] = str(ds["TEMP_ADJUSTED_QC"].dtype)

    # --- physical sanity of the good samples ---
    qc = _decode_qc(ds["TEMP_ADJUSTED_QC"].values)
    t = np.asarray(ds["TEMP_ADJUSTED"].values, dtype=float)
    good = qc == 1  # Argo: 1 = good
    detail["qc_good_pct"] = round(100 * float(good.mean()), 2)
    detail["qc_bad_n"] = int((qc == 4).sum())
    detail["qc_fill_n"] = int((qc == -1).sum())
    if good.sum() == 0:
        problems.append("no good TEMP_ADJUSTED values after QC")
    else:
        tgood = t[good]
        detail["temp_good"] = int(good.sum())
        detail["temp_min_max"] = f"{np.nanmin(tgood):.2f}..{np.nanmax(tgood):.2f} C"
        # open-ocean temperature must lie in a plausible band
        if not -2.0 < np.nanmin(tgood) < 5.0:
            problems.append(f"min temp {np.nanmin(tgood):.2f} C implausible")
        if not 20.0 < np.nanmax(tgood) < 32.0:
            problems.append(f"max temp {np.nanmax(tgood):.2f} C implausible")

    p = np.asarray(ds["PRES_ADJUSTED"].values, dtype=float)
    detail["pres_max_dbar"] = round(float(np.nanmax(p)), 1)

    # --- position + time ---
    lat = np.asarray(ds["LATITUDE"].values, dtype=float)
    detail["lat_range"] = f"{np.nanmin(lat):.2f}..{np.nanmax(lat):.2f}"
    if not np.all(np.abs(lat) <= 90):
        problems.append("latitude out of range")
    detail["cycle_range"] = (
        f"{int(ds['CYCLE_NUMBER'].values[0])}.."
        f"{int(ds['CYCLE_NUMBER'].values[-1])}"
    )
    ds.close()

    if problems:
        return Result(status="FAIL", note="; ".join(problems), detail=detail)

    return Result(
        status=PASS,
        note=(
            f"{detail['n_profiles']} cycles x {detail['n_levels']} levels in "
            f"{detail['kb']} KB, one file per float. QC flags present and decoded "
            f"(dtype={detail['qc_encoding']}): {detail['qc_good_pct']}% good, "
            f"{detail['qc_bad_n']} bad, {detail['qc_fill_n']} fill. "
            f"T {detail['temp_min_max']}, max depth {detail['pres_max_dbar']} dbar. "
            f"NO argopy -- broken against erddapy 3.x."
        ),
        detail=detail,
    )


if __name__ == "__main__":
    import sys

    from ._common import append_verdict

    res = run(HARNESS, check)
    append_verdict(res)
    sys.exit(0 if res.status == "PASS" else 1)
