"""Definitions for the workshop notebooks.

Each ``nb_NN`` function returns a built notebook. ``scripts/build_notebooks.py`` writes
them and ``scripts/execute_notebooks.py`` runs them so the committed output is real.

Content is organised by **access pattern** rather than by dataset, because the patterns
transfer to sources none of us have heard of and the datasets do not:

    01  the request, three ways        curl -> requests -> xarray
    02  REST griddap                   ERDDAP
    03  cloud object storage           GCS / NCEI
    04  browsable tree + netCDF        Argo GDAC
    05  credentialed API               Copernicus Marine
    06  fixed-format text              NDBC
    07  when a library wins            gsw
    08  capstone: join three sources   + TimescaleDB
    09  the trap table                 reference

Every number quoted in a notebook was measured, not estimated. Where an approach does
not work, the notebook says so and says what the server actually replied.
"""

from __future__ import annotations

from nbbuild import build, code, md

# ---------------------------------------------------------------------------
# shared preamble, prepended to every notebook
# ---------------------------------------------------------------------------
SETUP = '''
import sys
from pathlib import Path

# notebooks/ holds _fetch.py and _sources.py; src/ holds the project's own helpers.
for p in (Path.cwd(), Path.cwd() / ".." / "src"):
    if p.exists() and str(p) not in sys.path:
        sys.path.insert(0, str(p.resolve()))

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

import _fetch
import _sources as S

sns.set_theme(style="whitegrid", context="notebook")
plt.rcParams["figure.dpi"] = 110

_fetch.OFFLINE and print("offline mode: serving prefetched responses")
'''


def preamble() -> list:
    """The shared import cell, prepended to every notebook."""
    return code(SETUP)


