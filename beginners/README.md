# Beginners — your first API

Five notebooks. About 40 minutes. **No database, no Docker, no account, no API key.**

Assumes you know a bit of Python and have used pandas. Assumes you have **never
fetched a URL**.

## Start here

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r beginners/requirements.txt
jupyter lab beginners/
```

Then open `00_a_url_is_a_thing.ipynb`.

## The notebooks

| | what it is |
|---|---|
| **00** | a URL is a thing you can fetch. `curl` by hand, then the same in Python |
| **01** | comma-separated text — the four ways to get it, and the header trick |
| **02** | JSON — nested text, and column names you did not choose |
| **03** | compressed text — where `r.text` quietly gives you nothing |
| **04** | you write them |

## The shape of it

Four techniques, applied three times:

| | |
|---|---|
| `curl` | see the bytes yourself, before trusting anything |
| `requests` | the same fetch in Python, with a status code to check |
| `pandas` | a DataFrame, once you know the shape you were handed |
| `duckdb` | the same thing in one line, when you would rather not think about framing |

The three *shapes* are the variable: delimited text, JSON, compressed text. The four
*techniques* are constant, and they are the part you will use at a job that is not
oceanography.

## Rules worth keeping

1. **Check `status_code`.** `r.raise_for_status()`.
2. **Look at `r.text[:200]` before parsing.** Every strange result is a header, a
   wrapper, or an error message where you expected data.
3. **A plausible number is not a correct number.** The traps here are not exceptions.
   They are answers that look reasonable and are wrong.

## After this

`../notebooks/` — the same ideas against harder services, with a database, and about
thirty catalogued failure modes. Come back to it when this is comfortable.

Or skip it, which is a legitimate choice: take one of these instead.

- Point the URLs at a service you actually care about. You have the tools.
- Add a fourth shape — XML, or a NetCDF endpoint. Each has its own reader, and each
  fails in a new way.
- Add a service that needs an API key. Almost nothing in the code changes — one header.
  Do it to find out that it is almost nothing.
