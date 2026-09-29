"""Verify that candidate questions are ANSWERABLE and NON-DEGENERATE.

This replaces the unautomatable version of "gate step 3".

The original wording -- write down three questions you want to answer -- was called a
gate while admitting it could not be automated. That is a contradiction: a gate needs an
exit condition. So it is split into two parts, and only one of them is a gate:

  * **Verifiable (this script).** Does each question have a real, non-degenerate answer
    in the data? Does the data exist, does the answer actually vary, is the signal above
    its own noise floor, and are the three questions distinguishable from one another?
    A question that fails any of these is not a good question, whatever the answer
    happens to be.
  * **Not verifiable.** Whether the question is *interesting to the person asking it*.
    No test can decide that, and claiming otherwise would be dishonest.

So this is a **precondition check**, not the gate itself. Passing it does not mean the
questions are good; it means they are not broken.

Run:  uv run python scripts/verify_questions.py
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import psycopg

from ocean_sim.dsn import dsn

DSN = dsn()


def q(sql: str, **params) -> pd.DataFrame:
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with psycopg.connect(DSN) as conn:
            return pd.read_sql_query(sql, conn, params=params)


# ---------------------------------------------------------------------------
# checks: each returns (ok, detail). They test the *question*, not the answer.
# ---------------------------------------------------------------------------

CHECKS: dict[str, callable] = {}


def check(fn):
    CHECKS[fn.__name__] = fn
    return fn


@dataclass
class Question:
    qid: str
    text: str
    needs: list[str]           # tables the question depends on
    target: str                # what it explains, for the distinctness test
    verify: str                # name of the check function
    sql_hint: str = ""


QUESTIONS = [
    Question(
        qid="Q1",
        text="When did the thermocline cross 15 m, and what was the ocean doing that week?",
        needs=["ocean_profile_daily"],
        target="ocean stratification over time",
        verify="varies_over_time",
        sql_hint="LAG / FIRST_VALUE with an explicit frame over depth",
    ),
    Question(
        qid="Q2",
        text=(
            "Why do the 30-80 Hz bands respond to wind when nothing below 80 Hz does?"
        ),
        needs=["acoustic_tol_hourly", "wind_daily"],
        target="frequency dependence of the wind response",
        verify="band_structure",
        sql_hint="band-level regression against wind, compared across bands",
    ),
    Question(
        qid="Q3",
        text="Do dolphin detections follow a diel cycle, or are they spread evenly?",
        needs=["detection_hourly", "acoustic_tol_hourly"],
        target="temporal pattern in biological detections",
        verify="beats_chance",
        sql_hint="EXTRACT(hour ...) with a rate test",
    ),
]


@check
def varies_over_time(question: Question) -> tuple[bool, str]:
    """Is the quantity the question asks about actually changing, or is it constant?"""
    # Thermocline = depth of the strongest temperature gradient, per day.
    # DISTINCT ON is the Postgres idiom; the window function cannot be referenced
    # inside a FILTER clause, which is the obvious thing to try first.
    df = q(
        """
        WITH prof AS (
            SELECT observed_at::date AS day, depth_m,
                   avg(raw_temperature_c) AS t
            FROM ocean_profile_daily GROUP BY 1, 2
        ), g AS (
            SELECT day, depth_m, t,
                   t - LAG(t) OVER (PARTITION BY day ORDER BY depth_m) AS dcdz
            FROM prof
        )
        SELECT DISTINCT ON (day) day, depth_m AS tc_m
        FROM g
        WHERE dcdz IS NOT NULL
        ORDER BY day, dcdz ASC
        """
    )
    tc = pd.to_numeric(df["tc_m"], errors="coerce").dropna()
    if len(tc) < 30:
        return False, f"only {len(tc)} days with a computable thermocline"
    spread = float(tc.max() - tc.min())
    detail = (
        f"{len(tc)} days, thermocline spans {spread:.1f} m "
        f"({tc.min():.1f}-{tc.max():.1f} m), sd {tc.std():.2f} m"
    )
    return spread > 3.0, detail


@check
def band_structure(question: Question) -> tuple[bool, str]:
    """Does the relationship differ across groups, or would one answer cover them all?

    A question whose answer is the same for every band is really one question, and
    usually a boring one.
    """
    from ocean_sim.stats import block_bootstrap_pvalue

    df = q(
        """
        SELECT a.observed_at::date AS day, w.wind_speed_mean_ms,
               avg(a.band_25hz) AS b25, avg(a.band_40hz) AS b40,
               avg(a.band_160hz) AS b160, avg(a.band_400hz) AS b400,
               avg(a.band_1000hz) AS b1k, avg(a.band_8000hz) AS b8k,
               avg(a.band_20000hz) AS b20k
        FROM acoustic_tol_hourly a
        JOIN wind_daily w ON w.observed_at = a.observed_at::date AND w.station_id='46092'
        GROUP BY 1, 2 ORDER BY 1
        """,
    )
    rs = {}
    for col, hz in (("b25", 25), ("b40", 40), ("b160", 160), ("b400", 400),
                    ("b1k", 1000), ("b8k", 8000), ("b20k", 20000)):
        p = df[["wind_speed_mean_ms", col]].dropna()
        res = block_bootstrap_pvalue(
            p["wind_speed_mean_ms"].to_numpy(), p[col].to_numpy(),
            max_lag=2, n_boot=300, seed=3,
        )
        rs[hz] = res["obs_max_abs_r"]
    vals = list(rs.values())
    spread = max(vals) - min(vals)
    detail = "  ".join(f"{hz}Hz:{r:+.2f}" for hz, r in rs.items())
    return spread > 0.15, f"{detail}  (spread {spread:.2f})"


@check
def beats_chance(question: Question) -> tuple[bool, str]:
    """Is the rate different across hours, beyond what random placement would give?

    Guard against the obvious trap: with 8,390 hours and 22.7% positives, tiny spurious
    patterns are guaranteed. Rates are normalised per hour first, so a busy hour is not
    mistaken for a preferred one, and the overall positive rate is used as the null.
    """
    df = q(
        """
        SELECT EXTRACT(hour FROM observed_at)::int AS hr,
               count(*) AS n,
               sum(presence) AS positives
        FROM detection_hourly
        WHERE taxon='dolphin' AND NOT is_event_list
        GROUP BY 1 ORDER BY 1
        """,
    )
    n = df["n"].to_numpy(dtype=float)
    p = df["positives"].to_numpy(dtype=float)
    total_n, total_p = n.sum(), p.sum()
    expected = total_p / total_n

    # Pearson chi-square of hourly rate against the flat overall rate
    obs = p / n
    chi2 = float((((obs - expected) ** 2) / expected * n).sum())
    dof = len(n) - 1
    p_val = _gammainc_upper(dof / 2.0, chi2 / 2.0)

    detail = (
        f"{int(total_n):,} hours, overall positive rate {expected:.3f}, hourly rate "
        f"{obs.min():.3f}-{obs.max():.3f}, chi2={chi2:.1f} on {dof} dof"
    )
    # deliberately lenient: the gate is "is there any structure at all", not significance
    return (
        bool((obs.max() - obs.min()) > 0.03 and p_val < 0.05),
        f"{detail}, p={p_val:.3g}",
    )


def _gammainc_upper(a: float, x: float) -> float:
    """Upper regularised incomplete gamma Q(a, x).

    Written out rather than pulled from scipy: scipy is already a dependency, but this
    keeps the gate script honest about what it is computing rather than hiding the
    significance test behind one import.
    """
    from math import exp, lgamma

    if x < a + 1.0:
        ap, total, delta = a, 1.0 / a, 1.0 / a
        for _ in range(500):
            ap += 1.0
            delta *= x / ap
            total += delta
            if abs(delta) < abs(total) * 1e-12:
                break
        return float(np.clip(1.0 - total * exp(-x + a * np.log(x) - lgamma(a)), 0.0, 1.0))

    tiny = 1e-300
    b, c, d = x + 1.0 - a, 1.0 / tiny, 1.0 / (x + 1.0 - a)
    h = d
    for i in range(1, 500):
        an = -i * (i - a)
        b += 2.0
        d = an * d + b
        if abs(d) < tiny:
            d = tiny
        c = b + an / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-12:
            break
    return float(np.clip(h * exp(-x + a * np.log(x) - lgamma(a)), 0.0, 1.0))


def main() -> int:
    print("Gate step 3, verifiable half")
    print("=" * 78)
    print(
        "Checks that each question has a real, non-degenerate answer in the data.\n"
        "It does NOT check whether the question is interesting -- no test can."
    )

    results = []
    for question in QUESTIONS:
        print(f"\n{question.qid}: {question.text}")
        print(f"    needs {question.needs}   [{question.sql_hint}]")

        missing = []
        for t in question.needs:
            n = len(q(f"SELECT 1 FROM {t} LIMIT 1"))
            if n == 0:
                missing.append(t)
        if missing:
            print(f"    FAIL  empty tables: {missing}")
            results.append((question, False, "empty table"))
            continue

        try:
            ok, detail = CHECKS[question.verify](question)
        except Exception as exc:
            print(f"    FAIL  check raised {type(exc).__name__}: {exc}")
            results.append((question, False, f"{type(exc).__name__}"))
            continue

        print(f"    {'PASS' if ok else 'FAIL'}  {detail}")
        results.append((question, ok, detail))

    # --- distinctness: three questions about one thing are one question ---
    print("\n" + "=" * 78)
    print("distinctness")
    targets = [r[0].target for r in results]
    dupes = {t for t in targets if targets.count(t) > 1}
    if dupes:
        print(f"  FAIL  these questions share a target and are really one question: {dupes}")
    else:
        print(f"  PASS  {len(set(targets))} distinct targets, no overlap")

    passed = sum(1 for _, ok, _ in results if ok)
    print("\n" + "=" * 78)
    print(f"{passed}/{len(results)} questions are answerable and non-degenerate.")
    if passed == len(results) and not dupes:
        print(
            "\nPrecondition met. The remaining gate is yours: do these actually\n"
            "interest you? This script cannot answer that, and a script that claimed\n"
            "to would be lying."
        )
    return 0 if passed == len(results) and not dupes else 1


if __name__ == "__main__":
    raise SystemExit(main())
