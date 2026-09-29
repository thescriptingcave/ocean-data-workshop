"""NDBC moored met-ocean observations.

Buoy 46042 sits at 36.752 N, 122.028 W — about 5 km from the ocean site, so it is the
wind and wave forcing for the same water the GLORYS box describes. Real observations,
hourly, no account, no key: **class A**.

This is the missing forcing variable. Upwelling along the California coast is driven by
northerly wind, so this is what lets the ocean signal be explained rather than merely
described.

Format notes that cost time to rediscover:

  * Historical files are gzipped text at
    ``/data/historical/stdmet/<station>h<year>.txt.gz``.
  * **Line 0 is the variable *names*, line 1 is the units, and data starts at line 2.**
    Parsing the units line instead of the names line silently yields columns called
    ``#yr``, ``mo``, ``dy``.
  * **Resolution is not uniform within a file.** Station 46042 is hourly early in 2019
    and 10-minute by December, so a year file has ~14,900 rows rather than 8,760. Never
    assume hourly, and expect duplicate timestamps once you floor to the hour.
  * Missing sentinels are **99** for most fields but **999** for ``WDIR``, ``MWD`` and
    ``PRES``. Blanking 99 in ``WDIR`` is a real bug: 99 degrees is a valid easterly.
  * Wind direction is the direction the wind comes *from*, in degrees true. So
    ``u = -speed*sin(dir)``, ``v = -speed*cos(dir)``.
  * Timestamps are stamped ~50 min past the hour and are UTC.
  * Assigning a RangeIndex Series into a timestamp-indexed frame silently yields all
    NaN -- pandas aligns on index. Values must be passed positionally.
"""

from __future__ import annotations

import gzip
import io
from pathlib import Path

import numpy as np
import pandas as pd

NDBC_STD_MET = "https://www.ndbc.noaa.gov/data/historical/stdmet/{station}h{year}.txt.gz"

# Buoy 46042, Monterey Bay. ~5 km from OCEAN_SITE.
MONTEREY_46042 = {
    "station": "46042",
    "lat": 36.752,
    "lon": -122.028,
    "name": "MONTEREY BAY 17 NM SW OF SAN FRANCISCO CA",
}

# Per-column missing sentinels. Do NOT blanket-apply 99: it is a valid WDIR.
SENTINELS = {
    "WDIR": [999.0],
    "WSPD": [99.0],
    "GST": [99.0],
    "WVHT": [99.0],
    "DPD": [99.0],
    "APD": [99.0],
    "MWD": [999.0],
    "PRES": [9999.0],
    "ATMP": [99.0],
    "WTMP": [99.0],
    "DEWP": [99.0],
    "VIS": [99.0],
    "TIDE": [99.0],
}


def fetch(station: str, year: int, cache_dir: str | Path) -> Path:
    """Download the hourly standard-meteorology file for one station-year, if absent."""
    cache = Path(cache_dir)
    cache.mkdir(parents=True, exist_ok=True)
    cp = cache / f"ndbc_{station}h{year}.txt.gz"
    if cp.exists() and cp.stat().st_size > 0:
        return cp
    from ..http import http_session

    http = http_session()
    url = NDBC_STD_MET.format(station=station, year=year)
    r = http.get(url, timeout=http.request_timeout)
    r.raise_for_status()
    cp.write_bytes(r.content)
    return cp


def load(path: Path) -> pd.DataFrame:
    """Parse an NDBC standard-meteorology file into a tz-naive UTC DataFrame.

    Timestamps are made **tz-naive UTC** on purpose: the GLORYS cube carries naive
    timestamps, and mixing aware and naive indexes fails at join time with a confusing
    error. Everything in this project uses naive UTC.

    Resolution is whatever the station reported, which is *not* always uniform -- see the
    module docstring. Resample before assuming a cadence.
    """
    text = gzip.open(path, "rt").read()
    lines = text.splitlines()
    cols = [c.lstrip("#") for c in lines[0].split()]  # names line, not units
    frame = pd.DataFrame([ln.split() for ln in lines[2:] if ln.strip()], columns=cols)

    stamps = pd.to_datetime(
        dict(
            year=pd.to_numeric(frame["YY"], errors="coerce"),
            month=pd.to_numeric(frame["MM"], errors="coerce"),
            day=pd.to_numeric(frame["DD"], errors="coerce"),
            hour=pd.to_numeric(frame["hh"], errors="coerce"),
            minute=pd.to_numeric(frame["mm"], errors="coerce"),
        ),
        utc=True,
    ).dt.tz_localize(None)

    out = pd.DataFrame(index=stamps)
    for c, sentinels in SENTINELS.items():
        if c in frame:
            # .to_numpy(), not the Series: assigning a RangeIndex Series into a
            # timestamp-indexed frame aligns on index and yields all-NaN.
            out[c.lower()] = pd.to_numeric(frame[c], errors="coerce").replace(
                sentinels, np.nan
            ).to_numpy()
    out["wind_speed"] = out["wspd"]
    out["wind_gust"] = out["gst"]
    out["wave_height"] = out["wvht"]
    out["air_temp"] = out["atmp"]
    out["water_temp"] = out["wtmp"]
    out["pressure"] = out["pres"]

    # meteorological convention: components point where the air is GOING
    rad = np.radians(out["wdir"])
    out["wind_u_east"] = -out["wspd"] * np.sin(rad)
    out["wind_v_north"] = -out["wspd"] * np.cos(rad)
    # northerly component: positive when wind blows FROM the north, which is what drives
    # upwelling on the California coast
    out["wind_northward"] = out["wspd"] * np.cos(rad)
    return out.sort_index()


def daily(frame: pd.DataFrame) -> pd.DataFrame:
    """Daily aggregates. Wind *direction* is not averaged here on purpose: bearings wrap
    at 360 degrees and a naive mean is meaningless. See `circular_mean` if you need it.
    """
    return pd.DataFrame(
        {
            "wind_speed_mean": frame["wspd"].resample("1D").mean(),
            "wind_gust_max": frame["gst"].resample("1D").max(),
            "wave_height_max": frame["wvht"].resample("1D").max(),
            "air_temp_mean": frame["atmp"].resample("1D").mean(),
            "water_temp_mean": frame["wtmp"].resample("1D").mean(),
            "wind_u_mean": frame["wind_u_east"].resample("1D").mean(),
            "wind_v_mean": frame["wind_v_north"].resample("1D").mean(),
            "wind_northward_mean": frame["wind_northward"].resample("1D").mean(),
        }
    )


def circular_mean(degrees: pd.Series) -> float:
    """Mean of bearings, correctly. Bearings wrap at 360, so averaging degrees gives
    nonsense: 350 and 10 average to 180, which is the exact opposite of 0.
    """
    rad = np.radians(degrees.dropna())
    if rad.empty:
        return float("nan")
    return float(np.degrees(np.arctan2(np.sin(rad).mean(), np.cos(rad).mean())) % 360)
