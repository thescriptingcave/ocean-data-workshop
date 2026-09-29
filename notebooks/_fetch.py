"""A real ``requests.Session`` that caches to disk.

The point of this module is what it *doesn't* do. An earlier version wrapped requests in
a ``_fetch.get()`` function that returned a custom ``FetchResult``, and every notebook
called that. It made the workshop robust, and it made the workshop useless: nobody
learned ``requests``, and the parsing of a response into a DataFrame was buried in a
return type instead of being taught.

So the only thing that changes here is ``Session.send``. Everything else -- ``.text``,
``.content``, ``.json()``, ``.status_code``, ``.raise_for_status()``, ``params=``,
``headers=`` -- is genuine ``requests``, and the code in the notebooks is code you would
write in your own project.

The cache exists because venue wifi is the one thing you cannot control and the one
thing that ends a data workshop. It is implemented where a proxy would sit, so it is
invisible at the call site: a successful request is written to disk, and *any* failure --
timeout, DNS, 5xx, rate limit -- is served from disk with a loud warning. The worst case
is a stale-but-real response, not thirty tracebacks.

It also forces IPv4, because some machines resolve AAAA records but have no IPv6 route,
where ``requests`` waits out the full connect timeout on the dead address. ``curl`` races
address families and looks healthy while doing it. Measured 100x. See Notebook 01.

Usage in every notebook::

    http = _fetch.session()          # a real requests.Session
    r = http.get(url)                # real requests
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text), skiprows=[1])
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "notebooks" / ".cache"

# Make `import _fetch` work regardless of the kernel's working directory, and pull in
# the project's own IPv4 fix without duplicating it.
for _p in (ROOT, ROOT / "src"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from ocean_sim.http import force_ipv4  # noqa: E402

_IPV4_APPLIED = force_ipv4()

# Set OCEAN_SIM_OFFLINE=1 to forbid the network entirely. Used to test the fallback
# path, and useful on a train.
OFFLINE = os.environ.get("OCEAN_SIM_OFFLINE", "").strip().lower() in ("1", "true", "yes")

_TIMEOUT = (10, 120)  # connect, read


def _key(url: str, params: dict | None) -> str:
    full = url if not params else f"{url}?{urlencode(sorted(params.items()))}"
    return hashlib.sha1(full.encode()).hexdigest()[:20]


def _paths(k: str) -> tuple[Path, Path]:
    return CACHE / f"{k}.bin", CACHE / f"{k}.meta"


def _warn_cached(url: str, reason: str, meta: dict, age: float | None) -> None:
    when = (time.strftime("%Y-%m-%d %H:%M", time.localtime(meta["ts"]))
            if meta.get("ts") else "an earlier run")
    print("  !! NETWORK UNAVAILABLE -- serving the cached response")
    print(f"  !!   reason : {reason}")
    print(f"  !!   fetched: {when}")
    if age is not None:
        print(f"  !!   age    : {age / 3600:.0f} h")
    print("  !!   the numbers below are real data, but not necessarily current.")


def session():
    """Return a caching ``requests.Session``.

    Everything about this object is standard ``requests``. ``send`` is overridden --
    that is the single seam -- and that is all.
    """
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry

    class CachedSession(requests.Session):
        """A real requests.Session. Only ``send`` is overridden, to add a disk cache.

        Because ``send`` is the last step before the socket, the caching is invisible at
        the call site: you write ordinary requests code and get a cache.
        """

        def send(self, request, **kwargs):
            kwargs.setdefault("timeout", _TIMEOUT)
            k = _key(request.url, None)
            bin_p, meta_p = _paths(k)

            if not OFFLINE:
                try:
                    resp = super().send(request, **kwargs)
                    resp.raise_for_status()
                    CACHE.mkdir(parents=True, exist_ok=True)
                    bin_p.write_bytes(resp.content)
                    meta_p.write_text(json.dumps({
                        "url": request.url,
                        "status": resp.status_code,
                        "content_type": resp.headers.get("Content-Type", ""),
                        "encoding": resp.encoding,
                        "ts": time.time(),
                    }, indent=2))
                    return resp
                except Exception as exc:
                    reason = f"{type(exc).__name__}: {str(exc).splitlines()[0][:80]}"
            else:
                reason = "offline mode (OCEAN_SIM_OFFLINE=1)"

            if not bin_p.exists():
                raise requests.exceptions.ConnectionError(
                    f"No cached response and no working network for:\n  {request.url}\n"
                    f"  failed as: {reason}\n"
                    f"  On a connected machine run: uv run python scripts/prefetch.py"
                )

            meta = json.loads(meta_p.read_text()) if meta_p.exists() else {}
            ts = float(meta.get("ts", 0.0))
            age = (time.time() - ts) if ts else None
            _warn_cached(request.url, reason, meta, age)

            # Rebuild a genuine Response so callers keep the whole requests API.
            cached = requests.Response()
            cached.status_code = int(meta.get("status", 200))
            cached._content = bin_p.read_bytes()
            cached.headers["Content-Type"] = meta.get("content_type", "")
            cached.encoding = meta.get("encoding") or "utf-8"
            cached.url = request.url
            cached.request = request
            # Mark the provenance. describe() reads this, and without it the prefetch
            # reported "LIVE" for every entry even with OCEAN_SIM_OFFLINE=1 -- an
            # output that lies about where the data came from is worse than no output.
            cached._from_cache = True
            cached._cached_age = age
            return cached

    sess = CachedSession()
    retry = Retry(total=3, backoff_factor=0.6,
                  status_forcelist=(429, 500, 502, 503, 504),
                  allowed_methods=frozenset({"GET", "HEAD"}), raise_on_status=False)
    sess.mount("https://", HTTPAdapter(max_retries=retry))
    sess.mount("http://", HTTPAdapter(max_retries=retry))
    return sess


def describe(r) -> str:
    """One line about a response, for logging. Handy when sweeping many URLs.

    Reports CACHED when the response came off disk, which is the thing you want to know
    when you are deciding whether the workshop can survive without a network.
    """
    if getattr(r, "_from_cache", False):
        age = getattr(r, "_cached_age", None)
        stamp = f", {age / 3600:.0f} h old" if age is not None else ""
        return f"CACHED  {len(r.content) / 1024:,.1f} KB  HTTP {r.status_code}{stamp}"
    return f"LIVE    {len(r.content) / 1024:,.1f} KB  HTTP {r.status_code}"


def erddap(base: str, var: str, index: str, *, fmt: str = "csv", server: dict | None = None):
    """Build an ERDDAP griddap URL. **The brackets stay in the URL, not in ``params=``** --
    and that is not a style preference.

    ERDDAP's index expression is part of the *parameter name*, so the wire format is::

        jplMURSST41.csv?analysed_sst[(t0):(t1)][(lat0):(lat1)][(lon0):(lon1)]

    with no ``=`` after it. ``requests``' ``params=`` cannot express this, in either
    direction:

      * ``{expr: None}``  -- requests **drops** the parameter entirely, so ERDDAP
        answers 500 ``destinationVariableName=... wasn't found``
      * ``{expr: ""}``    -- requests emits a trailing ``=``, and ERDDAP 500s on it

    Both fail with the same opaque 500, so the cause is not obvious from the symptom.
    Hand-build the query string. Verified: 200, 2,647 lines.

    ``server`` may carry server-side directives such as ``{"time": "first"}``. They need
    a leading dot or ERDDAP answers 400 -- see Notebook 01 for what they actually do,
    which is mostly nothing.
    """
    q = f"{base}.{fmt}?{var}{index}"
    for k, v in (server or {}).items():
        q += f"&{k if k.startswith('.') else f'.{k}'}={v}"
    return q


def expect(label: str, got, want, tol: float = 0.0, rtol: float = 0.0) -> None:
    """Assert a value is what the notebook said it would be, loudly.

    Included because the failure mode that costs an afternoon is not a crash -- it is a
    200 OK containing plausible nonsense. Every notebook states an expectation up front
    and checks it at the end, so a wrong answer is visible in three seconds rather than
    after someone has plotted it.

    ``tol`` is an **absolute** allowance and ``rtol`` is a **fraction of** ``want``. They
    are separate arguments on purpose: a single ``tol=0.01`` that silently means
    "within one hundredth of a unit" was a footgun, and it did fail silently for exactly
    that reason -- ``abs(133960 - 134020) = 60``, which is not <= 0.01.

    Use ``rtol`` for anything a live service generates (byte counts, timestamps, ids) and
    ``tol`` for anything you control.
    """
    # Only coerce to float when a tolerance is actually being applied. `want` is
    # legitimately a list or a string in several assertions, and float() on those is a
    # TypeError rather than a comparison.
    if rtol or tol:
        diff = abs(float(got) - float(want))
        ok = diff <= (abs(float(want)) * rtol if rtol else tol)
    else:
        ok = got == want
    print(f"  {'ok ' if ok else '!! '} {label}: got {got!r}, expected {want!r}")
    if not ok:
        raise AssertionError(
            f"{label}: got {got!r}, expected {want!r}. The response is not what this "
            f"notebook says it should be -- stop and read the traps section first."
        )


def expect_range(label: str, got, lo, hi) -> None:
    """Assert a physical value falls in a plausible range."""
    ok = lo <= float(got) <= hi
    print(f"  {'ok ' if ok else '!! '} {label}: {got} in [{lo}, {hi}]")
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
