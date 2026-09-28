"""Tests for ocean_sim.stats.

These exist because the bootstrap is easy to get subtly wrong in ways that produce
confident, plausible, wrong numbers. Each test pins a property whose failure would be
invisible in the output.

Run: uv run pytest tests/test_stats.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ocean_sim.stats import (  # noqa: E402
    block_bootstrap_pvalue,
    effective_n,
    estimate_block_length,
    lag_correlations,
)


def ar1(n, rho, rng, sigma=1.0):
    """Stationary AR(1) with the given autocorrelation and unit marginal sd."""
    innov = rng.normal(scale=sigma * np.sqrt(1 - rho**2), size=n)
    out = np.empty(n)
    out[0] = innov[0]
    for k in range(1, n):
        out[k] = rho * out[k - 1] + innov[k]
    return out


def test_effective_n_white_noise_is_near_n():
    """Uncorrelated data must not be penalised."""
    x = np.random.default_rng(0).normal(size=3000)
    n_eff = effective_n(x)
    assert 0.7 * 3000 < n_eff <= 3000


def test_effective_n_collapses_for_persistent_series():
    """Strongly autocorrelated data must be heavily penalised. This is the whole reason
    a naive p-value on daily ocean data is wrong."""
    x = ar1(3000, 0.95, np.random.default_rng(1))
    n_eff = effective_n(x)
    assert n_eff < 3000 / 5, f"n_eff={n_eff} not small enough for AR(1) rho=0.95"


def test_effective_n_is_monotone_in_rho():
    prev = np.inf
    for rho in (0.0, 0.5, 0.8, 0.95):
        n_eff = effective_n(ar1(2000, rho, np.random.default_rng(2)))
        assert n_eff < prev
        prev = n_eff


def test_block_length_beats_correlation_time():
    """Block length must be at least as long as the dependence time, or the bootstrap
    null is too narrow and p-values come out optimistic."""
    rng = np.random.default_rng(3)
    for rho in (0.5, 0.8, 0.9):
        block = estimate_block_length(ar1(2000, rho, rng))
        assert block >= 1.0 / (1 - rho), f"block {block} too short for rho={rho}"


def test_lag_correlations_recovers_a_planted_lag():
    """A signal planted at lag k must peak at k, not somewhere else."""
    rng = np.random.default_rng(4)
    x = ar1(1500, 0.7, rng)
    y = np.roll(x, 7) + rng.normal(scale=0.5, size=1500)
    r = lag_correlations(x, y, 14)
    assert int(np.argmax(np.abs(r))) == 7


def test_bootstrap_resampled_pairs_have_equal_length():
    """Regression test. Sampling block *indices* instead of element offsets makes
    trailing slices run off the end; the two series then come out different lengths and
    the null is silently meaningless."""
    rng = np.random.default_rng(5)
    x = ar1(1200, 0.8, rng)
    y = ar1(1200, 0.6, rng)
    res = block_bootstrap_pvalue(x, y, max_lag=8, n_boot=200, seed=11)
    assert res["n"] == 1200
    assert res["p_boot"] > 0.0
    assert np.isfinite(res["obs_max_abs_r"])


def test_bootstrap_null_is_not_significant():
    """Two independent autocorrelated series must NOT come out significant. This is the
    false-positive guard: naive lag scanning on 30 daily points reported r=-0.61, and
    this test is what says whether that would have held up."""
    rng = np.random.default_rng(6)
    x = ar1(1500, 0.85, rng)
    y = ar1(1500, 0.7, rng)
    res = block_bootstrap_pvalue(x, y, max_lag=10, n_boot=600, seed=12)
    assert res["p_boot"] > 0.05, f"false positive: p={res['p_boot']}"


def test_bootstrap_detects_a_planted_relationship():
    """A genuine lagged signal must be found significant."""
    rng = np.random.default_rng(7)
    x = ar1(1500, 0.8, rng)
    y = np.roll(x, 4) + rng.normal(scale=0.4, size=1500)
    res = block_bootstrap_pvalue(x, y, max_lag=10, n_boot=600, seed=13)
    assert res["p_boot"] < 0.05, f"missed a real signal: p={res['p_boot']}"
    assert res["best_lag"] == 4


def test_bootstrap_pvalue_is_never_zero():
    """Add-one smoothing: a p-value of exactly 0 would be a claim of infinite evidence."""
    rng = np.random.default_rng(8)
    x = ar1(1000, 0.8, rng)
    res = block_bootstrap_pvalue(x, x.copy(), max_lag=5, n_boot=200, seed=14)
    assert res["p_boot"] > 0.0


def test_bootstrap_rejects_too_few_points():
    with pytest.raises(ValueError):
        block_bootstrap_pvalue(np.arange(20.0), np.arange(20.0), max_lag=5)


def test_bootstrap_is_deterministic_for_a_seed():
    rng = np.random.default_rng(9)
    x = ar1(800, 0.7, rng)
    y = ar1(800, 0.5, rng)
    a = block_bootstrap_pvalue(x, y, max_lag=6, n_boot=200, seed=99)
    b = block_bootstrap_pvalue(x, y, max_lag=6, n_boot=200, seed=99)
    assert a == b


def test_block_length_is_capped_to_the_lag_scale():
    """Regression test for a real anticonservative bug.

    Daily SST has a ~200-day seasonal dependence. Estimating the block length from the
    whole series therefore picks ~206 days while we are testing 10-day lags. That block
    over-preserves structure, narrows the null, and manufactures significance. The block
    must be capped relative to max_lag.
    """
    rng = np.random.default_rng(20)
    seasonal = ar1(3000, 0.98, rng) + 3.0 * np.sin(
        2 * np.pi * np.arange(3000) / 365.25
    )
    res = block_bootstrap_pvalue(seasonal, ar1(3000, 0.5, rng), max_lag=10, n_boot=200, seed=21)
    assert res["block"] <= 4 * 10, f"block {res['block']} not capped to the lag scale"
