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

    # Write the generated inventory from *all* recorded results, not just the ones that
    # ran this invocation. Otherwise `--only foo` silently truncates INVENTORY.md to a
    # single row, which is exactly the bug that made this file briefly wrong.
    recorded: dict[str, dict] = {}
    rj = PROJECT / "probes" / "RESULTS.jsonl"
    if rj.exists():
        for ln in rj.read_text().splitlines():
            if ln.strip():
                d = json.loads(ln)
                recorded[d["slug"]] = d  # later lines win

    lines = [INVENTORY_HEADER]
    npass = ntotal = 0
    for modname in PROBE_MODULES:
        mod = importlib.import_module(f"probes.{modname}")
        h = mod.HARNESS
        if h.slug not in recorded:
            continue
        d = recorded[h.slug]
        npass += d["status"] == "PASS"
        ntotal += 1
        lines.append(
            f"| {MARK[d['status']]} | **{h.slug}** — {h.name} | {h.klass} | "
            f"{h.provides} | {d['status']} in {d['seconds']:.1f}s |\n"
        )
    lines.append(f"\n**{npass}/{ntotal} passing.**\n")

    out = PROJECT / "probes" / "INVENTORY.md"
    out.write_text("".join(lines))
    scope = "" if not wanted else f" (ran {len(results)} of {ntotal})"
    print(f"\nwrote {out.relative_to(PROJECT)}  ({npass}/{ntotal} passing){scope}")

    (PROJECT / "probes" / "LATEST.json").write_text(
        json.dumps(recorded, indent=2, sort_keys=True) + "\n"
    )

    # Exit non-zero only if something we actually ran failed.
    ran_failed = [r for r in results if r.status != "PASS"]
    return 1 if ran_failed else 0


if __name__ == "__main__":
    sys.exit(main())
