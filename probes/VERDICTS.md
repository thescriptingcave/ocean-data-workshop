# Probe Verdicts

Hand-written judgements. An exit code says "the fetch worked"; this says whether the
data is *usable* and what we should do about it.

**Status: 10/10 Tier 1 probes green, including the one Class C source.** The gate (§7) is
the one item still outstanding.

---

## Machine-level gotchas (found once, fixed in `probes/_common.py`)

**`requests` was 100× slower than `curl` on this machine.** `coastwatch.pfeg.noaa.gov`
has an AAAA record but this host has **no IPv6 route**. curl races IPv4/IPv6
(Happy Eyeballs, RFC 8305) and looks fine; urllib3 waits out the full connect timeout on
the dead IPv6 address first. Every call took exactly 20.0 s — the timeout value — and
then succeeded. `force_ipv4()` in `_common.py` fixed it: 20.24 s → 0.20 s. **Any HTTP
code in this project must use `http_session()`.**

**`~/.aws/config` sets `endpoint_url = http://localhost:9000` (MinIO) in the default
profile**, so a bare `aws s3 ls` silently tries a local service and fails. Use
`--endpoint-url https://storage.googleapis.com`, or just use the GCS JSON API over HTTPS,
which needs no CLI at all.

---

## 1. gsw / TEOS-10 — PASS (arm64 wheel, no compiler)

**Units are degrees C, not Kelvin.** `gsw.sound_speed(35, 20, 0)` → 1521.2 m/s, the
textbook value for seawater. Passing 293.15 returns **NaN**. TEOS-10 defines
Conservative Temperature on the ITS-90 scale in kelvin, so the °C convention is a genuine
trap — I would have shipped a Kelvin bug. `sound_speed` takes exactly 3 args
(SA, CT, p); no `depth` argument.

**d c/dp ≈ 17 m/s per 1000 dbar**, rising monotonically with depth (16.5 → 17.7), i.e.
~1470 m/s at the surface to ~1556 m/s at 5000 dbar. I got this wrong twice while writing
the probe — first off by 100×, then by misreading a per-500-dbar delta. Checks on
physical *derivatives* (d c/dT = 3.2 m/s/°C, d c/dp) are far more robust than asserting
absolute values from memory. Recommend keeping that style.

## 2. ERDDAP — PASS (anonymous, no key, no account)

**Plan correction: NOAA OISST is not on either ERDDAP host.** Neither
`coastwatch.pfeg.noaa.gov` nor `www.ncei.noaa.gov` carries it. The anonymous SST options
are:

| Dataset | What it actually is | Resolution |
|---|---|---|
| `jplMURSST41` | JPL Multi-Resolution SST, `analysed_sst` | **0.045° — finer than OISST's 0.25°** |
| `NOAA_DHW` | Coral Reef Watch SST (not OISST) | 5 km, near-real-time |

Not a problem — MURSST is better for our purpose. OISST remains available from NCEI
directly if ever needed. ~1,000+ griddap datasets are enumerable.

**A probe's box must be small.** The full 2.5° site box at 0.045° is ~90,000 cells/day
and made the netCDF route hang. A 0.2° box is instant. Rule for all future probes.

## 3. SST at Monterey — PASS (real data, physically right)

September 2019 at 36.6 °N, 122.1 °W: **14.37 – 17.02 °C, mean 15.6**, 30 days,
13,230 valid cells, zero fills. That is exactly right for a central-California
upwelling coast in early autumn. Both CSV and netCDF routes work.

Two format traps: ERDDAP CSV has **two header rows** (names, then units) so
`skiprows=[1]` is required; and netCDF coordinates are float32, so a grid centre can land
a few millionths of a degree outside the requested box — needs a tolerance.

## 4. Toolchain — PASS

PostgreSQL 17.11 + TimescaleDB 15.2.0 in Docker, arm64, healthy in ~6 s. Hypertable
write/read works, `time_bucket()` works, plotly renders. DSN comes from
`OCEAN_SIM_DSN` so no credential is ever in the repo.

