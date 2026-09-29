# Getting started

From nothing to running notebooks. About **85 seconds** on a working connection, plus
the time to download Docker if you do not have it.

Written for **macOS (Apple silicon), Linux, and Windows**. Where a platform differs, it
says so.

---

## 1. What you need

| | requirement | notes |
|---|---|---|
| **Python** | 3.11 or newer | you do **not** need to install it — see below |
| **Docker** | Docker Desktop, or `docker-ce` + the compose plugin | only for Notebook 08 |
| **Disk** | ~200 MB free | Python env, ~15 MB of data, 6 MB of cache |
| **Time** | 5 min to set up, 2h40 of workshop | compute time is 27 s; the rest is discussion |

A free **Copernicus Marine** account is optional. It unlocks Notebook 05; the notebook
detects its absence and teaches what it can without it. Everything else is anonymous.

### If you do not have Python

Install [uv](https://docs.astral.sh/uv/), which manages Python for you:

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows PowerShell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Then `uv run` uses the right Python automatically. You never install or manage a
virtualenv yourself.

---

## 2. Get the code

```bash
git clone <repository-url> ocean-sim
cd ocean-sim
```

## 3. Set up

```bash
uv run workshop-setup
```

That one command:

1. checks Docker is installed and running
2. starts PostgreSQL 17 + TimescaleDB and **waits for it to be healthy**
3. applies the schema from `learning/schema.sql`
4. downloads ~15 MB of real data and loads it
5. warms the API cache so the notebooks do not depend on the network

Re-run it any time — every stage is idempotent.

### Already have PostgreSQL on port 5432?

```bash
uv run workshop-setup --port 5433
```

The port is read from `OCEAN_SIM_PORT` by the database *and* by every script that
connects, so the override stays consistent.

### Two copies of this repo on one machine?

Each gets its own container and database automatically, because the compose project name
defaults to the checkout's directory name. Add `--port` as well if both are on 5432.

---

## 4. Verify

```bash
uv run jupyter lab notebooks/
```

Open `00_orientation.ipynb` and run all cells. The last cell asserts the environment is
ready and prints **"Environment is ready. Start with 01."**

To check the offline path end to end:

```bash
OCEAN_SIM_OFFLINE=1 uv run jupyter lab notebooks/
```

Every notebook should still work, each request printing a warning that it is using a
cached response. **That is expected, and the numbers are still correct.**

---

## 5. Work through the notebooks

Start with `01_request_three_ways` — it is the spine, and everything else is a variation
of it.

Every notebook is independently runnable, so you can skip around. Each follows the same
six steps:

1. **What you should get** — the size, shape and range to expect, *before* the request
2. **On the wire** — `curl`, so you can see the actual exchange
3. **In Python** — `requests`, and what it does not do for you
4. **In a library** — `xarray` or a domain package
5. **⚠️ Traps here** — the failure modes, which are the point
6. **What you got** — a plot, and assertions that fail if the data is wrong

**If you're comfortable with raw HTTP**, notebooks 02, 03, 05 and 06 are mostly review.
The ones worth your time are **01** (the spine), **08** (the result) and **09** (the trap
table).

---

## Timing, measured

Execution times, from the build system. **Nobody is waiting on compute** — 27 seconds for
the whole workshop. The time is spent talking about traps.

| notebook | runs in | worth spending |
|---|---|---|
| 00 orientation | 1.7 s | 10 min |
| 01 the request, three ways | 6.5 s | 25 min |
| 02 ERDDAP griddap | 1.9 s | 20 min |
| 03 GCS object storage | 2.0 s | 20 min |
| 04 Argo GDAC | 1.8 s | 20 min |
| 05 Copernicus | 5.1 s | 15 min |
| 06 NDBC | 1.8 s | 12 min |
| 07 gsw | 1.8 s | 10 min |
| 08 capstone | 3.5 s | 25 min |
| 09 trap table | 1.6 s | reference, 0 min |

Full run: **2h37** of material, plus ~20 minutes of breaks.

### A shorter version

If you have **60 minutes**, notebooks **00 + 01 + 09** are a complete workshop on their
own: orientation, the spine, and the trap table. The other seven are depth. This has not
been rehearsed end to end yet — treat it as untested.

---

## If something goes wrong

| symptom | cause | fix |
|---|---|---|
| `port is already allocated` | local PostgreSQL on 5432 | `uv run workshop-setup --port 5433` |
| `container name is already in use` | another checkout of this repo | `OCEAN_SIM_PROJECT=$(basename $PWD) uv run workshop-setup --port 5433` |
| `Docker is installed but the daemon is not responding` | Docker Desktop still starting | wait for it, then re-run |
| `No cached copy and no working network` | first run, and the network failed | re-run `uv run python scripts/prefetch.py` on a working network |
| `No module named 'ocean_sim...'` | project not installed | `uv sync` |
| Every call takes exactly the timeout | **IPv6 without an IPv6 route** | already handled by the helper; if you see it in your own code, force IPv4 — see Notebook 01 |
| Kernel not found in Jupyter | kernelspec not registered | `uv run python -m ipykernel install --user --name python3` |
| Notebooks are unexecuted and you want the output | reading the `.ipynb` on disk | they are committed executed; run `uv run python scripts/build_notebooks.py --execute` |

### Getting the error messages you actually want

Some of the traps taught here produce an unhelpful error on purpose. If you hit one and
want the real message:

```bash
uv run python -c "
import sys; sys.path.insert(0, 'src')
import requests
r = requests.get('...', timeout=30)
print(r.status_code); print(r.text[:2000])"
```

`raise_for_status()` first, then read `r.text` — several of these services return **XML**
error bodies from their JSON APIs, so `.json()` raises a `JSONDecodeError` and hides the
message you needed.

---

## Rebuilding

The notebooks are generated from Python so they can be reviewed as a diff and re-run
reliably.

```bash
uv run python scripts/build_notebooks.py            # render, do not run
uv run python scripts/build_notebooks.py --execute  # render and run, saving output
uv run python scripts/build_notebooks.py --execute --only 08_capstone_join
```

One notebook failing does not stop the others — during a build you want to know
everything that is broken, not just the first thing.

---

## Where things are

```
notebooks/            the workshop
  README.md           overview, the result, the trap summary
  _fetch.py           cached fetch + the expect() assertions
  _sources.py         every endpoint, built by functions
  *.ipynb             10 notebooks, executed, with output
src/ocean_sim/
  data/               loaders: glorys, ncei, ndbc
  http.py             IPv4-forcing HTTP session
  dsn.py              one place that knows the database address
  workshop_setup.py   the one-command setup
scripts/              build, prefetch, load, verify
learning/schema.sql   the database schema, written to be read
probes/               the original source-access audit and its verdicts
GLOSSARY.md           every term used, defined
```

---

## Data sources

Nine of the ten sources are **anonymous** — no account, no key, no registration. One
(Copernicus Marine) needs a free account, and it is the only source of ocean *currents*,
which is why the project was built with a fallback ladder rather than around a single
dependency.

No credentials are committed. They live in `~/.copernicusmarine/` and a gitignored
`.env`.
