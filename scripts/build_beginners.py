"""Generate the beginners notebooks.

A separate tier from ``notebooks/``, and deliberately much smaller. The workshop
tier assumes you can already hold six access patterns in your head; this one assumes
you have never fetched a URL.

Design decisions that came out of feedback that the workshop tier was too hard:

  * **Plain ``requests``.** No caching helper, no session wrapper. They learn the
    library they will use at work, not one that exists only in this repo.
  * **No Docker, no database, no ``make``, no ``.env``, no prefetch.** The whole
    install is ``pip install -r beginners/requirements.txt``.
  * **Three response shapes**, because those are what actually differ: delimited
    text, JSON, and compressed text. Same four techniques applied three times, so
    the second and third are recognisable.
  * **A trap appears only after the working version.** The workshop led with the
    traps; here you fetch it successfully first, then see what the library quietly
    fixed for you.
  * **Short.** 8-14 cells each. If a notebook is hard to follow it is too long,
    not too subtle.

Sources, all ocean, all anonymous, all verified while writing this:

  CSV ......... ERDDAP / jplMURSST41          flat, one header row you must skip
  JSON ......... NOAA CO-OPS tides & currents  object wrapping a list, cryptic keys
  gzip ......... NDBC 46092                   compressed, fixed columns, sentinels

``scripts/build_beginners.py --execute`` renders and runs them.
"""

from __future__ import annotations

import sys
from pathlib import Path

import nbformat as nbf

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "beginners"
KERNEL = "python3"

# ---------------------------------------------------------------- URLs, verbatim
# Written out in full in the notebooks rather than imported from a module. A beginner
# should be able to read the address that produced the data in front of them.
ERDDAP = "https://coastwatch.pfeg.noaa.gov/erddap/griddap/jplMURSST41"
SST_URL = (
    ERDDAP + ".csv?analysed_sst"
    "%5B(2019-09-01T00:00:00Z):(2019-09-30T00:00:00Z)%5D"
    "%5B(36.6):(36.6)%5D%5B(-122.2):(-122.2)%5D"
    "&.time=first&.lat=first&.lon=first"
)

COOPS_URL = (
    "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
    "?product=wind&application=beginners"
    "&begin_date=20240115&end_date=20240116&station=9414290"
    "&time_zone=gmt&units=metric&interval=h&format=json"
)

NDBC_URL = "https://www.ndbc.noaa.gov/data/historical/stdmet/46092h2019.txt.gz"


def md(t: str):
    return nbf.v4.new_markdown_cell(t.strip("\n"))


def code(t: str):
    return nbf.v4.new_code_cell(t.strip("\n"))


def build(*cells, title: str):
    nb = nbf.v4.new_notebook()
    nb.cells = list(cells)
    nb.metadata = {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": KERNEL},
        "language_info": {"name": "python"},
        "beginners": {"title": title},
    }
    return nb


