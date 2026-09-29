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
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

# src/ocean_data_workshop/workshop_setup.py -> repo root is two levels up
ROOT = Path(__file__).resolve().parents[2]

os.environ.setdefault("OCEAN_DATA_WORKSHOP_OFFLINE", "0")

DB_PORT = int(os.environ.get("OCEAN_DATA_WORKSHOP_PORT", "5432"))

# Compose project name, defaulting to this checkout's directory so that two clones on
# one machine get separate containers and separate volumes instead of colliding.
def _project_name() -> str:
    """Compose project name, defaulting to this checkout's directory.

    Exported into os.environ in main() so that *every* subprocess inherits it. It used
    to be passed only to `docker compose up`, while the later `docker compose exec`
    inherited the plain environment -- so the two resolved different projects whenever
    the directory name was not the default, and setup died at "postgres is not
    accepting connections" on a database it had itself just started. Local testing hid
    it: the main checkout is called ocean-sim, and a container left over from an earlier
    run happened to be healthy under the name the exec resolved to.
    """
    return (
        os.environ.get("OCEAN_DATA_WORKSHOP_PROJECT")
        or re.sub(r"[^a-z0-9_-]+", "-", ROOT.name.lower()).strip("-")
        or "ocean-data-workshop"
    )


PROJECT = _project_name()


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


def run_visible(cmd: list[str], *, timeout: int = 3600) -> None:
    """Run a long step with its output visible.

    The data load is the slowest step and the one most likely to partially fail. It used
    to run with captured output, which meant an attendee whose ocean profile was skipped
    for want of a Copernicus account saw nothing between two progress headings and had no
    way to tell that half their data was missing. Stream it.
    """
    print(f"  $ {' '.join(str(c) for c in cmd)}")
    proc = subprocess.Popen(cmd, cwd=ROOT, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True)
    assert proc.stdout is not None
    for line in proc.stdout:
        print(f"  {line.rstrip()}")
    if proc.wait(timeout=timeout) != 0:
        die(f"`{' '.join(str(c) for c in cmd)}` failed")


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
    step(1, 6, "Checking prerequisites")

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
    step(2, 6, f"Starting PostgreSQL + TimescaleDB on port {DB_PORT}")

    r = subprocess.run(
        ["docker", "compose", "up", "-d", "--wait"],
        capture_output=True, text=True, cwd=ROOT, timeout=300,
    )
    if r.returncode != 0:
        out = r.stderr + r.stdout
        if "port is already allocated" in out:
            die(
                f"host port {DB_PORT} is already in use",
                "You probably have a local PostgreSQL. Either stop it, or pick another:\n"
                "    uv run workshop-setup --port 5433\n"
                "The port is read from OCEAN_DATA_WORKSHOP_PORT by the database and by every\n"
                "script that connects, so this stays consistent.",
            )
        if "already in use by container" in out or "Conflict" in out:
            die(
                "another checkout of this repo is already running its database",
                "Two checkouts otherwise share one compose project and one volume. Give\n"
                "this checkout its own project so the two stay independent:\n"
                "    OCEAN_DATA_WORKSHOP_PROJECT=$(basename $PWD) uv run workshop-setup --port 5433\n"
                "or tear the other one down first:\n"
                "    docker compose -p ocean-data-workshop down",
            )
        die(f"docker compose up failed\n{out[-800:]}")

    ok("container healthy (docker compose --wait consumed the healthcheck)")

    # Confirm we can actually query it, not merely that the container is up.
    # `docker compose exec` resolves the container itself, so nothing here hardcodes
    # the name -- which is what lets two checkouts coexist.
    r = run(
        ["docker", "compose", "exec", "-T", "db", "psql", "-U", "postgres",
         "-d", "ocean_data_workshop", "-tAc", "select 1"],
        check=False, quiet=True, timeout=60,
    )
    if r.returncode != 0:
        die("container is up but postgres is not accepting connections yet")
    ok("accepting connections")