# ===========================================================================
# 01 -- The request, three ways
# ===========================================================================
def nb_01() -> object:
    b = build(
        md("""
# 01 — One request, three ways

This is the spine of the workshop. Everything after it is a variation.

We will fetch **one** thing — sea surface temperature off Monterey Bay, one point per
day for September 2019 — and express the same fetch three ways:

| | what it shows you |
|---|---|
| **1. `curl`** | what is actually on the wire, including the parts every library hides from you |
| **2. `requests`** | the Python idiom, and the one thing it must do that `curl` does not |
| **3. `xarray`** | when a domain library has already solved the problem for you |

The order matters. Most people meet step 2 first, use it for a year, and never find out
that step 1 would have told them why their query was malformed.
"""),
        md("""
## The site

Everything in this workshop is within about 20 km of one point in Monterey Bay.

| | |
|---|---|
| Ocean site | 36.70 N, 122.10 W — the centre of everything we will compute |
| Acoustic recorder | 36.798 N, 121.976 W — SanctSound **MB01**, 16 km away, 116 m deep |
| Wind | NDBC buoy **46092** "MBM1", 10 km away |

The recorder and the buoy are real instruments moored in the same bay as the
reanalysis grid cell we are about to read. That is what makes it possible to ask a
question about *why* the ocean and the underwater sound behave as they do, rather than
only describing them.
"""),
        *preamble(),

        md("""
## 1. What you should get

State the expectation before the request. This is the habit that separates "I got some
data" from "I got **the right** data", and the failure it catches is the expensive one:
a `200 OK` containing plausible nonsense.

| | |
|---|---|
| Response | 1,324 bytes, 30 data rows, 4 columns |
| Columns | `time`, `latitude`, `longitude`, `analysed_sst` |
| SST at this cell | 15.08 – 17.02 °C, mean **15.97** °C |
| Whole 0.22° box, for contrast | 690,813 bytes, 15,870 rows, mean 15.58 °C |

About 15–17 °C is what you expect for a central-California upwelling coast in
September: cold for a California summer, because upwelling is pulling cold water up
from depth. If you get 22 °C you have probably asked for the wrong hemisphere or the
wrong month, and no amount of plotting will tell you.

Note that the single cell is *warmer* than the box average (15.97 vs 15.58). That is not
noise — it is the upwelling structure, and we plot it at the end to show why.
"""),
        code('''
# Build the query. `point=True` collapses the lat/lon box to a single cell.
URL = S.sst_csv(point=True)
print(URL)
print()
print("Broken up:")
for part, label in [
    (S.ERDDAP,          "the griddap endpoint for this dataset"),
    (".csv",            "the format -- swap for .nc, .json, .html, ... "),
    ("?analysed_sst",   "the variable we want"),
    ("[(t0):(t1)]",     "time range"),
    ("[(lat):(lat)]",   "latitude -- a degenerate range, i.e. one cell"),
    ("[(lon):(lon)]",   "longitude"),
]:
    print(f"  {label:52} {part}")
'''),

        md("""
## 2. On the wire — `curl`

`curl` sends the request and prints the response with nothing in between. It is the
closest thing to reading the HTTP exchange off the network, and it is how you find out
what a library is doing on your behalf.
"""),
        md("""
### ⚠️ Trap — `curl` reads `[` and `]` as glob patterns

Before we can run it: the URL is full of square brackets, because that is what ERDDAP's
index syntax uses. `curl` has treated `[...]` as a **glob range** since 7.21 — the same
feature that lets you do `curl 'https://x/[1-10].txt'` — and with no matching host it
fails with **exit code 3, `URL malformat`**, and *no error message at all* under `-s`.

So the first thing you see is an empty response and no explanation. The fix is one flag:

| | |
|---|---|
| `curl -s URL` | exit 3, 0 bytes, silent |
| `curl -s -g URL` | exit 0, 1,324 bytes |

`-g` / `--globoff` disables globbing. You will need it for every griddap URL, and you
will need to *know* you need it, because nothing tells you.
"""),
        code('''
import shutil
import subprocess

if shutil.which("curl"):
    for label, flags in [("without -g", ["-s"]), ("with -g", ["-s", "-g"])]:
        r = subprocess.run(
            ["curl", *flags, "--max-time", "30", URL], capture_output=True, text=True
        )
        print(f"  {label:12} exit {r.returncode}   {len(r.stdout):>6,} bytes")
    print()

    out = subprocess.run(
        ["curl", "-s", "-g", "--max-time", "30", URL], capture_output=True, text=True
    ).stdout
    lines = out.splitlines()
    print(f"  {len(lines)} lines, {len(out.encode()):,} bytes")
    print()
    for ln in lines[:4]:
        print("   |", ln[:76])
    print("   |  ...")
else:
    print("curl not found (it ships with macOS, Linux and Windows 10+).")
    print("Python equivalent:")
    print(_fetch.get(URL).text[:400])
'''),

        md("""
### ⚠️ Trap — ERDDAP CSV has **two** header rows

Look at the first two lines above. The first is column *names*, the second is column
*units*. That second row is not a comment and not a footnote — it is a data row as far
as `pandas` is concerned, so a naive `read_csv` gives you a first row of strings and an
off-by-one on every subsequent row.

This is the single most common way to get silently corrupted data out of ERDDAP: no
error, no warning, just a frame where one temperature is the string `degree_C`.
"""),
        code('''
url = S.sst_csv(point=True)
raw = _fetch.get(url)
print(raw.text)
'''),

        md("""
## 3. In Python — `requests`

The Python equivalent. Note what is *absent* compared to the notebook's helper: no
timeout, and no IPv4 forcing. Both matter, and both are traps — we come back to them.
"""),
        code('''
import requests

r = requests.get(URL)          # no timeout: this can hang forever, which is its own bug
print("status :", r.status_code)
print("bytes  :", len(r.content))
print("first  :", r.text.splitlines()[0])
''', fast_lane=True),

        md("""
### ⚠️ Trap — you cannot build a griddap query with `params=`

This is the trap that costs the most time, because the index expression
`[(t0):(t1)][(lat)][(lon)]` is part of the **parameter name**, not its value. The wire
format has no `=` after it:

```
...jplMURSST41.csv?analysed_sst[(2019-09-01...):(2019-09-30...)][(36.6):(36.6)][...]
                       ^^^^^^^^^^^^^^^ the whole thing is the KEY
```

And `requests` cannot express that through `params=` in **either** direction. Both
attempts were run against the live server:

| what you write | what goes on the wire | what ERDDAP replies |
|---|---|---|
| `params={expr: None}` | the parameter is **dropped entirely** | `500` — `destinationVariableName=... wasn't found` |
| `params={expr: ""}` | `...%5D=` — a trailing `=` | `500` — the same error |

The two different mistakes produce the *same* opaque 500, which is why the cause is
hard to see from the symptom. The fix is to build the query string by hand and pass it
as the URL.
"""),
        code('''
# Show exactly what `requests` would put on the wire, for each of the two mistakes.
# No network needed -- this is just string assembly, so it works offline too.
expr = "[(2019-09-01T00:00:00Z):(2019-09-30T00:00:00Z)][(36.6):(36.6)][(-122.2):(-122.2)]"

def query_of(params):
    """The query string requests would send -- or the fact that there is none."""
    u = requests.Request("GET", S.ERDDAP + ".csv", params=params).prepare().url
    return u.split("?", 1)[1] if "?" in u else None

print("mistake 1 -- value None:")
q = query_of({"analysed_sst" + expr: None})
print("    query string:", q)
print("    ^ None. requests dropped the parameter, so the URL has no '?' at all,")
print("      and ERDDAP is asked for the whole dataset with no variable selected.")

print()
print("mistake 2 -- value empty string:")
q = query_of({"analysed_sst" + expr: ""})
print("   ", q[:86], "...")
print("    ^ note the trailing %5D= -- ERDDAP rejects the whole query.")

print()
print("what actually works -- hand-built, passed as the URL:")
print("   ", URL.split("?", 1)[1][:86], "...")
print("    ^ no '=' after the index expression, which is what ERDDAP expects.")
'''),

        md("""
### ⚠️ Trap — how you *reduce* an ERDDAP response (three ways that do not work)

The natural instinct, when you want one point per day instead of a full grid, is to ask
the server for less. Three obvious-looking approaches were tested against the live
server for September 2019 at this site:

| approach | result |
|---|---|
| full box, 0.22° square | **690,813 B**, 15,870 rows (23 × 23 cells per day) |
| `&.time=first&.lat=first&.lon=first` | **690,813 B** — *byte-identical. A no-op.* |
| `&time=...&latitude=...` (constraint variables) | `400` — *"must be followed by a .griddap server variable"* |
| strides in the index, `[(0):(1):(29)]` | `400` — *"axis#0=time Constraint=..."* |
| **a degenerate box, `[(36.6):(36.6)]`** | **1,324 B**, 30 rows — a 520× reduction |

The `.time=first` one is the dangerous one: it is in the examples people copy, it looks
like it is doing something, and it does nothing at all. ERDDAP's griddap DSL has no
strides and no constraint variables.

**Shrink the box instead.** That is the whole trick, and `_sources.sst_url(point=True)`
is the one line that does it.
"""),
        code('''
box = _fetch.get(S.sst_csv(), quiet=True)
point = _fetch.get(S.sst_csv(point=True), quiet=True)
print(f"  full box : {len(box.content):>9,} B   {len(box.text.splitlines()) - 2:>6,} rows")
print(f"  one point: {len(point.content):>9,} B   {len(point.text.splitlines()) - 2:>6,} rows")
print(f"  ratio    : {len(box.content) / len(point.content):,.0f}x smaller")
'''),

        md("""
### ⚠️ Trap — two header rows, again, now in pandas

Fix: skip the units row explicitly. `skiprows=[1]` keeps row 0 (the names) and drops
row 1 (the units).
"""),
        code('''
import io

df = pd.read_csv(io.StringIO(raw.text), skiprows=[1])
df["time"] = pd.to_datetime(df["time"].str.replace("Z", "", regex=False))

print(df.head(3).to_string(index=False))
print()
print("dtypes:", dict(df.dtypes.astype(str)))
'''),

        md("""
### ⚠️ Trap — IPv6, and why `requests` can be 100× slower than `curl`

Some machines — including the one this workshop was written on — resolve AAAA records
but have **no IPv6 route**.

`curl` races the two address families (Happy Eyeballs, RFC 8305), so it connects over
IPv4 immediately and looks perfectly healthy. `requests`, built on urllib3, waits out
the **full connect timeout** on the dead IPv6 address before falling back.

Measured on the same machine, same URL:

```
curl      0.20 s
requests  20.0 s   -- and 20.0 s is exactly the timeout value
```

The tell is that *every* call takes precisely the timeout. It reads like "this API is
slow" rather than "this API is fine and something on my machine is wrong".

There is no clean fix in `requests` itself, so the workshop's helper forces IPv4 once at
import. You do not need to do anything about this — but if a colleague ever tells you
their ERDDAP calls are mysteriously slow, this is why.
"""),
        code('''
import socket
from ocean_sim.http import force_ipv4

# What the machine resolves...
addrs = socket.getaddrinfo(S.ERDDAP.split("/")[2], 443, type=socket.SOCK_STREAM)
families = {socket.AddressFamily(i[0]).name for i in addrs}
print("  address families this host resolves:", ", ".join(sorted(families)))

# ...versus what we actually use.
already = force_ipv4()   # idempotent; False means it was already applied
print("  IPv4-only already active:", not already)
print("  -> every fetch in this workshop is unaffected by the above")
'''),

        md("""
## 4. In a library — `xarray`

Now the escape hatch. The same data, asked for as netCDF instead of CSV, and handed
straight to `xarray`: labelled dimensions, coordinates, and no manual column assembly.

This is what you should reach for **after** you know what the wire format looks like.
A library hides structure you need to know about in order to debug it.
"""),
        code('''
import xarray as xr

nc = _fetch.get(S.sst_nc(), quiet=True)
path = Path.cwd() / "_sst_sep2019.nc"
path.write_bytes(nc.content)

ds = xr.open_dataset(path)
print(ds)
print()
print("the variable we asked for:", list(ds.data_vars))
print("its units attribute      :", ds[S.SST_VAR].attrs.get("units"))
'''),

        md("""
## 5. Traps so far

| # | trap | symptom | fix |
|---|---|---|---|
| 1 | ERDDAP CSV has two header rows | first row of strings, off-by-one everywhere | `pd.read_csv(..., skiprows=[1])` |
| 2 | index expression is part of the parameter *name* | `500 destinationVariableName=... wasn't found` | hand-build the URL; do not use `params=` |
| 3 | `.time=first` is a no-op | you get 500× more data than you asked for | shrink the box instead |
| 4 | constraint variables rejected | `400 must be followed by a .griddap server variable` | use the index form only |
| 5 | no `=` after the index expression | `500`, same as trap 2 | hand-build the URL |
| 6 | IPv6 with no route | every call takes exactly the timeout | force IPv4 (helper does it) |
| 7 | no timeout on `requests` | hangs forever on a dead host | always pass `timeout=` |

There are about 28 of these across the whole workshop. Notebook 09 is the full list.
"""),

        md("""
## 6. What you got

September 2019 sea surface temperature at 36.6 N, 122.2 W — one point per day.
"""),
        code('''
fig, axes = plt.subplots(2, 1, figsize=(10, 6), height_ratios=[1, 2])

ax = axes[0]
ax.plot(df["time"], df[S.SST_VAR], marker="o", ms=4, color="#c0392b", lw=1.4)
ax.set_ylabel("SST  (°C)")
ax.set_title("Sea surface temperature, Monterey Bay — September 2019", loc="left", fontweight="bold")
ax.annotate(
    f"mean {df[S.SST_VAR].mean():.1f} °C",
    xy=(0.02, 0.06), xycoords="axes fraction", fontsize=9, color="#555",
)

# The full box, as a mean field -- this is the upwelling structure the point sits in.
ax = axes[1]
grid = (
    pd.read_csv(io.StringIO(box.text), skiprows=[1])
      .query("analysed_sst > -1")
      .groupby(["latitude", "longitude"])[S.SST_VAR].mean()
      .unstack()
)
sns.heatmap(grid, cmap="RdYlBu_r", ax=ax, cbar_kws={"label": "mean SST (°C)", "shrink": 0.85})
ax.set_title("Mean SST over the same month, 0.22° box", loc="left", fontweight="bold")
ax.set_xlabel("longitude")
ax.set_ylabel("latitude")

plt.tight_layout()
plt.show()
'''),

        md("""
The point sits in the *warm* part of the box. Monterey Bay is a classic **upwelling
system**: a cool filament of water drawn from depth runs along the coast just outside,
and the bay itself is a degree or two warmer. Seeing the point in context is the
difference between a number and an observation — and it is why "which cell did I
download?" is a real question worth asking before you trust any single value.
"""),

        code('''
# Assert the response is what this notebook said it would be.
_fetch.expect("response bytes", len(raw.content), 1324)
_fetch.expect("rows", len(df), 30)
_fetch.expect("columns", list(df.columns), ["time", "latitude", "longitude", "analysed_sst"])
_fetch.expect_range("mean SST", df[S.SST_VAR].mean(), 15.5, 16.5)
_fetch.expect_range("SST min", df[S.SST_VAR].min(), 14.5, 16.0)
_fetch.expect_range("SST max", df[S.SST_VAR].max(), 13.0, 19.0)
print()
print("  14-17 C in September is upwelling-consistent for central California.")
print("  Had any of these failed, the number would have been wrong, not the plot.")
'''),
        title="01 The request, three ways",
    )
    return b


