"""GLORYS12V1 loader.

The only source that supplies **currents** — Argo has profiles but no velocity, and
ERDDAP has surface temperature only — which is why the Class C Copernicus account is
load-bearing for this project.

Two layers:

  * ``fetch`` wraps the ``copernicusmarine subset`` CLI and caches netCDF on disk.
  * ``load`` opens the cached files as one labelled xarray Dataset, in memory.

Deliberately CLI-based rather than the Python API: the CLI caches properly, its
credentials handling is the documented path, and it avoids depending on internal
client behaviour. The cost is a subprocess per variable.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import xarray as xr

from ..config import GLORYS_DATASETS

# Physical ranges, used to reject silent unit errors and fill-value confusion. A subset
# that returns values outside these is a download or decoding problem, not oceanography.
RANGES = {
    "thetao": (-2.0, 35.0, "degC"),
    "so": (0.0, 42.0, "1e-3"),
    "uo": (-2.5, 2.5, "m s-1"),
    "vo": (-2.5, 2.5, "m s-1"),
    "zos": (-3.0, 3.0, "m"),
}

UNITS = {
    "thetao": "degree_Celsius",
    "so": "1e-3",
    "uo": "m s-1",
    "vo": "m s-1",
    "zos": "m",
}


def _env_with_credentials() -> dict:
    """The child process environment, with credentials loaded from .env if needed."""
    import os

    from ..credentials import load

    load()
    return {**os.environ}


def fetch(
    variables: list[str],
    box: dict,
    start: str,
    end: str,
    cache_dir: str | Path,
    dataset_id: str = GLORYS_DATASETS["daily"],
) -> dict[str, Path]:
    """Download one netCDF per variable if not already cached. Returns {name: path}.

    ``variables`` uses *this project's* names ("temperature", not "thetao") so callers
    never have to know GLORYS short names. The translation happens here, and the cache
    glob is keyed on the GLORYS short name because that is what appears in the filename
    copernicusmarine writes.
    """
    cache = Path(cache_dir)
    cache.mkdir(parents=True, exist_ok=True)
    reverse = {new: short for short, new in RENAME.items()}

    out: dict[str, Path] = {}
    for name in variables:
        short = reverse.get(name, name)
        existing = sorted(cache.glob(f"*{dataset_id}*{short}*.nc"))
        if existing and existing[0].stat().st_size > 0:
            out[name] = existing[0]
            continue
        cmd = [
            "copernicusmarine", "subset",
            "--dataset-id", dataset_id,
            "--variable", short,
            "--minimum-longitude", str(box["min_longitude"]),
            "--maximum-longitude", str(box["max_longitude"]),
            "--minimum-latitude", str(box["min_latitude"]),
            "--maximum-latitude", str(box["max_latitude"]),
            "--minimum-depth", str(box["min_depth"]),
            "--maximum-depth", str(box["max_depth"]),
            "--start-datetime", start,
            "--end-datetime", end,
            "--output-directory", str(cache),
            "--file-format", "netcdf",
            "--overwrite",
        ]
        # Credentials reach the CLI as environment variables, which are the names
        # `copernicusmarine login --help` documents. A value already in os.environ
        # wins, so CI and explicit overrides are unaffected. Nothing is printed.
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=1800,
                           env=_env_with_credentials())
        files = sorted(cache.glob(f"*{dataset_id}*{short}*.nc"))
        if r.returncode != 0 or not files:
            tail = (r.stderr or r.stdout).strip().splitlines()[-2:]
            raise RuntimeError(
                f"copernicusmarine subset failed for {short}: {' | '.join(tail)}"
            )
        out[name] = files[0]
    return out


def load(paths: dict[str, Path] | list[Path], label: str = "") -> xr.Dataset:
    """Merge per-variable netCDF files into one Dataset, renaming GLORYS short names.

    Renames are driven by what is *in each file*, not by the keys of ``paths`` -- the
    dictionary may be keyed by this project's names while the netCDFs still hold
    GLORYS short names, and those two are not obliged to agree.
    """
    file_list = list(paths.values()) if isinstance(paths, dict) else list(paths)
    parts = []
    for path in file_list:
        ds = xr.open_dataset(path)
        renames = {v: RENAME[v] for v in ds.data_vars if v in RENAME}
        if renames:
            ds = ds.rename(renames)
        parts.append(ds)
    if not parts:
        raise ValueError("no netCDF files to load")
    merged = xr.merge(parts, compat="override")
    for short, unit in UNITS.items():
        new = RENAME.get(short, short)
        if new in merged:
            merged[new].attrs["units"] = unit
    if label:
        merged.attrs["label"] = label
    merged.attrs["source"] = "GLORYS12V1 / GLOBAL_MULTIYEAR_PHY_001_030"
    return merged


# GLORYS short name -> the name we use in this project
RENAME = {
    "thetao": "temperature",
    "so": "salinity",
    "uo": "u_eastward",
    "vo": "v_northward",
    "zos": "sea_surface_height",
}


def check_ranges(ds: xr.Dataset) -> dict[str, tuple]:
    """Report min/max per variable and flag anything physically impossible.

    A subset that lands outside these bounds is a download, decoding or fill-value
    problem -- not oceanography. Cheap insurance against a silently wrong unit.
    """
    report: dict[str, tuple] = {}
    for short, new in RENAME.items():
        if new not in ds:
            continue
        lo, hi, _ = RANGES[short]
        da = ds[new]
        mn, mx = float(da.min()), float(da.max())
        report[new] = (mn, mx, "ok" if (lo <= mn and mx <= hi) else "OUT OF RANGE")
    return report