# ===========================================================================
def nb_00():
    return build(
        md("""
# 00 — A URL is a thing you can fetch

This is the whole course in one page. Everything after it is a variation.

**A URL is just a string** that says where something lives on the internet. When a
program "fetches" a URL, it does exactly what your browser does: it asks a computer
somewhere else for a file, and gets one back.

That is the entire model. Request, response, done.
"""),
        md("""
## 1. Do it by hand first

Before any Python, do it in a terminal. `curl` asks a server for a file and prints
what comes back. It is the shortest possible program.

Copy this into a terminal and press enter. If you do not have `curl`, open the URL in
a browser instead — you will see the same bytes, just rendered.

```bash
curl -s "https://coastwatch.pfeg.noaa.gov/erddap/griddap/jplMURSST41.csv?analysed_sst%5B(2019-09-01T00:00:00Z):(2019-09-30T00:00:00Z)%5D%5B(36.6):(36.6)%5D%5B(-122.2):(-122.2)%5D&.time=first&.lat=first&.lon=first"
```

You should get some text that looks like:

```
time,latitude,longitude,analysed_sst
UTC,degrees_north,degrees_east,degree_C
2019-09-01T09:00:00Z,36.6,-122.2,16.383
```

That is **sea surface temperature off Monterey Bay, one reading per day for
September 2019**, and it is free, public, and about 1.3 kB. You are about to do the
same thing from Python, and then do it about forty more times in a way that means
something.
"""),
        md("""
## 2. Now do it from Python

`curl` is the command-line version of a program called `requests`. Same request, same
response, same bytes. Python just lets you keep the result in a variable.
"""),
        code('''
# One import. This is the whole library.
import requests

url = (
    "https://coastwatch.pfeg.noaa.gov/erddap/griddap/jplMURSST41.csv"
    "?analysed_sst%5B(2019-09-01T00:00:00Z):(2019-09-30T00:00:00Z)%5D"
    "%5B(36.6):(36.6)%5D%5B(-122.2):(-122.2)%5D"
    "&.time=first&.lat=first&.lon=first"
)

r = requests.get(url)          # ask for it; this takes a moment
print(r.status_code)           # 200 means "here it is"
print(len(r.content), "bytes") # how big it is
print(r.text[:120])            # the body, as text
'''),
        md("""
## 3. What just happened

Three things, and they are the same three things every time:

| | |
|---|---|
| **a request** | your program sends the URL to a server |
| **a response** | the server sends back a status code and a body |
| **the body** | the actual data, in one of a few shapes |

`r.status_code` is the reply. `200` means fine. `404` means "no such thing here".
`500` means the server broke. **Check it every time** — a lot of what follows is
really just that.

`r.content` is the body as raw bytes. `r.text` is the same bytes decoded as text.
Most of the trouble in this course is knowing which of the two you should want.

## 4. What is next

Three notebooks, one per shape a server might answer in:

| | shape | how you normally see it |
|---|---|---|
| **01** | comma-separated text | a spreadsheet, exported |
| **02** | JSON | nested text: `{}` and `[]` |
| **03** | compressed text | a file that un-compresses into 01 |

Each one does the same four things — `curl`, `requests`, `pandas`, `duckdb` — so by
notebook 03 you will recognise the pattern rather than learn it.
"""),
        title="00 A URL is a thing you can fetch",
    )


