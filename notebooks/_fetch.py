"""A fetch that never dies in a room.

The single most reliable way to end a data workshop is to depend on a live network.
Not because the APIs are bad -- they are good -- but because *workshop* networks are
throttled, firewalled, or shared with thirty other laptops doing the same thing at
once.

So every request in these notebooks goes through :func:`get`, which:

  1. tries the network,
  2. on success, writes the response to ``notebooks/.cache/`` and returns it,
  3. on *any* failure -- timeout, DNS, 5xx, rate limit -- falls back to the cached
     copy and says so, loudly, in a way that is visible in a shared room.

That means the worst case is a stale-but-real response with a printed warning, rather
than thirty tracebacks and a dead afternoon.

It also forces IPv4. Some machines resolve AAAA records but have no IPv6 route:
``curl`` races addresses and looks fine, while urllib3 waits out the full connect
timeout on the dead address before falling back -- measured here at 100x slower, with
every call taking exactly the timeout value. Notebooks get that fix for free; see
Notebook 01 for why it exists.

Cache layout::

    notebooks/.cache/<sha1>.bin      raw response bytes
    notebooks/.cache/<sha1>.meta     url, params, timestamp, content-type

Deleting ``notebooks/.cache/`` is always safe; it refills on the next run.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "notebooks" / ".cache"

# Make `import _fetch` work regardless of the kernel's working directory, and pull in
# the project's own IPv4 fix without duplicating it.
for _p in (ROOT, ROOT / "src"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from ocean_sim.http import force_ipv4  # noqa: E402

_force_ipv4_applied = force_ipv4()

# Set OCEAN_SIM_OFFLINE=1 to forbid the network entirely. Used to test the fallback
# path, and useful on a train.
OFFLINE = os.environ.get("OCEAN_SIM_OFFLINE", "").strip().lower() in ("1", "true", "yes")

_TIMEOUT = (10, 120)  # connect, read


class FetchResult:
    """A response, and an honest account of where it came from."""

    def __init__(self, content: bytes, url: str, *, live: bool, status: int = 200,
                 content_type: str = "", age_seconds: float | None = None):
        self.content = content
        self.url = url
        self.live = live
        self.status = status
        self.content_type = content_type
        self.age_seconds = age_seconds

    @property
    def text(self) -> str:
        return self.content.decode("utf-8", errors="replace")

    def __len__(self) -> int:
        return len(self.content)

    def save(self, path: str | Path) -> Path:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(self.content)
        return p

    def describe(self) -> str:
        source = "LIVE" if self.live else "CACHED"
        kb = len(self.content) / 1024
        age = "" if self.age_seconds is None else f", {self.age_seconds / 3600:.1f} h old"
        return f"{source}  {kb:,.1f} KB  HTTP {self.status}{age}"


def _key(url: str, params: dict | None) -> str:
    full = url if not params else f"{url}?{urlencode(sorted(params.items()))}"
    return hashlib.sha1(full.encode()).hexdigest()[:20]


def _paths(k: str) -> tuple[Path, Path]:
    return CACHE / f"{k}.bin", CACHE / f"{k}.meta"


def get(
    url: str,
    params: dict[str, Any] | None = None,
    *,
    refresh: bool = False,
    quiet: bool = False,
) -> FetchResult:
    """GET a URL, falling back to the cached response if the network fails.

    ``params`` is part of the cache key, so two different queries never collide.
    ``refresh=True`` forces the network even when a cache entry exists -- use it when
    teaching a query change and you want to prove the change did something.
    """
    CACHE.mkdir(parents=True, exist_ok=True)
    k = _key(url, params)
    bin_p, meta_p = _paths(k)

    if not refresh and not OFFLINE:
        try:
            import requests

            r = requests.get(url, params=params, timeout=_TIMEOUT)
            r.raise_for_status()
            bin_p.write_bytes(r.content)
            meta_p.write_text(
                json.dumps(
                    {
                        "url": url,
                        "params": params,
                        "status": r.status_code,
                        "content_type": r.headers.get("Content-Type", ""),
                        "ts": time.time(),
                    },
                    indent=2,
                )
            )
            if not quiet:
                print(f"  {FetchResult(r.content, url, live=True, status=r.status_code).describe()}")
            return FetchResult(
                r.content, url, live=True, status=r.status_code,
                content_type=r.headers.get("Content-Type", ""),
            )
        except Exception as exc:
            reason = f"{type(exc).__name__}: {exc}"
    elif OFFLINE:
        reason = "offline mode (OCEAN_SIM_OFFLINE=1)"

    # --- fall back to cache -------------------------------------------------
    if not bin_p.exists():
        raise RuntimeError(
            f"No cached copy and no working network for:\n  {url}\n"
            f"  failed as: {reason}\n"
            f"  Run `uv run python scripts/prefetch.py` on a working network first, "
            f"or re-run this cell once you have connectivity."
        )

    meta = json.loads(meta_p.read_text()) if meta_p.exists() else {}
    content = bin_p.read_bytes()
    ts = float(meta.get("ts", 0.0))
    age = time.time() - ts if ts else None
    if not quiet:
        when = time.strftime("%Y-%m-%d %H:%M", time.localtime(ts)) if ts else "an earlier run"
        print("  !! NETWORK UNAVAILABLE -- using cached response")
        print(f"  !!   reason : {reason}")
        print(f"  !!   fetched: {when}")
        if age is not None:
            print(f"  !!   age    : {age / 3600:.1f} hours")
        print("  !!   the numbers below are real data, but not necessarily current.")
    return FetchResult(
        content, url, live=False,
        status=int(meta.get("status", 200)),
        content_type=str(meta.get("content_type", "")),
        age_seconds=age,
    )


def fetch_bytes(url: str, params: dict | None = None, **kw) -> bytes:
    """Shorthand when only the payload matters."""
    return get(url, params, **kw).content


def erddap(base: str, var: str, index: str, *, fmt: str = "csv", server: dict | None = None):
    """Build an ERDDAP griddap URL. **The brackets must stay in the URL, not in
    ``params``** -- and that is not a style preference, see below.

    ERDDAP's index expression is part of the *parameter name*, so the wire format is::

        jplMURSST41.csv?analysed_sst[(t0):(t1)][(lat0):(lat1)][(lon0):(lon1)]

    There is no ``=`` after the index expression. ``requests``' ``params=`` argument
    cannot express this, in either direction:

      * ``{expr: None}``  -- requests **drops** the parameter entirely, so ERDDAP
        answers 500 ``destinationVariableName=... wasn't found in datasetID=...``
      * ``{expr: ""}``    -- requests emits a trailing ``=``, and ERDDAP 500s on it

    Both fail with the same opaque 500, so the cause is not obvious from the symptom.
    Hand-build the query string instead. Verified: 200, 2,647 lines.

    ``server`` may carry ``.time`` / ``.lat`` / ``.lon`` server-side directives, e.g.
    ``{"time": "first"}``, which return one column per day instead of the full cube --
    far smaller responses.
    """
    q = f"{base}.{fmt}?{var}{index}"
    for k, v in (server or {}).items():
        # Server-side directives are ``.time=first``, and the leading dot is required.
        # Omitting it returns a bare 400 with no explanation. Normalised here so a
        # notebook cannot get it wrong, and so the mistake stays visible in the code.
        name = k if k.startswith(".") else f".{k}"
        q += f"&{name}={v}"
    return q


def expect(label: str, got, want, tol: float = 0.0) -> None:
    """Assert a value is what we said it would be, loudly.

    Included because the failure mode that costs an afternoon is not a crash -- it is a
    200 response containing plausible nonsense. Every notebook states an expectation up
    front and checks it at the end, so a wrong answer is visible in three seconds rather
    than after someone has built a plot on top of it.
    """
    ok = abs(float(got) - float(want)) <= tol if tol else got == want
    mark = "ok " if ok else "!! "
    print(f"  {mark} {label}: got {got!r}, expected {want!r}")
    if not ok:
        raise AssertionError(
            f"{label}: got {got!r}, expected {want!r}. "
            f"The response is not what this notebook says it should be -- stop and "
            f"read the traps section before continuing."
        )


def expect_range(label: str, got, lo, hi) -> None:
    """Assert a physical value falls in a plausible range."""
    ok = lo <= float(got) <= hi
    mark = "ok " if ok else "!! "
    print(f"  {mark} {label}: {got} in [{lo}, {hi}]")
    if not ok:
        raise AssertionError(
            f"{label}: {got} is outside the physically plausible range [{lo}, {hi}]. "
            f"That is a decoding, unit or fill-value problem -- not oceanography."
        )


def note(text: str = "") -> None:
    """A boxed aside, for traps that need more room than a comment."""
    bar = "!" * 78
    print()
    print(bar)
    for line in text.strip().splitlines():
        print(f"! {line}")
    print(bar)
