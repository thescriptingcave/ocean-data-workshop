"""Render and execute the workshop notebooks.

    uv run python scripts/build_notebooks.py            # write .ipynb from the definitions
    uv run python scripts/build_notebooks.py --execute  # ...and run them, saving output

Output is committed deliberately. Most attendees read these cold, days later, having not
attended, and a notebook with no output is a wall of unverified code. With output *and*
the assertions from Notebook 01, it is a record of what actually happened.

One notebook failing does not stop the others -- during the build you want to know
everything that is broken, not just the first thing.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import workshop_notebooks as nbdefs  # noqa: E402
from nbbuild import NOTEBOOKS, write  # noqa: E402

# Name -> builder attribute in workshop_notebooks. Resolved lazily with getattr so a
# notebook that has not been written yet does not stop the ones that have.
#
# Execution order is the order of this list. 01 is the spine and must pass before
# anything that assumes the reader has seen it; 00 is written last and listed first
# only because it is what a person opens.
NOTEBOOK_ORDER = [
    # Data retrieval notebooks
    "00_orientation",
    "01_request_three_ways",
    "02_erddap_griddap",
    "03_gcs_object_storage",
    "04_cloud_access_policy",
    "05_argo_gdac_netcdf",
    "06_copernicus_credentialed",
    "07_ndbc_fixed_format",
    "08_gsw_domain_library",
    "09_capstone_join",
    "10_trap_table",
    # ML notebooks
    "ml_01_orientation",
    "ml_02_classification",
    "ml_03_features",
    "ml_04_evaluation",
    "ml_05_metrics",
    "ml_06_wind",
    "ml_07_clustering",
    "ml_08_capstone",
    "ml_09_traps",
    "ml_10_pytorch",
]


def execute(path: Path, timeout: int = 900) -> tuple[bool, str]:
    """Execute one notebook in place. Returns (ok, first_error_line).

    The executed notebook is written back to disk, which is the entire point: the
    committed output is what makes these readable cold by someone who did not attend.
    """
    import nbformat
    from nbclient import NotebookClient
    from nbclient.exceptions import CellExecutionError

    nb = nbformat.read(str(path), as_version=4)
    client = NotebookClient(
        nb,
        timeout=timeout,
        kernel_name="python3",
        resources={"metadata": {"path": str(NOTEBOOKS)}},
        allow_errors=True,
    )
    err = ""
    try:
        client.execute()
    except CellExecutionError as exc:
        err = str(exc).splitlines()[0][:100]
    except Exception as exc:
        err = f"{type(exc).__name__}: {str(exc)[:90]}"

    # A cell that raised is not a failure of the *run*, but it is a failure of the
    # notebook: an unhandled error in a workshop artifact is a bug in this repo.
    if not err:
        for i, cell in enumerate(nb.cells):
            if cell.cell_type != "code":
                continue
            for out in cell.get("outputs", []):
                if out.get("output_type") == "error":
                    err = f"cell {i}: {out.get('ename', '?')}: " + (out.get("evalue") or "")[:70]
                    break
            if err:
                break

    # Write back either way. A notebook that errored still shows *where* it errored,
    # which is more useful in a diff than an empty file.
    nbformat.write(nb, str(path))

    # Guard against the silent failure mode: an "executed" notebook with no output at
    # all means execution never happened, and would otherwise look like success.
    if not err:
        n_out = sum(
            len(c.get("outputs", [])) for c in nb.cells if c.cell_type == "code"
        )
        n_code = sum(1 for c in nb.cells if c.cell_type == "code")
        if n_code and not n_out:
            return False, "executed but produced no output at all"

    return (not err), err


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true", help="run them and save output")
    ap.add_argument("--only", nargs="*", help="build just these notebook names")
    args = ap.parse_args()

    wanted = args.only or NOTEBOOK_ORDER
    print("=" * 72)
    print(f"  {'building and ' if args.execute else ''}writing {len(wanted)} notebooks")
    print("=" * 72)

    built: list[Path] = []
    for name in wanted:
        # Handle ML notebooks (ml_01 -> nb_ml_01)
        if name.startswith("ml_"):
            # Extract the number: ml_01_orientation -> 01
            number = name.split("_")[1]  # "01"
            fn_name = f"nb_ml_{number}"
        else:
            fn_name = f"nb_{name[:2]}"
        fn = getattr(nbdefs, fn_name, None)
        if fn is None:
            print(f"  SKIP {name:28} no builder yet")
            continue
        nb = fn()
        path = write(nb, f"{name}.ipynb")
        built.append(path)
        print(f"  wrote {path.name:34} {len(nb.cells):>3} cells")

    if not args.execute:
        return 0

    print()
    failed = []
    t0 = time.time()
    for path in built:
        t = time.time()
        ok, err = execute(path)
        if ok:
            print(f"  ok    {path.name:34} {time.time() - t:>5.1f}s")
        else:
            print(f"  FAIL  {path.name:34} {err}")
            failed.append(path.name)

    print("-" * 72)
    print(f"  {len(built) - len(failed)}/{len(built)} executed clean in {time.time() - t0:.0f}s")
    if failed:
        print(f"  failed: {', '.join(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
