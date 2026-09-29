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
def nb_01() -> "object":
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
