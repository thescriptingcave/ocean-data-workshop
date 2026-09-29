# ocean-sim

An ocean **data workbench** for learning time-series SQL and ML on real public data.

Not a simulator. For observational data the measurements *are* the answer — the job is
to interpret them, not to predict them.

## Start here

**Pick the tier that matches you.** They share no code and no setup.

| | if you have… | start |
|---|---|---|
| **Workshop Intro** | never fetched a URL | [`beginners/README.md`](beginners/README.md) — 5 notebooks, 40 min, 5 packages |
| **Workshop Advanced** | used `requests` before | [`notebooks/README.md`](notebooks/README.md) — 11 notebooks, a database, ~39 catalogued traps |

The Intro is standalone: no database, no Docker, no `make`, no `.env`, no account, no
API key. `pip install -r beginners/requirements.txt` and open Jupyter Lab.

Also:

**→ [`GETTING_STARTED.md`](GETTING_STARTED.md)** — from nothing to running, ~85 seconds
**→ [`GLOSSARY.md`](GLOSSARY.md)** — every term used, defined

**MIT licensed** for the code — see [`LICENSE`](LICENSE). The data it fetches is not
covered; see the bottom of that file.

If you are contributing: [`CONTRIBUTING.md`](CONTRIBUTING.md) — the notebooks are
generated, do not edit the `.ipynb` files.

## Workshop Intro

If you have never fetched a URL, start here and skip everything below.

```bash
pip install -r beginners/requirements.txt
jupyter lab beginners/
```

Five notebooks, about 40 minutes, against three real ocean services that need no key.
One notebook per response shape — comma-separated text, JSON, compressed text — with
the same four techniques (`curl`, `requests`, `pandas`, `duckdb`) applied to each so
the second and third are recognisable. Each one gets it working *first*, then shows
what quietly went wrong.

Deliberately nothing else: no database, no Docker, no `make`, no `.env`, no cache, no
accounts. It does not import a single thing from the rest of this repository, and CI
tests it that way so it stays true.

## Workshop Advanced

Eleven notebooks on getting real ocean data out of public APIs — the parts that are
documented badly, and the parts that are not documented at all. Assumes you have
fetched a URL before; if not, do the Intro first.

```bash
make                            # setup, then open Jupyter Lab
```

Under a minute from a fresh clone.

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

Organised by **access pattern** rather than by dataset, because the patterns transfer and
the datasets do not. Ends with a result: across 30 frequency bands, wind's correlation
with underwater noise is 0.204 below 500 Hz and 0.699 above 2 kHz, and every one of the 9
bands that fails a block-bootstrap significance test is below 200 Hz.

**39 traps** found while building it, catalogued in Notebook 10 — **39 reproduced against
live services**, the rest documented from the service's own behaviour, and not one of them documented anywhere.

## Phase -1: data access audit

The first phase answers one question about every candidate dataset: **can we get it, and
what does getting it cost?**

```bash
uv run python -m probes.run_all
```

Writes `probes/INVENTORY.md` (generated, ticked per probe). The human judgement —
which is the real output — is in **[`probes/VERDICTS.md`](probes/VERDICTS.md)**.

Current status: **10/10 Tier 1 probes passing, including the one Class C source.**

## Access classes

| Class | Meaning | One-time cost |
|---|---|---|
| **A** | Anonymous HTTP. No account, no key. | 0 |
| **B** | Anonymous, other protocol (FTP, OPeNDAP). | 0–1 hr |
| **C** | Free account, password login. | 5–15 min |
| **D** | Free account + API key. | 10–30 min |
| **E** | Account + terms or approval. | 1 day–2 weeks |
| **F** | Manual request — email, form, a person. | days–weeks |
| **G** | Licensed. Free academic, commercial prohibited. | constrains the project |
| **H** | Unavailable. | — |

A and B are free wins. E, F, and G are where projects die.

## What works, with no account and no key

| Source | Gives | Access |
|---|---|---|
| **NCEI passive acoustic** (`noaa-passive-bioacoustic`, GCS) | hydrophone detections, sound-level metrics, clips | A |
| **Argo GDAC** (`data-argo.ifremer.fr`) | in-situ T/S/pressure to 2000 m, QC flags | A |
| **ERDDAP** (`coastwatch.pfeg.noaa.gov`) | `jplMURSST41` SST at 0.045°, 1,000+ griddap datasets | A |
| **NDBC 46092 (MBM1)** | hourly wind speed/direction, gusts, air and sea temperature | A |
| **GEBCO / WOA23 / HYCOM** | bathymetry, climatology, reanalysis | A/B |
| **GLORYS12V1** (Copernicus Marine) | daily T/S/**currents**/SSH, 1/12°, 50 levels | **C** |

