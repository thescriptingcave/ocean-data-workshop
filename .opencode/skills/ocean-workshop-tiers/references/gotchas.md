# Verified gotchas

Everything here was established by **fetching**, not by reading documentation. That
matters: the traps in this repository are the ones that survive contact with a real
response, and several contradict what the docs imply.

When you add a source, verify it by hand first and add what you find here. A trap you
discovered and did not write down will be rediscovered slowly, by someone else.

---

## ERDDAP (`coastwatch.pfeg.noaa.gov`) — the flakiest source in the repo

**Two header rows.** Line 1 is column names, line 2 is units, data starts at line 3.
`pd.read_csv` without `skiprows=[1]` shifts every row by one, the first data value
becomes the string `"UTC"`, and nothing raises. The highest-value trap in the course
because it is invisible.

**Index syntax is part of the parameter *name*, not its value.**
`analysed_sst[(2019-09-01):(2019-09-30)]` is a single parameter name containing an
index expression. Get it wrong and ERDDAP returns a 500 with
`destinationVariables is not a valid...` — a server-side error that reads like a typo.

**Square brackets must be percent-encoded** as `%5B` / `%5D`, or curl treats them as a
glob pattern and fails with exit code 3 and no useful message.

**`.time=first` is a documented no-op** on griddap and was previously described in this
repo as if it worked. It is accepted and ignored. Do not teach it as meaningful.

**IPv6: the host publishes an AAAA record that some networks cannot route.**
`2610:20:90a3:3bcc::15`, with A record `161.55.160.15`. `urllib3` commits to the first
address and waits out the full connect timeout before falling back, so:

| client | time to fetch 1,324 bytes |
|---|---|
| `curl` (Happy Eyeballs, RFC 8305 — races addresses) | **0.53 s** (0.33 s to connect) |
| `requests`, no fix | **31–36 s** |
| `requests`, IPv4 forced | **1.4 s** |

On a network with no fallback at all it fails outright rather than slowly. This is why
the CI `workshop intro` job failed intermittently and why the fix lives in the builder.

**The fix is in `scripts/build_beginners.py`, and it must reach the kernel.**
`NotebookClient` executes each notebook in a *separate kernel process*; a monkeypatched
`socket.getaddrinfo` does not cross a process boundary. Measured with the patch applied
in the parent: the child still took **63.9 s** and reported the patch as absent. The
builder now writes a `sitecustomize` module to a temp directory and prepends it to
`PYTHONPATH`, which CPython imports at startup in every process, kernel included.

**When you write a similar patch for any builder, check it actually reached the
kernel.** A builder-side monkeypatch that silently does nothing is worse than none,
because it looks like a fix.

---

## DuckDB

**No netCDF extension exists.** `httpfs`, `parquet` and `json` are available; netCDF is
not. Do not plan a notebook around DuckDB reading netCDF.

**`read_csv_auto` on ERDDAP CSV gets the header right but leaves the units row as
data.** The columns come out right; the table then contains `UTC, degrees_north, ...`
as a row, which is why `time` and `analysed_sst` arrive as `VARCHAR` and arithmetic
fails. The fix is to filter and cast in SQL:

```sql
SELECT time::TIMESTAMP, analysed_sst::DOUBLE
FROM read_csv_auto('<url>') WHERE time <> 'UTC' ORDER BY time
```

**`skip = 1` breaks that same file** — it promotes the units row to be the header and
you get columns named `UTC, degrees_north, degrees_east, degree_C`. It looks like it
should help. It is the opposite.

**It refuses space-padded files.** NDBC's variable runs of spaces are ambiguous, so the
sniffer errors with a "search space" message rather than guessing. Forcing it means
`auto_detect=false` plus eighteen explicit column names plus a nineteenth to absorb
the padding — longer than the pandas it replaces. This refusal is taught as *correct
behaviour* in Intro notebook 03; do not "fix" it away.

**`read_json_auto` on an object returns one row.** It parses the object correctly and
treats it as a single record, so a list nested under a key becomes one cell. It only
gives you a table in one line for *list-shaped* JSON.

---

