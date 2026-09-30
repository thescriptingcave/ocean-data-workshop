"""Every repo-relative path the docs mention must exist.

The reorg moved `notebooks/` and `beginners/` to `Workshop/...` and left the references
behind in the places a first-time user looks first: the root README, GETTING_STARTED, and
each workshop's own README. Those files also told people to `jupyter lab notebooks/`,
and `gates.yml` tried to extract a `notebooks/cache-archive.tar.gz` that had not existed
for several commits. Nothing failed, because nothing checked.

`make fresh` proves setup runs from a clean clone, but it cannot tell you that the
instructions you just followed point at a directory that is not there.

Deliberately narrow about what counts as a path, so prose like `make lab` is not
mistaken for a file: either a known top-level directory, or a name with a file extension.

Run: uv run pytest tests/test_doc_paths.py -q
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DOCS = [
    "README.md",
    "Workshop/docs/GETTING_STARTED.md",
    "Workshop/workshop_1/README.md",
    "Workshop/workshop_2/README.md",
    "Workshop/workshop_3/README.md",
    "Workshop/sql_tutorials/README.md",
    "Workshop/CONTRIBUTING.md",
]

PATTERNS = [
    # A path rooted at a known top-level directory.
    re.compile(r"`((?:Workshop|scripts|src|probes|docs)/[A-Za-z0-9_./*-]+)`"),
    # A bare filename with an extension.
    re.compile(r"`([A-Za-z0-9_-]+\.(?:py|sql|toml|yml|yaml|txt|json|ini|cfg))`"),
]

# `pip install -r <path>` and friends: the target is what matters, and these are the
# commands a reader copies verbatim.
INSTALL = re.compile(r"(?:pip install -r|python -m|jupyter lab|tar -xzf)\s+(\S+)")

# `python -m probes.run_all` is a module path, not a file: check the package exists
# rather than the .py that does not.
MODULE = re.compile(r"python -m ([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z0-9_]+)*)")


def references(text: str) -> set[str]:
    found: set[str] = set()
    for pat in (*PATTERNS, INSTALL):
        found.update(pat.findall(text))
    found.update(MODULE.findall(text))
    return found


def _resolves(ref: str, doc: Path) -> bool:
    """True if `ref` names something that exists, relative to the repo or to `doc`.

    A README that documents a directory's own contents refers to them from inside that
    directory, so sql_tutorials/README.md says `schema.sql`, not
    `Workshop/sql_tutorials/schema.sql`. Both readings have to be tried or every such
    document fails on its own table of contents.
    """
    rel = ref.rstrip("/")
    if rel.startswith(("http", "-", "$")) or rel in {".", ""}:
        return True
    for base in (ROOT, doc.parent):
        if "*" in rel:
            prefix = rel.split("*")[0].rstrip("/")
            if prefix and (base / prefix).exists():
                return True
        elif (base / rel).exists():
            return True
    return False


@pytest.mark.parametrize("doc", DOCS, ids=[d.replace("/", "_") for d in DOCS])
def test_documented_paths_exist(doc: str) -> None:
    """Referenced repo paths resolve."""
    path = ROOT / doc
    assert path.is_file(), f"{doc} does not exist"

    broken: list[str] = []
    modules = set(MODULE.findall(path.read_text()))
    for ref in sorted(references(path.read_text())):
        if ref in modules:
            # `python -m probes.run_all` names a module, and the file is run_all.py inside
            # probes/ -- so check the package, not the .py. A broken `python -m` target
            # is an ImportError the reader hits before anything else works.
            parts = ref.split(".")
            if not (ROOT / parts[0]).is_dir():
                broken.append(ref)
                continue
            leaf = ROOT.joinpath(*parts[:-1], parts[-1] + ".py")
            if not leaf.is_file() and not (ROOT.joinpath(*parts) / "__init__.py").is_file():
                broken.append(ref)
        elif not _resolves(ref, path):
            broken.append(ref)

    assert not broken, (
        f"{doc} references paths that do not exist: {', '.join(broken)}. "
        "Stale paths here are the first thing a new user hits."
    )


def test_getting_started_documents_a_working_clone() -> None:
    """The documented first-run path matches the Makefile's actual default."""
    makefile = (ROOT / "Makefile").read_text()
    assert re.search(r"^\.DEFAULT_GOAL\s*:?=\s*all", makefile, re.M), (
        "`make` with no arguments is documented as the whole install; "
        "the Makefile no longer defaults to it"
    )

    getting_started = (ROOT / "Workshop" / "docs" / "GETTING_STARTED.md").read_text()
    assert "--notebook-dir=Workshop" in getting_started, (
        "GETTING_STARTED must document the same Lab command `make lab` runs"
    )
    # The reorg-era paths, which were still in these files after the move.
    for stale in ("jupyter lab notebooks/", "notebooks/cache-archive", "beginners/requirements"):
        assert stale not in getting_started, f"GETTING_STARTED still says `{stale}`"
