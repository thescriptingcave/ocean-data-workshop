# Getting started

> **This page is for Workshop Advanced.** Never fetched a URL? Start at
> [**Workshop Intro**](Workshop/workshop_1/README.md) instead — 5 packages, 5 notebooks,
> 40 minutes, and no Docker, database or Copernicus account.

From nothing to running notebooks. About **85 seconds** on a working connection, plus
the time to download Docker if you do not have it.

Written for **macOS (Apple silicon), Linux, and Windows**. Where a platform differs, it
says so.

---

## 1. What you need

| | requirement | notes |
|---|---|---|
| **Python** | 3.11 or newer | you do **not** need to install it — see below |
| **Docker** | Docker Desktop, or `docker-ce` + the compose plugin | only for Notebook 09 |
| **Disk** | ~1 GB free | ~850 MB is the Python env on its own; plus ~15 MB of data and the cache |
| **Time** | 5 min to set up, 2h40 of workshop | compute time is 27 s; the rest is discussion |

A free **Copernicus Marine** account is optional. It unlocks Notebook 06 and the ocean
profile (temperature, salinity, currents).

**Verified working without one.** On a machine with no account: the three anonymous
sources load, every notebook runs, and Notebook 09's result is unaffected — it joins
wind to acoustics, and neither needs an account. Nothing else needs a login.

### Which workshop is right for you?

| Workshop | Target Audience | Duration | Prerequisites |
|----------|----------------|----------|---------------|
| **Workshop Intro** (`Workshop/workshop_1/`) | Complete beginners | 40 min | None |
| **Workshop Advanced** (`Workshop/workshop_2/`) | Has used `requests` | 2h40 | Basic Python, fetched a URL before |
| **ML Workshop** (`Workshop/workshop_3/`) | Has ML experience | 6-8 hours | Basic ML concepts, Python |

### Supplying the credentials

Copy `.env.example` to `.env` and fill it in. `.env` is gitignored, and the loader reads
it automatically — no login step, nothing to remember:

```bash
cp .env.example .env
chmod 600 .env          # it holds a password
```

The two variable names are **not** guessable, and a wrong one is silently ignored:

```
COPERNICUSMARINE_SERVICE_USERNAME
COPERNICUSMARINE_SERVICE_PASSWORD
```

A variable already in the environment always wins over `.env`, so CI can inject secrets
without touching the working tree:

```bash
COPERNICUSMARINE_SERVICE_PASSWORD=... uv run python scripts/load_db.py
```

`copernicusmarine login` (interactive, writes to `~/.copernicusmarine/`) also works, and
is the route to use if you would rather not have a password in the project directory.

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

## 3. Set up and open Jupyter — one command

```bash
make
```

That is the whole thing. It prints six numbered steps:

1. checks Docker is installed, the daemon responds, and the compose plugin exists
2. starts PostgreSQL 17 + TimescaleDB from `docker-compose.yml` and **waits for it to
   be healthy**
3. applies the schema from `Workshop/sql_tutorials/schema.sql`
4. downloads ~15 MB of real data and loads it (the GLORYS ocean profile is
   **not** included by default — see below)
5. warms the API cache so the notebooks do not depend on the network
6. registers the Jupyter kernel and checks that `jupyter lab` actually runs

then opens Jupyter Lab on the `Workshop/` folder, so all three workshops are in the
file browser.

Typical time from a fresh clone: **under a minute**, about 15 MB of downloads.

**About 40 seconds is the number to expect once the Docker image is present, and a much
longer one is a problem, not patience.** On a machine that has never run this before,
the first step also has to pull `timescale/timescaledb:2.30.1-pg17`, and that pull is
most of a fresh install. The GLORYS ocean profile is the only slow *data* step and it is
skipped by default; if setup seems stuck, this is what to check — see the troubleshooting
entry for "stuck at 4/6" below. Re-run it any time — every stage is idempotent.

`make` is a build tool: already installed with the Xcode command line tools on macOS,
and available from your package manager on Linux and Windows. If you would rather not
use it, the same two steps are:

```bash
uv run workshop-setup
uv run jupyter lab --notebook-dir=Workshop
```

`--notebook-dir=Workshop` is what `make lab` passes, and it opens on the folder holding
all three workshops rather than one notebook directory. Jupyter Lab restores the last
directory you were in, so `make` clears that first — otherwise a session spent inside
`workshop_3/` wins over the flag and it looks like the flag was ignored.

### If the network is bad

```bash
make lab-offline
```

Also one command. Everything is served from the cache and each request prints a warning
that it is doing so — the numbers are real, just not new.

### The rest of the targets

`make help` lists them all. The ones worth knowing:

| | |
|---|---|
| `make lab` | open Jupyter Lab again, without redoing setup |
| `make notebook` | run every notebook top to bottom, saving output |
| `make test` | notebooks, cell-independence report, unit tests, lint |
| `make check` | every notebook with the **network forbidden** — the offline guarantee |
| `make fresh` | clone to a temp dir and run setup from nothing |
| `make db` | reload the data |
| `make db-ocean` | also load the GLORYS ocean profile (~325 MB, needs a Copernicus account) |
| `PORT=5433 make` | use a different database port |

### Already have PostgreSQL on port 5432?

```bash
PORT=5433 make
```

The port is read from `OCEAN_DATA_WORKSHOP_PORT` by the database *and* by every script that
connects, so the override stays consistent.

### Two copies of this repo on one machine?

Each gets its own container and database automatically, because the compose project name
defaults to the checkout's directory name. Add `--port` as well if both are on 5432.

---

## 4. Verify

In Jupyter, open `00_orientation.ipynb` and run all cells. The last cell asserts the
environment is ready and prints **"Environment is ready. Start with 01."**

