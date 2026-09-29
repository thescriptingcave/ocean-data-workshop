import pathlib

p = pathlib.Path("scripts/workshop_notebooks.py")
s = p.read_text()

anchor = '''        md("""
## 5. Traps so far'''
assert anchor in s, "traps anchor not found"

new_section = '''        md("""
## 4b. Getting a response *into* a DataFrame

Everything so far has produced a `requests.Response`. A response is not a DataFrame, and
this step is where most of the real mistakes happen — not in the request.

Four attributes carry the payload, and which one you need is decided by the format:

| attribute | what it is | use it for |
|---|---|---|
| `r.text` | body decoded to `str` | JSON, CSV, HTML — anything human-readable |
| `r.content` | body as `bytes`, untouched | binary: netCDF, gzip, images |
| `r.json()` | body parsed as JSON | any JSON API |
| `r.headers` / `r.status_code` / `r.ok` | metadata | checks before you trust the body |

`pandas` reads a **file-like object**, not a string and not a response. So you need one
thin adapter, and which one depends on whether you have text or bytes.
"""),
        code("""
# 1. JSON -> DataFrame. The easy case: r.json() gives you Python objects.
gcs = http.get(S.GCS_API, params=S.gcs_list_params(
    f"sanctsound/products/sound_level_metrics/{S.NCEI_SITE}/", "/", 200))
body = gcs.json()                      # a dict
print("  top-level keys:", list(body))

rows = pd.DataFrame(body["items"])    # dict of lists -> DataFrame
print("  DataFrame shape:", rows.shape)
print("  columns:", list(rows.columns))
print()
print("  pd.DataFrame(...) works when the JSON is a dict of equal-length lists.")
print("  For nested JSON, use pd.json_normalize(body) instead -- that flattens")
print("  one level, which is what almost every listing API actually returns.")
'''),
        code("""
# 2. Text -> DataFrame. You need a file-like object, so wrap the string.
import io

df = pd.read_csv(io.StringIO(http.get(URL).text), skiprows=[1])
print("  from r.text   ->", df.shape, list(df.columns))

# 3. Bytes -> DataFrame. BytesIO, not StringIO -- the reverse silently mangles data.
csv_bytes = http.get(S.sst_csv()).content
df2 = pd.read_csv(io.BytesIO(csv_bytes), skiprows=[1])
print("  from r.content->", df2.shape, "  identical:", df.equals(df2))
"""),
        code("""
# 4. Binary -> xarray. Some formats have no text form at all, so this is the only route.
nc_bytes = http.get(S.sst_nc()).content
path = Path.cwd() / "_from_bytes.nc"
path.write_bytes(nc_bytes)            # xarray needs a seekable file, so write it out
ds = xr.open_dataset(path)
print("  netCDF via r.content ->", dict(ds.sizes))

# Why the round-trip: xarray can read a BytesIO directly, but many netCDF engines want
# a real path or a seekable stream. Writing 134 KB to disk is cheap and always works.
ds2 = xr.open_dataset(io.BytesIO(nc_bytes))
print("  BytesIO works too  ->", dict(ds2.sizes))
"""),
        code("""
# 5. Gzipped text is the trap in this section. NDBC serves .txt.gz.
gz = http.get(S.ndbc_url())
print("  r.content type :", type(gz.content).__name__, len(gz.content), "bytes")
print("  r.text   type  :", type(gz.text).__name__, len(gz.text), "chars")
print()
print("  r.text DECODES the gzip bytes as if they were plain text. It does not")
print("  decompress. You get mojibake, and pd.read_csv on it produces nonsense")
print("  with no error at all. So for .gz you must use r.content + gzip:")
import gzip

text = gzip.decompress(gz.content).decode()
lines = text.splitlines()
print("  after gzip.decompress:", len(lines), "lines, header:", lines[0][:56])
"""),
        md("""
### The rule, in one line

**`r.text` for anything the server describes as text. `r.content` for everything else,
and always check `Content-Type` when you are unsure.**

```python
r = http.get(url)

r.raise_for_status()            # before you trust any of it
if "json" in r.headers.get("Content-Type", ""):
    df = pd.json_normalize(r.json())
elif "csv" in r.headers.get("Content-Type", ""):
    df = pd.read_csv(io.StringIO(r.text))
else:
    Path("payload.bin").write_bytes(r.content)   # netCDF, gzip, ...
```

`r.raise_for_status()` first, always. A 500 with a JSON error body is not JSON, and
`r.json()` on it raises a `JSONDecodeError` that tells you nothing — you have to check
the status to see the message the server actually sent.

### And there is no magic in the session

`_fetch.session()` returns an ordinary `requests.Session`. It overrides one method,
`send`, and that is the entire cache. You could write the same code yourself:

```python
import requests
r = requests.get(url, timeout=(10, 120))     # the whole of it
```

The session adds exactly two things: it forces IPv4 (Notebook 01, trap 6), and it falls
back to a cached response when the network fails. Everything else you saw above —
`.get`, `params=`, `.text`, `.content`, `.json()`, `.status_code`, `.raise_for_status()`,
`.headers` — is `requests`, and it is the same in your own project.
"""),
        code("""
# Proof: the session is a requests.Session, and a plain request still works.
import requests

print("  type(http)       :", type(http).__name__)
print("  isinstance of Session:", isinstance(http, requests.Session))
print("  overridden methods   :", [m for m in ("get", "post", "send", "request")
                                    if m in vars(type(http))])
print()
print("  http is a requests.Session with ONE method overridden (send).")
print("  requests.get() is unchanged and still available when you want it.")
"""),

'''

s = s.replace(anchor, new_section + anchor, 1)
p.write_text(s)
print("inserted the response -> DataFrame section into notebook 01")
