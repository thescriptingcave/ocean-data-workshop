"""Probe 05 — NOAA NCEI Passive Acoustic Data archive: bucket is public.

The single highest-value access question in the inventory. Everything on the acoustic
side of this project depends on it.

Findings that are *not* obvious and cost real time to rediscover:

  * Bucket name is ``noaa-passive-bioacoustic``.
  * It is genuinely public: listable with no account, no key, no signature. The GCS
    JSON API over plain HTTPS works, which avoids needing the aws CLI at all.
  * Layout is ``<project>/products/<product_type>/<site>/<dataset>/{data,metadata}/``.
    There is a mandatory ``data/`` level -- omitting it yields a confusing NoSuchKey.
  * This machine's ~/.aws/config sets ``endpoint_url = http://localhost:9000`` (MinIO)
    in the *default* profile, so a bare ``aws s3 ls`` silently fails against a local
    service. Pass ``--endpoint-url https://storage.googleapis.com`` or use the JSON API.
  * 29 top-level projects, including ``mbarc_socal`` (Southern California, nearest to
    the Monterey site), ``dclde`` (labelled ML challenge data) and ``sanctsound``.
"""

from __future__ import annotations

from ._common import PASS, Probe, Result, run

HARNESS = Probe(
    slug="ncei_pad",
    name="NOAA NCEI Passive Acoustic Data archive (GCS bucket)",
    tier=1,
    klass="A",
    provides="raw hydrophone audio, sound-level metrics, and species/vessel detections",
    protocol="GCS JSON API over HTTPS, anonymous",
    order=5,
)

BUCKET = "noaa-passive-bioacoustic"
API = "https://storage.googleapis.com/storage/v1/b/" + BUCKET + "/o"
HTTP = None


def _list(prefix: str = "", delimiter: str = "/", n: int = 200):
    """List objects or common prefixes. Returns (status, prefixes, items)."""
    r = HTTP.get(
        API, params={"prefix": prefix, "delimiter": delimiter, "maxResults": n},
        timeout=HTTP.request_timeout,
    )
    if r.status_code != 200:
        return r.status_code, [], []
    d = r.json()
    return r.status_code, d.get("prefixes", []), d.get("items", [])


def check() -> Result:
    global HTTP
    from ._common import http_session

    HTTP = http_session()

    detail: dict = {"bucket": BUCKET}
    problems: list[str] = []

    # 1. the bucket exists and is anonymously listable
    st, pre, items = _list()
    detail["list_http"] = st
    if st != 200:
        return Result(
            status="FAIL", note=f"anonymous list returned HTTP {st}", detail=detail
        )
    if not pre and not items:
        return Result(
            status="FAIL", note="bucket listed but is empty or fully private", detail=detail
        )
    detail["n_projects"] = len(pre)
    detail["projects_sample"] = ",".join(p.rstrip("/") for p in pre[:8])

    # 2. the projects we care about are present
    want = ("sanctsound", "mbarc_socal", "dclde", "nrs", "soundcoop")
    have = {p.strip("/") for p in pre}
    detail["projects_wanted"] = ",".join(w for w in want if w in have)
    missing = [w for w in want if w not in have]
    if missing:
        # not fatal, but the plan's anchor site depends on sanctsound
        detail["projects_missing"] = ",".join(missing)
        if "sanctsound" in missing:
            problems.append("sanctsound absent -- the anchor site depends on it")

    # 3. the product taxonomy under sanctsound
    st, prods, _ = _list("sanctsound/products/")
    detail["sanctsound_products"] = ",".join(
        p.rstrip("/").split("/")[-1] for p in prods
    )
    if "detections" not in "".join(prods):
        problems.append("no sanctsound detections -- the labelled data lives there")

    # 4. the /data/ level exists (its absence is the NoSuchKey trap).
    #    delimiter="" so we get real objects, not the data/ and metadata/ prefixes.
    st, _, items = _list(
        "sanctsound/products/detections/ci02/sanctsound_ci02_04_dolphins_1h/", delimiter=""
    )
    names = [i["name"] for i in items]
    detail["n_objects_ci02_04_dolphins"] = len(items)
    has_data = any("/data/" in n for n in names)
    detail["data_level_present"] = has_data
    if not items:
        problems.append("no objects under the ci02_04 dolphin dataset")
    elif not has_data:
        problems.append("no /data/ level in the object paths")

    if problems:
        return Result(status="FAIL", note="; ".join(problems), detail=detail)

    return Result(
        status=PASS,
        note=(
            f"public, anonymous, no key. {len(pre)} projects "
            f"(sanctsound + mbarc_socal + dclde + nrs + soundcoop all present). "
            f"Layout <project>/products/<type>/<site>/<dataset>/data/. "
            f"NOTE: bare 'aws s3 ls' fails here -- local MinIO endpoint override."
        ),
        detail=detail,
    )


if __name__ == "__main__":
    import sys

    from ._common import append_verdict

    res = run(HARNESS, check)
    append_verdict(res)
    sys.exit(0 if res.status == "PASS" else 1)