# ===========================================================================
# 02 -- REST griddap
# ===========================================================================
def nb_02() -> "object":
    b = build(
        md("""
# 02 — Query a grid, dimensionally

**Access pattern: REST griddap.** One dataset, addressed by index expression, returned
in whatever format you negotiate.

ERDDAP is the reference implementation and it fronts dozens of NOAA and NASA datasets.
The pattern is common to OPeNDAP servers generally, and the same three or four traps
apply to most of them.
"""),
        *preamble(),

        md("""
## 1. What you should get

| | |
|---|---|
| Endpoint | `coastwatch.pfeg.noaa.gov/erddap/griddap/jplMURSST41` |
| Variable | `analysed_sst` — daily analysed SST, 0.045°, 2002–present |
| Dimensions | `time`, `latitude`, `longitude` — always in that order, for every griddap |
| As netCDF | 30 × 23 × 23, 134,020 bytes |

The dimension order is a **property of the server, not of your query**, and it is the
single most common reason a griddap query returns an error: the brackets have to
follow the server's axis order, and you cannot tell from the URL which order that is.
You have to ask.
"""),
        code('''
# The server tells you its own shape. Always ask before you index.
info = _fetch.get(f"{S.ERDDAP}.das", quiet=True).text
for line in info.splitlines():
    if any(k in line for k in ("dimensions:", "time {", "latitude {", "longitude {")):
        print("   ", line.strip())
'''),

        md("""
## 2. The index expression

A griddap query names the variable, then brackets each dimension in server order:

```
<endpoint>.<format>?<variable>[<time>][<lat>][<lon>]
```

Each bracket is `[start:(stop)]` in the dimension's own units — a real timestamp for
`time`, decimal degrees for the spatial ones. A range whose start equals its stop is a
*degenerate range*, which is how you ask for exactly one cell.
"""),
        code('''
lat0, lat1, lon0, lon1 = S.SST_BOX
parts = {
    "endpoint + format": f"{S.ERDDAP}.csv",
    "variable":          "analysed_sst",
    "time":              "[(2019-09-01T00:00:00Z):(2019-09-30T00:00:00Z)]",
    "latitude":          f"[({lat0}):({lat1})]",
    "longitude":         f"[({lon0}):({lon1})]",
}
for k, v in parts.items():
    print(f"  {k:18} {v}")

print()
print("  concatenated:")
print("   ", S.sst_csv())
'''),

        md("""
### ⚠️ Trap — the axis order is not the order you expect

Reversing the spatial brackets does **not** error. It returns a plausible field, because
the numbers still land inside the dataset's latitude range. It is simply the wrong
answer, transposed.

This is the dangerous class of error: the server was asked a well-formed question, and
answered it correctly. The only defence is to check the axis order against the `.das`
metadata *before* trusting a spatial result, and to sanity-check that the latitude range
you got back is the one you asked for.
"""),
        code('''
# Prove the ordering matters by checking what comes back, not by trusting the URL.
txt = _fetch.get(S.sst_csv(), quiet=True).text
import io
d = pd.read_csv(io.StringIO(txt), skiprows=[1])
print("  latitude  range returned:", d.latitude.min(), "..", d.latitude.max())
print("  longitude range returned:", d.longitude.min(), "..", d.longitude.max())
print("  latitude  range asked for:", lat0, "..", lat1)
print("  longitude range asked for:", lon0, "..", lon1)
print()
print("  -> matches. Had the brackets been swapped, latitude and longitude above")
print("     would be reversed while still looking entirely reasonable.")
'''),

        md("""
## 3. Format negotiation

The extension before the `?` is the format. Same query, different serialisation:

| extension | you get | size for this month |
|---|---|---|
| `.csv` | flat table, **two** header rows | 690,813 B |
| `.nc` | CF-1.6 netCDF, labelled dimensions | 134,020 B |
| `.json` | nested objects | larger |
| `.html` | a table you can look at in a browser | — |

`.nc` is smaller *and* self-describing: units, axis order and coordinates travel with
the data, so `xarray` does not have to be told what the columns mean. For anything past
exploration, ask for `.nc` first.
"""),
        code('''
import xarray as xr

nc = _fetch.get(S.sst_nc(), quiet=True)
p = Path.cwd() / "_sst_month.nc"
p.write_bytes(nc.content)
ds = xr.open_dataset(p)

print("  csv:", f"{len(_fetch.get(S.sst_csv(), quiet=True).content):,} bytes")
print("  nc :", f"{len(nc.content):,} bytes")
print()
print("  and the netCDF answers questions the CSV cannot:")
print("    units       :", ds[S.SST_VAR].attrs.get("units"))
print("    conventions :", ds.attrs.get("Conventions"))
print("    creator     :", ds.attrs.get("creator_name"))
'''),

        md("""
### ⚠️ Trap — coordinates come back as `float32`

ERDDAP stores its grid in single precision. A box you requested as `36.60` to `36.82`
can come back with a `latitude.min()` of `36.599998` and a `latitude.max()` of
`36.820002` — outside the box you asked for, by a few millionths of a degree.

The result is a spatial filter that mysteriously excludes the edge of your own
selection. Use a tolerance rather than exact comparison:

```python
assert lat0 - 1e-3 <= ds.latitude.min() and ds.latitude.max() <= lat1 + 1e-3
```
"""),
        code('''
lat_min, lat_max = float(ds.latitude.min()), float(ds.latitude.max())
print(f"  requested : {lat0} .. {lat1}")
print(f"  returned  : {lat_min!r} .. {lat_max!r}")
print(f"  dtype     : {ds.latitude.dtype}")
print()
print("  exact comparison passes? ", lat0 <= lat_min and lat_max <= lat1)
print("  with a 1e-3 tolerance?    ", lat0 - 1e-3 <= lat_min and lat_max <= lat1 + 1e-3)
print()
print("  The fill value is the other half of this trap, and the two are not")
print("  interchangeable:")
sst = ds[S.SST_VAR]
print(f"    dtype                  : {sst.dtype}")
print(f"    NaN cells              : {int(sst.isnull().sum())}")
print(f"    cells <= -1 C (fill)   : {int((sst <= -1.0).sum())}")
print(f"    overall min            : {float(sst.min()):.2f}")
print()
print("  A NaN fill is skipped automatically by every reduction. A -999.0 fill is NOT:")
import numpy as _np
with_fill    = float(sst.mean(dim="time").mean())
without_fill = float(sst.where(sst > -1.0).mean(dim="time").mean())
print(f"    mean including fill   : {with_fill:.4f}")
print(f"    mean excluding fill   : {without_fill:.4f}")
print(f"    difference            : {with_fill - without_fill:.4f} C")
print()
print("  So 'is my field physical?' is a check worth automating, not eyeballing.")
'''),

        md("""
### ⚠️ Trap — `itemsPerLargePage` silently returns nothing

ERDDAP pages large CSV responses. Ask for page 2 without asking for page 1 and you get
an **empty response with HTTP 200** — not an error, not a warning, just nothing. If you
are paging a large dataset and a page comes back empty, this is almost always why.
"""),
        md("""
## 4. The field, and what it is showing you

Now the reason we came. A month of SST over the bay, as a map.
"""),
        code('''
mean_field = ds[S.SST_VAR].where(ds[S.SST_VAR] > -1.0).mean(dim="time")
spread = ds[S.SST_VAR].where(ds[S.SST_VAR] > -1.0).std(dim="time")

fig, axes = plt.subplots(1, 2, figsize=(13, 5.2), constrained_layout=True)

for ax, field, title in [
    (axes[0], mean_field, "mean SST, September 2019"),
    (axes[1], spread,    "day-to-day variability (sd)"),
]:
    im = ax.pcolormesh(field.longitude, field.latitude, field.values,
                       cmap="RdYlBu_r", shading="nearest")
    ax.scatter([S.SITE_LON], [S.SITE_LAT], marker="*", s=180, c="black",
               edgecolors="white", linewidths=0.8, zorder=3, label="ocean site")
    ax.set_title(title, loc="left", fontweight="bold")
    ax.set_xlabel("longitude"); ax.set_ylabel("latitude")
    fig.colorbar(im, ax=ax, shrink=0.86)

axes[0].legend(loc="lower right", fontsize=8)
plt.suptitle("jplMURSST41 — ERDDAP griddap, 0.045°", x=0.02, ha="left",
             fontsize=9, color="#666")
plt.show()
'''),

        code('''
# The physical reading. Scalar reductions on a 2-D DataArray need numpy -- xarray
# wants an explicit `dim` for anything but a 1-D array.
vals  = mean_field.values
lats  = mean_field.latitude.values
lons  = mean_field.longitude.values
cold, warm = float(vals.min()), float(vals.max())
ci, cj = np.unravel_index(int(vals.argmin()), vals.shape)
wi, wj = np.unravel_index(int(vals.argmax()), vals.shape)

print(f"  mean field spans {cold:.2f} .. {warm:.2f} C   (range {warm - cold:.2f} C)")
print(f"  coldest cell: lat {lats[ci]:.2f}  lon {lons[cj]:.2f}   (NE, inshore)")
print(f"  warmest cell: lat {lats[wi]:.2f}  lon {lons[wj]:.2f}   (SW, offshore)")
print()
print("  It is a smooth, monotonic SW -> NE gradient: offshore water is warmer, and")
print("  the water at the northern, inshore corner of the bay is coldest. That is the")
print("  upwelling centre, and it sits at the mouth of Monterey Bay. Northerly wind")
print("  drags surface water away from the coast and cold water rises to replace it,")
print("  so the coldest water is the closest-to-land water at the northern end.")
print()
print(f"  Note the gradient is only {warm - cold:.2f} C. That is small in absolute terms")
print("  and easy to dismiss -- and it is the entire spatial signal in this box.")
print("  Whether that matters depends on the question, which is the next notebook.")
'''),

        code('''
_fetch.expect("netCDF bytes", len(nc.content), 134020)
_fetch.expect("time steps", int(ds.sizes["time"]), 30)
_fetch.expect("latitude points", int(ds.sizes["latitude"]), 23)
_fetch.expect("longitude points", int(ds.sizes["longitude"]), 23)
_fetch.expect_range("mean SST", float(mean_field.values.mean()), 15.0, 17.0)
_fetch.expect_range("field range", warm - cold, 0.5, 8.0)
print()
print("  A field with a range near zero would mean the fill values leaked in.")
print("  A mean outside 12-20 C would mean the wrong box or the wrong month.")
'''),
        title="02 ERDDAP griddap",
    )
    return b