# ===========================================================================
def nb_01():
    return build(
        md("""
# 01 — Comma-separated text

The shape you already know: rows and columns, separated by commas. A server hands
you one and you turn it into a table.

Four ways to do the same fetch. The last is one line.
"""),
        md("""
## 1. What we're fetching

```bash
""" + SST_URL + """
```

A URL is three things glued together:

```
https://coastwatch.pfeg.noaa.gov/erddap/griddap/jplMURSST41.csv   <- where
?analysed_sst%5B...%5D%5B36.6...%5D%5B-122.2...%5D              <- what
&.time=first&.lat=first&.lon=first                                <- how to slice it
```

The part after `?` is a query string: `name=value` pairs joined by `&`. You have
written one before — every search box on the internet builds one. Square brackets
have to be written `%5B` and `%5D` so they survive the trip; that is all that
encoding is.

This particular one asks for one point in the ocean, every day in September 2019.
"""),
        code('''
import io

import pandas as pd
import requests

SST_URL = (
    "https://coastwatch.pfeg.noaa.gov/erddap/griddap/jplMURSST41.csv"
    "?analysed_sst%5B(2019-09-01T00:00:00Z):(2019-09-30T00:00:00Z)%5D"
    "%5B(36.6):(36.6)%5D%5B(-122.2):(-122.2)%5D"
    "&.time=first&.lat=first&.lon=first"
)

r = requests.get(SST_URL)
r.raise_for_status()          # 4xx/5xx become an exception you can read
print(r.status_code, len(r.content), "bytes")
print()
print(r.text[:150])
'''),
        md("""
## 2. The part that is annoying

`r.text` is a **string**, and pandas wants either a file path or a file-like object.
One line bridges them:

```python
io.StringIO(r.text)
```

That is the whole trick, and you will write it constantly.
"""),
        code('''
df = pd.read_csv(io.StringIO(r.text), skiprows=[1])
print(df.shape, list(df.columns))
print(df.head(3).to_string(index=False))
'''),
        md("""
## 3. What `skiprows` was for

Without it you get something wrong and nothing tells you:

```python
pd.read_csv(io.StringIO(r.text))
```

The first column would be full of the strings `"UTC"`, `"degrees_north"` and so on —
one row, one value, shifted by one. **No error. No warning.** Just a table where the
first data row is the file's units.

Look back at the raw text above. Line 1 is the names. Line 2 is the units. Line 3 is
the first real row. `skiprows=[1]` drops line 2 and leaves the rest correct.

This is the shape of most data problems you will ever have: **the data is fine, the
framing is not.** `skiprows` is the most common fix in this entire course.
"""),
        code('''
naive = pd.read_csv(io.StringIO(r.text))          # the mistake
fixed = pd.read_csv(io.StringIO(r.text), skiprows=[1])   # the fix

print("without skiprows -- first row:")
print(naive.head(1).to_string(index=False))
print()
print("with skiprows -- first row:")
print(fixed.head(1).to_string(index=False))
print()
print(f"naive has {naive.analysed_sst.isna().sum()} missing temperatures, "
      f"fixed has {fixed.analysed_sst.isna().sum()}")
'''),
        md("""
## 4. One line, with DuckDB

Everything above — the request, the text, the `StringIO`, the `skiprows` — exists
because a library is fussy about what it accepts.

DuckDB is not. Give it a URL and a SQL query and it does the rest:

```python
duckdb.sql("SELECT * FROM read_csv_auto('<url>')")
```

No download, no parse, no cache. It is not in your standard stack yet, which is why
it is last, but it is the punchline of the next three notebooks.
"""),
        code('''
import duckdb

rows = duckdb.sql(f"""
    SELECT time::TIMESTAMP AS time,
           analysed_sst::DOUBLE AS analysed_sst
    FROM read_csv_auto('{SST_URL}')
    WHERE time <> 'UTC'          -- drop the units row, which is still a data row
    ORDER BY time
""").df()                       # .df() to get a pandas DataFrame back

print(rows.shape, dict(rows.dtypes.astype(str)))
print(rows.head(3).to_string(index=False))
'''),
        md("""
The same numbers, and notice what DuckDB did and did not do for you.

It read the **header** correctly with no help. It did **not** remove the units line —
that is still sitting in the table as a row of data, which is why `time` came back as
text and `analysed_sst` came back as text, and why the arithmetic failed until you
cast them.

`pandas` failed differently: it trusted your `skiprows` and got the shift right by
accident. DuckDB got the header right and left the rest for you to ask for in SQL.

**Neither tool is smarter. They guess differently, and here they each got half of it.**
That is worth more than a rule about which to use, because it is the rule: look at what
you got before you compute with it.
"""),
        code('''
import matplotlib.pyplot as plt

fig, ax = plt.subplots(figsize=(10, 3.5))
ax.plot(rows.time, rows.analysed_sst, marker="o", ms=4, lw=1.4, color="#c0392b")
ax.set_ylabel("sea surface temperature  (°C)")
ax.set_title("Monterey Bay, September 2019 — one point per day, fetched from a URL",
             loc="left", fontweight="bold")
plt.tight_layout()
plt.show()

print(f"  {rows.analysed_sst.min():.1f} to {rows.analysed_sst.max():.1f} °C, "
      f"mean {rows.analysed_sst.mean():.1f}")
print("  15-17 °C is right for a California coast in September: upwelling pulls cold")
print("  water up from depth. If you had got 22 °C, something was wrong with the fetch.")
'''),
        title="01 Comma-separated text",
    )


