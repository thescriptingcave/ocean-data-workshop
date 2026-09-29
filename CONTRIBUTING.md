# Contributing

## The one thing to know

**The notebooks are generated. Do not edit the `.ipynb` files.**

They are built from `scripts/workshop_notebooks.py` and executed by
`scripts/build_notebooks.py`. Editing the `.ipynb` directly means your change is
silently overwritten on the next build — which has happened here more than once, most
recently when a hand-edited notebook reverted cleanly and took a fix with it.

```bash
make notebook     # render + execute, saving output -- this is the supported path
```

Open `notebooks/01_request_three_ways.ipynb` in an editor if you want to read a notebook,
but make changes in the Python.

Workshop Intro (`beginners/`) is generated the same way, from a single self-contained
file:

```bash
make beginners    # scripts/build_beginners.py --execute
```

`beginners/requirements.txt` is Workshop Intro's *complete* dependency list and is
deliberately separate from the root `pyproject.toml`. Do not add project packages to
it — the CI `workshop intro` job installs only that file and fails if the tier has
grown a dependency on the database, the cache or the rest of the repo. That isolation
is the feature.

## Before you push

```bash
make test
```

That is: execute every notebook, report cells that cannot run alone, run the unit tests,
and lint. A notebook that raises is a failed build — the build treats an unhandled error
as a failure rather than saving the traceback, because a broken cell in workshop material
is a bug in the material.

Also worth running when you touch the fetch layer, the cache, or the database:

```bash
make check     # every notebook with the network forbidden
make fresh     # clone to a temp dir and run setup from nothing
```

`make fresh` is the one that finds things nothing else does. It found a `.gitignore`
rule that had silently excluded three source files from every commit, and a compose
file that could not be started twice on one machine. Neither was visible from the
working tree.

## Style

- `ruff` governs. `make lint`.
- Comments explain *why*, not what. The existing code is the reference: the traps are
  documented in full, because the reasoning is the deliverable and the next person will
  otherwise rediscover it the expensive way.
- If you find a new trap, add it to `TRAPS` in `scripts/workshop_notebooks.py`. The count
  in Notebook 00 and 09 is computed from that table — do not write it by hand.
- No credentials, ever. `.env` is gitignored; `.env.example` is the template. If a
  failure needs a secret, the code should read it from the environment at runtime.

## Adding a data source

1. Verify it first — anonymously if possible, and check the size before downloading.
   `data/` caches raw responses; the loaders in `src/ocean_data_workshop/data/` parse them.
2. Record what cost you. The value of this project is the list of things that are not in
   the documentation, and a trap nobody writes down is a trap somebody pays for again.
3. Add the endpoint to `notebooks/_sources.py` with a builder function, and to its
   `manifest()`. The prefetch and the notebooks share those builders on purpose: a
   prefetch that has drifted from the notebooks is worse than none, because it fails
   silently and the workshop makes live calls in a room.
