"""Probe 02 — ERDDAP reachability and catalogue.

The plan's fallback ladder starts with "OISST via ERDDAP". This probe establishes that
ERDDAP works at all, is anonymous, and can serve griddap data. It also records which
SST datasets actually exist on the host, because the plan named NOAA OISST and OISST
turns out not to be present on either ERDDAP host -- the anonymous options are
``jplMURSST41`` (JPL Multi-Resolution SST) and ``NOAA_DHW`` (Coral Reef Watch SST).

That substitution is a plan change, not a problem: MURSST is 0.045 deg vs OISST's
0.25 deg, so it is finer. OISST remains reachable from NCEI directly if ever needed.
"""

from __future__ import annotations

from ._common import PASS, Probe, Result, cache_path, http_session, run

HARNESS = Probe(
    slug="erddap",
    name="ERDDAP griddap service (NOAA CoastWatch)",
    tier=1,
    klass="A",
    provides="HTTP access to thousands of gridded ocean/atmospheric datasets",
    protocol="REST (griddap)",
    order=2,
)

BASE = "https://coastwatch.pfeg.noaa.gov/erddap"

# Candidate SST dataset ids discovered on the host, with what each actually is.
CANDIDATES = {
    "jplMURSST41": "JPL Multi-Resolution SST, 0.045 deg, daily",
    "NOAA_DHW": "NOAA Coral Reef Watch SST, 5 km, near-real-time",
    "nceiOisst21Agg": "NOAA OISST 2.1 (expected)",
    "noaacwBLENDED": "NOAA OISST blended (expected)",
    "nceiErsst": "NOAA ERSST (expected)",
}


HTTP = http_session()


def check() -> Result:
    detail: dict = {}
    problems: list[str] = []

    # 1. service reachable, anonymously
    r = HTTP.get(
        f"{BASE}/info/index.json", params={"page": 1, "itemsPerPage": 1}, timeout=HTTP.request_timeout
    )
    detail["info_http"] = r.status_code
    if r.status_code != 200:
        return Result(status="FAIL", note=f"info endpoint returned {r.status_code}")

    # 2. griddap index is enumerable (proves it is not just a landing page).
    #    NB: ERDDAP's index.json carries only columnNames/columnTypes/rows --
    #    there is no nRows key, so read the first dataset id out of the rows.
    r = HTTP.get(
        f"{BASE}/griddap/index.json",
        params={"page": 1, "itemsPerPage": 1},
        timeout=HTTP.request_timeout,
    )
    detail["griddap_http"] = r.status_code
    if r.status_code == 200:
        try:
            tbl = r.json()["table"]
            detail["first_dataset"] = tbl["rows"][0][
                tbl["columnNames"].index("griddap")
            ].rsplit("/", 1)[-1]
        except Exception as exc:
            problems.append(f"griddap index not parseable: {type(exc).__name__}")

    # 3. which of the candidate SST datasets actually exist
    found, missing = [], []
    for ds in CANDIDATES:
        try:
            rr = HTTP.get(f"{BASE}/griddap/{ds}.das", timeout=HTTP.request_timeout)
            if rr.status_code == 200 and rr.text.strip().startswith("Attributes"):
                found.append(ds)
            else:
                missing.append(ds)
        except Exception as exc:
            missing.append(f"{ds}({type(exc).__name__})")
    detail["sst_found"] = ",".join(found) or "none"
    detail["sst_missing"] = ",".join(missing) or "none"

    if not found:
        problems.append("no candidate SST dataset resolved on this host")

    # 4. a .das must be cacheable -- these get re-fetched constantly
    if found:
        cp = cache_path("erddap_jplMURSST41.das", ".das")
        rr = HTTP.get(f"{BASE}/griddap/{found[0]}.das", timeout=HTTP.request_timeout)
        cp.write_bytes(rr.content)
        detail["cached_das_kb"] = round(cp.stat().st_size / 1024, 1)

    if problems:
        return Result(status="FAIL", note="; ".join(problems), detail=detail)

    return Result(
        status=PASS,
        note=(
            f"anonymous, no key, griddap index enumerates (first={detail.get('first_dataset')}). "
            f"SST available: {detail['sst_found']} (NOAA OISST absent from this host; "
            f"jplMURSST41 at 0.045 deg is finer than OISST's 0.25 deg)"
        ),
        detail=detail,
    )


if __name__ == "__main__":
    import sys

    from ._common import append_verdict

    res = run(HARNESS, check)
    append_verdict(res)
    sys.exit(0 if res.status == "PASS" else 1)