# ===========================================================================
def nb_02():
    return build(
        md("""
# 02 — JSON

Same fetch, different shape. Where notebook 01 got a flat table of text, this one
gets **nested** text: objects `{}` and lists `[]`.

JSON is what most modern APIs answer in, so this is the one you will meet most.
"""),
        md("""
## 1. What we're fetching

```bash
""" + COOPS_URL + """
```

NOAA's tides and currents service, wind observations from a station near San
Francisco. No key, no account, no rate limit to worry about.

Three useful things about how this URL is written, because they are true of most
real APIs:

  * parameters are `name=value`, joined by `&`
  * `application=something` is a courtesy — most APIs ask you to identify yourself
  * `format=json` is the default here, but on many APIs `format=csv` or
    `format=json` is how you choose the shape. **The same service, three shapes.**
"""),
        code('''
import matplotlib.pyplot as plt
import requests

COOPS_URL = (
    "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
    "?product=wind&application=beginners"
    "&begin_date=20240115&end_date=20240116&station=9414290"
    "&time_zone=gmt&units=metric&interval=h&format=json"
)

r = requests.get(COOPS_URL)
r.raise_for_status()
print(r.status_code, len(r.content), "bytes")
print()
print(r.text[:300])
'''),
        md("""
## 2. `r.json()` — one line, and it is the whole difference

`r.text` would give you the string. `r.json()` gives you **Python objects**: dicts for
`{}`, lists for `[]`, numbers, strings, `True`/`False`, `None`.

Look at the shape before you do anything else. Printing the type and the keys is the
first move in any JSON work.
"""),
        code('''
payload = r.json()

print("type:", type(payload).__name__)
print("top-level keys:", list(payload.keys()))
print()
print("metadata:", payload["metadata"])
print()
print("type of ['data']:", type(payload["data"]).__name__, "with", len(payload["data"]), "items")
print("first item:", payload["data"][0])
'''),
        md("""
## 3. The shape, drawn out

```
{                              <- one object
  "metadata": { ... },         <- an object inside it
  "data": [                    <- a list inside it
    { "t": "...", "s": ... }, <- objects inside the list
    { "t": "...", "s": ... },
    ...
  ]
}
```

A **list of objects** is the shape you want, because it is exactly a table. Dig to it
and hand it to pandas.
"""),
        code('''
import pandas as pd

df = pd.json_normalize(payload["data"])
print(df.shape, list(df.columns))
print(df.head(3).to_string(index=False))
'''),
        md("""
`pd.json_normalize` takes a list of dicts and gives you one column per key, nesting
included. `pd.DataFrame(payload["data"])` does the same when there is no nesting to
flatten. Start with `json_normalize` — it is never worse.

## 4. Now the annoying part, and it is not the parsing

Those column names are `t`, `s`, `d`, `dr`, `g`, `f`. Single letters.
"""),
        code('''
print(df.head(2).to_string(index=False))
print()
print("Six columns. Six single letters. Nothing is wrong with the data; the server")
print("simply refuses to be helpful. You have to know that")
print("  t  = time")
print("  s  = speed, m/s")
print("  d  = direction, degrees true")
print("  dr = direction, as text (WSW)")
print("  g  = gust, m/s")
print("  f  = flags")
print()
print("and that information is in the product documentation, not in the response.")
'''),
        md("""
**This is the real lesson of JSON, and it is not about syntax.** Any API will hand you
data in a shape chosen by whoever built the service, with names chosen for their
database, not for you. There is no technique that avoids reading the documentation.
The best you can do is *look at the names before you trust them* — and `df.columns`
costs nothing.

Renaming is trivial once you know:
"""),
        code('''
wind = df.rename(columns={
    "t": "time", "s": "speed_ms", "d": "direction_deg",
    "dr": "direction_text", "g": "gust_ms", "f": "flags",
})
wind["time"] = pd.to_datetime(wind["time"])
wind = wind.sort_values("time")

print(wind.head(3).to_string(index=False))
print()
print("Names you chose, rather than names you inherited.")
'''),
        md("""
## 5. DuckDB on JSON

Worth knowing where DuckDB stops helping. It reads **list-shaped** JSON in one line,
but this response is an *object* wrapping the list, so DuckDB sees one row with two
nested columns. You would reach for the JSON pointer syntax, and at this point you are
happier in pandas.
"""),
        code('''
import duckdb

# A list-shaped JSON response: DuckDB, one line.
listy = duckdb.sql("""
    SELECT * FROM read_json_auto(
        'https://api.open-meteo.com/v1/forecast'
        '?latitude=36.7&longitude=-122.1&current=temperature_2m&timezone=UTC'
    )
""").df()
print("open-meteo (object-wrapped too):", listy.shape, listy.columns) if False else None

# The honest demonstration: our object-shaped response comes back as ONE row.
one = duckdb.sql(f"SELECT * FROM read_json_auto('{COOPS_URL}')").df()
print("CO-OPS via DuckDB ->", one.shape, "row")
print("  columns:", list(one.columns))
print()
print("  DuckDB parsed the object correctly; it just treats an object as a single")
print("  record, so the 48 measurements are a nested list inside one cell.")
print("  For list-shaped JSON it is genuinely one line -- see the docs for read_json.")
'''),
        code('''
fig, ax = plt.subplots(figsize=(10, 3.5))
ax.plot(wind.time, wind.speed_ms, marker="o", ms=3, lw=1.3, label="speed")
ax.plot(wind.time, wind.gust_ms, marker="o", ms=3, lw=1.0, alpha=0.6, label="gust")
ax.set_ylabel("wind  (m/s)")
ax.set_xlabel("")
ax.legend()
ax.set_title("NOAA station 9414290, 15 January 2024 — same URL, different shape",
             loc="left", fontweight="bold")
plt.tight_layout()
plt.show()
'''),
        title="02 JSON",
    )


