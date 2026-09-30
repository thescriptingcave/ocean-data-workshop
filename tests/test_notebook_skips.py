"""A deliberate skip is not a failure.

Notebook 07 stops on purpose when `ocean_profile_daily` is empty, because `make setup`
skips GLORYS by default. build_notebooks.execute() must report that as a skip, so
`make notebook` stays green on a default install, and must say *why* rather than
collapsing every skip to "data not available".
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))


def _execute(path: Path) -> tuple[bool, str]:
    """Run execute() against a notebook that raises the skip marker."""
    import build_notebooks

    return build_notebooks.execute(path)


def test_skip_marker_matches_the_name_the_notebook_raises() -> None:
    """The marker in build_notebooks is the ename notebook 07 actually raises.

    These are two strings in two files, and nothing else connects them: build_notebooks
    does not import the notebook builders, and the notebook defines the exception
    locally so it does not need nbclient. If either is renamed, every skip silently
    becomes a failure instead.
    """
    src = (ROOT / "scripts" / "workshop_notebooks.py").read_text()
    assert "class NotebookSkipped(Exception):" in src, (
        "notebook 07 no longer defines the skip exception"
    )
    import build_notebooks

    assert build_notebooks.SKIP_MARKER in src, (
        f"build_notebooks.SKIP_MARKER is {build_notebooks.SKIP_MARKER!r}, which "
        "workshop_notebooks.py does not use"
    )


def test_skipped_notebook_is_reported_as_a_skip_not_a_failure(tmp_path: Path) -> None:
    """A notebook that raises the marker returns ok=True with a 'skipped' reason."""
    nb = {
        "cells": [
            {
                "cell_type": "code",
                "source": "class NotebookSkipped(Exception):\n    pass\nraise NotebookSkipped('needs data')",
                "id": "skip-cell",
                "metadata": {},
                "execution_count": None,
                "outputs": [],
            }
        ],
        "metadata": {"kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"}},
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    path = tmp_path / "skipper.ipynb"
    path.write_text(json.dumps(nb))

    ok, err = _execute(path)
    assert ok, f"a deliberate skip must not fail the build, got {err!r}"
    assert err.startswith("skipped"), f"expected a 'skipped' reason, got {err!r}"
    assert "needs data" in err, f"the notebook's own reason was lost: {err!r}"


def test_real_failure_still_fails(tmp_path: Path) -> None:
    """The skip path must not have weakened the real failure path."""
    nb = {
        "cells": [
            {
                "cell_type": "code",
                "source": "raise ValueError('a genuine bug')",
                "id": "broken-cell",
                "metadata": {},
                "execution_count": None,
                "outputs": [],
            }
        ],
        "metadata": {"kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"}},
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    path = tmp_path / "broken.ipynb"
    path.write_text(json.dumps(nb))

    ok, err = _execute(path)
    assert not ok, "a genuine error must still fail the build"
    assert "ValueError" in err


def test_notebook_07_states_how_to_get_the_data() -> None:
    """The reader is told what to run, not just that something is missing."""
    src = (ROOT / "scripts" / "workshop_notebooks.py").read_text()
    assert "make db-ocean" in src, (
        "notebook 07's guard must name the command that fixes it"
    )


def test_reported_skip_line_is_distinct_from_ok() -> None:
    """main() must not print a skip as `ok`, which would hide the only useful fact."""
    src = (ROOT / "scripts" / "build_notebooks.py").read_text()
    assert 'f"  SKIP  {path.name' in src, "a skip is printed as plain 'ok'"
