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

NOTEBOOKS = pathlib.Path(__file__).resolve().parent.parent / "notebooks"

# The kernel name. "python3" resolves to whichever python the attendee's uv env
# provides, which is what they want.
KERNEL = "python3"

FAST_LANE = """> **Fast lane.** If you are comfortable with raw HTTP, start at the cell
> marked *three ways, step 2*. You will lose nothing by skipping the curl cell."""


def md(text: str) -> Any:
    """A markdown cell. Trailing whitespace is stripped so the JSON stays clean."""
    return nbf.v4.new_markdown_cell(text.strip("\n"))


def code(text: str, *, fast_lane: bool = False) -> Any:
    """A code cell, optionally prefixed with the skip-ahead note."""
    if fast_lane:
        text = f"{FAST_LANE}\n\n" + text
    return nbf.v4.new_code_cell(text.strip("\n"))


def raw(text: str) -> Any:
    return nbf.v4.new_raw_cell(text.strip("\n"))


def build(*cells: Any, title: str) -> nbf.NotebookNode:
    """Assemble a notebook. The first markdown cell becomes the title."""
    nb = nbf.v4.new_notebook()
    nb.cells = list(cells)
    nb.metadata = {
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": KERNEL,
        },
        "language_info": {"name": "python", "version": sys.version.split()[0]},
        "ocean_sim": {"title": title},
    }
    return nb


def write(nb: nbf.NotebookNode, filename: str) -> pathlib.Path:
    NOTEBOOKS.mkdir(parents=True, exist_ok=True)
    p = NOTEBOOKS / filename
    nbf.write(nb, str(p))
    return p
