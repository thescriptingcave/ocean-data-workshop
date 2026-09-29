"""NCEI / SanctSound passive acoustic products.

All anonymously readable from the public ``noaa-passive-bioacoustic`` GCS bucket. The
GCS JSON API is used rather than the aws CLI because it needs no configuration at all
(and this machine's default AWS profile redirects ``aws s3`` to a local MinIO).

Object layout::

    sanctsound/products/<type>/<site>/<dataset>/data/<files>
    sanctsound/products/<type>/<site>/<dataset>/metadata/<files>

The mandatory ``data/`` level is a trap -- omitting it returns ``NoSuchKey``, not a 404,
which reads like a permissions problem rather than a path typo.

Size matters enormously here. The same product comes in four resolutions and the
difference is three orders of magnitude:

    psd_1h   1 Hz spectral density      ~456 MB per deployment   DO NOT DOWNLOAD
    tol_1h   third-octave band levels  ~0.7 MB per deployment   the default choice
    ol_1h    octave band levels         ~0.4 MB per deployment
    bb_1h    broadband level            ~0.2 MB per deployment

Third-octave is the sweet spot: enough frequency resolution to separate biological,
shipping and wind noise, small enough to hold a year in memory. For a first pass prefer
``tol_1h`` and fall back to ``psd_1h`` only if a specific frequency question requires it.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import xarray as xr

BUCKET = "noaa-passive-bioacoustic"
API = f"https://storage.googleapis.com/storage/v1/b/{BUCKET}/o"
FILES = f"https://storage.googleapis.com/{BUCKET}"

PRODUCT_TYPES = ("sound_level_metrics", "detections", "sound_clips")

# MB01 is the site at 36.798 N, 121.976 E -- 16 km from the ocean site, moored at
# 115.5/116.5 m, recorded at 48 and 96 kHz. Selected by probe 09 from the file-level
# metadata index, not by guesswork.
ANCHOR_SITE = "mb01"


_SESSION = None


def _session():
    global _SESSION
    if _SESSION is None:
        from ..http import http_session

        _SESSION = http_session()
    return _SESSION


def list_prefix(prefix: str, delimiter: str = "/", max_items: int = 400):
    """List common prefixes and objects under a prefix. Returns (prefixes, items)."""
    http = _session()
    r = http.get(
        API,
        params={"prefix": prefix, "delimiter": delimiter, "maxResults": max_items},
        timeout=http.request_timeout,
    )
    r.raise_for_status()
    d = r.json()
    return d.get("prefixes", []), d.get("items", [])


def find_data_file(site: str, product: str, suffix: str = ".nc") -> str | None:
    """Resolve the data file for a site and product suffix.

    ``product`` is the part *after* the site, e.g. ``('mb01', '09_tol_1h')`` resolves to
    ``sanctsound/products/sound_level_metrics/mb01/sanctsound_mb01_09_tol_1h/data/``.
    Passing the site inside ``product`` too would double it into
    ``sanctsound_mb01_mb01_...`` and quietly find nothing.
    """
    _, items = list_prefix(
        f"sanctsound/products/sound_level_metrics/{site}/"
        f"sanctsound_{site}_{product}/data/"
    )
    for i in items:
        if i["name"].endswith(suffix):
            return i["name"]
    return None


def fetch(key: str, cache_dir: str | Path) -> Path:
    """Download one object by its full key, if not already cached."""
    cache = Path(cache_dir)
    cache.mkdir(parents=True, exist_ok=True)
    cp = cache / key.rsplit("/", 1)[-1]
    if cp.exists() and cp.stat().st_size > 0:
        return cp
    r = _session().get(f"{FILES}/{key}", timeout=(30, 900))
    r.raise_for_status()
    cp.write_bytes(r.content)
    return cp


def load_sound_levels(
    site: str, product: str, cache_dir: str | Path = "data/acoustic"
) -> xr.Dataset:
    """Load a 1-hour sound-level product as a labelled Dataset."""
    key = find_data_file(site, product, ".nc")
    if key is None:
        raise FileNotFoundError(f"no netCDF for {site}/{product}")
    return xr.open_dataset(fetch(key, cache_dir))


def band_summary(ds: xr.Dataset) -> dict:
    """Describe a sound-level product: shape, time span, frequency axis, and range.

    Sanity bounds matter: an uncalibrated or mis-decoded product can come back with
    plausible-looking but physically wrong dB values, and 0 dB re 1 uPa^2/Hz is the
    reference, not a real measurement.
    """
    freq = None
    for cand in ("frequency", "frequency_Hz", "f", "center_frequency"):
        if cand in ds.coords or cand in ds:
            freq = cand
            break
    out = {
        "dims": {k: int(v) for k, v in ds.sizes.items()},
        "vars": [v for v in ds.data_vars],
        "freq_axis": freq,
    }
    if "time" in ds.coords:
        t = ds.time.values
        out["time_span"] = f"{str(t[0])[:19]} .. {str(t[-1])[:19]}"
        out["n_steps"] = int(t.size)
    if freq:
        f = ds[freq].values
        out["freq_range_hz"] = f"{f.min():.3g} .. {f.max():.3g} Hz"
        out["n_bands"] = int(f.size)
    for v in ds.data_vars:
        da = ds[v]
        if da.dtype.kind in "fiu" and da.size:
            out[f"{v}_range"] = f"{float(da.min()):.2f} .. {float(da.max()):.2f}"
    return out


def detection_frame(csv_path: Path) -> "pd.DataFrame":  # noqa: F821
    """Load a SanctSound detection CSV (hourly presence/absence) as a tidy frame."""
    import pandas as pd

    df = pd.read_csv(csv_path)
    time_col = next(
        (c for c in df.columns if c.lower() in ("isostarttime", "time", "t", "timestamp")),
        df.columns[0],
    )
    df = df.rename(columns={time_col: "time"})
    df["time"] = pd.to_datetime(df["time"], format="mixed", utc=True, errors="coerce")
    return df.dropna(subset=["time"]).sort_values("time")
