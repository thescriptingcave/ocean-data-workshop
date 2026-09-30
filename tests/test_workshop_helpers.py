"""Guards on the committed workshop artifacts.

`build_notebooks.py:6` commits executed output on purpose, so a notebook is a build
product that is also a tracked file. Two failure modes follow from that: the per-
workshop helper copies drifting apart, and a notebook being saved from Jupyter Lab and
committed with local edits instead of the builder's output.

Run: uv run pytest tests/test_workshop_helpers.py -q
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
WORKSHOP_DIRS = ["workshop_1", "workshop_2", "workshop_3"]

# nbbuild.py:68 is the single place this is defined; every notebook carries a copy of
# the string, and a Lab save re-stamps it with whichever kernel the author happened to
# be running, which is how one notebook ended up advertising a different display name
# than the other 25.
EXPECTED_DISPLAY_NAME = "Python 3"
EXPECTED_KERNEL_NAME = "python3"
PAIRS = [
    ("_fetch.py", ROOT / "Workshop" / "workshop_2" / "_fetch.py", ROOT / "Workshop" / "workshop_3" / "_fetch.py"),
    ("_sources.py", ROOT / "Workshop" / "workshop_2" / "_sources.py", ROOT / "Workshop" / "workshop_3" / "_sources.py"),
]


@pytest.mark.parametrize("name,a,b", PAIRS, ids=[p[0] for p in PAIRS])
def test_helper_copies_are_identical(name: str, a: Path, b: Path) -> None:
    """Both copies exist and have not drifted.

    `_fetch.py` and `_sources.py` exist once per workshop directory, colocated with the
    notebooks that read them, because those are teaching artifacts an attendee opens
    next to the notebook. That is a defensible reason to have two copies. It is not a
    reason for them to become *different*.

    The hazard is silent: `import _fetch` resolves by working directory, and
    `build_notebooks.py:75` executes every notebook with the working directory set to
    `Workshop/workshop_2`. So the workshop_3 notebooks import workshop_2's copy, not
    their own. If the two diverge, the ML notebooks keep running and keep producing
    plausible numbers while testing code nobody is reading. A test is the fix rather
    than a shared module, because deduplicating would move the file out from under the
    notebook that teaches it.
    """
    assert a.is_file(), f"{a} is missing"
    assert b.is_file(), f"{b} is missing"
    assert a.read_bytes() == b.read_bytes(), (
        f"{name} differs between workshop_2 and workshop_3. "
        "The workshop_3 notebooks import the workshop_2 copy at build time, so a "
        "divergence is silent -- fix by making both copies identical again."
    )


def _notebooks() -> list[Path]:
    out: list[Path] = []
    for d in WORKSHOP_DIRS:
        out.extend(sorted((ROOT / "Workshop" / d).glob("*.ipynb")))
    return out


def test_every_workshop_has_notebooks() -> None:
    """Guard the glob above: an empty list would make the tests below pass vacuously."""
    nbs = _notebooks()
    assert len(nbs) == 26, f"expected 26 committed notebooks, found {len(nbs)}"
    for d in WORKSHOP_DIRS:
        assert any(d in n.parts for n in nbs), f"no notebooks found in {d}"


@pytest.mark.parametrize("nb", _notebooks(), ids=lambda p: p.name)
def test_notebook_kernelspec_is_the_builder_default(nb: Path) -> None:
    """All notebooks advertise the same kernel.

    Saving from Jupyter Lab rewrites `display_name` to the kernel the author was running,
    which is how ml_03_features.ipynb came to claim "Python 3 (ipykernel)" while the
    other 25 said "Python 3". Harmless to execution -- `name` is what Jupyter matches on
    -- but it makes the picker inconsistent for a reader, and it means the committed file
    no longer matches `nbbuild.py:68`.
    """
    meta = json.loads(nb.read_text()).get("metadata", {})
    ks = meta.get("kernelspec", {})
    assert ks.get("name") == EXPECTED_KERNEL_NAME, (
        f"{nb.name} declares kernel {ks.get('name')!r}, expected {EXPECTED_KERNEL_NAME!r}"
    )
    assert ks.get("display_name") == EXPECTED_DISPLAY_NAME, (
        f"{nb.name} declares display_name {ks.get('display_name')!r}, expected "
        f"{EXPECTED_DISPLAY_NAME!r}. A Lab save rewrites this; re-render with "
        f"'make notebooks' rather than committing the saved copy."
    )


@pytest.mark.parametrize("name,a,b", PAIRS, ids=[p[0] for p in PAIRS])
def test_cache_path_points_at_the_shared_cache(name: str, a: Path, b: Path) -> None:
    """Both copies resolve CACHE to Workshop/.cache, the one `make clean-cache` removes.

    CACHE is `Path(__file__).parent.parent / ".cache"`, so a copy that ever moves out of
    a workshop directory would silently start writing its own private cache and the
    offline guarantee would quietly stop applying to it.
    """
    import re

    for path in (a, b):
        text = path.read_text()
        m = re.search(r'^ROOT\s*=\s*Path\(__file__\)\.resolve\(\)\.parent\.parent', text, re.M)
        assert m, f"{path} no longer derives ROOT as parent.parent; check CACHE"
        expected = path.resolve().parent.parent / ".cache"
        assert expected == ROOT / "Workshop" / ".cache", (
            f"{path} would cache under {expected}, not the shared Workshop/.cache"
        )