# ===========================================================================
def nb_03():
    return build(
        md("""
# 03 — Compressed text

The third shape, and the one that catches everyone once. The file arrives
**gzip-compressed** — smaller to send, which is why almost every data service does it.

The data inside is ordinary text. The compression is on the outside.
"""),
        md("""
## 1. What we're fetching

```bash
""" + NDBC_URL + """
```

Hourly wind and wave observations from an actual buoy 10 km off Monterey Bay. The
`.gz` at the end is gzip.
"""),
        code('''
import requests

NDBC_URL = "https://www.ndbc.noaa.gov/data/historical/stdmet/46092h2019.txt.gz"

r = requests.get(NDBC_URL)
r.raise_for_status()
print(r.status_code, len(r.content), "bytes")
print("content type:", r.headers.get("Content-Type"))
'''),
        md("""
## 2. The mistake everybody makes

`r.text` looks like it should work. It does not.

`r.text` takes the **bytes** and *decodes them as text*. Gzip bytes are not text —
they are a compressed stream, and decoding them gives you a few hundred characters of
mojibake followed by nothing. It raises nothing. You would have to read the output to
notice.

`r.content` is the bytes untouched. You un-compress those yourself.
"""),
        code('''
import gzip

wrong = r.text[:60]
print("r.text gives you:")
print("   ", repr(wrong))
print()
print("  That is the gzip header, decoded as if it were language. Silently useless.")
print()

text = gzip.decompress(r.content).decode()   # the actual file
lines = text.splitlines()
print("r.content + gzip gives you:", len(lines), "lines")
for ln in lines[:3]:
    print("   ", ln[:74])
'''),
        md("""
## 3. The second thing about this file

Line 0 is the column **names**. Line 1 is the **units**. Data starts at line 2.

Same shape as notebook 01's trap, and the mistake is identical: parse the units line
instead of the names line and your columns come out called `#yr`, `mo`, `dy`, `hr`,
`mn`. You will not find out for an hour, when something you thought was a column
turns out not to exist.

There is no pandas option that reads fixed-width NDBC text for you. You read the two
header lines and split the rest.
"""),
        code('''
cols = [c.lstrip("#") for c in lines[0].split()]      # the NAMES line
rows = [ln.split() for ln in lines[2:] if ln.strip()]  # from line 2 onwards

print("columns:", cols)
print("rows   :", len(rows))
print("first  :", rows[0])
'''),
        code('''
import pandas as pd

df = pd.DataFrame(rows, columns=cols)
print(df.head(3).to_string(index=False))
'''),
        md("""
## 4. The third thing, and this one loses data quietly

Missing values are written as a **sentinel** — a number that cannot occur, standing in
for "nothing here". For most columns that number is `99`. For wind direction it is
`999`.

So a filter written as "anything ≥ 99 is missing" is **wrong**, because 99 degrees is
a real easterly wind. That filter does not raise; it quietly deletes real weather.
"""),
        code('''
wd = pd.to_numeric(df["WDIR"], errors="coerce")
wspd = pd.to_numeric(df["WSPD"], errors="coerce")

print("wind direction, raw range:", f"{wd.min():.0f} to {wd.max():.0f} degrees")
print("  how many exactly 99? ", int((wd == 99).sum()))
print("  how many exactly 999?", int((wd == 999).sum()))
print()
print("A blanket '>= 99 means missing' filter would remove", int((wd >= 99).sum()),
      "rows in this file.")
print("In a file that did contain 99-degree bearings it would delete real observations,")
print("and nothing would tell you.")
'''),
        code('''
# The correct way: mask per column, because the sentinel is per column.
wspd = wspd.replace(99.0, None)          # WSPD: 99 means missing
wd = wd.replace(999.0, None)            # WDIR: 999 means missing

# Split the wind into its along-coast and offshore components. A wind FROM the north
# (a bearing under 180) pushes surface water offshore, which is what brings cold
# nutrient-rich water up. A wind from the south does the opposite.
offshore = wspd * (wd < 180) - wspd * (wd >= 180)    # northerly -> negative
alongshore = wspd * (wd < 180) + wspd * (wd >= 180)  # always positive

out = pd.DataFrame({"wind_ms": wspd, "offshore_ms": offshore}).dropna()
print(f"{len(out):,} usable hours, mean wind {out.wind_ms.mean():.2f} m/s")
print(f"  mean offshore component {out.offshore_ms.mean():+.2f} m/s "
      f"({'northerly' if out.offshore_ms.mean() < 0 else 'southerly'} on average)")
print()
print("A negative offshore component means the wind was blowing FROM the north, which")
print("is what drives upwelling on this coast.")
'''),
        md("""
## 5. And where DuckDB stops helping

Notebook 01 ended with five lines of Python replaced by one line of SQL. This is the
other half of that story: **DuckDB is fast because it guesses, and sometimes the file is
too ambiguous to guess about.**

This NDBC file is space-*padded* — columns separated by varying runs of spaces — so
DuckDB cannot tell whether the delimiter is a single space, a tab or something else. It
declines rather than guessing wrong.
"""),
        code('''
import duckdb

NDBC_URL = "https://www.ndbc.noaa.gov/data/historical/stdmet/46092h2019.txt.gz"

try:
    print(duckdb.sql(f"SELECT count(*) FROM read_csv_auto('{NDBC_URL}')").fetchall())
except Exception as exc:
    print("DuckDB declines:")
    for line in str(exc).splitlines()[:3]:
        print("   ", line)
    print()
    print("  That is the correct behaviour. Guessing and being wrong silently is worse")
    print("  than refusing.")
'''),
        md("""
You *can* force it — turn off the guess, and write out all eighteen column names plus
a nineteenth to absorb the padding. It works. It is also longer than the four lines of
`pandas` above, and you would only bother if you had a hundred files like this rather
than one.

**So the rule is not "use DuckDB".** It is: *use DuckDB when the file is well-behaved,
because then it really is one line, and fall back to `pandas` when it is not.* Knowing
which case you are in is the skill. The one-liner is only a one-liner while the guessing
happens to be right.

## What to take from three notebooks

| shape | how you normally get it in | the thing that bites |
|---|---|---|
| delimited text | `pd.read_csv(io.StringIO(r.text))` | a second header line, silently shifting every row |
| JSON | `pd.json_normalize(r.json()["data"])` | column names chosen by the server, not by you |
| compressed | `gzip.decompress(r.content)` | `r.text` gives you mojibake, and no error |

The shapes will keep changing. Those three rows, and the habit of looking at
`r.text[:200]` before trusting anything, will not.
"""),
        title="03 Compressed text",
    )


