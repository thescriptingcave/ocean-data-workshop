"""Run every probe, dedupe by slug, and regenerate probes/INVENTORY.md.

    uv run python -m probes.run_all
    uv run python -m probes.run_all --only ncei_pad,argo_gdac

RESULTS.jsonl is append-only and therefore contains the whole iteration history,
including failures that have since been fixed. The table below keeps only the most
recent result per slug -- that is the one that reflects current code.
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys

from ._common import PROJECT, Result, run

PROBE_MODULES = [
    "probe_01_gsw",
    "probe_02_erddap",
    "probe_03_sst",
    "probe_04_toolchain",
    "probe_05_ncei_pad",
    "probe_06_ncei_labels",
    "probe_07_argo",
    "probe_08_glorys",
    "probe_09_metadata",
    "probe_10_ndbc_wind",
]

MARK = {"PASS": "[x]", "FAIL": "[ ]", "WARN": "[~]"}

INVENTORY_HEADER = """# Data Access Inventory

**GENERATED** by `uv run python -m probes.run_all` -- do not hand-edit.
Shows the most recent result per probe. Written verdicts live in `VERDICTS.md`.

Access classes: **A** anonymous HTTP · **B** anonymous, other protocol ·
**C** free account + password · **D** account + API key · **E** terms/approval ·
**F** manual request · **G** licensed · **H** unavailable

| | probe | class | provides | verdict |
|---|---|---|---|---|
"""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="comma-separated slugs to run")
    args = ap.parse_args(argv)

    wanted = set(args.only.split(",")) if args.only else None

    results: list[Result] = []
    for modname in PROBE_MODULES:
        mod = importlib.import_module(f"probes.{modname}")
        if wanted and mod.HARNESS.slug not in wanted:
            continue
        res = run(mod.HARNESS, mod.check)
        from ._common import append_verdict

        append_verdict(res)
        results.append(res)

    # write the generated inventory
    lines = [INVENTORY_HEADER]
    npass = 0
    for modname in PROBE_MODULES:
        mod = importlib.import_module(f"probes.{modname}")
        h = mod.HARNESS
        r = next((x for x in results if x.slug == h.slug), None)
        if r is None:
            continue
        npass += r.status == "PASS"
        lines.append(
            f"| {MARK[r.status]} | **{h.slug}** — {h.name} | {h.klass} | "
            f"{h.provides} | {r.status} in {r.seconds:.1f}s |"
        )
    total = len(results)
    lines.append(f"\n**{npass}/{total} passing.**\n")

    out = PROJECT / "probes" / "INVENTORY.md"
    out.write_text("".join(lines))
    print(f"\nwrote {out.relative_to(PROJECT)}  ({npass}/{total} passing)")

    # also refresh the machine-readable latest-per-slug view
    latest = {}
    rj = PROJECT / "probes" / "RESULTS.jsonl"
    if rj.exists():
        for ln in rj.read_text().splitlines():
            if ln.strip():
                d = json.loads(ln)
                latest[d["slug"]] = d
    (PROJECT / "probes" / "LATEST.json").write_text(
        json.dumps(latest, indent=2, sort_keys=True) + "\n"
    )

    return 0 if npass == total else 1


if __name__ == "__main__":
    sys.exit(main())
