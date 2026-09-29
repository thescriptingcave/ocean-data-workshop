# Workshop Intermediate — proposed, NOT YET BUILT

**Status: specification only.** Nothing in this file exists. There is no
`intermediate/` directory, no builder, and no CI job. Treat it as a syllabus to
implement or to argue with, not as documentation of something shipped.

The intent is a **bridge**: everything between Intro's three simple shapes and
Advanced's database. It assumes the reader has fetched a URL and used pandas, and it
deliberately has **no database**.

## Why this tier exists

Right now the jump from Intro to Advanced is a cliff, and it is worth being precise
about the shape of it:

- Intro ends with three text shapes and five dependencies.
- Advanced opens with a database, Docker, netCDF, object storage and credentials.

A reader who has finished Intro and wants "a bit more" has nowhere to go that does not
also require them to stand up PostgreSQL. That is a bad gap to leave, because the
things they are actually ready for — the awkward binary formats and the authenticated
services — are what Advanced uses on its very first page, before any SQL.

So Intermediate takes exactly the parts of Advanced that are about **data access**,
strips the parts that are about **infrastructure**, and teaches them in the order a
person would meet them.

## What it takes from Advanced, and what it refuses

| takes | refuses |
|---|---|
| netCDF via `xarray` | PostgreSQL / TimescaleDB |
| GCS object storage as a plain HTTP API | Docker |
| an API-key service, credentials as an env var | the cache layer (`_fetch.py`) |
| the four techniques from Intro, unchanged | ML |
| the same "get it working, then break it" arc | the 36-trap table |

The line is: **Intermediate is about reaching data that is hard to reach. Advanced is
about what to do once you have a lot of it.** Databases are a "what to do" concern.

## Proposed syllabus

Six notebooks, ~2 hours. Order matters — each one earns the next.

### `00 — You are ready for more` (5 cells)

Bridge from Intro in one page. Recap the four techniques against a single ERDDAP fetch,
then say plainly what is about to change: the data stops arriving as text you can read.

No new technique. Its job is to make the reader feel ready, which is cheap to do and
expensive to skip.

### `01 — netCDF: the file you cannot read` (16 cells)

Source: Argo GDAC profile, or GLORYS. This is the single biggest jump from Intro, and
the reason Intermediate exists.

Show the four bytes at the start of the file, explain that they are a magic number and
that everything after is binary, then open it with `xarray.open_dataset` and show that
it has named dimensions, coordinates and typed variables. The idea to land: **a
container that describes its own contents**, versus a CSV where you have to be told.

Then the real trap: lazily loaded. `.mean()` on a 2 GB dataset is instant, and only the
`.load()` pulls the bytes. A reader who does not know this will load a file into RAM
and wonder why their laptop died.

Second trap: dimension order. Transposing a dataset is one call and is not the same
thing as transposing the array you would get in numpy, because the axes are named.

### `02 — Object storage: a bucket is a list` (18 cells)

Source: a public GCS bucket, same one Advanced uses.

Teach the three primitives and nothing else: list a prefix, read object metadata,
download one object. All three are plain HTTPS `GET`s against
`storage.googleapis.com` — no client library, no SDK, no credentials. That is the
headline: object storage is an HTTP API you can hit with `curl`.

Trap: the listing is **paginated**, capped at 1000 keys and continuing with a
`pageToken`. A reader who lists once and concludes the bucket is small has silently
missed most of it. This is the same species of bug as the NDBC `>= 99` filter — a
plausible number that is wrong and raises nothing.

Also worth a paragraph: prefixes are not directories, and nothing enforces a
hierarchy. "Everything in `ocean/2019/`" is a convention you are trusting.

### `03 — Credentials: one header, and what it changes` (14 cells)

Source: any service with an API key — Copernicus Marine is the obvious one, since
Advanced uses it and the account is optional everywhere.

The framing must be that **this is nearly free**. The whole delta from an anonymous
request is an auth header. The point of the notebook is the *feel* of a 401, not the
mechanics: make a request without the credential, read the error, add the header, see
it work.

Trap: credentials belong in the environment, never in the notebook and never in git.
Show a `.env` read by `python-dotenv` and state that a key committed to a public
repository is compromised permanently, because history keeps it.

This is where the existing `src/ocean_data_workshop/credentials.py` earns its place —
with the caveat that Intermediate must not *import* it, or it stops being standalone
the way Intro is. Duplicate as with Intro, or accept the dependency deliberately and
say so in the README.

### `04 — Same data, three libraries` (14 cells)

Re-fetch a dataset Intro already used — ERDDAP SST is ideal — three ways: `requests`
plus `pandas`, `xarray`, and DuckDB. Same bytes, same numbers, three views.

This notebook is the argument for the whole tier. It is the first place the reader
sees that the *library* is a choice with a shape, not a fixed cost, and that the shape
you pick determines what the data looks like afterwards.

Pair it with the honest limit again, because it is the same lesson at a higher level:
DuckDB still cannot read netCDF (no extension exists), and `xarray` is not a database
and will not survive a dataset larger than memory. Every tool has an edge, and the
skill is knowing which edge you are near.

### `05 — Now you choose` (8 cells)

Exercises across all three new sources, plus a short decision guide:

| if the data is… | use |
|---|---|
| delimited text on one host | `requests` + `pandas`, DuckDB if it is one file |
| gridded, multi-dimensional | `xarray` |
| in a bucket, many files | list the prefix, then read what you need |
| behind a key | add a header, keep it in the environment |
| bigger than RAM | DuckDB, out of core, and stop using pandas |

Then the hand-off: **Advanced assumes all of this.** It does not reteach it. It adds a
database and SQL, and by then the reader has earned the right to care.

## Constraints it must honour if it is built

- **No database, no Docker, no `make`, no prefetch.** Same rule as Intro, for the same
  reason: nothing may stand between the reader and the data.
- **Its own `requirements.txt`**, and a CI job that installs only that file, exactly
  like `workshop intro`. The isolation check is what stops the tier quietly growing a
  dependency on `src/ocean_data_workshop`.
- **Plain `requests` where a plain request works.** Object storage in particular is
  meant to be taught with `curl`.
- **Own builder**, e.g. `scripts/build_intermediate.py`, with the silent-cell gate from
  Intro. Do not extend `build_beginners.py`; the tiers are separate courses.
- **No `_fetch.py`, no cache.** Caching is an Advanced idea and is deliberately
  postponed, because a reader who has not yet been hurt by a slow fetch does not
  understand what the cache is for.
- **Verify every source by hand before writing prose about it.** See
  `gotchas.md` for what is already established about the Argo, GCS and Copernicus
  endpoints, and for the traps that are already known to bite.

## Open questions to settle before building

1. **Does it reuse Advanced's data, or find new sources?** Reusing ERDDAP SST in
   notebook 04 argues for overlap; teaching only old sources makes it feel like a
   rerun. Probably a mix: one familiar dataset for the comparison, the rest new.
2. **Is Copernicus worth including?** It needs an account, and account setup is the
   most common reason a reader abandons a workshop. A pure key-based service with
   instant signup would teach the same lesson with less friction.
3. **How much time is honest?** Six notebooks at Intermediate's density is closer to
   three hours than two. Either cut to four notebooks or budget three.
4. **Should it be one file, or a directory per tier per the existing convention?**
   Directory, obviously — but this is a decision to make before the first builder
   exists, not after.
5. **Does the trap table grow?** It currently has 36 entries and is Advanced-only.
   Intermediate will find new ones. Decide whether they get added there (making it
   less Advanced-specific) or given their own reference.
