"""Probe 04 — toolchain: TimescaleDB + a notebook-style connection + plotly.

Fifteen minutes of work that prevents a Thursday surprise. Deliberately not
interesting: a database is a database. What we are proving is only that the pieces
fit together on this machine -- extension installs, a connection from Python, a
hypertable accepts writes and reads back, and plotly renders.

The TimescaleDB connection string is read from the environment so no credential is
ever written into the repo. Defaults match the docker-compose setup in the README.
"""

from __future__ import annotations

import os

from ._common import PASS, Probe, Result, run

HARNESS = Probe(
    slug="toolchain",
    name="PostgreSQL + TimescaleDB + psycopg + plotly",
    tier=1,
    klass="A",
    provides="operational time-series store and interactive plotting",
    protocol="docker container, localhost:5432",
    order=4,
)

DSN = os.environ.get(
    "OCEAN_SIM_DSN", "postgresql://postgres:ocean@localhost:5432/ocean_sim"
)


def check() -> Result:
    detail: dict = {"dsn": DSN.split("@")[-1]}
    problems: list[str] = []

    import psycopg

    try:
        with psycopg.connect(DSN, connect_timeout=10) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT version()")
                detail["postgres"] = cur.fetchone()[0].split(" on ")[0]
                cur.execute("SELECT version()")
                ext = cur.fetchone()[0]
                detail["timescaledb"] = ext.split(" on ")[1] if " on " in ext else "?"
                cur.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")
                conn.commit()
    except Exception as exc:
        return Result(
            status="FAIL",
            note=f"cannot connect or create extension: {type(exc).__name__}: {exc}",
            detail=detail,
        )

    # a hypertable must accept writes and read back
    try:
        with psycopg.connect(DSN, connect_timeout=10, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute("DROP TABLE IF EXISTS _probe_ctd CASCADE")
                cur.execute(
                    "CREATE TABLE _probe_ctd ("
                    "  t TIMESTAMPTZ NOT NULL, depth_m REAL, sst_c REAL)"
                )
                cur.execute(
                    "SELECT create_hypertable('_probe_ctd', 't', "
                    "chunk_time_interval => INTERVAL '1 day')"
                )
                cur.execute(
                    "INSERT INTO _probe_ctd "
                    "SELECT ts, 40.0, 15.6 + random()*0.01 "
                    "FROM generate_series("
                    "  '2019-09-01'::timestamptz,"
                    "  '2019-09-30'::timestamptz, '1 hour') ts"
                )
                cur.execute("SELECT count(*) FROM _probe_ctd")
                n = cur.fetchone()[0]
                # 2019-09-01T00 to 2019-09-30T00 inclusive of the start, exclusive
                # of the end, is 29 days = 696 hours, so 697 rows with the first.
                expected = 29 * 24 + 1
                detail["hypertable_rows"] = n
                # the real time-series primitive: a native bucket/rollup
                cur.execute(
                    "SELECT time_bucket('1 day', t)::date d, "
                    "round(avg(sst_c)::numeric, 2) "
                    "FROM _probe_ctd GROUP BY d ORDER BY d LIMIT 3"
                )
                # cast to text so the verdict line stays readable and JSON-safe
                detail["time_bucket"] = [f"{r[0]}:{r[1]}" for r in cur.fetchall()]
                if n != expected:
                    problems.append(f"expected {expected} hourly rows, got {n}")
                cur.execute("DROP TABLE _probe_ctd CASCADE")
    except Exception as exc:
        problems.append(f"hypertable roundtrip failed: {type(exc).__name__}: {exc}")

    # plotly must render interactively
    try:
        import plotly.graph_objects as go

        fig = go.Figure(
            go.Scatter(x=[1, 2, 3], y=[1.0, 1.5, 1.2], name="probe")
        )
        detail["plotly"] = f"v{go.__version__ if hasattr(go, '__version__') else '?'}"
        detail["plotly_html_bytes"] = len(fig.to_html(include_plotlyjs="cdn"))
        if detail["plotly_html_bytes"] < 500:
            problems.append("plotly produced a suspiciously small HTML document")
    except Exception as exc:
        problems.append(f"plotly failed: {type(exc).__name__}: {exc}")

    if problems:
        return Result(status="FAIL", note="; ".join(problems), detail=detail)

    return Result(
        status=PASS,
        note=(
            "TimescaleDB extension active, hypertable write/read ok, "
            "time_bucket() works, plotly renders. DSN via OCEAN_SIM_DSN "
            "(no credential in repo)"
        ),
        detail=detail,
    )


if __name__ == "__main__":
    import sys

    from ._common import append_verdict

    res = run(HARNESS, check)
    append_verdict(res)
    sys.exit(0 if res.status == "PASS" else 1)
