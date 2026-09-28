# Probe Verdicts

Hand-written judgements. An exit code says "the fetch worked"; this says whether the
data is *usable* and what we should do about it.

**Status: 7/7 Tier 1 probes green.** The gate (§7) is the one item still outstanding.

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

## Plan changes arising

| Was | Now | Why |
|---|---|---|
| OISST via ERDDAP | **`jplMURSST41` via ERDDAP** | OISST absent; MURSST is finer |
| `argopy` for Argo | **GDAC direct** | argopy broken against erddapy 3.x |
| Argo by geographic box | **Copernicus `INSITU_GLO_TS_OA`** | no ERDDAP Argo; needs the Class C account |
| binary labels (ship vs dolphin) | **multi-class, 13 classes** | far richer than assumed |
| raw audio as the acoustic source | **detections + sound-level metrics first** | labels and HMD are the learning payload |

## Outstanding

- **The gate (§7 of the phase plan) is not done.** Load a month, plot time × depth, and
  write down three questions. Everything above proves *access*; nothing yet proves
  *interest*.
- **Class C untested.** Copernicus registration and first subset. This is the only
  friction-gated item left, and it blocks T/S/u/v/SSH. The fallback ladder holds without
  it (ERDDAP SST + Argo GDAC), but those give surface temperature and profiles — not
  currents, and not a full 4D field.
- **Watkins, OBIS, Orcasound, ShipsEar, WOA23, GEBCO, NDBC, HYCOM** — Tier 2/3, not yet probed.
