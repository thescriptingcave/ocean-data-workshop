# Changelog

## 1.0.0 — 2026-09-30

First release. Three workshops, 26 notebooks, one command to run them.

```
git clone https://github.com/thescriptingcave/ocean-data-workshop.git
cd ocean-data-workshop
make          # setup, build the notebooks, open Jupyter Lab
```

`make` installs dependencies, starts PostgreSQL + TimescaleDB and waits for it to be
healthy, applies the schema, loads ~15 MB of real data, warms the API cache, registers
the Jupyter kernel, renders the notebooks and opens Lab on `Workshop/`. About 85
seconds from a fresh clone, after Docker's image is present.

Requires Python 3.11+ (or [uv](https://docs.astral.sh/uv/)) and Docker. A free
Copernicus Marine account is optional; it is only needed for `make db-ocean` and the
ocean profile it loads.

### The workshops

| | notebooks | needs |
|---|---|---|
| **1 — Intro** | 5 | five pip packages. no Docker, no database |
| **2 — Advanced** | 11 | the database; 5 of the 6 access patterns |
| **3 — ML** | 10 | the database; scikit-learn and PyTorch |

### Fixes worth knowing about

These are the ones that produced user-visible breakage rather than tidiness.

**The Jupyter kernel was registered with `--user`, which Jupyter never selects.** Jupyter
searches the environment data directory before the user one, so the spec was written to a
slot that could not be used and the venv's stock kernel won instead. Worse, the
`argv` captured at install time pointed at `/private/tmp/timing/.venv/bin/python3` — a
deleted venv belonging to a different project. The kernel named `Python 3 (ocean-sim)`
was dead, and selecting it gave a wall of missing-module errors. Now installed with
`--sys-prefix`, where it is first in the search path.

**Notebook 10 was green because a `try/except ImportError` wrapped the whole cell.** That
swallowed every error raised after the import, so a `NameError` in the model definition
reported itself as "PyTorch not installed" and the notebook stayed broken. The import is
now the only guarded statement, and PyTorch is a default dependency rather than an extra
behind a second command.

**Notebook 07 failed cryptically without the GLORYS ocean profiles**, which `make setup`
skips by default. `StandardScaler` raised `Found array with 0 sample(s)` three cells
later, naming neither the cause nor the fix. It now stops where the problem is and says
`make db-ocean`. `build_notebooks` distinguishes this from a failure so `make notebook`
stays green.

**JupyterLab opened in the wrong directory.** `--notebook-dir` sets the server root, but
Lab restores its own last directory and that wins, so one session inside `workshop_3/`
made every later `make lab` ignore the flag. `scripts/lab_root.py` clears it.

**`make clean` named one of three notebook directories**, so the ML notebooks could not
be cleaned — which is how a second full set survived one. `make clean-cache` pointed at a
path that had not existed since a directory restructure and silently did nothing while
printing success.

**`gates.yml` referenced three paths that no longer existed**, so three CI jobs would fail
on any clean checkout.

**The `.ipynb` files and the API cache were both tracked by accident.** They were tracked
because their ignore rules named directories that had since been moved, so the rules
stopped matching while the files stayed tracked. Consequences: running a notebook modified
a tracked file and `git pull` asked for a stash; a notebook saved from Lab drifted from its
builder; and 1.9 MB of committed output carried absolute temp paths and kernel PIDs from
whichever machine ran it last. Neither is committed now — the notebooks are generated and
`make lab` builds them, and the cache ships as a compressed archive that is a strict
superset of what was tracked.

**The install instructions pointed at directories that did not exist**, and the timing
table predated notebook 04.

### Tests

56 tests, no network and no database required. `make test` runs them plus lint and
executes every notebook.

Three files guard properties that had silently rotted, because nothing was watching them:

- `tests/test_doc_paths.py` — every repo-relative path in the seven documents a reader
  touches resolves, and every `make` target they mention exists
- `tests/test_workshop_helpers.py` — the per-workshop `_fetch.py` / `_sources.py` copies
  have not drifted (the ML notebooks import `workshop_2`'s copy at build time, so
  divergence is silent), and all 26 notebooks declare the builder's kernelspec
- `tests/test_notebook_skips.py` — a deliberate skip stays a skip, and a genuine error
  still fails

### Known limitations

- **`make notebook` takes about 18 minutes**, roughly 16 of it in `ml_04_evaluation`,
  which runs a block bootstrap with 100 resamples. The 35-second figure in
  `GETTING_STARTED.md` covers Workshop 2 alone.
- **`ml_07_clustering` is the only notebook needing `make db-ocean`.** Without it the
  other nine Workshop 3 notebooks run normally and 07 reports a skip.
- **Workshop 1 is standalone by design** and does not use `make`, Docker, the database or
  this venv. A CI job exists specifically to keep it that way.
