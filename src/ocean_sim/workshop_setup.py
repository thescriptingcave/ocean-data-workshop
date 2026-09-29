"""One command that takes a clean checkout to a working workshop environment.

    uv run workshop-setup

Written in Python rather than shell on purpose. The audience is macOS (Apple silicon)
and Linux, with a few Windows users, and a ``.sh`` plus a ``.bat`` would drift apart
within one release. This runs identically on all three, with no ``bash`` required and
no ``timeout`` binary (which does not exist on macOS -- curl's ``--max-time`` does).

Stages, each skippable so a failure costs one minute rather than a whole session:

    1. check prerequisites (docker, uv)
    2. start PostgreSQL 17 + TimescaleDB and *wait for it to be healthy*
    3. apply the schema
    4. load the data
    5. prefetch API responses into the notebook cache

Re-running is safe at every stage: the loader is idempotent, the cache skips what it
already has, and the container is already up.

Flags:
    --skip-db      do not touch the database (workshop notebooks 00-07, 09)
    --skip-load    start the database but do not fetch the data
    --skip-fetch   do not prefetch API responses
    --port N       use a host port other than 5432 (for a local PostgreSQL already running)
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

# src/ocean_sim/workshop_setup.py -> repo root is two levels up
ROOT = Path(__file__).resolve().parents[2]

os.environ.setdefault("OCEAN_SIM_OFFLINE", "0")

DB_PORT = int(os.environ.get("OCEAN_SIM_PORT", "5432"))


def step(n: int, total: int, title: str) -> None:
    print(f"\n[{n}/{total}] {title}")
    print("-" * 72)


def ok(msg: str) -> None:
    print(f"  ok   {msg}")


def warn(msg: str) -> None:
    print(f"  !!   {msg}")


def die(msg: str, hint: str = "") -> None:
    print(f"\n  FAILED: {msg}")
    if hint:
        print(f"\n  {hint}\n")
    sys.exit(1)


def run(cmd: list[str], *, timeout: int = 1800, check: bool = True,
        quiet: bool = False) -> subprocess.CompletedProcess:
    """Run a command. No shell=True anywhere: the arguments differ per platform and a
    string command is how you get quoting bugs that only reproduce on Windows."""
    if not quiet:
        print(f"  $ {' '.join(str(c) for c in cmd)}")
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=ROOT)
    if check and r.returncode != 0:
        tail = "\n".join((r.stderr or r.stdout or "").strip().splitlines()[-12:])
        die(f"`{' '.join(str(c) for c in cmd)}` exited {r.returncode}\n{tail}")
    return r


# ---------------------------------------------------------------------------
# 1. prerequisites
# ---------------------------------------------------------------------------
def check_prereqs() -> None:
    step(1, 5, "Checking prerequisites")

    if shutil.which("docker"):
        r = run(["docker", "compose", "version"], check=False, quiet=True)
        if r.returncode == 0:
            ok("docker + compose plugin found")
        else:
            die(
                "docker found but the compose plugin is not available",
                "Docker Desktop (macOS/Windows) or docker-ce + docker-compose-plugin (Linux).",
            )
    else:
        die(
            "docker not found",
            "Install Docker Desktop: https://docs.docker.com/desktop/\n"
            "It is required for the SQL portion (Notebook 08). Notebooks 00-07 and 09\n"
            "do not need it -- you can still do most of the workshop.",
        )

    r = run(["docker", "info"], check=False, quiet=True)
    if r.returncode != 0:
        die(
            "docker is installed but the daemon is not responding",
            "Start Docker Desktop and wait for it to finish starting, then re-run.",
        )
    ok("docker daemon is running")

    if shutil.which("uv"):
        ok("uv found")
    else:
        warn("uv not found -- assuming this was run with an existing Python environment")


# ---------------------------------------------------------------------------
# 2. database
# ---------------------------------------------------------------------------
def start_db() -> None:
    step(2, 5, f"Starting PostgreSQL + TimescaleDB on port {DB_PORT}")

    env = {**os.environ, "OCEAN_SIM_PORT": str(DB_PORT)}
    r = subprocess.run(
        ["docker", "compose", "up", "-d", "--wait"],
        capture_output=True, text=True, cwd=ROOT, timeout=300, env=env,
    )
    if r.returncode != 0:
        if "port is already allocated" in (r.stderr + r.stdout):
            die(
                f"host port {DB_PORT} is already in use",
                "You probably have a local PostgreSQL. Either stop it, or pick another:\n"
                f"    uv run workshop-setup --port 5433\n"
                "The port is read from OCEAN_SIM_PORT by the database and by every\n"
                "script that connects, so this stays consistent.",
            )
        die(f"docker compose up failed\n{(r.stderr or r.stdout)[-800:]}")

    ok("container healthy (docker compose --wait consumed the healthcheck)")

    # Confirm we can actually query it, not merely that the container is up.
    r = run(
        ["docker", "exec", "ocean-sim-db", "psql", "-U", "postgres", "-d", "ocean_sim",
         "-tAc", "select 1"],
        check=False, quiet=True, timeout=60,
    )
    if r.returncode != 0:
        die("container is up but postgres is not accepting connections yet")
    ok("accepting connections")


def apply_schema() -> None:
    step(3, 5, "Applying schema")
    run(["uv", "run", "python", "-c",
         "import sys,psycopg,pathlib;"
         "sys.path.insert(0,'src');"
         "from ocean_sim.dsn import dsn;"
         "sql=pathlib.Path('learning/schema.sql').read_text();"
         "c=psycopg.connect(dsn(),autocommit=True);"
         "c.execute(sql);c.close();"
         "print('  ok   applied learning/schema.sql')"],
        timeout=180)


def load_data() -> None:
    step(4, 5, "Loading data")
    warn("first run downloads ~15 MB and takes a few minutes. Later runs are near-instant.")
    run(["uv", "run", "python", "scripts/load_db.py"], timeout=3600)


def prefetch() -> None:
    step(5, 5, "Prefetching API responses for the notebooks")
    run(["uv", "run", "python", "scripts/prefetch.py"], timeout=3600)


# ---------------------------------------------------------------------------
def main() -> int:
    global DB_PORT
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--skip-db", action="store_true", help="do not touch the database")
    ap.add_argument("--skip-load", action="store_true", help="start the DB but do not load")
    ap.add_argument("--skip-fetch", action="store_true", help="do not prefetch")
    ap.add_argument("--port", type=int, default=None, help="host port (default 5432)")
    args = ap.parse_args()

    if args.port is not None:
        DB_PORT = args.port
        os.environ["OCEAN_SIM_PORT"] = str(DB_PORT)

    print("=" * 72)
    print("  Ocean data workshop -- environment setup")
    print("=" * 72)

    t0 = time.time()
    check_prereqs()

    if args.skip_db:
        warn("--skip-db given: notebooks 00-07 and 09 will work, 08 will not.")
    else:
        start_db()
        apply_schema()
        if not args.skip_load:
            load_data()

    if not args.skip_fetch:
        prefetch()

    print("\n" + "=" * 72)
    ok(f"setup complete in {time.time() - t0:.0f} s")
    print("\n  Next:  uv run jupyter lab notebooks/\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