## 5. NCEI Passive Acoustic archive — PASS, and far better than expected

**Bucket is `noaa-passive-bioacoustic`, genuinely public.** No account, no key, no
signature. 29 top-level projects, and the four most relevant are all present:
`sanctsound`, `mbarc_socal` (Southern California — nearest to Monterey),
`dclde` (labelled ML challenge data), `soundcoop`, `nrs`, `mbari`.

Layout is `<project>/products/<type>/<site>/<dataset>/{data,metadata}/`. The mandatory
`/data/` level is a trap — omitting it returns a confusing `NoSuchKey` rather than a 404.

**The labelled data is much richer than the plan assumed.** Every CI deployment has
13 detection classes: `ships`, `dolphins_1h`, `bluewhale`, `bluewhale_manual`,
`finwhale`, `finwhale_1d`, `humpbackwhale_1d`, `bocaccio`, `pinnipeds`,
`plainfinmidshipman`, `explosions`, `sonar`, plus more. `ci02` alone has 48 datasets.
That is a genuine multi-class problem, not a binary one.

## 6. NCEI detection labels — PASS, with one serious caveat

Dolphin presence at CI02_04: **2,787 hourly rows, 1.22% positive (34 of 2,787)**,
**perfectly contiguous — zero gaps across 2,786 hours**, Feb–May 2020.

Two things follow, and both are good news for the learning goals:

- The 1.22% positive rate makes **"accuracy is a lie" a real lesson, not a hypothetical.**
  A model predicting "never" scores 98.8%.
- Contiguity means `LAG`, running frames, and gap logic work naturally on it.

**The caveat is real, though:** these labels are *algorithm output*, not ground truth.
Dolphin detections come from PamGuard's whistle/moan detector; vessel events from LTSA
analysis. A classifier trained on them may simply reproduce PamGuard. This is why the
Friday test — *can a one-line rule already get 99%?* — matters. If it can, the task is
trivial and we define our own target instead. **Not yet tested.**

**Also: trust netCDF, not CSV.** The `SanctSound_CI02_04_ships.csv` is 0 bytes; the
matching `.nc` is 18 KB with real variables. Always probe the netCDF.

## 7. Argo profiles — PASS, but `argopy` is unusable

**argopy is currently broken.** Both 1.3.1 and 1.4.0 import
`erddapy.erddapy._quote_string_constraints`, a private symbol removed in erddapy 3.x.
1.4.0 additionally caps `xarray<=2025.9.0`. Making it work means pinning `erddapy<3`
*and* downgrading xarray — a bad trade when ERDDAP already works.
**Decision: no argopy. Removed from the project.** Fetch GDAC files directly.

GDAC is plain browsable HTTPS, no account. `/dac/<dac>/<wmo>/<wmo>_prof.nc` holds
**every cycle for a float in one file** — 98 cycles × 92 levels in 673 KB. That is a much
better granularity than 98 separate files.

**QC flags are stored as bytes, not integers,** in the aggregated `_prof.nc`
(`b'1'`, `b'nan'`, `b'4'`). Comparing bytes to an int silently returns all-False and
reads as "no good data" rather than raising. `probes/probe_07_argo.py::_decode_qc`
handles both encodings. Decoded result for this float: **98.4% good, 4 bad, 140 fill**,
T 3.69–25.85 °C, to 2014 dbar.

Argo is **not** on the ERDDAP hosts checked (coastwatch, argo.ucsd.edu, data-argo), and
`argo.ucsd.edu/erddap` has no griddap index. For **geographic box queries** use Copernicus
`INSITU_GLO_TS_OA` instead — which needs the account the plan already assumes.

---

## 8. GLORYS12V1 — PASS (the only Class C source, and it works)

**Account works.** `copernicusmarine login` cached credentials to
`~/.copernicusmarine/` — outside the repo. `.env` holds the credentials and is already
gitignored. No credential has entered version control.

Catalogue facts worth recording, because the default invocation is expensive and the
CLI flags are not what you would guess:

| Fact | Detail |
|---|---|
| Product id | `GLOBAL_MULTIYEAR_PHY_001_030` — this *is* GLORYS12V1 (1/12°, 50 levels) |
| Datasets | `..._P1D-m` (daily), `..._P1M-m` (monthly), `..._climatology_P1M-m`, `..._static` |
| **`describe` with no filter** | downloads a **170 MB** catalogue. Always pass `--contains` or `--product-id` |
| CLI flags | `--end-datetime` (not `--stop-datetime`), `--file-format` / `--overwrite` (not `--output-format` / `--overwrite-existing`) |
| Variables | advertised as **0** in the catalogue; discovered from the netCDF. Request `thetao`, `so`, `uo`, `vo`, `zos` by name |

**What the data actually shows at Monterey, September 2019 — and this is the important part:**

- 30 days × 19 levels over 0.5–55.8 m
- Surface **15.6 °C** over deep **11.0 °C** — normal stratification
- **Thermocline at 15.8 m**
- **The thermocline moves 21.1 m across the month** (0.5 → 21.6 m)
- Currents present: mean |u,v| = **0.041 m/s**, u up to 0.066, v up to 0.194

That movement is what makes the central SQL question real. The plan's headline was
*"when did the thermocline cross 40 m?"* — and at this site it never reaches 40 m in this
month, but it crosses 10, 15, and 20 m, which is the same question with an answer in it.
**The question needs restating for the site, not abandoning.** The duct ceiling above a
40 m mooring therefore moves through the month, which is exactly the ducting behaviour
worth studying.

One artefact to watch: on some days the strongest gradient lands on the shallowest
available level (0.5 m), which is a surface-grid artefact rather than a real
thermocline. Depth-index tracking needs to ignore the first couple of levels.

This is also the **only** probed source that supplies currents — Argo gives profiles but
no velocity, and ERDDAP gives surface temperature only. So the "direction" metric from the
original brief is available *only* from here, which is why Class C was worth registering
for.

## Plan changes arising

| Was | Now | Why |
|---|---|---|
| OISST via ERDDAP | **`jplMURSST41` via ERDDAP** | OISST absent; MURSST is finer |
| `argopy` for Argo | **GDAC direct** | argopy broken against erddapy 3.x |
| Argo by geographic box | **Copernicus `INSITU_GLO_TS_OA`** | no ERDDAP Argo; needs the Class C account |
| binary labels (ship vs dolphin) | **multi-class, 13 classes** | far richer than assumed |
| raw audio as the acoustic source | **detections + sound-level metrics first** | labels and HMD are the learning payload |
| "when did the thermocline cross 40 m" | **"cross 10 / 15 / 20 m"** | at this site it reaches 21.6 m, not 40 m. Same question, with an answer in it |
| hydrophone at 48 kHz | **96 kHz, 116 m deep, 16 km away** | from the metadata index; 48 kHz clips the dolphin click band |
| wind from buoy 46042 | **wind from 46092 (MBM1), 10 km** | 46042's direction sensor was out for the entire window |
| acoustic anchor in the Channel Islands | **MB01, Monterey Bay itself** | the metadata index put the nearest site 16 km away, in the same bay |
| acoustic product unspecified | **third-octave `tol_1h`, never `psd_1h`** | 0.7 MB vs 456 MB per deployment |
| September-only analysis window | **widen it** | 30 daily points is too few for the lag correlations we want; both sources allow longer |

## Outstanding

- **The gate step 3 is still yours.** Steps 1–2 are done: `scripts/gate_look.py` produces
  three figures, and the month has two thermal phases plus a quasi-periodic ~9–10 day
  current oscillation. What is missing is three questions *you* want to ask.
- **Widen the analysis window.** September alone gives 30 daily points, which is too few
  to trust the lag correlations. Both GLORYS (from 1993) and NDBC (decades) allow much
  longer.
- **The ML question is untested.** Whether a one-line rule already solves the dolphin
  labels decides whether that exercise is real or needs a self-defined target.
- **Watkins, OBIS, Orcasound, ShipsEar, WOA23, GEBCO, NDBC, HYCOM** — Tier 2/3, not yet probed.
