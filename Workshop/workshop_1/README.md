# Workshop 1 (Intro)

If you have never fetched a URL, start here and skip everything below.

```bash
pip install -r Workshop/workshop_1/requirements.txt
jupyter lab Workshop/workshop_1/
```

Five notebooks, about 40 minutes, against three real ocean services that need no key.
One notebook per response shape — comma-separated text, JSON, compressed text — with
the same four techniques (`curl`, `requests`, `pandas`, `duckdb`) applied to each so
the second and third are recognisable. Each one gets it working *first*, then shows
what quietly went wrong.

Deliberately nothing else: no database, no Docker, no `make`, no `.env`, no cache, no
accounts. It does not import a single thing from the rest of this repository, and CI
tests it that way so it stays true.

## What you'll get

By the end of Workshop Intro, you will be able to:

- Fetch data from public APIs using Python
- Parse CSV, JSON, and compressed text responses
- Analyze data with pandas and DuckDB
- Understand the four fundamental access patterns for ocean data

## Notebooks

| # | Topic | Duration | Access |
|---|-------|----------|--------|
| 00 | A URL is a thing you can fetch | 8 min | — |
| 01 | Comma-separated text | 8 min | NDBC 46092 |
| 02 | JSON | 8 min | NCEI passive acoustics |
| 03 | Compressed text | 8 min | Argo GDAC |
| 04 | You write them | 8 min | — |

## Run the workshop

```bash
# Install dependencies
pip install -r Workshop/workshop_1/requirements.txt

# Open Jupyter Lab
jupyter lab Workshop/workshop_1/
```

## No setup required

This workshop is completely self-contained. No database, no Docker, no credentials, no
API keys. Just Python and Jupyter.