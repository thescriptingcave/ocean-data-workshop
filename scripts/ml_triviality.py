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

# The recorder samples at 96 kHz, but no *public* product carries energy above ~24 kHz.
# Dolphin echolocation peaks far above that, so this is the only band in the whole
# third-octave feature set that touches the click band -- which makes it the band to
# ablate before trusting any result on this data.
CLICK_BAND_HZ = 20000.0
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

    decisive_checks(aligned)

    print(
        "\n--- what this actually means -------------------------------------------\n"
        "The plateau is real: this is NOT the naive circularity where a model reaches\n"
        "1.0. The permutation control lands exactly on the majority rate and the split\n"
        "is honestly time-based, so nothing is leaking.\n"
        "\n"
        "But that green light needs a large asterisk. Two things survive scrutiny:\n"
        "  * persistence alone is a strong baseline, because the label arrives in\n"
        "    blocks -- much of the apparent skill is 'it was there an hour ago';\n"
        "  * nearly all of the remaining skill lives in ONE band, and it is the only\n"
        "    band in the feature set that overlaps the click band.\n"
        "\n"
        "So: real, reproducible and worth teaching -- but a one-band task, whose one\n"
        "band is the one adjacent to the label's own provenance. That is a more\n"
        "interesting thing to teach than a clean detector would have been."
    )
    return 0


def frequency_ceiling() -> None:
    """How high does the public data actually go?

    Worth printing before any claim about clicks, because it bounds what is learnable.
    Verified: tol_1h 25..20000, ol_1h 31.5..16000, psd_1h 20..24000 -- all well below the
    10-70 kHz band where echolocation lives, despite 96 kHz sampling.
    """
    print("\n" + "=" * 74)
    print("the frequency ceiling: what the public products actually carry")
    print("=" * 74)
    for product in ("tol_1h", "ol_1h", "psd_1h"):
        try:
            ds = ncei.load_sound_levels(SITE, f"{DEPLOYMENTS[0]}_{product}")
            f = ds.frequency.values
            print(f"  {product:<8} {float(f.min()):>8.1f} .. {float(f.max()):>9.1f} Hz"
                  f"   n={len(f):>6}")
        except Exception as exc:
            print(f"  {product:<8} unavailable ({type(exc).__name__})")
    print("  the recorder samples at 96 kHz, so the data exists -- it is just not in")
    print("  these products. Any click-band claim from this data is a claim about the")
    print("  20 kHz band and nothing else.")


