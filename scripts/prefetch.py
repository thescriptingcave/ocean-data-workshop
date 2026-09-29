"""Warm the notebook cache so the workshop itself makes no network calls it depends on.

Run once before the session, on a working network:

    uv run python scripts/prefetch.py

Every response the notebooks need is listed in ``notebooks/_sources.py::manifest``, which
the notebooks also import -- so the cached response is guaranteed to be the one the
notebook asks for. A prefetch that drifted from the notebooks would be worse than none,
because it would fail silently.

The whole point is that venue wifi is the one thing you cannot control and the one
thing that ends workshops. If the cache is warm and the network dies, every notebook
still runs, prints a loud warning, and produces correct (if slightly stale) numbers.

Not prefetched: Copernicus Marine (Notebook 05). It authenticates per user, and
caching someone's credentials on a shared laptop is not a trade worth making. That
notebook has its own degradation path.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "notebooks"))
sys.path.insert(0, str(ROOT / "src"))

from _fetch import CACHE, describe, session  # noqa: E402
from _sources import manifest  # noqa: E402

ARCHIVE = ROOT / "notebooks" / "cache-archive.tar.gz"


def install_archive() -> bool:
    """Unpack a shipped cache archive, if one is present. Lets the workshop run with no
    network at all, which is the difference between 'probably fine' and 'verified'."""
    if not ARCHIVE.exists():
        return False
    import tarfile

    CACHE.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(ARCHIVE, "r:gz") as tf:
        tf.extractall(CACHE.parent, filter="data")
    n = len(list(CACHE.glob("*.bin")))
    print(f"  installed {n} cached responses from {ARCHIVE.name} "
          f"({ARCHIVE.stat().st_size / 1e6:.1f} MB)")
    return n > 0


def main() -> int:
    if "--install" in sys.argv:
        if install_archive():
            print("  done. The notebooks no longer need a network.")
            return 0
        print(f"  no archive at {ARCHIVE}")
        return 1

    items = manifest()
    print("=" * 72)
    print(f"  prefetching {len(items)} responses for the notebooks")
    print("=" * 72)

    refresh = "--refresh" in sys.argv
    http = session()

    ok, failed, total_bytes = 0, [], 0
    t0 = time.time()
    for label, url, params in items:
        try:
            # Not refresh by default. refresh=True is what guarantees a prefetch never
            # passes a stale entry off as fresh -- correct before a workshop on a
            # machine with a network, but fatal on a machine without one, where every
            # call would raise. The archive below is the offline story instead.
            r = http.get(url, params=params)
            total_bytes += len(r.content)
            print(f"  ok   {label:24} {len(r.content):>10,} B  {describe(r)}")
            ok += 1
        except Exception as exc:
            print(f"  FAIL {label:24} {type(exc).__name__}: {str(exc)[:70]}")
            failed.append(label)

    print("-" * 72)
    print(f"  {ok}/{len(items)} cached, {total_bytes / 1e6:.1f} MB, {time.time() - t0:.0f} s")
    if not refresh:
        print("  (using existing cache where present; pass --refresh to force downloads)")
    if failed:
        print(f"\n  not cached: {', '.join(failed)}")
        print("  The notebooks that need these will make a live call instead, and will")
        print("  say so. Everything else is safe offline.")

    print("\n  test it:  OCEAN_SIM_OFFLINE=1 uv run jupyter lab notebooks/\n")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