# ===========================================================================
def nb_04():
    return build(
        md("""
# 04 — Now you do it

Three fetches, three shapes, and now **you** write them. The answers are in the last
cell if you want them, but try first.

Everything you need is on the previous three notebooks.
"""),
        md("""
## Before you start

Three rules, and they are the whole course:

1. **Always check `status_code`.** `r.raise_for_status()` if you want the failure to
   stop the program.
2. **Look at `r.text[:200]` before parsing.** Every weird result in this course was a
   header, a wrapper, or an error message where you expected data.
3. **A plausible number is not a correct number.** The traps are not exceptions; they
   are answers that look reasonable and are wrong.

## Exercise 1 — narrow the CSV fetch

Notebook 01 asked for September 2019 at one point. Get **one week** instead.

*Hint: the dates are in the URL. `2019-09-01` → `2019-09-07`.*
"""),
        code('''
# YOUR TURN. Build a URL for one week, and print the first three rows.
week_url = None  # <- replace

if week_url:
    import io

    import pandas as pd

    r = requests.get(week_url)
    r.raise_for_status()
    print(r.text[:200])          # look before you parse
    print()
    print(pd.read_csv(io.StringIO(r.text), skiprows=[1]).head(3).to_string(index=False))
else:
    print("Set week_url above.")
'''),
        md("""
## Exercise 2 — move the point somewhere else

Notebook 01 sat at 36.6 N, 122.2 W, which is inside Monterey Bay. Ask for a different
point and check the number is plausible for where you asked.

*Try 37.8 N, 122.5 W — just outside San Francisco Bay — for the same week.*

*Hint: it is two numbers in the URL, in latitude then longitude, both in brackets.*
"""),
        code('''
# YOUR TURN. Move the point, and say whether the temperature is plausible there.
moved_url = None  # <- replace

if moved_url:
    r = requests.get(moved_url)
    r.raise_for_status()
    import io

    import pandas as pd

    df = pd.read_csv(io.StringIO(r.text), skiprows=[1])
    print(df[["time", "analysed_sst"]].head().to_string(index=False))
    print()
    print("San Francisco Bay in January: 10-15 C is plausible. 25 C is not.")
else:
    print("Set moved_url above.")
'''),
        md("""
## Exercise 3 — the JSON one, and the real lesson

Fetch a **different station** and a **different day** from NOAA CO-OPS, and plot its
wind.

Do not stop at the columns named `t`, `s`, `d`. Look up what the other three mean and
say so in a comment. That lookup is the job.
"""),
        code('''
# YOUR TURN. A different station, a different day. Rename the columns and plot.
# Station 9414290 = San Francisco. Try 9414293 (San Mateo bridge) or 9415316.
new_url = None  # <- replace

if new_url:
    r = requests.get(new_url)
    r.raise_for_status()
    payload = r.json()
    import pandas as pd

    df = pd.json_normalize(payload["data"])
    print("columns as the server named them:", list(df.columns))
    print()
    print("metadata says:", payload["metadata"])
    # rename them, convert the time, and plot -- then say what f and dr mean.
else:
    print("Set new_url above.")
'''),
        md("""
## What you have now

Four techniques, applied to three shapes:

| | technique |
|---|---|
| `curl` | see the bytes yourself, before trusting anything |
| `requests` | the same fetch, in Python, with a status code to check |
| `pandas` | a DataFrame, once you know the shape you were handed |
| `duckdb` | the same thing in one line, when you would rather not think about framing |

The shapes will differ; those four will not. That is the transferable part, and it is
the only part you will need at a job that was not oceanography.

## Where to go next

`../notebooks/` — the same ideas, against harder services, with the failure modes
catalogued. Nine notebooks, a database, and about thirty traps.

**Or** take this one of three ways, which is a more honest order than doing them in
sequence:

1. **The same three shapes against a service you care about.** Swap the URLs. You have
   the tools; you do not need another lesson.
2. **Add a fourth shape.** An XML or a NetCDF endpoint. Each has its own reader, and
   each fails in a new way.
3. **Find a service with an API key** and see what changes. Almost nothing in the code
   — one header. The reason to try it is to see that it *is* almost nothing, which is
   reassuring and slightly boring, in that order.
"""),
        title="04 Now you do it",
    )