The acoustic side is the strongest find. The SanctSound CI sites carry **13 labelled
detection classes** (`ships`, `dolphins_1h`, three whale species, `bocaccio`,
`pinnipeds`, `plainfinmidshipman`, `explosions`, `sonar`, …) with hourly 0/1 presence.

A `big_query_metadata/` index in the same bucket catalogues all 25,503 recording files
with coordinates and sensor depths, which is how the acoustic anchor was chosen: a
hydrophone **16 km from the ocean site, moored at 116 m, recording at 96 kHz** — deep
enough for a real sound channel, and fast enough to capture the 30–50 kHz dolphin click
band. Same upwelling system as the GLORYS site, so the CTD and the hydrophone describe
the same water mass. That join is what the project rests on.

**GLORYS12V1 is the only source supplying currents** — Argo has profiles but no
velocity, ERDDAP has surface temperature only — so the Class C account is load-bearing
for the "direction" metric. It shows a thermocline at 15.8 m that **moves 21 m across
the month**, which is what makes the central SQL question answerable.

## Setup

```bash
uv sync
docker compose up -d          # TimescaleDB on :5432
export OCEAN_DATA_WORKSHOP_DSN="postgresql://postgres:ocean@localhost:5432/ocean_data_workshop"
```

## Two machine gotchas, already handled in `probes/_common.py`

**Use `http_session()`, never bare `requests`.** This host has AAAA records but no IPv6
route. curl races addresses (Happy Eyeballs); urllib3 waits out the full connect timeout
on the dead IPv6 address first — a measured **100× slowdown**, every call.

**`aws s3` is redirected to MinIO.** `~/.aws/config` sets
`endpoint_url = http://localhost:9000` in the default profile, so bare `aws s3 ls` fails
against a local service. Pass `--endpoint-url https://storage.googleapis.com`, or use the
GCS JSON API, which needs no CLI at all.

## Layout

```
beginners/       Workshop Intro — 5 notebooks, own requirements.txt
  00_..ipynb     a URL is a thing you can fetch
  01_..ipynb     comma-separated text
  02_..ipynb     JSON
  03_..ipynb     compressed text
  04_..ipynb     you write them
probes/          Phase -1 access probes
  _common.py     contract, cache, verdict format, IPv4-forcing HTTP session
  probe_NN_*.py  one per dataset, exposing fetch(tiny=True)
  run_all.py     runs everything, regenerates INVENTORY.md
  VERDICTS.md    hand-written judgements — the real output
  RESULTS.jsonl  append-only history, including fixed failures
  LATEST.json    most recent result per probe
```

Downloads cache to `~/.cache/ocean-sim-harness/` and are reused by later phases, so the
probes are not throwaway work.

## Dependencies that are *not* used

- **`argopy`** — broken. Both 1.3.1 and 1.4.0 import a private symbol removed in
  erddapy 3.x. GDAC is fetched directly instead.
- **Any ORM** — hypertables, `time_bucket()`, and the window functions this project
  exists to learn are raw-SQL features an ORM would obscure.

## Wind: the obvious source is broken

The nearest buoy to the ocean site, **46042** (36 km), lost its **wind-direction sensor
on 2019-08-18** and did not recover it until the end of December. September is 100%
missing. Speed kept reporting; direction did not — and the northerly component that
drives California upwelling is derived from direction, so the most important variable for
this site was absent for the entire planned window.

**46092 ("MBM1"), 10 km away, is complete** and is now the primary wind source. Mean
5.4 m/s from 316° — northwesterly and upwelling-favourable, confirming the site is in
the right dynamical setting.

The strongest relationship in the dataset is northerly wind leading southward current by
about six days (r = −0.61), which matches the known Ekman spin-up timescale. But 30 daily
points is thin for a lag correlation, so the window should be widened before that number
is trusted.

## The gate

Phase -1 is not finished until the gate passes: **load a month, plot time × depth, and
write down three questions worth asking.** Everything here proves *access*. Nothing yet
proves *interest*.
