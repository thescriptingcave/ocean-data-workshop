# ruff: noqa: N806  -- X, y, Xv, yv are the standard sklearn/pandas names for the
# design matrix and target. Renaming them to satisfy a style rule would make this
# file less recognisable as the ML code it is.
"""Is the MB01 detection task real, or circular?

The open question from the plan: NOAA's labels are *algorithm output* -- vessel events from
LTSA analysis, dolphin detections from PamGuard. Training on them risks reproducing the
algorithm rather than learning anything.

There is a second, sharper problem specific to this pairing. The detections are derived
from LTSAs; the hourly third-octave levels are *also* derived from LTSAs. So predicting a
detection from a band level is close to predicting a quantity from itself. That is
circular by construction, and the way to find out is not to argue about it but to measure
how well the obvious feature does.

**The test:** can a one-line rule get ~99%? If a single band separates the classes, the
task teaches nothing. If a small model does modestly better than the trivial rule, the
task is real.

This script runs that test and reports the numbers, whichever way they fall.

Run:  uv run python scripts/ml_triviality.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ocean_data_workshop.data import ncei

SITE = "mb01"
DEPLOYMENTS = ["02", "03", "04", "05"]  # these carry both ships and dolphins_1h
N_BOOT = 600


def _detection_series(path, want: str) -> pd.Series | None:
    """Read a SanctSound detection netCDF as an hourly 0/1 presence series.

    Structure notes, all of which are easy to get wrong:

    * ``time`` is a bare dimension with **no coordinate values**. The real timestamps
      live in ``time_stamp``, which is an **ISO-8601 string** despite its ``units``
      attribute claiming ``milliseconds``. ``start_time``/``end_time`` are genuine
      datetime64 but describe event bounds, not the sample grid.
    * ``ships`` is an **event list**: every row is a detection, so the presence column is
      all 1s. It is not an hourly presence/absence series and cannot be turned into one
      without the full hourly grid. ``dolphins_1h`` *is* a full 0/1 series.
      That difference makes them different problem shapes, not two versions of one task.
    """
    import xarray as xr

    d = xr.open_dataset(path)
    vname = next((v for v in d.data_vars if want in v.lower()), None)
    if vname is None:
        return None
    raw = d[vname].to_numpy()
    stamps = d["time_stamp"].to_numpy()
    idx = pd.to_datetime(pd.Index(stamps).str.slice(0, 19), errors="coerce")
    s = pd.Series(pd.to_numeric(raw, errors="coerce").astype("float64"), index=idx)
    s = s[s.index.notna()].groupby(level=0).max()
    return s.dropna()


def load_labels(dep: str) -> dict:
    """Presence/absence labels for ships and dolphins, keyed by hour."""
    out = {}
    for kind, dsuffix, var in (
        ("ships", "ships", "ships_presence"),
        ("dolphin", "dolphins_1h", "dolphin_presence"),
    ):
        prefix = (
            f"sanctsound/products/detections/{SITE}/"
            f"sanctsound_{SITE}_{dep}_{dsuffix}/data/"
        )
        try:
            _, items = ncei.list_prefix(prefix)
        except Exception as exc:
            print(f"  (no {kind} labels for {dep}: {type(exc).__name__})")
            continue
        nc = next((i["name"] for i in items if i["name"].endswith(".nc")), None)
        if nc is None:
            continue
        try:
            s = _detection_series(ncei.fetch(nc, "data/acoustic"), var)
            if s is not None and len(s):
                out[kind] = s
        except Exception as exc:
            print(f"  (no {kind} labels for {dep}: {type(exc).__name__}: {exc})")
    return out


def load_bands(dep: str) -> pd.DataFrame | None:
    try:
        ds = ncei.load_sound_levels(SITE, f"{dep}_tol_1h")
    except FileNotFoundError:
        return None
    return pd.DataFrame(
        ds.sound_pressure_levels.values,
        index=pd.to_datetime(ds.time.values).floor("h"),
        columns=[float(f) for f in ds.frequency.values],
    )


def main() -> int:
    print("loading labels and band levels ...")
    label_frames, band_frames = {}, {}
    for dep in DEPLOYMENTS:
        lab = load_labels(dep)
        bands = load_bands(dep)
        if not lab or bands is None:
            continue
        for k, v in lab.items():
            label_frames.setdefault(k, []).append(v)
        band_frames[dep] = bands
        print(f"  mb01_{dep}: {len(bands)} hourly band rows, labels {list(lab)}")

    labels = {k: pd.concat(v).sort_index() for k, v in label_frames.items()}
    bands = pd.concat(band_frames.values()).sort_index()
    bands = bands[~bands.index.duplicated(keep="first")]

    print("\n--- label balance ---")
    for k, s in labels.items():
        pos = float(s.sum())
        print(f"  {k:8} n={len(s):6d} hours  positive {int(pos):5d} ({100 * pos / len(s):5.2f}%)")

    # align EACH target independently -- ships is a sparse event list, so intersecting
    # all labels at once collapses the overlap to a single hour
    print("\n--- per-target alignment with band levels ---")
    aligned = {}
    results: dict = {}
    for k, s in labels.items():
        idx = bands.index.intersection(s.index)
        if len(idx) == 0:
            print(f"  {k}: no overlap with bands")
            continue
        y = s.loc[idx].astype(int)
        counts = y.value_counts()
        if len(counts) < 2:
            print(f"  {k}: single class ({counts.to_dict()}) -- event list, not a "
                  f"classification target. Skipping.")
            continue
        aligned[k] = (bands.loc[idx], y)
        print(f"  {k}: {len(idx)} hours, {100 * counts.get(1, 0) / len(y):.2f}% positive")
    if not aligned:
        print("  nothing to test")
        return 1

    for k, (X, y) in aligned.items():
        base = max((y == 0).mean(), (y == 1).mean())
        print(f"\n=== target: {k} (n={len(y)}, majority-class baseline = {base:.3f}) ===")
        best = []
        for f in X.columns:
            r = np.corrcoef(X[f], y)[0, 1]
            best.append((abs(r), r, f))
        best.sort(reverse=True)
        for _ar, r, f in best[:5]:
            thr = np.median(X[f])
            acc = max(
                float(((X[f] > thr) == (y == 1)).mean()),
                float(((X[f] <= thr) == (y == 1)).mean()),
            )
            print(f"  single band {f:>8.0f} Hz: r={r:+.3f}  one-threshold accuracy={acc:.3f}")
        best_band = best[0][2]
        results[k] = {
            "baseline": base,
            "best_band": best_band,
            "best_band_acc": max(
                float(((X[best_band] > X[best_band].median()) == (y == 1)).mean()),
                float(((X[best_band] <= X[best_band].median()) == (y == 1)).mean()),
            ),
        }

    print("\n" + "=" * 74)
    for k, r in results.items():
        verdict = (
            "TRIVIAL -- teaches nothing"
            if r["best_band_acc"] > 0.97
            else "informative"
        )
        print(f"{k}: best single band {r['best_band']:.0f} Hz reaches "
              f"{r['best_band_acc']:.3f} accuracy vs majority baseline {r['baseline']:.3f}"
              f"  -> {verdict}")

    # --- the real test: can ALL the bands together solve it? ---
    # Single-band weakness does not settle circularity. If a model on the full spectrum
    # reaches ~1.0, the labels are recoverable from the same LTSA the bands came from and
    # the task is circular. If it plateaus well short, there is genuine signal that the
    # detector used and these bands do not.
    #
    # Split by TIME, not randomly. A random split on hourly acoustic data puts adjacent
    # hours on both sides, and adjacent hours are near-duplicates -- the model scores well
    # by memorising the record rather than by generalising, which is the most common way a
    # time-series model looks brilliant and is worthless.
    print("\n" + "=" * 74)
    print("full-spectrum model, TIME-BASED split (last 25% held out)")
    print("=" * 74)
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import (
    accuracy_score,
    precision_recall_fscore_support,
    precision_score,
)

    for k, (X, y) in aligned.items():
        if len(y) < 1000 or y.value_counts().min() < 50:
            continue
        Xv = X.to_numpy()
        yv = y.to_numpy()
        cut = int(len(Xv) * 0.75)
        Xtr, Xte, ytr, yte = Xv[:cut], Xv[cut:], yv[:cut], yv[cut:]
        if len(np.unique(yte)) < 2:
            continue
        base = max((yte == 0).mean(), (yte == 1).mean())
        print(f"\n  target {k}: train {len(ytr)}, test {len(yte)}, "
              f"test majority baseline {base:.3f}")
        for name, model in (
            ("logistic", LogisticRegression(max_iter=2000)),
            ("random forest", RandomForestClassifier(
                n_estimators=200, random_state=0, n_jobs=-1)),
        ):
            model.fit(Xtr, ytr)
            pred = model.predict(Xte)
            acc = accuracy_score(yte, pred)
            p, rc, f1, _ = precision_recall_fscore_support(
                yte, pred, average="binary", zero_division=0
            )
            print(f"    {name:15} acc={acc:.3f}  precision={p:.3f}  "
                  f"recall={rc:.3f}  f1={f1:.3f}")

        # --- the lesson: a random split flatters the model ---
        # Hourly acoustics are autocorrelated at ~10-24 h, so a random split puts
        # near-duplicate hours on both sides. The model scores well by memorising the
        # record rather than by generalising to new time. This is the single most common
        # way a time-series model looks brilliant and is worthless in production.
        from sklearn.model_selection import train_test_split

        Xr, Xv_, yr, yv_ = train_test_split(
            Xv, yv, test_size=0.25, random_state=0, stratify=yv
        )
        lr = LogisticRegression(max_iter=2000).fit(Xr, yr)
        rpred = lr.predict(Xv_)
        racc = accuracy_score(yv_, rpred)
        _, rr, rf1, _ = precision_recall_fscore_support(
            yv_, rpred, average="binary", zero_division=0
        )
        print(f"    {'logistic (RANDOM split)':15} acc={racc:.3f}  "
              f"precision={precision_score(yv_, rpred, zero_division=0):.3f}  "
              f"recall={rr:.3f}  f1={rf1:.3f}")
        gap = racc - acc
        print(f"    -> random split {'OVERSTATES' if gap > 0 else 'DID NOT OVERSTATE'} "
              f"accuracy ({gap:+.3f} vs the time split).")
        if gap <= 0:
            print("       The expected leakage effect is absent here, and the comparison is")
            print("       confounded: the time-split test set is more class-imbalanced")
            print(f"       (majority {base:.3f}) than the stratified random one, which")
            print("       flatters accuracy on its own. A clean test would hold the test")
            print("       set fixed and vary only the splitting rule.")
        print(f"    (accuracy alone would be {base:.3f} by always guessing the majority)")

    print(
        "\nIf a full model approaches 1.0, the labels are recoverable from the same LTSA\n"
        "the bands came from and the task is circular. A plateau well short of 1.0 means\n"
        "the detector used information these bands do not contain -- a real, if imperfect,\n"
        "learning problem."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
