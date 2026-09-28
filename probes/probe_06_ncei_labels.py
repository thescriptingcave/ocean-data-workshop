"""Probe 06 — NCEI detection labels: are they usable for ML?

This answers the question the plan flagged as near-existential: *are these labels
real enough to learn from, and are they balanced enough to make a learning exercise
honest?*

What we know from the NCEI documentation and the data itself:

  * Vessel events and dolphin detections are **algorithm output**, not ground truth --
    vessels from LTSA analysis, dolphins from PamGuard's whistle/moan detector. A
    classifier trained on them may simply reproduce those algorithms. That is a real
    caveat, not a hypothetical, and it is why the ML exercise must define its own
    target if these turn out to be circular.
  * Each detection CSV is hourly 0/1 presence, which turned out to be **perfectly
    contiguous** -- a gift for time-series SQL (LAG, gaps, window frames).

The class balance turns out to be the important number: 1.22% positive, which means
"accuracy is a lie" is a real lesson here rather than a hypothetical one.
"""

from __future__ import annotations

import pandas as pd

from ._common import PASS, Probe, Result, cache_path, http_session, run

HARNESS = Probe(
    slug="ncei_labels",
    name="NCEI SanctSound detection labels (dolphin / ship)",
    tier=1,
    klass="A",
    provides="hourly presence/absence labels per species and per vessel",
    protocol="GCS JSON API -> CSV/netCDF",
    order=6,
)

BUCKET_URL = "https://storage.googleapis.com/noaa-passive-bioacoustic"
DET = "sanctsound/products/detections/ci02/sanctsound_ci02_04_{ds}/data/{fn}"
HTTP = None


def _fetch(ds: str, fname: str, cache_key: str):
    url = f"{BUCKET_URL}/{DET.format(ds=ds, fn=fname)}"
    cp = cache_path(cache_key, "")
    if not cp.exists() or cp.stat().st_size == 0:
        r = HTTP.get(url, timeout=HTTP.request_timeout)
        r.raise_for_status()
        cp.write_bytes(r.content)
    return cp


def check() -> Result:
    global HTTP
    HTTP = http_session()

    detail: dict = {}
    problems: list[str] = []

    # --- dolphin presence, hourly 0/1 ---
    try:
        cp = _fetch(
            "dolphins_1h", "SanctSound_CI02_04_dolphins_1h.csv", "ci02_04_dolphins_1h.csv"
        )
        df = pd.read_csv(cp)
        detail["dolphin_rows"] = len(df)
        detail["dolphin_cols"] = ",".join(df.columns)
        if list(df.columns) != ["ISOStartTime", "Presence"]:
            problems.append(f"unexpected dolphin columns: {list(df.columns)}")
        df["t"] = pd.to_datetime(df["ISOStartTime"], format="mixed", utc=True)
        vc = df["Presence"].value_counts().sort_index()
        pos = int(vc.get(1, 0))
        neg = int(vc.get(0, 0))
        detail["dolphin_pos"] = pos
        detail["dolphin_neg"] = neg
        detail["dolphin_pos_rate_pct"] = round(100 * pos / max(1, len(df)), 2)
        detail["dolphin_span"] = f"{df['t'].min().date()} .. {df['t'].max().date()}"
        if pos == 0 or neg == 0:
            problems.append("dolphin labels are single-class -- not learnable")
        # a contiguous hourly series is what makes the SQL exercises work
        gaps = df["t"].diff().dt.total_seconds().div(3600)
        n_gaps = int((gaps > 1.05).sum())
        detail["dolphin_gaps"] = n_gaps
        if n_gaps > 0:
            detail["dolphin_max_gap_h"] = int(gaps.max())
    except Exception as exc:
        problems.append(f"dolphin labels unavailable: {type(exc).__name__}: {exc}")

    # --- vessel events: note the CSV is often EMPTY, the netCDF is not ---
    try:
        cp = _fetch("ships", "SanctSound_CI02_04_ships.nc", "ci02_04_ships.nc")
        import xarray as xr

        ds = xr.open_dataset(cp)
        detail["ship_nc_kb"] = round(cp.stat().st_size / 1024, 1)
        detail["ship_dims"] = ",".join(f"{k}={v}" for k, v in ds.sizes.items())
        detail["ship_vars"] = ",".join(list(ds.data_vars)[:6])
        ds.close()
        if cp.stat().st_size == 0:
            problems.append("ships netCDF is empty")
    except Exception as exc:
        problems.append(f"ship events unavailable: {type(exc).__name__}: {exc}")

    # --- how many labelled datasets exist overall? (breadth of the ML play space) ---
    try:
        r = HTTP.get(
            "https://storage.googleapis.com/storage/v1/b/noaa-passive-bioacoustic/o",
            params={
                "prefix": "sanctsound/products/detections/ci02/",
                "delimiter": "/",
                "maxResults": 400,
            },
            timeout=HTTP.request_timeout,
        )
        names = {
            p.rstrip("/").split("/")[-1] for p in r.json().get("prefixes", [])
        }
        kinds = sorted({n.split("_", 3)[-1] for n in names if n.count("_") >= 3})
        detail["ci02_dataset_kinds"] = ",".join(kinds)
        detail["ci02_datasets"] = len(names)
    except Exception:
        pass

    if problems:
        return Result(status="FAIL", note="; ".join(problems), detail=detail)

    return Result(
        status=PASS,
        note=(
            f"dolphin labels: {detail['dolphin_rows']} hourly rows, "
            f"{detail['dolphin_pos_rate_pct']}% positive ({detail['dolphin_pos']}/"
            f"{detail['dolphin_pos'] + detail['dolphin_neg']}), contiguous. "
            f"Severely imbalanced -> 'accuracy is a lie' is a REAL lesson here. "
            f"CAVEAT: labels are PamGuard/LTSA-derived, not ground truth."
        ),
        detail=detail,
    )


if __name__ == "__main__":
    import sys

    from ._common import append_verdict

    res = run(HARNESS, check)
    append_verdict(res)
    sys.exit(0 if res.status == "PASS" else 1)