Jupyter Lab prints a URL that contains a **token**, and opens your browser at it. The
token is in the terminal you launched from — so keep that terminal open. If you ever land
on a `login?next=...` page instead, the token is the long string in the original URL;
paste it back and the page resolves. This is Jupyter's own behaviour, not a project
setting, and it is the one thing worth knowing before you walk in.

To check the offline path end to end:

```bash
make lab-offline
```

or, without make:

```bash
OCEAN_DATA_WORKSHOP_OFFLINE=1 uv run jupyter lab --notebook-dir=Workshop
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

Execution times, measured on this machine against a full build of the notebooks.
**Nobody is waiting on compute** — 35 seconds for the whole workshop. The time is spent
talking about traps.

| notebook | runs in | worth spending |
|---|---|---|
| 00 orientation | 1.4 s | 10 min |
| 01 the request, three ways | 4.7 s | 25 min |
| 02 ERDDAP griddap | 1.7 s | 20 min |
| 03 GCS object storage | 1.9 s | 20 min |
| 04 who may read this? | 4.1 s | 15 min |
| 05 Argo GDAC netCDF | 1.7 s | 20 min |
| 06 Copernicus | 11.4 s | 15 min |
| 07 NDBC | 1.7 s | 12 min |
| 08 gsw | 1.7 s | 10 min |
| 09 capstone | 3.4 s | 25 min |
| 10 trap table | 1.5 s | reference, 0 min |

Full run: **35 seconds** of compute, **2h40** of material, plus ~20 minutes of breaks.

04 is the one notebook that needs a live network — its subject is what three services say
*right now* about who may read them, so it deliberately bypasses the cache. The 4.1 s
above is with the network up; the offline figure is not meaningful for it.

### A shorter version

If you have **60 minutes**, notebooks **00 + 01 + 10** are a complete workshop on their
own: orientation, the spine, and the trap table. The other eight are depth. This has not
been rehearsed end to end yet — treat it as untested.

---

## If something goes wrong

| symptom | cause | fix |
|---|---|---|
| Setup seems stuck on "4/6 loading data" | it is downloading GLORYS, which is ~325 MB | Ctrl-C, then re-run. Finished downloads are cached in `data/` and will not repeat, so a second run is quick. To skip it entirely, that is already the default — if you are not seeing the skip message, you have a stale checkout: `git pull`. |
| Setup seems stuck on "4/6 loading data" (older checkouts) | before this was made opt-in, the ocean profile was always downloaded | `git pull`, then re-run. |
| `port is already allocated` | local PostgreSQL on 5432 | `PORT=5433 make` |
| `container name is already in use` | another checkout of this repo | `OCEAN_DATA_WORKSHOP_PROJECT=$(basename $PWD) PORT=5433 make` |
| `Docker is installed but the daemon is not responding` | Docker Desktop still starting | wait for it, then re-run |
| `No cached copy and no working network` | no cache archive and the network failed | the archive ships with the repo; if you deleted it, re-run `uv run python scripts/prefetch.py` |
| `ocean_profile_daily 0 <- empty` | no Copernicus account | expected. Everything else loaded; Notebook 09 still works |
| `No module named 'ocean_data_workshop...'` | project not installed | `uv sync` |
| Every call takes exactly the timeout | **IPv6 without an IPv6 route** | already handled by the helper; if you see it in your own code, force IPv4 — see Notebook 01 |
| `Jupyter command 'jupyter-lab' not found` | `jupyterlab` not installed | `uv sync` — `workshop-setup` now checks for this |
| Notebooks have no output and you want it | the `.ipynb` are generated, so they ship unexecuted | run `make notebook` (writes output into them) or just run the cells |
| A notebook is missing after `git clean` | they are build products, not tracked | `make lab` builds them, or `make notebooks` |
| A `login?next=...` page instead of the lab | Jupyter's token, in the terminal you launched from | paste the token from the original URL, or re-run the command |

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
uv run python scripts/build_notebooks.py --execute --only 09_capstone_join
```

One notebook failing does not stop the others — during a build you want to know
everything that is broken, not just the first thing.

---

## Where things are

```
Workshop/workshop_2/  the Advanced workshop
  README.md           overview, the result, the trap summary
  _fetch.py           cached fetch + the expect() assertions
  _sources.py         every endpoint, built by functions
  *.ipynb             11 notebooks, executed, with output
Workshop/workshop_1/  the Intro workshop
  *.ipynb             5 notebooks, executed, with output
Workshop/workshop_3/  the ML workshop
  *.ipynb             10 notebooks, executed, with output
src/ocean_data_workshop/
  data/               loaders: glorys, ncei, ndbc
  http.py             IPv4-forcing HTTP session
  dsn.py              one place that knows the database address
  workshop_setup.py   the one-command setup
scripts/              build, prefetch, load, verify
Workshop/sql_tutorials/schema.sql   the database schema, written to be read
probes/               the original source-access audit and its verdicts
Workshop/docs/GLOSSARY.md           every term used, defined
docker-compose.yml    PostgreSQL + TimescaleDB, for notebook 09
```

---

## Licence

**MIT**, for the code. See [`LICENSE`](LICENSE).

The *data* is not covered by it. Nothing is redistributed here — the repository holds an
HTTP cache so the workshop can run without a network, which is a convenience copy of
public data rather than a distribution of it. Each source carries its own terms, and if
you reuse a notebook, attribute the data to its provider and follow that provider's
licence. The list is at the bottom of the `LICENSE` file.

## Data sources

Nine of the ten sources are **anonymous** — no account, no key, no registration. One
(Copernicus Marine) needs a free account, and it is the only source of ocean *currents*,
which is why the project was built with a fallback ladder rather than around a single
dependency.

No credentials are committed. They live in `~/.copernicusmarine/` and a gitignored
`.env`.