## NOAA CO-OPS (`api.tidesandcurrents.noaa.gov`)

**The keys are single letters.** `{"metadata": {...}, "data": [...]}`, where each
record is `{t, s, d, dr, g, f}` = time, speed m/s, direction degrees true, direction
text, gust m/s, flags. The mapping lives in the product documentation, not the
response. `pd.json_normalize` gives you 48 rows × 6 columns with those opaque names and
does not rename anything. This is the best available teaching example of an API
choosing names for its own database rather than for you.

**`date=` accepts only `latest`, `recent` or `today`.** For a historical range you must
use `begin_date` and `end_date` (`YYYYMMDD`). A single `date=20240115` errors.

A working request:

```
https://api.tidesandcurrents.noaa.gov/api/prod/datagetter
  ?product=wind&application=<name>
  &begin_date=20240115&end_date=20240116&station=9414290
  &time_zone=gmt&units=metric&interval=h&format=json
```

---

## NDBC (`www.ndbc.noaa.gov`)

**Sentinels are per column, and one blanket filter silently deletes real data.**
`99` means missing in most columns; `999` means missing in `WDIR`. A filter written as
"`>= 99` is missing" removes every valid bearing from 99 to 360, because those are real
winds. It does not raise. Mask each column separately.

**Two header lines, and the names are `#`-prefixed.** `#YY MM DD hh mm WDIR WSPD ...`
then a units line, then data. `lstrip("#")` the names row.

**The file is gzipped**, and `r.text` on it returns a few hundred characters of
mojibake followed by nothing, silently. `r.content` + `gzip.decompress` is the file.

Verified: `46092h2019.txt.gz` is ~76 kB, 7,835 rows, 7,576 usable after masking.

---

## Copernicus Marine

**The CLI does not block waiting for credentials — it errors immediately.** Anyone
writing setup instructions that imply it will prompt is wrong.

**The dataset id is `cmems_mod_glo_phy_my_0.083deg_P1D-m`.** The plausible-looking
`GLOBAL_MULTIYEAR_PHY_001_030` is the *product* name, not the dataset id, and fails.

**GLORYS is opt-in** (`make db-ocean`, `load_db.py --with-ocean`). It is slow and large
enough that including it in the default path made a clean clone take 325 MB. Keep it
optional.

---

## Domain libraries

**`gsw.CT_from_t` takes °C, not Kelvin.** Passing Kelvin produces a plausible number
that is wrong by ~273, which is exactly the failure mode the workshop warns about.
This one is a unit bug, not a shape bug, and it will not be caught by a shape check.

---

## CI and infrastructure traps

Each of these was invisible locally and found by `make fresh` or by a clean runner.

- **Compose project name diverging between `up` and `exec`.** `docker compose up` and
  `docker compose exec` must agree on the project name or the second command talks to
  a container that does not exist.
- **CI DSN set per-step when it needed to be per-job.** Environment does not persist
  across steps the way a job-level `env:` block does.
- **`git diff` on a gitignored cache in CI** — reports nothing and hides real changes.
- **`data/` in `.gitignore` also hid `src/ocean_sim/data/`**, which is source, not
  output. Check that a new ignore rule does not catch something real.
- **A `refresh=` kwarg passed to a real `requests.Session`** — `requests.Session` takes
  no such argument. It was a leftover from the wrapper-function era.
- **`jupyterlab` was missing from dependencies**, so `make` succeeded and the browser
  never opened.
- **A compose service image must be pinned.** `timescale/timescaledb:2.30.1-pg17`,
  not `latest`.
- **`.time=first` documented as working when it is a no-op** (see ERDDAP above).

---

## Rules of thumb this all points to

1. **Look at `r.text[:200]` before parsing.** Every strange result above is a header, a
   wrapper, a sentinel, or an error message where you expected data.
2. **A plausible number is not a correct number.** The traps are not exceptions. They
   are answers that look reasonable and are wrong, which is why the build fails a cell
   that produces no output and why a unit bug like `CT_from_t` slips past a shape check.
3. **Verify on a clean clone and a clean runner.** The bugs above are concentrated
   exactly where the local environment is already correct.