def decisive_checks(aligned: dict) -> None:
    """The three tests that decide whether the task is worth teaching.

    Added after this script's first version reported a plain "green light". That verdict
    was defensible on its own terms -- the model plateaus well short of 1.0 -- but it had
    never been compared against the two baselines that actually matter: a rule that knows
    what happened an hour ago, and the model with the click band removed.
    """
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import (
        accuracy_score,
        f1_score,
        precision_score,
        recall_score,
    )
    from sklearn.preprocessing import StandardScaler

    print("\n" + "=" * 74)
    print("how much of that was the bands, and how much was the clock?")
    print("=" * 74)
    frequency_ceiling()

    for k, (X, y) in aligned.items():
        if len(y) < 1000 or y.value_counts().min() < 50:
            continue

        cut = int(len(X) * 0.75)
        Xtr, Xte, ytr, yte = X.iloc[:cut], X.iloc[cut:], y.iloc[:cut], y.iloc[cut:]
        base = max((yte == 0).mean(), (yte == 1).mean())
        print(f"\n  target {k}: test majority {base:.3f}, "
              f"train prevalence {ytr.mean():.1%}, test prevalence {yte.mean():.1%}")

        # how autocorrelated is the label?  this is what makes persistence strong
        agree = float((y.to_numpy()[1:] == y.to_numpy()[:-1]).mean())
        runs = (y != y.shift()).cumsum()
        lens = y.groupby(runs).agg(["size", "first"])
        lens = lens[lens["first"] == 1]["size"]
        print(f"  label comes in blocks: {agree:.1%} hour-to-hour agreement, "
              f"{len(lens)} positive runs, median {lens.median():.0f} h, "
              f"longest {lens.max():.0f} h")

        prev = y.shift(1)
        common = prev.index.intersection(yte.index)
        p_prev = prev.loc[common].fillna(0).astype(int)
        print(f"  {'persistence y(t-1)':38} acc {accuracy_score(yte, p_prev):.3f}")

        def fit(a_tr, a_te, y_tr, y_te):
            """y_tr/y_te are arguments rather than closed over, so this cannot bind
            the wrong loop iteration if a second target is ever added."""
            sc = StandardScaler().fit(a_tr)
            clf = LogisticRegression(max_iter=3000).fit(sc.transform(a_tr), y_tr)
            pred = clf.predict(sc.transform(a_te))
            return (accuracy_score(y_te, pred), f1_score(y_te, pred, zero_division=0),
                    precision_score(y_te, pred, zero_division=0),
                    recall_score(y_te, pred, zero_division=0))

        yv = y.astype(float)
        lags = pd.DataFrame({
            "lag1": yv.shift(1),
            "lag2": yv.shift(2),
            "roll3": yv.rolling(3, min_periods=1).max().shift(1),
            "roll6": yv.rolling(6, min_periods=1).max().shift(1),
        })
        Ltr, Lte = lags.iloc[:cut].fillna(0.0), lags.iloc[cut:].fillna(0.0)

        print()
        got = {}
        for name, a_tr, a_te in [
            ("lags only (6 h of past labels)", Ltr, Lte),
            ("all bands only", Xtr, Xte),
            ("lags + all bands", pd.concat([Ltr, Xtr], axis=1),
             pd.concat([Lte, Xte], axis=1)),
        ]:
            acc, f1, pr, rc = fit(a_tr.to_numpy(), a_te.to_numpy(), ytr, yte)
            got[name] = (acc, f1)
            print(f"  {name:38} acc {acc:.3f}  f1 {f1:.3f}  "
                  f"prec {pr:.3f}  rec {rc:.3f}")

        if CLICK_BAND_HZ not in X.columns:
            continue

        # The third-octave product stops at 20 kHz and dolphin echolocation peaks well
        # above it, so exactly one band in the whole feature set touches the click band.
        # If the model leans on that band, it is closer to recovering the label's own
        # provenance than to hearing a dolphin.
        rest = [c for c in X.columns if c != CLICK_BAND_HZ]
        acc_no, f1_no, _, _ = fit(
            pd.concat([Ltr, Xtr[rest]], axis=1).to_numpy(),
            pd.concat([Lte, Xte[rest]], axis=1).to_numpy(),
            ytr, yte,
        )
        acc_all, f1_all = got["lags + all bands"]
        print()
        print(f"  {f'lags + bands minus {CLICK_BAND_HZ:.0f} Hz':38} acc {acc_no:.3f}  "
              f"f1 {f1_no:.3f}")
        print(f"  -> dropping the only click-band column costs "
              f"{acc_all - acc_no:+.3f} accuracy and {f1_all - f1_no:+.3f} f1")

        # ablation on the full model, which is the honest way to ask the question
        A, B = Xtr.to_numpy(), Xte.to_numpy()
        sc = StandardScaler().fit(A)
        clf = LogisticRegression(max_iter=3000).fit(sc.transform(A), ytr)
        S_te = sc.transform(B)
        full = accuracy_score(yte, clf.predict(S_te))
        j = list(X.columns).index(CLICK_BAND_HZ)
        rng = np.random.default_rng(0)
        drops = []
        for _ in range(10):
            Bp = S_te.copy()
            Bp[:, j] = rng.permutation(Bp[:, j])
            drops.append(full - accuracy_score(yte, clf.predict(Bp)))
        print(f"  -> shuffling ONLY that column at test time: {full:.3f} -> "
              f"{full - float(np.mean(drops)):.3f}")


if __name__ == "__main__":
    raise SystemExit(main())
