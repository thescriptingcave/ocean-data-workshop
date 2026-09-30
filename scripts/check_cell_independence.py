"""Check that every code cell in every notebook runs on its own.

Notebook 01 promises a fast lane: "if you are comfortable with raw HTTP, start at cell
N". A promise like that is a claim that any cell can be run in isolation, and in a room
of thirty people somebody will do exactly that -- jump to a cell, hit Run, and get a
NameError about a variable defined twelve cells earlier.

That is not a hypothetical. It happened: a cell failed with
``NameError: name 'raw' is not defined`` because the fetch lived eight cells above it.
`Run All` had always passed, so nothing caught it.

This script runs each cell in a fresh kernel, with only the notebook's preamble (cell 2,
the imports) before it, and reports the ones that cannot stand alone.

    uv run python scripts/check_cell_independence.py

A failure is not necessarily a bug -- a cell that plots the result of the cell above it
is a legitimate teaching sequence. But in a workshop it is a trap, and the fix is two
lines of re-fetch. Fix them.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NOTEBOOKS = ROOT / "Workshop" / "workshop_2"

# The shared preamble is found by content, not position: it is the cell that does
# `import _fetch` and creates the session. Notebooks put a different number of markdown
# cells above it, so a fixed index silently "passes" the wrong cells.
def find_preamble(src) -> int:
    for i, c in enumerate(src.cells):
        if c.cell_type == "code" and "import _fetch" in c.source:
            return i
    raise LookupError("no preamble cell found -- it should contain `import _fetch`")


def check(path: Path) -> list[tuple[int, str, str]]:
    """Return [(cell_index, error_name, first_line)] for cells that need earlier state."""
    import nbformat
    from nbclient import NotebookClient

    src = nbformat.read(str(path), as_version=4)
    failures: list[tuple[int, str, str]] = []
    pre = find_preamble(src)

    code_cells = [i for i, c in enumerate(src.cells) if c.cell_type == "code"]
    for i in code_cells:
        if i <= pre:
            continue
        nb = nbformat.v4.new_notebook(
            cells=[src.cells[pre], src.cells[i]],
            metadata=src.metadata,
        )
        for n, c in enumerate(nb.cells):  # the same object twice; ids must be unique
            c["id"] = f"{path.stem}-{i}-{n}"
        try:
            NotebookClient(
                nb, kernel_name="python3", timeout=180,
                resources={"metadata": {"path": str(NOTEBOOKS)}}, allow_errors=True,
            ).execute()
        except Exception as exc:
            failures.append((i, type(exc).__name__, str(exc).splitlines()[0][:60]))
            continue
        for cell in nb.cells:
            for out in cell.get("outputs", []):
                if out.get("output_type") == "error":
                    failures.append((i, out.get("ename", "?"),
                                     (out.get("evalue") or "")[:60]))
    return failures


def main() -> int:
    print("=" * 72)
    print("  cell independence: does every cell run on its own?")
    print("=" * 72)

    total_bad = 0
    for path in sorted(NOTEBOOKS.glob("*.ipynb")):
        failures = check(path)
        n_code = sum(1 for c in __import__("nbformat").read(str(path), as_version=4).cells
                     if c.cell_type == "code")
        status = "ok  " if not failures else "deps"
        print(f"  {status} {path.name:34} {n_code - 1:>3} cells")
        for idx, name, detail in failures:
            print(f"         cell {idx}: {name}: {detail}")
        total_bad += len(failures)

    print("-" * 72)
    if total_bad:
        print(f"  {total_bad} cell(s) depend on earlier state. Informational, not a gate:")
        print("  these notebooks are sequential teaching material, so some cells build")
        print("  on the one above and that is intended. The check exists for the real bug")
        print("  class -- a cell missing an import, or a variable used far from where it")
        print("  is defined, which passes 'Run All' and fails when someone jumps in.")
    else:
        print("  every cell stands alone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
