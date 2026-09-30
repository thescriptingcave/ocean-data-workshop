# ocean-data-workshop

Hands-on workshops for getting real ocean data out of public APIs — the parts that are
documented badly, and the parts that are not documented at all.

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

| | notebook | access pattern | source |
|---|---|---|---|
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

Organised by **access pattern** rather than by dataset, because the patterns transfer and
the datasets do not. Ends with a result: across 30 frequency bands, wind's correlation
with underwater noise is 0.204 below 500 Hz and 0.699 above 2 kHz, and **21 of the 30
bands clear a block-bootstrap significance test** — significance climbing with
frequency, because the low bands are where the wind signal is buried in noise and the
high bands are the click band.

**39 traps** found while building it, catalogued in Notebook 10 — **38 reproduced against
live services**, the remaining one documented from the service's own behaviour, and not
one of them documented anywhere.

## The next workshop: ML on real labels

**Not built yet.** Before writing a lesson, the question worth answering is whether
there is a real learning task here at all — and on this data there is a specific reason
to doubt it.

NOAA's `ships` and `dolphin` labels are **algorithm output**: vessel events from LTSA
analysis, dolphin detections from PamGuard. The hourly third-octave levels are *also*
derived from LTSAs. So predicting a detection from a band level is close to predicting a
quantity from itself. That is circular by construction, and the way to find out is not
to argue about it but to measure it.

`scripts/ml_triviality.py` does exactly that:

```bash
make ml
```

The verdict is **a green light with a large asterisk**, and the asterisk is the
interesting part. It is worth recording in full, because the reasoning generalises
further than the conclusion does.

- **`ships` is not a target at all.** 2,942 hours, 100% positive — it is an event list,
  not a classification problem. A model on it would be measuring nothing.
- **`dolphin` is a real task.** 8,387 hours, 22.6% positive, majority baseline 0.803.
- **It is not the naive circularity.** A full model plateaus at 0.898, nowhere near the
  1.0 that would mean the labels are recoverable from the same LTSA the bands came from.
  The permutation control lands exactly on the majority rate, and the split is honestly
  time-based, so nothing is leaking.

Then three measurements that the first version of this spike did not make, and which
change the conclusion:

| | accuracy | f1 |
|---|---|---|
| always predict the majority | 0.803 | — |
| **persistence: "was there one an hour ago?"** | **0.872** | 0.676 |
| all 30 bands, no history | 0.898 | 0.700 |
| lags + all 30 bands | 0.910 | 0.753 |
| lags + bands **minus 20 kHz** | 0.876 | 0.647 |

**Persistence alone scores 0.872 against the model's 0.898.** The label arrives in
blocks — 86.5% hour-to-hour agreement, 565 positive runs, longest 21 hours — so most of
the apparent skill is "it was there an hour ago", and a one-line rule gets most of the
way there.

And nearly all of what remains lives in **one band**. Shuffling only the 20 kHz column
at test time takes the model from 0.898 to 0.548; removing it from the model entirely
gives back almost nothing (+0.003 over lags alone).

That band is the one that matters, because of where the data stops:

```
tol_1h    25 ..  20000 Hz     30 bands
ol_1h   31.5 ..  16000 Hz     10 bands
psd_1h    20 ..  24000 Hz  23,981 bins
```

The recorder samples at **96 kHz**, but no public product carries energy above ~24 kHz,
and dolphin echolocation peaks far above that. So the single band the model relies on is
the only band in the feature set that comes near the signal the label was derived from.

**So: real, reproducible, and worth teaching — but a one-band task, whose one band is the
one adjacent to the label's own provenance.** The features and the labels share a sensor
and a processing chain. A model can work well and still be nearly uninformative about
biology, because what it recovered was "was there a transient in this window", not "was
there a dolphin". That is a real, subtle, and rarely-taught distinction, and it is a much
better workshop than a clean detector would have been.

Two more traps fall out of the same measurements: **a random split overstates accuracy**
on a time series, and **train/test prevalence differ** (23.6% vs 19.7%) so an accuracy
figure can fall while recall rises.

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

**Use `http_session()`, never bare `requests`.** The ERDDAP host
(`coastwatch.pfeg.noaa.gov`) publishes an AAAA record that some networks cannot route.
curl races addresses (Happy Eyeballs); urllib3 waits out the full connect timeout on the
dead IPv6 address first — measured here as **31–36 s per 1.3 kB fetch** against curl's
0.53 s, and 1.4 s with the fix. This is a property of the host and the network between
them, not of your machine. Notebook 04 covers the same class of problem from the other
side.

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
notebooks/       Workshop Advanced — 11 notebooks
  _fetch.py      a real requests.Session, caching in send() only
  _sources.py    one manifest of every URL, shared with the prefetch
  cache-archive.tar.gz   the prefetched responses, so CI runs offline
learning/        teaching material: schema.sql is the source of truth for the database
scripts/         the builders, and the tooling around them
  workshop_notebooks.py  all notebook content -- never edit a .ipynb
  build_notebooks.py     render + execute, fail on error or a silent cell
  build_beginners.py     the same for Workshop Intro, self-contained
  load_db.py     apply the schema, load the data (--with-ocean for the slow part)
  prefetch.py    warm the response cache
  ml_triviality.py      the feasibility spike for the next workshop
src/              ocean_data_workshop/ -- setup, credentials, DSN, HTTP helpers
  workshop_setup.py     the 6-stage setup behind `make`
probes/          Phase -1 access probes
  _common.py     contract, cache, verdict format, IPv4-forcing HTTP session
  probe_NN_*.py  one per dataset, exposing fetch(tiny=True)
  run_all.py     runs everything, regenerates INVENTORY.md
  VERDICTS.md    hand-written judgements — the real output
  RESULTS.jsonl  append-only history, including fixed failures
  LATEST.json    most recent result per probe
tests/            unit tests, fast and offline
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

The standing test for any addition here: **a plausible number is not a correct number,
and access is not interest.**

Phase -1 passed its half of that by proving *access* — 10/10 Tier 1 sources, with the
judgements in [`probes/VERDICTS.md`](probes/VERDICTS.md). The other half is now carried
by the capstone, which joins three independently-fetched sources in SQL and reports a
result that survives a block bootstrap. That is the bar a new lesson has to clear: it
should end in a number you would defend, not a DataFrame you can print.
