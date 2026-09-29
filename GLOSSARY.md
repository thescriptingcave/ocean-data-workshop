# Glossary

Every term used in the workshop, defined. Terms are marked with the notebook they appear
in where that is useful.

Two vocabularies meet here and it is worth separating them early: **ocean science**,
which the room knows, and **data plumbing**, which is what the workshop is actually
about. The expensive misunderstandings happen at the boundary.

---

## Data access patterns

The six patterns the workshop is organised by. These transfer; the datasets do not.

**REST griddap** — *NB 02*
An HTTP interface that addresses a multidimensional array by index expression, in the
server's own dimension order. You name the variable and a range per axis, and the server
returns a slice. ERDDAP is the reference implementation.

**Index expression** — *NB 01, 02*
The bracketed ranges in a griddap query: `[(start):(stop)][(lat0):(lat1)][(lon0):(lon1)]`.
Critically, this is part of the **parameter name**, not its value — which is why
`requests`' `params=` cannot build one.

**Degenerate range** — *NB 01, 02*
A range whose start equals its stop: `[(36.6):(36.6)]`. A valid way to ask for exactly one
cell. This is how you actually shrink an ERDDAP response — 1,324 B instead of 690,813 B
for the same month.

**ERDDAP** — *NB 01, 02, 03*
A NOAA service that puts a griddap/REST interface in front of dozens of ocean and climate
datasets. Anonymous, no key, and the easiest place to start learning this.

**OPeNDAP** — the protocol ERDDAP and friends implement; the `.nc` response format is
the same regardless of transport.

**Cloud object storage** — *NB 03*
A bucket of files addressed by path, with no query language and no search. GCS, S3, Azure.
List a prefix, fetch an object. Most large public archives are one of these.

**Prefix / delimiter** — *NB 03*
The two halves of an object listing. `prefix` says where to start, `delimiter` says where
to stop rolling up. With `delimiter="/"` you get directories back; without it, files.

**Browseable tree** — *NB 04*
A plain web directory of files you can fetch and list by reading the HTML. Argo's GDAC is
one. No API, which is both its simplicity and its cost.

**GDAC / DAC / WMO number** — *NB 04*
Argo's *Global Data Assembly Centre*; a *Data Assembly Centre* within it; and a float's
7-digit WMO identifier, which is its filename everywhere. Float `1900063` is at
`dac/coriolis/1900063/`.

**Credentialed API** — *NB 05*
One that requires an account. Exactly one source in this workshop, and the only source of
ocean currents.

**Fixed-format text** — *NB 06*
A gzipped, column-oriented text file with a fixed header and no structure or
self-description. The oldest pattern here and the one that most quietly corrupts
analyses, because nothing in it raises an error.

**Domain library** — *NB 07*
A package that already knows the physics. `gsw` implements TEOS-10. Use it — but read
which units it wants, because it will not tell you.

---

## Formats and encodings

**netCDF** (`.nc`)
A self-describing array format built for climate data. Carries dimensions, coordinates
and units *with* the data, so a reader does not have to be told what the columns mean.
The right default: `.nc` responses are smaller **and** self-documenting.

**CF conventions** (Climate and Forecast)
The metadata standard netCDF files follow, which is what makes them portable. ERDDAP
declares `Conventions: CF-1.6, COARDS, ACDD-1.3`.

**xarray**
The Python library that makes labelled netCDF pleasant. Introduces the idea that a
variable has *dimensions* and *coordinates* rather than columns.

**Unpivot / long format**
Turning a wide table — one column per frequency band — into one row per band, so you can
group by it. In SQL, `CROSS JOIN LATERAL` over a `VALUES` list. See *NB 08*, where the
acoustic table is wide and `GROUP BY band_hz` does not resolve at all.

**Wide vs long**
*Wide*: a column per category. *Long*: a row per category. Wide is natural for measured
channels and hostile to analysis.

**float32**
Single precision, about 7 significant decimal digits. ERDDAP stores its grid this way, so
a coordinate you asked for as `36.60` can come back as `36.599998` — outside your own
box, by a few millionths. Compare with a tolerance. See *NB 02*.

---

## Error handling

**Fill value**
A sentinel number meaning "no data here" — often `-999.0` or `NaN`. The trap: `NaN` is
skipped automatically by every reduction, and `-999.0` is **not**, so one fill convention
gives you a silently wrong mean and the other does not.

**Sentinel / missing value**
The same idea in fixed-format text. NDBC uses `99.0` for most fields but `999.0` for wind
direction — and **99° is a valid bearing**, so a blanket filter deletes real easterly
winds. See *NB 06*.