# ===========================================================================
# 03 -- Cloud object storage
# ===========================================================================
def nb_03() -> "object":
    b = build(
        md("""
# 03 — List a bucket, fetch one object

**Access pattern: cloud object storage.** No query language, no search — just a
namespace you can list, and URLs you can fetch. Almost every large public data
archive is a bucket, and once you can list one you can list all of them.

This is the NOAA NCEI passive acoustic archive. Anonymous, no key, no account.
"""),
        *preamble(),

        md("""
## 1. The bucket is a filesystem, not a database

The object layout is a path:

```
sanctsound/products/<type>/<site>/<dataset>/data/<files>
                       ^^^^^^^   ^^^^^^  ^^^^^^^^^^^^^^^^^^  ^^^^^
                       product   site     dataset             level
```

Three things follow from that, and all three are traps below:

1. There is no index. To find a file you **list** its prefix and read the result.
2. A path that lists fine is not necessarily a path that **fetches** — the `data/`
   level is optional for listing and mandatory for fetching.
3. You can find out how big a file is **before** downloading it. Always do.
"""),
        code('''
# One request lists the whole site. delimiter="/" rolls up to the next path segment.
d = S.ncei_list(f"sanctsound/products/sound_level_metrics/{S.NCEI_SITE}/", "/", 200)
prefixes = d.get("prefixes", [])
print(f"  {len(prefixes)} dataset directories under mb01")
for p in prefixes[:6]:
    print("   ", p)
print("    ...")
'''),

        md("""
Same request, `delimiter` removed: now you get the objects instead of the directories,
one level deeper. This is the whole API — list a prefix, read the JSON, follow a name.
"""),
        code('''
d2 = S.ncei_list(f"sanctsound/products/sound_level_metrics/{S.NCEI_SITE}/", delimiter="")
print(f"  keys returned: {sorted(d.keys())}")
print(f"  prefixes (directory level): {len(d.get('prefixes', []))}")
print()
print("  Nine deployments, four products each -- 36 directories:")
deps = sorted({p.rsplit("_", 2)[-2] for p in prefixes})
prods = sorted({p.rstrip("/").rsplit("_", 1)[-1] for p in prefixes})
print(f"    deployments: {', '.join(deps)}")
print(f"    products:    {', '.join(prods)}")
'''),

        md("""
## 2. Know the size before you download

The same recording exists at four resolutions. The size difference is three orders of
magnitude, and picking wrong costs you an afternoon and a lot of patience.
"""),
        code('''
# Sizes are metadata in the listing. This costs one request and no downloads.
rows = []
for dep in ("01", "09"):
    d3 = S.ncei_list(f"{S.ncei_dataset_dir('tol_1h', dep)}/data/", delimiter="", max_items=10)
    for it in d3.get("items", []):
        rows.append((dep, it["name"].rsplit("/", 1)[-1], int(it["size"]), it.get("contentType")))

frame = pd.DataFrame(rows, columns=["deployment", "object", "bytes", "content_type"])
frame["MB"] = (frame.bytes / 1e6).round(2)
print(frame.to_string(index=False))
'''),
        md("""
| product | what it is | size per deployment |
|---|---|---|
| `psd_1h` | 1 Hz spectral density | **~456 MB** — do not |
| `tol_1h` | third-octave band levels | ~0.7–1.0 MB — **use this** |
| `ol_1h` | octave band levels | ~0.4 MB |
| `bb_1h` | broadband level | ~0.2 MB |

Third-octave is the sweet spot: 30 frequency bands from 25 Hz to 20 kHz is enough
resolution to separate biological, shipping and wind noise, and a whole deployment fits
in memory. Reach for `psd_1h` only when a question genuinely needs 1 Hz resolution.
"""),
        code('''
# Fetch the third-octave product. ~0.97 MB for deployment 01.
url = S.ncei_file_url("tol_1h", "01")
print("  key :", S.ncei_object_name("tol_1h", "01"))
print("  url :", url)
print()
res = _fetch.get(url)
print(" ", res.describe())
'''),

        md("""
### ⚠️ Trap — the `data/` level

Drop `data/` from the path and you get a 404 — but the body says:

```xml
<Error><Code>NoSuchKey</Code><Message>The specified key does not exist.</Message>
```

`NoSuchKey` reads like a permissions problem. The bucket *is* public, the listing *did*
show the object, and the object *is* there. It is a path typo, and it presents as an
access problem, so people go looking for credentials they do not need.

The directory-level listing above worked without `data/`, which is what makes this
confusing: the path that lists is not the path that fetches.
"""),
        code('''
wrong = S.ncei_file_url("tol_1h", "01").replace("/data/", "/")
print("  wrong URL:", wrong.rsplit("/", 1)[-1], "at the wrong level")
print()
try:
    _fetch.get(wrong, refresh=True)
except RuntimeError as exc:
    for line in str(exc).splitlines()[:4]:
        print("   ", line)
print()
print("  Notice: the HTTP status is 404, but the payload says NoSuchKey. Nothing in")
print("  the status code distinguishes 'you are not allowed' from 'that is not the")
print("  path'. Read the body.")
'''),

        md("""
### ⚠️ Trap — error bodies are XML even from the JSON API

`storage.googleapis.com/.../v1/b/<bucket>/o/<key>` is the *JSON* API. On success it
returns JSON. On failure it returns **XML**, with `Content-Type: text/plain`.

So the natural error handling fails in a confusing way:

```python
r = requests.get(url); r.json()   # JSONDecodeError, not a useful error message
```

`raise_for_status()` first, then read `r.text`. The message is in there.
"""),
        md("""
### ⚠️ Trap — capitalisation is not a rule you can guess

Three different capitalisations in one path, and no consistent rule:

| level | spelling |
|---|---|
| directory | `sanctsound_mb01_09_tol_1h` — all lower |
| filename | `SanctSound_MB01_09_TOL_1h` — title case, product letters upper |
| trailing unit | `1h`, **not** `1H` |

`product.upper()` gives `TOL_1H`, which does not exist, and the failure is a
`NoSuchKey` — the same error as the trap above, for a completely different reason. Two
unrelated mistakes, one indistinguishable symptom.
"""),
        code('''
for product in S.SOUND_PRODUCTS:
    name = S.ncei_object_name(product, "01").rsplit("/", 1)[-1]
    print(f"  {product:8} -> {name}")
print()
print("  The last file name is built as product[:-1].upper() + product[-1], which is")
print("  why it comes out TOL_1h and not TOL_1H.")
'''),
        md("""
### ⚠️ Trap — do not use the `aws s3` CLI here

It is the obvious tool and it will not work on many machines. `aws s3` reads
`~/.aws/config`, and a local profile pointing at a MinIO endpoint (for development
against something else) silently redirects every `aws s3` command — so you get
connection refusals to `localhost:9000` for a bucket that is public and fine.

The GCS JSON API used above needs **no configuration at all**: no profile, no region,
no credentials. For a public bucket that is strictly simpler, and it works the same on
every machine in the room. Use `aws s3 --endpoint-url https://storage.googleapis.com` if
you need the CLI, but you do not need the CLI.
"""),

        md("""
## 3. What you got

Deployment 01: 3,185 hours × 30 third-octave bands, from 25 Hz to 20 kHz.
"""),
        code('''
import xarray as xr

p = Path.cwd() / "_mb01_01_tol_1h.nc"
p.write_bytes(_fetch.get(S.ncei_file_url("tol_1h", "01"), quiet=True).content)
ds = xr.open_dataset(p)

print("  dims       :", dict(ds.sizes))
print("  variables  :", list(ds.data_vars))
print("  span       :", str(ds.time.values[0])[:19], "->", str(ds.time.values[-1])[:19])
print("  units      :", ds.sound_pressure_levels.attrs.get("units"))
freq = ds.frequency.values
print(f"  bands      : {len(freq)}   {freq.min():.0f} Hz .. {freq.max():.0f} Hz")
print("  first bands:", [float(f) for f in freq[:8]])
'''),
        code('''
# The median spectrum: what does the bay sound like, by frequency?
median_db = ds.sound_pressure_levels.median(dim="time").values
p25, p75 = np.percentile(ds.sound_pressure_levels.values, [25, 75], axis=0)

fig, ax = plt.subplots(figsize=(11, 5))
ax.fill_between(freq, p25, p75, color="#4a7fb5", alpha=0.25,
                label="interquartile range")
ax.plot(freq, median_db, color="#1b3a5c", lw=1.8, label="median")
ax.set_xscale("log")
ax.set_xlabel("frequency  (Hz, log scale)")
ax.set_ylabel("sound pressure level  (dB re 1 µPa²)")
ax.set_title("MB01 deployment 01 — underwater sound by frequency",
             loc="left", fontweight="bold")
ax.legend()

# Annotate the two regimes the rest of the workshop cares about.
for hz, label, colour in [(60, "shipping", "#c0392b"), (3000, "wind/waves", "#27ae60")]:
    i = int(np.argmin(np.abs(freq - hz)))
    ax.annotate(label, xy=(freq[i], median_db[i]), xytext=(6, 10),
                textcoords="offset points", fontsize=9, color=colour, weight="bold")
plt.tight_layout()
plt.show()
'''),
        code('''
# Why the spectrum is a useful thing to have in hand: noise is not flat, and the
# reason a question is answerable depends on which band you ask in.
flat = median_db.max() - median_db.min()
print(f"  level varies by {flat:.1f} dB across 25 Hz - 20 kHz")
print(f"  lowest band  ({freq[0]:.0f} Hz)  : {median_db[0]:.1f} dB")
print(f"  highest band ({freq[-1]:.0f} Hz) : {median_db[-1]:.1f} dB")
print()
print("  Low frequencies are dominated by distant shipping. High frequencies by")
print("  wind and breaking waves, which are loud only in storms. That is why")
print("  'is it windy' and 'is there a ship' are different questions about the")
print("  same recording -- and why one number cannot answer both.")
'''),
        code('''
_fetch.expect("deployment 01 hours", int(ds.sizes["time"]), 3185)
_fetch.expect("third-octave bands", int(ds.sizes["frequency"]), 30)
_fetch.expect("lowest band Hz", float(freq.min()), 25.0)
_fetch.expect("highest band Hz", float(freq.max()), 20000.0)
_fetch.expect_range("median level dB", float(np.median(median_db)), 60.0, 110.0)
_fetch.expect_range("spectral range dB", float(flat), 5.0, 60.0)
print()
print("  0 dB re 1 uPa^2 is a REFERENCE, not a measurement. Levels near 0 would mean")
print("  a decoding problem, not a quiet ocean.")
'''),
        title="03 GCS object storage",
    )
    return b


