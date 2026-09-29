"""Every remote endpoint the workshop touches, in one place.

This module exists so that the notebooks and ``scripts/prefetch.py`` cannot disagree
about a URL. That is not hypothetical: if the prefetch caches URL A and a notebook asks
for URL B, the cache silently misses and the notebook makes a live network call in a
room with thirty other laptops -- which is the exact failure this workshop is built to
avoid.

Every URL below was fetched and checked while writing the notebooks. The sizes in the
comments are real, not nominal.

Organised by **access pattern**, not by dataset, because the patterns transfer and the
datasets do not:

    REST griddap ............ ERDDAP          Notebook 02
    cloud object storage .... GCS / NCEI      Notebook 03
    browsable tree ......... Argo GDAC       Notebook 04
    credentialed API ....... Copernicus      Notebook 05
    fixed-format text ...... NDBC            Notebook 06
    domain library ......... gsw             Notebook 07
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from _fetch import erddap, get  # noqa: E402

# ---------------------------------------------------------------------------
# The site. Everything in the workshop is within ~20 km of this point.
# ---------------------------------------------------------------------------
SITE_LAT, SITE_LON = 36.70, -122.10          # ocean site
SITE_NAME = "Monterey Bay, CA"
ANCHOR_LAT, ANCHOR_LON = 36.798, -121.976    # SanctSound MB01, 16 km away
WIND_STATION = "46092"                        # NDBC "MBM1", 10 km away


# ---------------------------------------------------------------------------
# 1. REST griddap -- ERDDAP, NOAA CoastWatch, anonymous, no key
# ---------------------------------------------------------------------------
ERDDAP = "https://coastwatch.pfeg.noaa.gov/erddap/griddap/jplMURSST41"
SST_VAR = "analysed_sst"
SST_DS = "jplMURSST41"          # 0.045 deg daily analysed SST, 2002-present

# The query box used in notebooks 01 and 02. 0.22 x 0.22 deg ~ 24 km, spanning the bay
# mouth without dragging in the open ocean.
SST_BOX = (36.60, 36.82, -122.20, -121.98)


def sst_url(
    start: str = "2019-09-01T00:00:00Z",
    end: str = "2019-09-30T00:00:00Z",
    box: tuple = SST_BOX,
    *,
    fmt: str = "csv",
    point: bool = False,
) -> str:
    """An SST query URL for notebooks 01-02.

    ``point=True`` collapses the lat/lon box to a single cell, which is how you actually
    reduce an ERDDAP response. Measured for September 2019 at this site:

        full box (0.22 deg)   690,813 B   15,870 rows   23 x 23 cells per day
        point   (degenerate)   1,324 B       30 rows   one cell per day

    That is a 520x reduction, and it is the *only* reduction that works. All three of
    the alternatives were tested and are traps:

      * ``&.time=first&.lat=first&.lon=first`` -- silently a **no-op**. Byte-identical
        690,813 B response. This one is nasty, because it looks like it is doing
        something and the examples online use it.
      * ``&time=...&latitude=...`` constraint variables -- HTTP 400: *"In a griddap
        query, '&' must be followed by a .griddap server variable."*
      * strides inside the index, ``[(0):(1):(29)]`` -- HTTP 400: *"For variable
        analysed_sst axis#0=time Constraint=..."*

    So: **shrink the box.** ERDDAP's griddap DSL has no stride and no constraint
    variables, and the server-side directives people copy around are decorative.
    """
    lat0, lat1, lon0, lon1 = box
    if point:
        # keep the first cell of the box; a degenerate range is a valid single-cell query
        lat1, lon1 = lat0, lon0
    index = f"[({start}):({end})][({lat0}):({lat1})][({lon0}):({lon1})]"
    return erddap(ERDDAP, SST_VAR, index, fmt=fmt)


def sst_csv(**kw) -> str:
    return sst_url(**kw)


def sst_nc(**kw) -> str:
    return sst_url(fmt="nc", **kw)


# ---------------------------------------------------------------------------
# 2. Cloud object storage -- NOAA NCEI passive acoustic archive, anonymous
# ---------------------------------------------------------------------------
GCS_BUCKET = "noaa-passive-bioacoustic"
GCS_API = f"https://storage.googleapis.com/storage/v1/b/{GCS_BUCKET}/o"
GCS_FILES = f"https://storage.googleapis.com/{GCS_BUCKET}"
NCEI_SITE = "mb01"

# Product suffixes. The size difference is three orders of magnitude for the same
# recording, and this is the single most useful thing to know before downloading:
#
#     psd_1h   1 Hz spectral density      ~456 MB per deployment   DO NOT
#     tol_1h   third-octave band levels  ~0.7 MB per deployment   used here
#     ol_1h    octave band levels         ~0.4 MB per deployment
#     bb_1h    broadband level            ~0.2 MB per deployment
SOUND_PRODUCTS = ("tol_1h", "ol_1h", "bb_1h", "psd_1h")
DEPLOYMENTS = [f"{i:02d}" for i in range(1, 10)]   # 9 deployments at MB01


def ncei_dataset_dir(product: str, deployment: str = "09") -> str:
    """The dataset prefix, e.g. ``.../sanctsound_mb01_09_tol_1h``.

    The site is the *first* component; passing the site inside the product as well
    doubles it into ``sanctsound_mb01_mb01_...`` and quietly finds nothing.
    """
    return f"sanctsound/products/sound_level_metrics/{NCEI_SITE}/sanctsound_{NCEI_SITE}_{deployment}_{product}"


def gcs_list_params(prefix: str, delimiter: str = "/", max_items: int = 200) -> dict:
    """The query parameters for a bucket listing.

    Returned as a dict rather than baked into a URL so that the prefetch manifest and
    the notebooks build *byte-identical* requests. The cache key is a hash of the URL
    plus the sorted params, so two spellings of the same query are two different keys
    and the prefetch silently misses.
    """
    p = {"prefix": prefix, "maxResults": max_items}
    if delimiter:
        p["delimiter"] = delimiter
    return p


def ncei_list(prefix: str, delimiter: str = "/", max_items: int = 200) -> dict:
    """List a prefix in the bucket. Returns the parsed JSON body."""
    return json.loads(get(GCS_API, gcs_list_params(prefix, delimiter, max_items)).text)


def ncei_object_name(product: str = "tol_1h", deployment: str = "09",
                     ext: str = ".nc") -> str:
    """Full object key, including the mandatory ``data/`` level.

    Verified: ``SanctSound_MB01_09_TOL_1h.nc`` is 760,105 B with ``data/`` in the path,
    and returns ``NoSuchKey`` (HTTP 404, XML body) without it. That is a *path* error
    that looks like a *permissions* error, which is why it costs time.

    Note the capitalisation, which is not a rule you can guess: the directory is
    ``sanctsound_mb01_09_tol_1h`` (all lower) but the file is ``SanctSound_MB01_09_TOL_1h``
    -- title case for the product letters, and the trailing unit letter stays lower.
    ``product.upper()`` gives ``TOL_1H``, which does not exist.
    """
    d = ncei_dataset_dir(product, deployment)
    stem = f"SanctSound_{NCEI_SITE.upper()}_{deployment}_{product[:-1].upper()}{product[-1]}"
    return f"{d}/data/{stem}{ext}"


def ncei_file_url(product: str = "tol_1h", deployment: str = "09", ext: str = ".nc") -> str:
    return f"{GCS_FILES}/{ncei_object_name(product, deployment, ext)}"


# ---------------------------------------------------------------------------
# 3. Browsable tree + netCDF -- Argo GDAC, anonymous
# ---------------------------------------------------------------------------
GDAC_BASE = "https://data-argo.ifremer.fr/dac/coriolis"
ARGO_FLOAT = "1900063"
ARGO_DIR = f"{GDAC_BASE}/{ARGO_FLOAT}"

# The directory is an Apache HTML index, not a JSON API -- see Notebook 04 for how to
# read it without a parser. Files: _prof.nc, _meta.nc, _tech.nc, _Rtraj.nc, profiles/.
ARGO_FILES = {
    "prof": f"{ARGO_DIR}/{ARGO_FLOAT}_prof.nc",   # 689,348 B, all cycles in one file
    "meta": f"{ARGO_DIR}/{ARGO_FLOAT}_meta.nc",
    "tech": f"{ARGO_DIR}/{ARGO_FLOAT}_tech.nc",
}

# The demo float. NOTE: it is in the **North Atlantic** (24-27 N, 22-18 W), not the
# Pacific, and its cycles run 2002-2004. It is here because it is a small, complete,
# well-formed example of the file structure -- not because it is near the site. The
# workshop's local data comes from ERDDAP, GCS and NDBC.
#
# On finding a float near a given location, which is the obvious next question:
#
#   * The coriolis DAC holds 4,261 floats. There is **no index and no search API** --
#     tested /index/, /dac/index/, <wmo>_prof_index.txt and index/<wmo>.txt, all 404.
#   * No small file answers "where is it?" either. _meta.nc (35 KB) is configuration
#     and has no LATITUDE. _tech.nc (2.8 MB) is instrument metadata and has no LATITUDE
#     either. **Position lives in _prof.nc (689 KB).**
#   * So screening the DAC for a float near a site costs 689 KB per candidate: 2.9 GB
#     for all 4,261.
#
# That is a real cost, and a property of how the archive is laid out rather than a
# missing convenience. Notebook 04 states it rather than working around it quietly.
ARGO_EXPECTED_BYTES = 689_348


def argo_meta_url(wmo: str) -> str:
    """Metadata for any float. Configuration only -- **no position** (see above)."""
    return f"{GDAC_BASE}/{wmo}/{wmo}_meta.nc"


# ---------------------------------------------------------------------------
# 4. Fixed-format text -- NDBC, anonymous, no key
# ---------------------------------------------------------------------------
NDBC_STD_MET = "https://www.ndbc.noaa.gov/data/historical/stdmet/{station}h{year}.txt.gz"


def ndbc_url(station: str = WIND_STATION, year: int = 2019) -> str:
    return NDBC_STD_MET.format(station=station, year=year)


# ---------------------------------------------------------------------------
# 5. Credentialed API -- Copernicus Marine (Class C, the only one that needs an account)
# ---------------------------------------------------------------------------
GLORYS_DATASET = "GLOBAL_MULTIYEAR_PHY_001_030"
COPERNICUS_HOME = "https://data.marine.copernicus.eu/product/GLOBAL_MULTIYEAR_PHY_001_030/description"


# ---------------------------------------------------------------------------
# Prefetch manifest. scripts/prefetch.py iterates this; the notebooks use the same
# builders, so cache and notebook cannot disagree.
# ---------------------------------------------------------------------------
def manifest() -> list[tuple[str, str, dict | None]]:
    """(label, url, params) for every network response the workshop needs.

    Every entry is produced by the same function the notebook calls, so the cached
    response is guaranteed to be the one the notebook asks for. Hand-writing a URL here
    would be the bug this design exists to prevent.
    """
    items: list[tuple[str, str, dict | None]] = [
        ("erddap/sst-box-csv", sst_csv(), None),
        ("erddap/sst-point-csv", sst_csv(point=True), None),
        ("erddap/sst-nc", sst_nc(), None),
        # The .das metadata is how you learn the server's axis order, which Notebook 02
        # needs before it can trust any spatial result. Not optional.
        ("erddap/sst-das", f"{ERDDAP}.das", None),
        ("gcs/list-sites", GCS_API,
         gcs_list_params(f"sanctsound/products/sound_level_metrics/{NCEI_SITE}/", "/", 200)),
        # The same prefix with delimiter="" -- a different cache key, because the cache
        # key hashes url + sorted params. Notebook 03 shows both.
        ("gcs/list-sites-nodelim", GCS_API,
         gcs_list_params(f"sanctsound/products/sound_level_metrics/{NCEI_SITE}/", "", 200)),
    ]
    for dep in ("01", "09"):
        items.append((
            f"gcs/list-{dep}-tol", GCS_API,
            gcs_list_params(f"{ncei_dataset_dir('tol_1h', dep)}/data/", "", 10),
        ))
        items.append((f"gcs/file-{dep}-tol", ncei_file_url("tol_1h", dep), None))
    for key, url in ARGO_FILES.items():
        items.append((f"argo/{key}", url, None))
    items.append((f"ndbc/{WIND_STATION}-2019", ndbc_url(), None))
    return items