**`NoSuchKey`**
What GCS returns when a path does not exist. HTTP status 404, but the body says
`NoSuchKey`, which reads like a permissions problem rather than a path typo. The `data/`
level is mandatory when *fetching* an object even though listing works without it.

**500 / 400**
ERDDAP's generic server and query errors. Two different mistakes with
`requests` `params=` produce the *same* 500, which is why the cause is invisible from the
symptom.

**Graceful degradation**
Falling back to something workable instead of raising. Every request in the workshop falls
back to a cached response and says so; Notebook 05 detects missing credentials and keeps
teaching. Worst case is a stale answer with a warning, not a traceback.

---

## The site

**Monterey Bay** — 36.70 N, 122.10 W. A central California upwelling coast, and
everything in the workshop is within ~20 km of it.

**SanctSound MB01** — a passive acoustic recorder moored at 36.798 N, 121.976 W, 16 km
from the ocean site, 116 m deep, sampling at 96 kHz. The acoustic half of the data.

**NDBC 46092** ("MBM1") — a meteorological buoy 10 km away, hourly wind, gusts and waves.
Chosen over the nearer 46042 because 46042 **lost its wind-direction sensor** from
2019-08-18 to 2019-12-31, leaving September 100% missing.

**GLORYS12V1** — a global ocean reanalysis at 1/12°, daily from 1993. Supplies
temperature, salinity and — uniquely here — **currents**.

---

## Oceanography

**Upwelling**
Deep cold water rising to replace surface water pushed away by wind. The defining process
of this coast, and the reason SST is 15–17 °C in September rather than the ~22 °C a
similar latitude would give in summer.

**Thermocline**
The depth range over which temperature falls fastest. Roughly 15 m here in September. A
sound-speed gradient, and therefore a refracting layer for underwater sound.

**Halocline**
The depth range over which salinity falls fastest. Below it, deep water is nearly uniform
in salinity all the way down. *NB 04* computes its depth per cycle.

**Mixed layer**
The near-surface layer homogenised by wind and convection, above the thermocline. Nearly
constant sound speed, so it **reflects**; the thermocline refracts. This is why underwater
acoustics has a duct structure.

**Isotherm**
A line of constant temperature. Compare *thermocline*, which is where the gradient is
steepest.

**dbar** (decibar)
Pressure in units of 10,000 Pa. Approximately depth in metres, to within about 0.3% at the
surface. Argo reports pressure, not depth.

**SST** (sea surface temperature)
The skin of water at the top of the ocean. What ERDDAP serves. Differs from the
subsurface temperature that actually drives upwelling, which is a standard trap when
reasoning about thermocline depth from SST.

**Sponge / coastal filament**
The band of cool upwelled water hugging the coast. In *NB 02* the coldest cells sit at
the northern, inshore corner of the bay, and the field is a smooth SW→NE gradient.

**Forcing**
The external driver of a system. Wind forces waves; wind forces upwelling. Note that a
reanalysis is itself forced by atmospheric products, which is why the ocean reanalysis and
the wind buoy are **not independent** — see *NB 08*.

---

## Ocean acoustics

**dB re 1 µPa²**
The standard reference for underwater sound. **0 dB is a reference, not a measurement** —
levels near 0 would mean a decoding problem, not a quiet ocean.

**Third-octave band** (`tol_1h`)
A frequency band one-third of an octave wide. SanctSound's `tol` products give 30 such
bands from 25 Hz to 20 kHz. The sweet spot: enough frequency resolution to separate
biological, shipping and wind noise, small enough to hold a year in memory.

**Spectral density** (`psd_1h`)
1 Hz resolution — ~456 MB per deployment against 0.7 MB for third-octave. Same
information, 500× the data. Do not download it without a specific reason.

**Band level** (`tol`, `ol`) vs **broadband** (`bb`) vs **PSD** (`psd`)
The same recording at three levels of frequency detail: octave and third-octave bands,
a single broadband number, and full spectral density.

**Frequency band** — the index in the acoustic result. The finding in *NB 08* is that
wind response depends on it: mean |r| of 0.204 below 500 Hz against 0.699 above 2 kHz.

**Diel cycle**
Variation over the day. Dolphins here are detected at rates from 5% to 40% by hour of
day — a very strong signal, though part of it may be the *detector* looking harder rather
than the animals being louder.

**PAMGuard**
The software that produced the SanctSound dolphin detections. Worth keeping in mind when
reading a detection: it is one algorithm's opinion, not ground truth.

**Detection vs presence**
`sanctsound` ships a `ships` "detection" file that is actually an **event list** — 100%
positive by construction, because a row exists only where there was an event. It is not a
classification target. The `dolphin` file is real presence/absence at 22.7% positive.

