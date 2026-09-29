---
name: ocean-workshop-tiers
description: >-
  Specification and generation contract for the three ocean data workshop tiers in this
  repository (Workshop Intro, Workshop Intermediate, Workshop Advanced). Use this skill
  whenever the work touches a workshop notebook or tier: adding, editing, reviewing,
  reordering or deleting a notebook; deciding what belongs in which tier; adding a data
  source, access pattern or trap; wiring a notebook into the build or into CI; or
  debugging a notebook that will not execute, a silent cell, or a red CI job. Also use
  it when asked to "add a notebook", "teach X", "make the workshop simpler or harder",
  or "add a dataset", since those all change a tier's syllabus. Covers per-tier
  syllabi, the generate-don't-hand-edit rule, the isolation each tier must keep, and
  the empirically verified gotchas for every data source.
---

# Ocean workshop tiers

This repository teaches data retrieval in three tiers. Each tier is a self-contained
set of notebooks with its own entry point, its own dependencies, and its own
assumptions about the reader.

| tier | directory | built? | reader has… | time |
|---|---|---|---|---|
| **Workshop Intro** | `beginners/` | yes | used pandas, never fetched a URL | ~40 min |
| **Workshop Intermediate** | — | **no, not yet** | fetched a URL, no DB experience | target ~2 h |
| **Workshop Advanced** | `notebooks/` | yes | comfortable with APIs and pandas | ~2 h 40 |

The tiers are **not** a difficulty gradient within one course. They are separate
courses that happen to share a subject. A reader should be able to take Intro and
never open Advanced, and neither tier may import from the other.

Read the reference file for whichever tier you are working in:

- `references/intro.md` — the five existing Intro notebooks, cell by cell
- `references/intermediate.md` — the proposed bridge syllabus, **not yet built**
- `references/advanced.md` — the ten existing Advanced notebooks and their infra
- `references/gotchas.md` — verified behaviour of every data source, and the CI traps

## The rule that outranks everything else

**Notebooks are generated. Never hand-edit a `.ipynb`.**

Every notebook in this repo is rendered from Python and re-executed with its output
committed, so a reader gets correct answers without running anything. Hand-editing an
`.ipynb` means your change is silently reverted by the next build.

| tier | builders | driver |
|---|---|---|
| Intro | `scripts/build_beginners.py` (self-contained) | `make beginners` |
| Advanced | `scripts/workshop_notebooks.py` → `scripts/build_notebooks.py` | `make notebook` |

To change a notebook, change the builder, then rebuild. If you edit a `.ipynb` and a
later build reverts it, that is this rule working as intended, not a bug.

A past attempt to auto-annotate notebook cell dependencies corrupted seven of ten
Advanced notebooks, twice, from a wrong cell-index mapping. The file was deleted. If
you write a tool that rewrites notebooks programmatically, prove it on a throwaway
copy first.

## Before you add anything, answer these four questions

1. **Which tier?** If you cannot say, it is Intermediate — that is what it is for.
   Do not put a new concept in Advanced that Intro has not covered, and do not put
   infrastructure in Intro that Intro exists to avoid.
2. **Does the reader need infrastructure to see the idea?** If yes, it is not Intro.
3. **Can it fail silently?** If yes, it needs a trap cell *after* a working example.
4. **What verifies it?** A notebook nobody checks is a blog post.

## The design rules these tiers were built on

These came out of the original feedback that the workshop was "overly complicated".
Read them as constraints, not suggestions.

**Get it working first, then break it honestly.** Every Intro notebook completes a
real fetch before showing what quietly went wrong. The original workshop led with its
traps, which made them look like obstacles rather than the actual subject. A reader who
has seen the working version understands *what* the trap cost them; a reader who sees
only the trap has no baseline to measure it against.

**Traps are real, and they are a reference, not the spine.** The Advanced trap table
has 36 entries and lives in one notebook at the end. If a trap is interesting enough
to be its own lesson, it belongs in the body of a tier as a working example followed
by the failure — not in a list the reader is asked to memorise.

**Say what the tool cannot do.** The most useful moment in Intro is DuckDB *refusing*
the space-padded NDBC file because it cannot sniff the delimiter, followed by the
explanation that forcing it means writing eighteen column names by hand and is now
longer than the pandas it replaced. Tools save mechanics, not judgement, and a
workshop that only advertises the happy path teaches the wrong lesson.

