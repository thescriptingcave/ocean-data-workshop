# Workshop Advanced

Eleven notebooks on getting real ocean data out of public APIs — the parts that are
documented badly, and the parts that are not documented at all. Assumes you have
fetched a URL before; if not, do the Intro first.

```bash
make                            # setup, then open Jupyter Lab
```

About 85 seconds from a fresh clone.

That is the whole thing: it installs dependencies, starts the database and waits for it
to be healthy, loads the data, warms the API cache, registers the Jupyter kernel, and
opens Jupyter on the notebooks. If the network is bad, `make lab-offline` does the same
with the network forbidden -- also one command.

Without `make`, it is two:

```bash
uv run workshop-setup
uv run jupyter lab notebooks/
```

`make help` lists the rest: `make test`, `make check` (every notebook with the network
forbidden), `make fresh` (clone to a temp dir and run setup from nothing).

**One notebook needs a live network: 04, access policy.** It reads what S3 and BigQuery
say *right now* about who may read them, so it deliberately bypasses the response cache
— a cached `403` would outlive the policy that produced it. Every other notebook runs
offline from cache, which is why CI can execute ten of the eleven with the network
forbidden and gives 04 a job of its own.

## What you'll get

By the end of Workshop Advanced, you will be able to:

- Fetch data from ERDDAP, GCS, Argo GDAC, Copernicus Marine, and NDBC
- Understand the five access patterns: REST, griddap, object storage, access policy, netCDF
- Join data from multiple sources in SQL with TimescaleDB
- Recognize 39 common traps when working with ocean data

## Notebooks

| # | Topic | Access Pattern | Source |
|---|-------|----------------|--------|
| 00 | Orientation | — | — |
| 01 | **The request, three ways** | HTTP fundamentals | ERDDAP |
| 02 | Query a grid, dimensionally | REST griddap | ERDDAP SST |
| 03 | List a bucket, fetch one object | cloud object storage | NOAA NCEI GCS |
| 04 | **Who is allowed to read this?** | access policy | S3 + BigQuery — live only |
| 05 | Browse a tree, read netCDF | browsable netCDF | Argo GDAC |
| 06 | Authenticate, then query | credentialed API | Copernicus Marine |
| 07 | Parse fixed-format text | delimited text | NDBC 46092 |
| 08 | When a library beats a request | domain library | `gsw` |
| 09 | **Capstone: join three sources** | all of the above | + TimescaleDB |
| 10 | **The trap table** | reference | — |

## Prerequisites

- Basic Python knowledge
- Has fetched a URL before (from Workshop Intro or otherwise)

## Run the workshop

```bash
make                            # setup, then open Jupyter Lab
```

## Offline mode

If the network is bad or unavailable:

```bash
make lab-offline
```

Everything works from cache. Each request prints a warning that it is using a cached
response — this is expected, and the numbers are still correct.