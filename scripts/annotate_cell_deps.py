"""Annotate cells with the names they inherit from earlier cells.

Re-deriving ``c``, ``dbar``, ``SA``, ``resp`` in every dependent cell would duplicate the
computation five times and bury the teaching under boilerplate. The alternative is to
*say* what a cell needs, so someone who jumps in knows what to run first:

    # needs from above: c, dbar

That is the honest version of the guarantee. A cell that fails with a bare
``NameError: name 'c' is not defined`` is a trap; a cell that opens by telling you it
needs ``c`` is a sentence.

Reads the failures from ``check_cell_independence.py`` and inserts the comment at the top
of the offending cell. Idempotent.

    uv run python scripts/annotate_cell_deps.py
    uv run python scripts/build_notebooks.py --execute
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import nbformat

ROOT = Path(__file__).resolve().parent.parent
NOTEBOOKS = ROOT / "notebooks"
SRC = ROOT / "scripts" / "workshop_notebooks.py"

MARK = "# needs from above:"

# Names that are imports rather than derived data. A cell missing one of these is a bug
# to fix, not a dependency to document.
IMPORTS = {
    "gsw", "psycopg", "xarray", "xr", "plt", "np", "pd", "io", "gzip", "shutil",
    "subprocess", "dsn", "port", "Path", "sns", "requests", "warnings", "tarfile",
    "re", "sys", "textwrap", "datetime", "timedelta", "json", "os", "math",
}


def failures() -> dict[str, list[tuple[int, str]]]:
    """{notebook: [(cell_index, missing_name)]}, from the independence checker."""
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_cell_independence.py")],
        capture_output=True, text=True,
        env={**os.environ, "OCEAN_SIM_OFFLINE": "1"},
    )
    out: dict[str, list[tuple[int, str]]] = {}
    current: str | None = None
    for line in r.stdout.splitlines():
        m = re.search(r"(FAIL|ok\s+)\s+(\S+\.ipynb)", line)
        if m:
            current = m.group(2) if m.group(1) == "FAIL" else None
            if current:
                out[current] = []
            continue
        m = re.search(r"cell (\d+): NameError: name '(\w+)' is not defined", line)
        if m and current:
            out[current].append((int(m.group(1)), m.group(2)))
    return out


def code_ordinal(nb: str, cell_index: int) -> int | None:
    """Position of ``cell_index`` among *code* cells, or None if it is markdown.

    The checker reports indices into ``nb.cells``, which includes markdown. The source
    builder contains only ``code(...)`` blocks. Mapping one straight onto the other is
    how the first version of this script annotated the wrong cells with confident,
    plausible, wrong notes.
    """
    src = nbformat.read(str(NOTEBOOKS / nb), as_version=4)
    if src.cells[cell_index].cell_type != "code":
        return None
    ordinal = sum(1 for c in src.cells[:cell_index] if c.cell_type == "code")
    # ordinal 0 is the preamble, which is injected as *preamble() -> code(SETUP)
    # rather than a literal code(''') block, so the blocks list starts one after it.
    return None if ordinal == 0 else ordinal - 1


def strip_existing() -> int:
    """Remove previously-inserted annotations so a re-run cannot leave stale ones."""
    lines = SRC.read_text().splitlines(keepends=True)
    kept = [ln for ln in lines if not ln.strip().startswith(MARK)]
    removed = len(lines) - len(kept)
    if removed:
        SRC.write_text("".join(kept))
    return removed


def main() -> int:
    print("=" * 72)
    print("  cell dependency annotation")
    print("=" * 72)

    removed = strip_existing()
    if removed:
        print(f"\n  stripped {removed} previously-inserted annotation(s)")
    else:
        print("\n  no existing annotations")

    all_failures = failures()
    import_only: list[str] = []
    derived: dict[str, dict[int, list[str]]] = {}

    for nb, items in all_failures.items():
        derived[nb] = {}
        for idx, name in items:
            if name in IMPORTS:
                import_only.append(f"{nb} cell {idx}: {name}")
            else:
                derived[nb].setdefault(idx, []).append(name)

    if import_only:
        print("\n  MISSING IMPORTS -- bugs, fix them in the cell:")
        for x in import_only:
            print(f"    {x}")
    else:
        print("\n  ok  no cell is missing an import")

    src = SRC.read_text()
    total = 0
    for nb, cells in derived.items():
        num = nb.replace(".ipynb", "").split("_")[0]
        m = re.search(rf"^def nb_{num}\(\).*?\n(.*?)(?=^def nb_|\Z)", src, re.S | re.M)
        if not m:
            print(f"  SKIP {nb}: no builder found")
            continue
        body = m.group(1)
        new_body = body
        blocks = list(re.finditer(r"code\('''\n", new_body))
        for idx, names in sorted(cells.items()):
            ordinal = code_ordinal(nb, idx)
            if ordinal is None or ordinal >= len(blocks):
                print(f"  SKIP {nb} cell {idx}: no matching code block")
                continue
            b = blocks[ordinal]
            note = f"        {MARK} {', '.join(sorted(set(names)))}\n"
            new_body = new_body[:b.end()] + note + new_body[b.end():]
            total += 1
        if new_body != body:
            src = src[:m.start(1)] + new_body + src[m.end(1):]

    SRC.write_text(src)
    print(f"\n  annotated {total} cell(s) with '{MARK}'")
    print("  then:  uv run python scripts/build_notebooks.py --execute")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
