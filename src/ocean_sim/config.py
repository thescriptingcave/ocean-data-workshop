"""Site and time-window configuration.

One place, so the ocean site and the acoustic anchor site can be checked against each
other rather than drifting apart. `acoustic_anchor` was chosen from the SanctSound
metadata index (probe 09) by distance, sample rate and depth -- not guessed.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Site:
    name: str
    lat: float
    lon: float
    depth_m: float | None = None
    note: str = ""


@dataclass(frozen=True)
class Window:
    start: str
    end: str
    label: str = ""


# --- the ocean site: the GLORYS box everything else is compared against ---
OCEAN_SITE = Site(
    name="Monterey Bay, CA",
    lat=36.70,
    lon=-122.10,
    note="central California upwelling coast; thermocline sits near 15 m in September",
)

# A small box around the point. 0.22 deg ~ 24 km, which spans the bay mouth without
# dragging in the open ocean. 1/12 deg GLORYS cells are ~9 km, so this is a few cells.
OCEAN_BOX = {
    "min_latitude": 36.60,
    "max_latitude": 36.82,
    "min_longitude": -122.20,
    "max_longitude": -121.98,
    "min_depth": 0.0,
    "max_depth": 60.0,
}

# --- the acoustic anchor, from probe 09 ---
ACOUSTIC_ANCHOR = Site(
    name="SanctSound 36.798N 121.976E",
    lat=36.798,
    lon=-121.976,
    depth_m=116.5,
    note=(
        "16 km from the ocean site; 96 kHz captures the 30-50 kHz dolphin click band; "
        "116 m mooring depth gives a real sound channel"
    ),
)

SEPT_2019 = Window(start="2019-09-01T00:00:00", end="2019-10-01T00:00:00", label="Sept 2019")

# The SanctSound metadata index only covers Apr-Sep 2019, so the acoustic side cannot be
# pushed past September without a different source.
ACOUSTIC_INDEX_COVERAGE = Window(start="2019-04-01", end="2019-09-09", label="Apr-Sep 2019")

# GLORYS12V1 dataset ids, resolved via `copernicusmarine describe`.
GLORYS_DATASETS = {
    "daily": "cmems_mod_glo_phy_my_0.083deg_P1D-m",
    "monthly": "cmems_mod_glo_phy_my_0.083deg_P1M-m",
}

ALL = field(default=None)
