"""Statistics for autocorrelated environmental time series.

Written because the obvious approach is wrong here, in a way that would have produced a
confident-looking nonsense number.

**The trap.** With 30 daily points, northerly wind appeared to lead southward current by
six days at r = -0.61. Plausible, and physically sensible -- wind stress takes days to
spin up Ekman transport. But two separate biases make a naive lag scan overstate it:

1. **Autocorrelation.** Daily ocean fields are strongly autocorrelated at the ~10-day
   timescale we already found. A naive p-value assumes independent samples, so the
   *effective* sample size is far below n. With a ~10-day correlation time and n = 30,
   n_eff is closer to 3 than 30.

2. **Selection over lags.** Scanning lag 0..6 and reporting the best one inflates the
   result regardless of correlation. Seven tests at p < 0.05 give a 30% chance of a
   spurious hit.

**The fix.** A moving-block bootstrap, which handles both simultaneously:

  * resample *blocks* of each series independently, preserving each series' own
    autocorrelation structure;
  * recompute the **max over lags** on each synthetic pair, so the null distribution
    already includes the lag-selection bias;
  * compare the observed max against that null.

Resampling the two series *independently* is deliberate: it builds a null of "no
relationship at all, each keeping its own persistence", which is the right question.

The bootstrap assumes the block length is at least as long as the dependence time; if
that is wrong the p-values are optimistic. ``estimate_block_length`` picks it from the
data rather than guessing.
"""

from __future__ import annotations

import numpy as np


def effective_n(x: np.ndarray, max_lag: int = 20) -> float:
    """Sample size adjusted for serial correlation.

    n_eff = n / (1 + 2 * sum of autocorrelations up to max_lag), Bartlett-style. Uses
    only positive correlations, because negative ones cannot reduce n_eff.
    """
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    n = x.size
    if n < 4:
        return float(n)
    y = x - x.mean()
    denom = float(np.dot(y, y))
    if denom <= 0:
        return float(n)
    total = 0.0
    for k in range(1, min(max_lag, n - 1) + 1):
        r = float(np.dot(y[:-k], y[k:]) / denom)
        if r <= 0:
            break
        total += r
    return float(n / (1.0 + 2.0 * total))


def estimate_block_length(x: np.ndarray, n_candidates: int = 12) -> int:
    """Block length for the bootstrap: twice the first lag where autocorrelation drops
    below 1/e (or 5% of the block-length grid, whichever is smaller)."""
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    n = x.size
    y = x - x.mean()
    denom = float(np.dot(y, y))
    if denom <= 0 or n < 20:
        return max(5, n // 10)
    for k in range(1, min(60, n - 1) + 1):
        r = float(np.dot(y[:-k], y[k:]) / denom)
        if r < np.exp(-1.0):
            return max(5, int(2 * k))
    return max(5, n // n_candidates)


def lag_correlations(x: np.ndarray, y: np.ndarray, max_lag: int) -> np.ndarray:
    """r for each lag. Entry k is corr(x[:-k], y[k:]) -- x leads y by k steps."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    out = np.empty(max_lag + 1)
    for k in range(max_lag + 1):
        if k == 0:
            out[k] = np.corrcoef(x, y)[0, 1]
        else:
            out[k] = np.corrcoef(x[:-k], y[k:])[0, 1]
    return out


def block_bootstrap_pvalue(
    x: np.ndarray,
    y: np.ndarray,
    max_lag: int = 10,
    n_boot: int = 2000,
    block: int | None = None,
    seed: int = 0,
) -> dict:
    """Two-sided p-value for the strongest lag relationship, null built by block resampling.

    Returns a dict with the observed per-lag correlations, the best lag, the observed
    max |r|, the bootstrap p-value, the block length used, and the effective sample size.

    **Block length is capped relative to ``max_lag``.** Estimating it from the whole
    series is wrong here: daily SST has a ~200-day seasonal dependence, so an
    uncapped estimate picks a 206-day block while we are testing 10-day lags. A block
    that long preserves far more structure than the test needs, which makes the null too
    narrow and the p-values *anticonservative* -- it manufactures significance. The block
    only has to be as long as the dependence at the lag scale being examined, so it is
    capped at 4x max_lag.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    keep = np.isfinite(x) & np.isfinite(y)
    x, y = x[keep], y[keep]
    n = x.size
    if n < 30:
        raise ValueError(f"need at least 30 paired points, got {n}")

    if block is None:
        block = max(
            estimate_block_length(x), estimate_block_length(y)
        )
    # Cap to the lag scale under test, and floor at 2x max_lag so the block still spans
    # the dependence that generates the lagged correlations.
    block = int(min(block, 4 * max_lag))
    block = int(max(block, min(2 * max_lag, max(n // 4, 5))))
    block = int(min(max(block, 5), max(n // 4, 5)))
    n_blocks = int(np.ceil(n / block))

    observed = lag_correlations(x, y, max_lag)
    best = int(np.argmax(np.abs(observed)))
    obs_max = float(np.abs(observed[best]))

    rng = np.random.default_rng(seed)
    null_max = np.empty(n_boot)
    n_starts = n - block + 1
    for b in range(n_boot):
        # Sample *element start offsets*, not block indices, so every block is exactly
        # `block` long. Indexing with block units instead makes trailing slices run off
        # the end of the array, and because the two series draw different offsets the
        # resampled pair ends up different lengths -- which silently corrupts the null.
        xs = np.concatenate(
            [x[s : s + block] for s in rng.integers(0, n_starts, n_blocks)]
        )[:n]
        ys = np.concatenate(
            [y[s : s + block] for s in rng.integers(0, n_starts, n_blocks)]
        )[:n]
        if xs.size != n or ys.size != n:
            continue  # cannot happen once blocks are length-exact, but never test a
            #            pair of mismatched lengths
        null_max[b] = np.abs(lag_correlations(xs, ys, max_lag)).max()
    null_max = null_max[np.isfinite(null_max)]

    # add-one smoothing: the bootstrap p-value is never exactly 0
    p = float((1 + np.sum(null_max >= obs_max)) / (1 + n_boot))
    return {
        "n": int(n),
        "lags": list(range(max_lag + 1)),
        "r": [round(float(v), 3) for v in observed],
        "best_lag": best,
        "obs_max_abs_r": round(obs_max, 3),
        "p_boot": round(p, 4),
        "block": block,
        "n_eff_x": round(effective_n(x), 1),
        "n_eff_y": round(effective_n(y), 1),
    }
