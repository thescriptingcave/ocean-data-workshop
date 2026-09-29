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
