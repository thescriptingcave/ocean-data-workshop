"""Authoring layer for the workshop notebooks.

The notebooks are the deliverable, but writing them as raw ``.ipynb`` JSON is
unreviewable and impossible to diff. So they are written here as a list of
``md(...)`` / ``code(...)`` calls and rendered to real notebooks by
``scripts/build_notebooks.py``, which then executes them so the committed output is
real rather than illustrative.

Why commit executed output at all: most attendees read these cold, days later, having
not attended. A notebook with no output is a wall of unverified code. A notebook with
output *and* assertions in it is a record of what actually happened.

Two conventions in every notebook, applied by ``code()`` rather than remembered:

  * a fast-lane markdown note at the top, for people comfortable with raw HTTP
  * every cell that makes a claim ends in an ``_fetch.expect`` assertion
"""

from __future__ import annotations

import pathlib
import sys
from typing import Any

import nbformat as nbf

NOTEBOOKS = pathlib.Path(__file__).resolve().parent.parent / "Workshop" / "workshop_2"

# The kernel name. "python3" resolves to whichever python the attendee's uv env
# provides, which is what they want.
KERNEL = "python3"

FAST_LANE = """> **Fast lane.** If you are comfortable with raw HTTP, start at the cell
> marked *three ways, step 2*. You will lose nothing by skipping the curl cell."""


def md(text: str) -> list:
    """A markdown cell, as a list, so cells can be composed without special cases."""
    return [nbf.v4.new_markdown_cell(text.strip("\n"))]


def code(text: str, *, fast_lane: bool = False) -> list:
    """A code cell, optionally preceded by the skip-ahead note.

    The note is a *separate markdown cell*. It cannot be prepended as a comment: the
    original version did that and produced a cell beginning with ``> **Fast lane**``,
    which is a SyntaxError rather than a note.
    """
    cells = md(FAST_LANE) if fast_lane else []
    cells.append(nbf.v4.new_code_cell(text.strip("\n")))
    return cells


def raw(text: str) -> list:
    return [nbf.v4.new_raw_cell(text.strip("\n"))]


def build(*cells: Any, title: str) -> nbf.NotebookNode:
    """Assemble a notebook from cells and/or lists of cells."""
    flat: list = []
    for c in cells:
        flat.extend(c if isinstance(c, list) else [c])

    nb = nbf.v4.new_notebook()
    nb.cells = flat
    nb.metadata = {
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": KERNEL,
        },
        "language_info": {"name": "python", "version": sys.version.split()[0]},
        "ocean_data_workshop": {"title": title},
    }
    return nb


def write(nb: nbf.NotebookNode, filename: str) -> pathlib.Path:
    NOTEBOOKS.mkdir(parents=True, exist_ok=True)
    p = NOTEBOOKS / filename
    nbf.write(nb, str(p))
    return p
