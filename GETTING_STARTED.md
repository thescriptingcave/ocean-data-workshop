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

A free **Copernicus Marine** account is optional. It unlocks Notebook 05 and the ocean
profile (temperature, salinity, currents).

**Verified working without one.** On a machine with no account: the three anonymous
sources load, all ten notebooks run, and Notebook 08's result is unaffected — it joins
wind to acoustics, and neither needs an account. Nothing else needs a login.

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

That is the whole thing. It:

1. checks Docker is installed and running
2. starts PostgreSQL 17 + TimescaleDB and **waits for it to be healthy**
3. applies the schema from `learning/schema.sql`
4. downloads ~15 MB of real data and loads it
5. warms the API cache so the notebooks do not depend on the network
6. registers the Jupyter kernel and checks that `jupyter lab` actually runs
7. opens Jupyter Lab on `notebooks/`

Typical time from a fresh clone: **~85 seconds**, about 15 MB of downloads. Re-run it
any time — every stage is idempotent.

`make` is a build tool: already installed with the Xcode command line tools on macOS,
and available from your package manager on Linux and Windows. If you would rather not
use it, the same two steps are:

```bash
uv run workshop-setup
uv run jupyter lab notebooks/
```

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
| `PORT=5433 make` | use a different database port |

### Already have PostgreSQL on port 5432?

```bash
PORT=5433 make
```

The port is read from `OCEAN_SIM_PORT` by the database *and* by every script that
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
setting, and it is the one thing worth knowing before you walk in. The last cell asserts the environment is
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
| `port is already allocated` | local PostgreSQL on 5432 | `PORT=5433 make` |
| `container name is already in use` | another checkout of this repo | `OCEAN_SIM_PROJECT=$(basename $PWD) PORT=5433 make` |
| `Docker is installed but the daemon is not responding` | Docker Desktop still starting | wait for it, then re-run |
| `No cached copy and no working network` | no cache archive and the network failed | the archive ships with the repo; if you deleted it, re-run `uv run python scripts/prefetch.py` |
| `ocean_profile_daily 0 <- empty` | no Copernicus account | expected. Everything else loaded; Notebook 08 still works |
| `No module named 'ocean_sim...'` | project not installed | `uv sync` |
| Every call takes exactly the timeout | **IPv6 without an IPv6 route** | already handled by the helper; if you see it in your own code, force IPv4 — see Notebook 01 |
| `Jupyter command 'jupyter-lab' not found` | `jupyterlab` not installed | `uv sync` — `workshop-setup` now checks for this |
| Notebooks are unexecuted and you want the output | reading the `.ipynb` on disk | they are committed executed; run `uv run python scripts/build_notebooks.py --execute` |
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

## Licence

No licence has been chosen yet, which means "all rights reserved" by default — nobody may
legally reuse this. If you are publishing it, add a `LICENSE` file and a `license` field
in `pyproject.toml`. The code is original; the *data* it fetches is public and belongs to
NOAA, NASA/JPL, Copernicus and the Argo programme, and carries its own terms.

## Data sources

Nine of the ten sources are **anonymous** — no account, no key, no registration. One
(Copernicus Marine) needs a free account, and it is the only source of ocean *currents*,
which is why the project was built with a fallback ladder rather than around a single
dependency.

No credentials are committed. They live in `~/.copernicusmarine/` and a gitignored
`.env`.