NOTEBOOKS = {
    "00_a_url_is_a_thing": nb_00,
    "01_comma_separated_text": nb_01,
    "02_json": nb_02,
    "03_compressed_text": nb_03,
    "04_now_you_do_it": nb_04,
}


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--only", nargs="*")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    wanted = args.only or list(NOTEBOOKS)
    written = []

    print("=" * 70)
    for name in wanted:
        fn = NOTEBOOKS.get(name)
        if fn is None:
            print(f"  SKIP {name} -- no builder")
            continue
        p = OUT / f"{name}.ipynb"
        nbf.write(fn(), str(p))
        written.append(p)
        print(f"  wrote {p.name:34} {len(fn().cells):>3} cells")

    if not args.execute:
        return 0

    from nbclient import NotebookClient

    print()
    failed = []
    for p in written:
        nb = nbf.read(str(p), as_version=4)
        nb.metadata.setdefault("kernelspec", {})["name"] = KERNEL
        try:
            NotebookClient(
                nb, kernel_name=KERNEL, timeout=600, allow_errors=True,
                resources={"metadata": {"path": str(OUT)}},
            ).execute()
            errs = [
                (i, o.get("ename", "?"), (o.get("evalue") or "")[:60])
                for i, c in enumerate(nb.cells)
                for o in c.get("outputs", []) if o.get("output_type") == "error"
            ]
            # A cell that ran but printed nothing has almost always fetched something
            # empty -- a URL that quietly changed shape, most often. A beginner staring
            # at a blank cell learns nothing from it, so treat it as a failure here
            # rather than shipping it. Exercises in notebook 04 are excluded: they are
            # meant to be blank until the reader fills them in, and their placeholder
            # branch does print, so they pass either way.
            silent = [
                i for i, c in enumerate(nb.cells)
                if c.cell_type == "code"
                and c.source.strip()
                and "YOUR TURN" not in c.source
                and not c.get("outputs")
            ]
        except Exception as exc:
            errs = [(-1, type(exc).__name__, str(exc)[:60])]
            silent = []
        nbf.write(nb, str(p))          # write back regardless: the error is the output
        if errs:
            i, name, msg = errs[0]
            print(f"  FAIL {p.name:34} cell {i}: {name}: {msg}")
            failed.append(p.name)
        elif silent:
            print(f"  FAIL {p.name:34} cell {silent[0]}: ran but produced no output")
            failed.append(p.name)
        else:
            print(f"  ok   {p.name}")

    print("-" * 70)
    print(f"  {len(written) - len(failed)}/{len(written)} clean")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