**Wind-generated noise**
Rises with wind speed, concentrated in the high bands. Below roughly 200 Hz, distant
shipping dominates instead, on its own schedule. So "is it windy" and "is there a ship"
are different questions about the same recording, and one number cannot answer both.

---

## Standards and units

**TEOS-10**
The UNESCO standard for seawater thermodynamics. What `gsw` implements. *NB 07*.

**SP — Practical Salinity.** What instruments report. Reference 35 PSU, dimensionless in
practice, and **not** the right input to a physical equation.

**SA — Absolute Salinity.** In g/kg. What sound speed is a function of. The difference is
~0.17 g/kg in the North Atlantic, ~0.0 in the Pacific, and it depends on **pressure and
position**, not just salinity.

**CT — Conservative Temperature.** In **degrees Celsius**. *Not* Kelvin. Passing Kelvin to
`gsw.sound_speed` returns `nan` with only a `RuntimeWarning` — see *NB 07*.

**dc/dp**
The rate at which sound speed increases with pressure: about **17 m/s per 1000 dbar**, or
1.7 cm/s per dbar. It is nearly constant, which is what makes sound speed such a good
vertical coordinate. A factor-of-100 slip gives a plausible-looking small number, so
always state the units of whatever you are comparing it against.

**Banker's rounding**
Python's `round()` rounds half to even, so `int(round(31.5))` is `32` but
`int(round(62.5))` is `62`. Surprising when deriving a column name from a frequency.

**Q flag (quality control)**
Argo's per-value quality marker: 1 good, 2 probably good, 3/4 bad, 9 missing. **Stored as
bytes** in the aggregated `_prof.nc` files, so `qc == 1` is silently all-False. See *NB 04*.

---

## Tooling

**Jupyter / notebook / cell / kernel**
A notebook is a sequence of cells — markdown or code — executed by a kernel. Committed
*executed*, so it reads as a record of what happened rather than a wall of unverified
code.

**uv**
Manages Python versions, virtual environments and dependencies. `uv run` picks the right
interpreter without you maintaining an env.

**DSN** (data source name)
The connection string for a database. Held in one place (`src/ocean_sim/dsn.py`) so that
every script agrees; when it was copy-pasted into three scripts, making the port
configurable moved one copy and not the others.

**Docker / compose / image digest**
Docker runs the database reproducibly. Compose describes it declaratively. The image is
**pinned** to an explicit version, because an unpinned `latest` tag means everyone who
runs it on a different day gets a different database — and the thing you tested is not
the thing they ran.

**Hypertable** (TimescaleDB)
A PostgreSQL table automatically partitioned by time, with fast aggregates over time
ranges.

**DSN conflict / container name**
Two checkouts of this repo on one machine collide unless each has its own compose
project and port. Found by cloning to a second directory — which is exactly what an
attendee does.

---

## Statistics

Stated honestly, because each of these is a way to be wrong confidently.

**Autocorrelation**
Consecutive values being related. Daily weather is autocorrelated at ~3–10 days. Ignoring
it makes any test overconfident.

**Effective sample size** (`n_eff`)
How many *independent* points the data really contains. For daily SST here, n = 2,475
gave n_eff = 68.8 — a **36× reduction**. A correlation on autocorrelated points behaves
like one on far fewer points, and the confidence intervals are correspondingly wider.

**Block bootstrap**
Resampling *blocks* of consecutive points rather than individual ones, so the
autocorrelation is preserved. A plain permutation test destroys the dependence it is
supposed to respect, and returns the overconfident answer with extra steps. *NB 08*.

**Correlation is not causation**
Two things that share a driver will correlate whether or not one causes the other. In
*NB 08* the ocean reanalysis and the wind buoy both reflect the same weather, so part of
any lag-0 correlation is shared forcing rather than a physical pathway.

**p-value**
Under a null hypothesis, how often you would see a result this extreme. It is not the
probability the hypothesis is true, and it is not an effect size. A significant `r` of
0.2 is still a weak relationship.

**confounding / shared forcing**
When a third variable drives both members of a correlation. See above — and it is why
"remove the seasonal cycle" is a control worth running on *both* series.

---

## The habit

**State what you expect before you fetch, then assert it.** A response size, a row count,
a physical range.

The failure this catches is not a crash. It is a `200 OK` containing a wrong answer that
looks entirely reasonable — the only kind of data bug that costs anyone a day. Every
`expect()` call in the workshop is that habit, and *NB 09* lists the **33 traps** it would
have caught.