def apply_schema() -> None:
    step(3, 6, "Applying schema")
    run(["uv", "run", "python", "-c",
         "import sys,psycopg,pathlib;"
         "sys.path.insert(0,'src');"
         "from ocean_data_workshop.dsn import dsn;"
         "sql=pathlib.Path('learning/schema.sql').read_text();"
         "c=psycopg.connect(dsn(),autocommit=True);"
         "c.execute(sql);c.close();"
         "print('  ok   applied learning/schema.sql')"],
        timeout=180)


def load_data() -> None:
    step(4, 6, "Loading data")
    warn("first run downloads ~15 MB and takes a few minutes. Later runs are near-instant.")
    run_visible(["uv", "run", "python", "scripts/load_db.py"])


def prefetch() -> None:
    step(5, 6, "Preparing API responses for the notebooks")

    archive = ROOT / "notebooks" / "cache-archive.tar.gz"
    if archive.exists():
        ok("cache archive present -- the notebooks will not need a network")
        run(["uv", "run", "python", "scripts/prefetch.py", "--install"], timeout=600)
        return

    warn("no cache archive -- fetching over the network")
    warn("if this fails the notebooks cannot be guaranteed to run offline")
    run_visible(["uv", "run", "python", "scripts/prefetch.py"])


# ---------------------------------------------------------------------------
def register_jupyter() -> None:
    step(6, 6, "Registering the Jupyter kernel and checking Jupyter Lab")

    # Needed, and easy to miss: `ipykernel` alone gives you a working *kernel* but no
    # `jupyter lab` subcommand, and the kernel has to be registered under a name Jupyter
    # will look for. Every one of these was a failure found by an attendee, not by the
    # test suite -- `build_notebooks.py` uses nbclient directly and never needed any
    # of it, so "10/10 execute clean" was true and still said nothing about whether
    # anyone could open the notebooks.
    r = run(
        ["uv", "run", "python", "-m", "ipykernel", "install", "--user",
         "--name", "python3", "--display-name", "Python 3 (ocean-sim)"],
        check=False, quiet=True, timeout=120,
    )
    ok("kernel 'python3' registered" if r.returncode == 0
       else "kernel install reported a problem (may already be registered)")

    r = run(["uv", "run", "jupyter", "lab", "--version"], check=False, quiet=True, timeout=120)
    if r.returncode != 0:
        die(
            "jupyter lab is not available",
            "It should be a project dependency. Repair with:\n"
            "    uv sync\n"
            "then re-run. Until it is available you can still read the committed\n"
            "notebooks, which are stored with their output.",
        )
    ok(f"jupyter lab {(r.stdout or '').strip().splitlines()[0]}")


def main() -> int:
    global DB_PORT
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--skip-db", action="store_true", help="do not touch the database")
    ap.add_argument("--skip-load", action="store_true", help="start the DB but do not load")
    ap.add_argument("--skip-fetch", action="store_true", help="do not prefetch")
    ap.add_argument("--port", type=int, default=None, help="host port (default 5432)")
    args = ap.parse_args()

    # Export before anything else so that every subprocess -- including the bare
    # `docker compose exec` in start_db() -- resolves the same database and the same
    # compose project as the `up` that created them.
    os.environ["OCEAN_DATA_WORKSHOP_PROJECT"] = PROJECT
    if args.port is not None:
        DB_PORT = args.port
    os.environ["OCEAN_DATA_WORKSHOP_PORT"] = str(DB_PORT)

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

    if not args.skip_db:
        register_jupyter()

    print("\n" + "=" * 72)
    ok(f"setup complete in {time.time() - t0:.0f} s")
    print("\n  Next:  uv run jupyter lab notebooks/")
    print("\n  Offline, if the network is bad:  OCEAN_DATA_WORKSHOP_OFFLINE=1 uv run jupyter lab notebooks/")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
