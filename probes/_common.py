"""Shared helpers for Phase -1 access probes.

A probe is the lightest thing that proves we can get a dataset. Most are a single
request; a few need a login. The only shared machinery worth having is:

  * a cache directory, so a probe never re-downloads the same bytes twice
  * a verdict format that both a human and ``run_all.py`` can read

Design rules (from the plan):
  * never write a probe heavier than it needs to be
  * cache everything under ~/.cache/ocean-sim-harness/ and reuse it later
  * no Postgres, no schema, no plotting in a probe -- fetch and report only
"""

from __future__ import annotations

import json
import sys
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path

CACHE = Path.home() / ".cache" / "ocean-sim-harness"
PROJECT = Path(__file__).resolve().parent.parent
ARTIFACTS = PROJECT / "probes" / "_artifacts"

# Primary working site: Monterey Bay, California.
# Chosen for strong upwelling, real thermocline movement, and good data coverage
# across every source in the inventory.
SITE = {
    "name": "Monterey Bay, CA",
    "lat": 36.70,
    "lon": -122.10,
    "bbox": (35.5, -123.5, 38.0, -121.0),  # lat_min, lon_min, lat_max, lon_max
}

# Access taxonomy. This is the column that matters in the inventory.
ACCESS_CLASSES = {
    "A": "Anonymous HTTP. No account, no key.",
    "B": "Anonymous but non-HTTP protocol (FTP, OPeNDAP, THREDDS).",
    "C": "Free account, password login, no key issued.",
    "D": "Free account + explicit API key / token.",
    "E": "Account + terms acceptance or approval required.",
    "F": "Manual request - email, form, or a person.",
    "G": "Licensed. Free academic, commercial/redistribution prohibited.",
    "H": "Unavailable.",
}

PASS, FAIL, WARN = "PASS", "FAIL", "WARN"


# ---------------------------------------------------------------------------
# HTTP session
# ---------------------------------------------------------------------------
# The implementation lives in ocean_sim.http so that src/ocean_sim does not have to
# import from probes/ -- the dependency was the wrong way round. Re-exported here for
# the probes' convenience.

def force_ipv4() -> bool:
    from ocean_sim.http import force_ipv4 as _f

    return _f()


def http_session(*args, **kwargs):
    from ocean_sim.http import http_session as _s

    return _s(*args, **kwargs)


def cache_path(key: str, suffix: str = "") -> Path:
    """Return a cache path, creating parent dirs. Caller skips if the file exists."""
    safe = key.replace("/", "_").replace(":", "_")
    p = CACHE / (safe + suffix)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def artifact_path(slug: str, name: str) -> Path:
    p = ARTIFACTS / slug
    p.mkdir(parents=True, exist_ok=True)
    return p / name


@dataclass
class Probe:
    """One dataset access check."""

    slug: str
    name: str
    tier: int
    klass: str  # A-H
    provides: str
    protocol: str
    setup: str = "none"
    order: int = 99


@dataclass
class Result:
    slug: str = ""  # filled in by run()
    status: str = PASS
    note: str = ""
    seconds: float = 0.0
    detail: dict = field(default_factory=dict)

    def render(self) -> str:
        if not self.detail:
            return f"{self.status:<4} {self.slug:<22} {self.note}"
        bits = [f"{k}={v}" for k, v in self.detail.items() if v is not None]
        extra = ("  (" + ", ".join(bits) + ")") if bits else ""
        return f"{self.status:<4} {self.slug:<22} {self.note}{extra}"


def header(p: Probe) -> None:
    print(f"\n=== probe: {p.slug} — {p.name}")
    print(f"    class {p.klass}: {ACCESS_CLASSES[p.klass]}")
    print(f"    provides: {p.provides}")
    print(f"    protocol: {p.protocol}   setup: {p.setup}")


def run(p: Probe, fn) -> Result:
    """Execute a probe function, timing it and capturing failure as data."""
    header(p)
    t0 = time.perf_counter()
    try:
        res = fn()
        res.slug = p.slug
        res.seconds = time.perf_counter() - t0
        if not res.note:
            res.status = WARN
            res.note = "ran but returned no note"
    except Exception as exc:
        res = Result(
            slug=p.slug,
            status=FAIL,
            note=f"{type(exc).__name__}: {exc}",
            seconds=time.perf_counter() - t0,
        )
        traceback.print_exc(limit=2, file=sys.stderr)
    print(f"    -> {res.render()}")
    return res


def append_verdict(result: Result) -> None:
    """Append a machine-readable line to probes/RESULTS.jsonl.

    ``default=str`` matters: probe details routinely contain datetimes, Decimals and
    numpy scalars, and this function is called *outside* run()'s try/except, so a
    serialisation error here would kill the whole suite rather than fail one probe.
    """
    p = PROJECT / "probes" / "RESULTS.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a") as fh:
        fh.write(
            json.dumps(
                {
                    "slug": result.slug,
                    "status": result.status,
                    "note": result.note,
                    "seconds": round(result.seconds, 2),
                    "detail": result.detail,
                },
                default=str,
            )
            + "\n"
        )