# ===========================================================================
# 04 -- Browsable tree + netCDF
# ===========================================================================
def nb_04() -> "object":
    b = build(
        md("""
# 04 — Browse a tree, read netCDF

**Access pattern: a browsable HTTPS directory of netCDF files.** No query language, no
search index, no object-store API. Just a path, and files you can fetch. Argo's GDAC
(global data assembly centre) is the reference example, and so is much of the climate
archive.

**One thing to say up front, because it would otherwise be a surprise:** the float used
here, `1900063`, is in the **North Atlantic** (24–27 N, 22–18 W) and its cycles run
2002–2004. It is not near Monterey Bay. It is here because it is a small, complete and
well-formed example of the *file structure*, which is what this notebook teaches. The
cost of that compromise is stated in section 5 — it is worth reading.
"""),
        *preamble(),

        md("""
## 1. The directory is HTML, and that is fine

There is no listing API. You fetch the directory and read the links. An HTML parser is
overkill for a list of `href`s, so a regex is both sufficient and easier to read.
"""),
        code('''
import re

listing = _fetch.get(S.ARGO_DIR, quiet=True).text
links = re.findall(r'href="([^"?/][^"]*)"', listing)
files = [l for l in links if l.endswith((".nc", ".txt"))]

print(f"  {len(files)} files in {S.ARGO_FLOAT}/")
for f in files:
    print("   ", f)
'''),

        md("""
| file | size | what it holds |
|---|---|---|
| `_prof.nc` | 689,348 B | **all 98 cycles** of temperature, salinity, pressure — the data |
| `_meta.nc` | 34,900 B | float configuration: launch date, PI, serial number |
| `_tech.nc` | 2,855,864 B | instrument metadata, 10,976 parameters |

The aggregated `_prof.nc` is the right granularity. The alternative — one file per cycle
— means 98 requests and 98 chances to get a partial result.
"""),
        code('''
import xarray as xr

p = Path.cwd() / "_argo_1900063_prof.nc"
p.write_bytes(_fetch.get(S.ARGO_FILES["prof"], quiet=True).content)
ds = xr.open_dataset(p)

print("  dims:", dict(ds.sizes))
print("  PRES:", ds.PRES.dtype, ds.PRES.shape, ds.PRES.attrs.get("units"))
print("  TEMP:", ds.TEMP.dtype, ds.TEMP.shape, ds.TEMP.attrs.get("units"))
print("  PSAL:", ds.PSAL.dtype, ds.PSAL.shape, ds.PSAL.attrs.get("units"))
print("  JULD:", ds.JULD.dtype, ds.JULD.shape, "->", str(ds.JULD.values[0])[:10],
      "..", str(ds.JULD.values[-1])[:10])
'''),

        md("""
### ⚠️ Trap — `N_PARAM` exists but does not index the data

`N_PARAM` is in `ds.sizes` with value 3, and `STATION_PARAMETERS` is shaped
`(N_PROF, N_PARAM)`. The natural assumption is that `TEMP` is
`(N_PROF, N_LEVELS, N_PARAM)` and you index all three.

It is not. This is the **v1.0** file format, where temperature, salinity and pressure
are already split into separate variables of shape `(N_PROF, N_LEVELS)`, while
`N_PARAM` is a leftover from the v2.4 stacked format.

```python
ds.TEMP.isel(N_PROF=0, N_PARAM=0)
# ValueError: Dimensions {'N_PARAM'} do not exist.
```

So: **check `.shape` before you index.** The dimension list is not a contract about
which variables use it.
"""),
        code('''
print("  N_PARAM is in ds.sizes:", "N_PARAM" in ds.sizes, "=", ds.sizes.get("N_PARAM"))
print("  STATION_PARAMETERS shape:", ds.STATION_PARAMETERS.shape)
print("  TEMP shape              :", ds.TEMP.shape, " <- no N_PARAM")
print()
try:
    ds.TEMP.isel(N_PROF=0, N_PARAM=0)
except ValueError as exc:
    print("  ds.TEMP.isel(N_PROF=0, N_PARAM=0) ->")
    print("   ", str(exc)[:96])
print()
print("  STATION_PARAMETERS is a byte array too:")
print("   ", ds.STATION_PARAMETERS.values.ravel()[:3])
'''),

        md("""
### ⚠️ Trap — Argo QC flags are **bytes**, and comparing them to an int is all-False

Every measurement has a quality-control flag: `1` good, `2` probably good, `3` bad,
`4` bad, `5` value changed, `9` missing. In the aggregated `_prof.nc` they are stored as
**characters**, so `xarray` gives you an object array of `numpy.bytes_`.

```python
ds.PRES_QC == 1      # -> array([False, False, False, ...])
```

No exception. No warning. It reads as "nothing passed QC", which is a conclusion you
would happily believe and act on.

Why it happens: the per-cycle `.nc` / `_D` byte files store flags as `int8`, so code
written against those works fine until it meets an aggregated file. **The encoding
depends on which file you opened.**

```python
>>> np.asarray(ds.PRES_QC.values).ravel()[:4]
array([b'1', b'1', b'1', b'1'], dtype=object)
>>> (np.asarray(ds.PRES_QC.values) == 1).all()
np.False_
```
"""),
        code('''
qc = ds["PRES_QC"].values
print("  dtype       :", qc.dtype)
print("  first values:", qc.ravel()[:4])
print()
print("  the bug, live:")
print("    (qc == 1).all()  ->", (qc == 1).all())
print("    (qc == b'1').all() ->", (qc == b"1").all())
print()
print("  Neither of those is the right test, because a single bad value makes .all()")
print("  False anyway. Decode to ints, then count:")

def decode_qc(arr):
    """Argo QC flags: int8 in the per-cycle files, characters in the aggregated file."""
    a = np.asarray(arr)
    if a.dtype.kind in "iu":                      # already numeric
        return a.astype(int)
    flat = [int(v.decode()) if isinstance(v, (bytes, np.bytes_)) and v.isdigit()
            else -1 for v in a.ravel()]
    return np.array(flat, dtype=int).reshape(a.shape)

codes = decode_qc(qc)
values, counts = np.unique(codes, return_counts=True)
lookup = {0: "no QC", 1: "good", 2: "probably good", 3: "bad", 4: "bad",
          5: "value changed", 6: "below range", 7: "above range", 8: "range differs",
          9: "missing"}
for v, n in zip(values, counts):
    print(f"    QC {v:>2}  {lookup.get(v, '?'):16} {n:>7,}  ({n / codes.size:5.1%})")

good = codes == 1
print()
print(f"  good values: {good.sum():,} of {codes.size:,}  ({good.sum() / codes.size:.1%})")
print("  -> 1 means GOOD. So the correct test is (decoded == 1), not (raw == 1).")
'''),

        md("""
## 2. One profile

Take the first cycle: pressure, temperature and salinity against depth.
"""),
        code('''
prof = 0
p_dbar = ds.PRES.isel(N_PROF=prof).values
temp = ds.TEMP.isel(N_PROF=prof).values
sal = ds.PSAL.isel(N_PROF=prof).values
keep = ~np.isnan(p_dbar)

print(f"  cycle {prof} at {str(ds.JULD.values[prof])[:10]}")
print(f"  {keep.sum()} levels,  {p_dbar[keep].min():.0f} - {p_dbar[keep].max():.0f} dbar")
print(f"  temperature {temp[keep].min():.2f} - {temp[keep].max():.2f} C")
print(f"  salinity    {sal[keep].min():.2f} - {sal[keep].max():.2f} PSU")
'''),
        code('''
fig, axes = plt.subplots(1, 3, figsize=(12, 6.5), sharey=True)
depth = p_dbar[keep]

axes[0].plot(temp[keep], depth, color="#c0392b", lw=1.6)
axes[0].set_xlabel("temperature  (°C)")

axes[1].plot(sal[keep], depth, color="#1b3a5c", lw=1.6)
axes[1].set_xlabel("salinity  (PSU)")

axes[2].plot(sal[keep], temp[keep], color="#27ae60", lw=1.6)
axes[2].set_xlabel("salinity  (PSU)")
axes[2].set_ylabel("temperature  (°C)")

for ax in axes[:2]:
    ax.set_ylabel("pressure  (dbar)")
    ax.invert_yaxis()
axes[2].legend(["profile 0"], loc="lower left", fontsize=8)

fig.suptitle(f"Argo float {S.ARGO_FLOAT}, cycle {prof} — {str(ds.JULD.values[prof])[:10]}",
             x=0.02, ha="left", fontweight="bold")
plt.tight_layout()
plt.show()
'''),
        md("""
The middle panel is the one to look at. In the **upper ocean** salinity rises steeply
with depth — that is the **halocline**, and it is the boundary between fresher
subtropical surface water and the saltier water below. Below it, salinity is nearly flat
all the way to 2,000 m, which is characteristic of deep water everywhere.

A single float tells you this once, at one place. What makes it useful is that the
float repeats every ~10 days, so you can watch the halocline move.
"""),
        code('''
# The halocline: the depth of the strongest salinity gradient, per cycle.
def halocline(depth, sal):
    """Depth of maximum dS/dz, ignoring fill and the top few levels."""
    ok = ~np.isnan(sal) & (depth > 10) & (depth < 800)
    d, s = depth[ok], sal[ok]
    if d.size < 5:
        return np.nan
    grad = np.abs(np.gradient(s, d))
    return float(d[int(np.argmax(grad))])

hal = np.array([halocline(ds.PRES.isel(N_PROF=i).values, ds.PSAL.isel(N_PROF=i).values)
                for i in range(ds.sizes["N_PROF"])])
juld = pd.to_datetime(ds.JULD.values)

print(f"  {np.isfinite(hal).sum()} of {hal.size} cycles gave a halocline")
print(f"  depth {np.nanmin(hal):.0f} - {np.nanmax(hal):.0f} dbar   mean {np.nanmean(hal):.0f} dbar")
'''),
        code('''
fig, ax = plt.subplots(figsize=(11, 4))
ax.plot(juld, hal, lw=1.2, color="#1b3a5c")
ax.set_ylabel("halocline depth  (dbar)")
ax.set_xlabel("")
ax.set_title("Halocline depth over 98 cycles — the float is a time series, not a snapshot",
             loc="left", fontweight="bold")
ax.invert_yaxis()
plt.tight_layout()
plt.show()
'''),

        md("""
## 3. Traps so far

| # | trap | symptom |
|---|---|---|
| 1 | directory listing is HTML, not JSON | a parser, or a regex for `href=` |
| 2 | `N_PARAM` is in `ds.sizes` but unused by `TEMP` | `ValueError` on `isel`, or a wrong answer if you ignore it |
| 3 | QC flags are **bytes** in aggregated files, `int8` in per-cycle files | `== 1` is silently all-False |
| 4 | a single bad QC value makes `.all()` False anyway | count the codes, don't use `.all()` |

## 4. `argopy` is not an option here

The obvious library is `argopy`. It is currently broken against modern `erddapy`:
versions 1.3.1 and 1.4.0 both import `erddapy.erddapy._quote_string_constraints`, a
private symbol removed in `erddapy` 3.x. `argopy` 1.4.0 additionally pins `xarray<=2025.9.0`.

Making it work means pinning `erddapy<3` **and** downgrading xarray — dragging a
working stack backwards for a convenience wrapper. When a library requires that, and the
underlying files are plain netCDF over HTTPS, fetching them directly is the better trade.
"""),
        md("""
## 5. The cost of choosing a float by hand

This notebook uses a float that is not near the site, and the honest reason is that
**there is no index**. Verified, not assumed:

| you would like | what exists |
|---|---|
| `/index/` | 404 |
| `/dac/index/` | 404 |
| `<wmo>_prof_index.txt` | 404 |
| `index/<wmo>.txt` | 404 |

Worse, no *small* file answers "where is this float?":

| file | size | has `LATITUDE`? |
|---|---|---|
| `_meta.nc` | 34,900 B | **no** — configuration only |
| `_tech.nc` | 2,855,864 B | **no** — instrument metadata |
| `_prof.nc` | 689,348 B | yes |

So finding one float near a given site costs 689 KB per candidate, and the coriolis DAC
holds **4,261** floats — about **2.9 GB** to screen it exhaustively. Sampling 711 of them
found none in the north-east Pacific box (30–45 N, 130–115 W).

That is a property of how the archive is laid out, not an oversight, and it is worth
internalising as a design lesson: **if you are about to screen a catalogue by
downloading it, that is the archive telling you its index is missing — plan for it, or
find a source that has one.** ERDDAP and Copernicus both do. This is precisely why the
project kept a fallback ladder rather than committing to the first source that answered.
"""),
        code('''
_fetch.expect("profiles", int(ds.sizes["N_PROF"]), 98)
_fetch.expect("levels", int(ds.sizes["N_LEVELS"]), 92)
_fetch.expect("_prof.nc bytes", S.ARGO_EXPECTED_BYTES, 689348)
_fetch.expect_range("surface temperature", float(np.nanmax(temp)), 15.0, 30.0)
_fetch.expect_range("abyssal temperature", float(np.nanmin(temp)), 0.0, 6.0)
_fetch.expect_range("surface salinity", float(np.nanmax(sal)), 34.0, 38.0)
_fetch.expect_range("halocline depth", float(np.nanmean(hal)), 50.0, 900.0)
print()
print("  0-6 C at depth and 34-38 PSU at the surface are the only physically")
print("  sensible values for an ocean profile. If a profile gives you 4 PSU or")
print("  200 C, you have a scale, a fill-value or a QC problem.")
'''),
        title="04 Argo GDAC netCDF",
    )
    return b


