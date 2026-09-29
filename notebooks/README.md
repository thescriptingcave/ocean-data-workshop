# Workshop Advanced — data retrieval

Ten notebooks on getting real ocean data out of public APIs — the parts that are
documented badly, and the parts that are not documented at all.

Built around real data from **Monterey Bay, California**: sea surface temperature from
ERDDAP, 30-band underwater sound from NOAA's passive acoustic archive, wind from an NDBC
buoy, temperature/salinity/currents from GLORYS, and T/S profiles from an Argo float.

**If you have never fetched a URL, do [Workshop Intro](../beginners/README.md) first** —
40 minutes, five packages, no database. These notebooks assume you already have.

## Also read

- **[`../GETTING_STARTED.md`](../GETTING_STARTED.md)** — from nothing to running
- **[`../GLOSSARY.md`](../GLOSSARY.md)** — every term used, defined

## Run it

```bash
git clone <this repo> && cd ocean-sim
make            # setup, then open Jupyter Lab
```

One command sets up everything, and it behaves identically on **macOS (Apple silicon),
Linux and Windows** — it is Python, not shell, specifically so a `.sh` and a `.bat` cannot
drift apart. It installs dependencies, starts PostgreSQL, waits for it to be *healthy*,
applies the schema, loads the data, and warms the API cache.

Typical time from a fresh clone: **~85 seconds**, about 15 MB of downloads.

Already have PostgreSQL on 5432? Use another port — the database and every script read
the same variable:

```bash
uv run workshop-setup --port 5433
```

## The network is not a dependency

Every request goes through a helper that tries the network, caches the response, and
falls back to cache on *any* failure — timeout, DNS, 5xx, rate limit — printing a loud
warning. The whole workshop was verified with the network switched off:

```bash
OCEAN_SIM_OFFLINE=1 uv run jupyter lab notebooks/
```

Worst case is a stale-but-real response with a warning, rather than thirty people
watching a traceback. Venue wifi is the one thing you cannot control and the one thing
that ends data workshops.

## The notebooks

| # | notebook | access pattern | source |
|---|---|---|---|
| 00 | Orientation | — | — |
| 01 | **The request, three ways** | HTTP fundamentals | ERDDAP |
| 02 | Query a grid, dimensionally | REST griddap | ERDDAP SST |
| 03 | List a bucket, fetch one object | cloud object storage | NOAA NCEI GCS |
| 04 | Browse a tree, read netCDF | browsable netCDF | Argo GDAC |
| 05 | Authenticate, then query | credentialed API | Copernicus Marine |
| 06 | Parse fixed-format text | delimited text | NDBC 46092 |
| 07 | When a library beats a request | domain library | `gsw` |
| 08 | **Capstone: join three sources** | all of the above | + TimescaleDB |
| 09 | **The trap table** | reference | — |

Organised by **access pattern**, not by dataset: the patterns transfer to sources none
of us have heard of, and the datasets do not.

Every notebook follows the same six steps — what you should get, on the wire, in Python,
in a library, **traps here**, what you got — and ends with assertions that *fail* if the
data is wrong. A wrong response that looks fine is the failure mode that costs an
afternoon.

## Two ways to run it

Notebooks are committed **with output**, so they read cold, days later, without having
been run. They also all still execute, and each is independently runnable — none depends
on another having been run first.

```bash
uv run python scripts/build_notebooks.py --execute   # rebuild + rerun, with output
```

One notebook failing does not stop the others; during a build you want to know everything
that is broken, not just the first thing.

## The result

Notebook 08 joins wind to underwater noise across 30 frequency bands, over 313 days:

| | mean \|r\| | bands |
|---|---|---|
| 500 Hz and below | 0.204 | 14 |
| above 2 kHz | 0.699 | 10 |

21 of 30 bands reach p<0.05 under a block bootstrap, and **every one of the 9 that do
not is below 200 Hz**. Wind explains essentially nothing below 200 Hz and a great deal
above 250 Hz.

The `r` is not a significance test on its own: the series are autocorrelated, and the
effective sample size is about 128 from 313 daily points — a 2.4× reduction. A naive test
is overconfident by roughly that factor.

## The trap table

Notebook 09 lists **35 traps** found while building this material, **34 of them reproduced against
live services**, and none of them documented anywhere. A sample:

| trap | symptom |
|---|---|
| `curl` reads `[` `]` as a glob pattern | exit 3, `URL malformat`, no message under `-s` |
| ERDDAP CSV has a names row *and* a units row | first row of strings, off-by-one everywhere |
| ERDDAP's index expression is part of the parameter *name* | `500` — and `requests` cannot express it |
| `.time=first` is a **no-op** | byte-identical response; you get 520× the data you asked for |
| the `data/` level is mandatory when fetching GCS objects | `404` + `NoSuchKey` — reads as a permissions problem |
| GCS filename capitalisation | directory all-lower, file title-case, unit `1h` not `1H` |
| Argo QC flags are **bytes** in aggregated files | `== 1` is silently all-False |
| NDBC line 0 is names, line 1 is units | columns come out as `#yr`, `mo`, `dy` |
| `RangeIndex` Series into a `DatetimeIndex` frame | aligns on index; every column silently NaN |
| `gsw` takes °C, not Kelvin | returns `nan` with only a `RuntimeWarning` |

The five recurring shapes behind them, and the one habit that prevents most of them, are
in the notebook.

## Layout

```
notebooks/            the workshop
  _fetch.py           cached fetch + expect() assertions
  _sources.py         every endpoint, built by functions
  *.ipynb             10 notebooks, executed, with output
src/ocean_data_workshop/
  data/               loaders: glorys, ncei, ndbc
  http.py             IPv4-forcing session
  dsn.py              one place that knows the database address
  workshop_setup.py   the one-command setup
scripts/
  build_notebooks.py  render + execute the notebooks
  prefetch.py         warm the cache
  load_db.py          idempotent loader
learning/schema.sql   the schema, written to be read
probes/               the original source-access audit
```

`_fetch.py` returns a **real `requests.Session`**. It overrides exactly one method,
`send`, and that single override is the whole cache — so the code in the notebooks is
code you would write in your own project, and nothing needs unlearning afterwards. An
earlier version wrapped `requests` in a `_fetch.get()` function returning a custom type;
it made the workshop robust and it made the workshop useless, because nobody learned
`requests` and the parsing of a response into a DataFrame was hidden in a return type.
Notebook 01 now has a section on exactly that step.

`_sources.py` exists so the prefetch and the notebooks cannot disagree about a URL. Both
build every request from the same functions — hand-written URLs in the manifest caused a
silent cache miss on all four GCS entries, and the notebooks then made live calls in a
room, which is the exact failure the cache exists to prevent.

## Licence and data

All sources are public and anonymous except Copernicus Marine, which needs a free
account. No credentials are committed; they live in `~/.copernicusmarine/` and a
gitignored `.env`.