**Never teach a workaround as if it were the API.** Where this repo works around a
host pathology (see `references/gotchas.md` on the ERDDAP IPv6 record), the workaround
lives in the build script. The notebook keeps plain `requests.get(url)`. A reader's own
network is their own to diagnose, and a workshop that reads like a pile of workarounds
is the exact thing these tiers exist to stop being.

**Check the status code, look at the raw text, and question a plausible number.** These
three habits are the transferable content. Shapes, endpoints and column names change;
the habit of looking at `r.text[:200]` before trusting a parse does not.

**Never assert on a value the reader can eyeball.** Plausibility checks beat equality
in teaching material, and they are more honest about what is actually known.

## What each tier must keep

### Workshop Intro — isolation is the feature

`beginners/requirements.txt` is a **complete** dependency list: `requests`, `pandas`,
`duckdb`, `matplotlib`, `jupyterlab`. Nothing else.

The `workshop intro` CI job installs *only* that file and runs the tier in a bare
venv. That job is the mechanism, not a formality: if Intro ever imports anything from
`src/ocean_data_workshop`, from `probes/`, or from the root `pyproject.toml`, it
fails. Keep it that way. When you need a helper the root already has, duplicate it
into the Intro builder with a comment saying why, and keep the copy stdlib-only.

Intro also has no database, no Docker, no `make`, no `.env`, no prefetch, no accounts
and no API keys — nothing may stand between the reader and a first `requests.get`.

### Workshop Advanced — assumes the reader can already fetch

Advanced may assume `requests`, `pandas` and a database. It may use
`notebooks/_fetch.py` and `notebooks/_sources.py`, which give it a caching session and
a single source manifest. What it must not do is *teach* caching as the first idea.

The database exists to teach SQL and time-series aggregation. The capstone join is
trivially easy in pandas, and that is fine — the point is the SQL, not the join.

## Verification, and why it is shaped like this

**A clean-clone install is the highest-value check in this repository.** It has found
a compose project-name mismatch between `up` and `exec`, a CI DSN set per-step where it
needed to be per-job, and a 325 MB default download — none of which were visible
locally, because a local environment already had all three right.

- `make fresh` — clean-clone install, ~40 s from an empty `data/`
- `make test` — lint, unit tests, and offline notebook execution
- `make beginners` — rebuild and execute the Intro tier

Notebooks are committed **with output**, and the build fails on an unhandled cell
error *and* on a cell that ran but printed nothing. A blank cell in a first API lesson
teaches nothing, and a cell that fetched an empty response usually means a URL changed
shape upstream. Exercises a reader is meant to fill in are exempt, since they are
blank on purpose.

CI has five jobs: lint, unit tests, notebooks offline (checksum-guarded, no network),
integration against TimescaleDB, and `workshop intro` — which installs only
`beginners/requirements.txt` and runs that tier in a bare venv. Offline by default is
deliberate: a public data service being briefly unreachable should not be able to
block a merge.

A new tier gets a CI job, and that job is how the tier's constraints stay true.

## Adding a notebook: the actual steps

1. Decide the tier. If it needs a database, credentials, or netCDF, it is not Intro.
2. Write the builder function in that tier's builder file. Write the URLs out in
   full, in the notebook, rather than importing them from a module — a reader should be
   able to read the address that produced the data in front of them.
3. Verify the source by hand **before** writing prose about it. Every trap in this
   repo was found by fetching, not by reading documentation. See
   `references/gotchas.md` for what has already been established.
4. Build and execute. Fix what breaks. Expect the shape to differ from what you
   assumed — it usually does.
5. Confirm the committed output is real: a table with plausible values, not a shape
   tuple and an error.
6. Re-run the gates, then `make fresh` if you touched anything structural.
7. Update the tier's README and the table at the top of the root `README.md`.

## Cross-references

- `CONTRIBUTING.md` — the generate-don't-hand-edit rule, from a contributor's view
- `probes/VERDICTS.md` — the original source-access audit; most traps originate here
- `learning/schema.sql` — the database schema, source of truth for Advanced
- `/Users/dev/.opencode/plan/data-retrieval-workshop.md` — original plan and clean-room
  findings