# ===========================================================================
# 06 -- Fixed-format text
# ===========================================================================
def nb_06() -> "object":
    b = build(
        md("""
# 06 — Parse fixed-format text

**Access pattern: a gzipped, column-oriented text file with a two-line header.** No
API, no structure, no self-description. This is the oldest pattern here and still the
one that quietly corrupts your analysis, because nothing in it raises an error.

Deliberately the shortest notebook. It is the least abstract pattern, and it lands well
after the harder ones.
"""),
        *preamble(),

        md("""
## 1. What it looks like

NDBC moored meteorological data, one file per station-year, gzipped:

```
https://www.ndbc.noaa.gov/data/historical/stdmet/46092h2019.txt.gz
```
"""),
        code('''
import gzip

res = _fetch.get(S.ndbc_url(), quiet=True)
text = gzip.decompress(res.content).decode()
lines = text.splitlines()

print(f"  {len(res.content):,} bytes gzipped -> {len(text):,} bytes, {len(lines):,} lines")
print()
for i in range(4):
    tag = "NAMES" if i == 0 else "UNITS" if i == 1 else "data"
    print(f"  [{tag}] {lines[i][:74]}")
'''),

        md("""
### ⚠️ Trap — line 0 is the names, line 1 is the units, data starts at line 2

Parse line 1 instead of line 0 and every column comes out named `#yr`, `mo`, `dy`, `hr`,
`mn` instead of `YY`, `MM`, `DD`, `hh`, `mm`. No error. The file parses perfectly. The
bug is that your code now refers to `frame["MM"]` and gets a `KeyError` an hour later,
far from the cause.

The giveaway is the `#` prefix in the units line — the file marks the units row as a
comment, which is why the names row also carries a `#`.
"""),
        code('''
cols = [c.lstrip("#") for c in lines[0].split()]
print("  parsed from line 0 (correct):", cols[:8])
print("  parsed from line 1 (wrong)  :", [c.lstrip("#") for c in lines[1].split()][:8])
print()
print("  data rows:", len([l for l in lines[2:] if l.strip()]))
print()
print("  Note it is the NAMES line that is prefixed with '#', not the units line --")
print("  so 'strip the #' is not a reliable way to find the header either.")
'''),

        md("""
### ⚠️ Trap — the resolution is **not** uniform

A year of hourly data is 8,760 rows. This file has **7,835**. Timestamps are stamped
about 50 minutes past the hour, and UTC.

The span starts on 5 January, not 1 January — the first days are simply absent. So
"hourly" is a description of intent, not of the file. Never assume a cadence; always
check, and resample explicitly.
"""),
        code('''
raw = pd.DataFrame([l.split() for l in lines[2:] if l.strip()], columns=cols)
stamps = pd.to_datetime(
    dict(year=pd.to_numeric(raw.YY), month=pd.to_numeric(raw.MM),
         day=pd.to_numeric(raw.DD), hour=pd.to_numeric(raw.hh),
         minute=pd.to_numeric(raw.mm)),
    utc=True,
).dt.tz_localize(None)

print(f"  rows            : {len(stamps):,}")
print(f"  span            : {stamps.min()}  ->  {stamps.max()}")
print(f"  a full year 2019 is 8,760 hours; this file has {len(stamps):,}")
print(f"  distinct hours  : {stamps.dt.floor('h').nunique():,}")
print(f"  missing minutes : {stamps.dt.minute.value_counts().head(3).to_dict()}")
print()
gap = pd.Series(stamps).diff().dt.total_seconds().div(3600)
print(f"  most common gap : {gap.value_counts().head(3).to_dict()} hours")
print("  -> resample explicitly before any arithmetic that assumes hourly.")
'''),

        md("""
### ⚠️ Trap — missing-value sentinels differ per column, and 99 is a valid bearing

Most fields use `99.0` for missing. But `WDIR`, `MWD` and `PRES` use `999.0` /
`9999.0`. And a blanket `>= 99` filter on wind direction **deletes real easterly
winds** — 99° is a perfectly ordinary direction.

| column | sentinel |
|---|---|
| `WSPD`, `GST`, `WVHT`, `DPD`, `APD`, `ATMP`, `WTMP`, `DEWP`, `VIS`, `TIDE` | 99.0 |
| `WDIR`, `MWD` | 999.0 |
| `PRES` | 9999.0 |

Worth being precise about: **in this particular file, for 2019, neither 99 nor 999
appears in `WDIR` at all** (measured below). The bug is latent rather than observed
here — which is worse, because a missing-data handler that quietly deletes a degree of
wind direction will not announce itself until someone plots the compass rose.
"""),
        code('''
wd = pd.to_numeric(raw.WDIR, errors="coerce")
print(f"  WDIR: {wd.min():.0f} - {wd.max():.0f} deg")
print(f"  values equal to 99  : {(wd == 99).sum()}")
print(f"  values equal to 999 : {(wd == 999).sum()}")
print()
print("  So for 2019 at this station the sentinel does not occur. The trap is still")
print("  real: a handler written as 'WDIR >= 99 is missing' removes valid bearings")
print("  whenever the sentinel is 999, and silently biases any direction rose.")
print()
# What a blanket filter would cost, in a year that does contain 99s.
n_would_drop = int((wd.between(99, 99)).sum())
print(f"  a blanket >= 99 filter would drop {n_would_drop} rows here, and would drop")
print("  real data in any file where 99 deg is reported.")
'''),

        md("""
## 2. Wind is a vector, and direction is *from*

Two conventions that are easy to get backwards:

1. `WDIR` is the direction the wind comes **from**, in degrees true. 350° is wind from
   the north, blowing south.
2. The components below point where the air is **going**, so they carry a sign flip.
"""),
        code('''
wspd = pd.to_numeric(raw.WSPD, errors="coerce").replace(99.0, np.nan)
wdir = pd.to_numeric(raw.WDIR, errors="coerce").replace(999.0, np.nan)

rad = np.radians(wdir)
u = -wspd * np.sin(rad)      # eastward component
v = -wspd * np.cos(rad)      # northward component
# The northerly component: POSITIVE when wind blows FROM the north. This is the one
# that drives upwelling on the California coast, so sign convention matters a lot.
northerly = wspd * np.cos(rad)

# ⚠️ `.to_numpy()` on every one of these, and that is not stylistic.
# Passing a Series into DataFrame(..., index=<DatetimeIndex>) makes pandas ALIGN ON
# INDEX. These Series carry a RangeIndex 0..7834, the frame carries timestamps, no
# labels match, and every column comes out NaN. No error, no warning -- just a
# column of missing data that looks exactly like a column of missing data.
frame = pd.DataFrame({"wspd": wspd.to_numpy(), "wdir": wdir.to_numpy(),
                      "u": u.to_numpy(), "v": v.to_numpy(),
                      "northerly": northerly.to_numpy()}, index=stamps)

# Show the failure, so it is recognisable next time.
wrong = pd.DataFrame({"wspd": wspd}, index=stamps)   # the bug
print("  with .to_numpy()   -> mean wind speed", f"{frame.wspd.mean():.2f} m/s")
print("  without it (the bug)-> mean wind speed", f"{wrong.wspd.mean():.2f} m/s")
print()
print(f"  mean northerly component: {frame.northerly.mean():+.2f} m/s")
print()
print("  A negative mean northerly component means the wind predominantly blows")
print("  FROM the south -- downwelling-favourable on this coast. A positive value is")
print("  upwelling-favourable.")
'''),
        md("""
### ⚠️ Trap — you cannot average a compass bearing

Bearings wrap. The naive mean of 350° and 10° is **180°** — the exact opposite of 0°.
For any month with wind from both sides of north, a plain `.mean()` gives you a
direction nobody experienced.

The fix is to average the unit vectors instead, which is exactly what `u` and `v` above
already are:

```
mean direction = atan2(mean(u), mean(v))
```
"""),
        code('''
def circular_mean_deg(degrees):
    """Mean of bearings. Bearings wrap, so average the vectors, not the degrees."""
    r = np.radians(pd.Series(degrees).dropna())
    if r.empty:
        return float("nan")
    return float((np.degrees(np.arctan2(np.sin(r).mean(), np.cos(r).mean())) + 360) % 360)

naive = frame.wdir.mean()
correct = circular_mean_deg(frame.wdir)
print(f"  naive  .mean()   : {naive:6.1f} deg")
print(f"  circular mean    : {correct:6.1f} deg")
print(f"  difference       : {abs(naive - correct):6.1f} deg")
print()
print("  Demonstration of why: bearings either side of north.")
demo = [350, 10]
print(f"    {demo}  naive mean = {np.mean(demo):.1f} deg, circular = {circular_mean_deg(demo):.1f} deg")
print("    The naive answer is due south. The wind was from the north.")
'''),
        code('''
fig, axes = plt.subplots(1, 2, figsize=(12, 4.6), constrained_layout=True)

daily = frame.resample("1D").agg(
    wind_speed=("wspd", "mean"),
    northerly=("northerly", "mean"),
    u=("u", "mean"), v=("v", "mean"),
)
daily["dir"] = [circular_mean_deg(g.wdir) for _, g in frame.resample("1D")]
axes[0].plot(daily.index, daily.wind_speed, color="#1b3a5c", lw=0.9)
axes[0].set_ylabel("wind speed  (m/s)")
axes[0].set_title(f"NDBC {S.WIND_STATION} daily mean wind, 2019", loc="left", fontweight="bold")

axes[1].plot(daily.index, daily.northerly, color="#c0392b", lw=0.9)
axes[1].axhline(0, color="#888", lw=0.8, ls="--")
axes[1].set_ylabel("northerly component  (m/s)")
axes[1].set_title("positive = wind FROM the north = upwelling-favourable",
                  loc="left", fontweight="bold")

plt.show()
'''),
        code('''
# Wind rose, done correctly: bin the vectors, not the bearings.
n = len(frame)
bins = 16
theta = np.radians(frame.wdir)
edges = np.linspace(-np.pi, np.pi, bins + 1)
idx = np.digitize(theta, edges) - 1
speeds = frame.wspd.to_numpy()

fig = plt.figure(figsize=(7, 6.2))
ax = fig.add_subplot(111, polar=True)
radii, colours = [], []
for b in range(bins):
    m = (idx == b) & ~np.isnan(speeds)
    radii.append(float(speeds[m].mean()) if m.any() else 0.0)
    colours.append("#c0392b" if np.cos(edges[b]) > 0 else "#4a7fb5")
ax.bar(edges[:-1] + np.pi / bins, radii, width=2 * np.pi / bins, color=colours, alpha=0.85)
ax.set_theta_zero_location("N")
ax.set_theta_direction(-1)
ax.set_title("Wind rose — red: from the north (upwelling-favourable)",
             pad=22, fontweight="bold")
plt.show()

print(f"  {bins} sectors, {n:,} observations")
print(f"  fastest sector mean: {max(radii):.2f} m/s")
'''),
        code('''
_fetch.expect("data rows", len(stamps), 7835)
_fetch.expect("columns", cols[:6], ["YY", "MM", "DD", "hh", "mm", "WDIR"])
_fetch.expect_range("mean wind speed", float(frame.wspd.mean()), 3.0, 12.0)
_fetch.expect_range("mean northerly", float(frame.northerly.mean()), -8.0, 8.0)
_fetch.expect("naive != circular", abs(naive - correct) > 0.01, True)
print()
print("  The last assertion is the one that matters. If a naive bearing mean and a")
print("  circular mean agree, either the wind did not cross north, or your circular")
print("  mean is not doing anything. They should differ.")
'''),
        title="06 NDBC fixed format",
    )
    return b
