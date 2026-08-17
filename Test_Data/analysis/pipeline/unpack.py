"""Read the extracted `.csv.gz` files without decompressing by hand.

Two modes:

    python -m pipeline.unpack                       # unpack ALL -> extracted_csv/
    python -m pipeline.unpack --unit R3_5G_A        # unpack one run's files
    python -m pipeline.unpack --peek R3_5G_A ue     # print to the terminal
    python -m pipeline.unpack --peek R3_5G_A ue --cols ts,pusch_snr_db,last_phr_db

`extracted_csv/` is a throwaway convenience copy for opening in Excel or VS
Code; it is regenerated on demand and is not the durable artefact. The
compressed tree stays the source of truth (809 KB versus ~9 MB unpacked).
"""
from __future__ import annotations

import argparse
import csv
import gzip
import shutil
import sys

from . import paths

PLAIN = paths.ANALYSIS / "extracted_csv"

# short aliases so you can type `ue` instead of `metrics_ue.csv.gz`
ALIASES = {
    "ue": "metrics_ue.csv.gz",
    "cell": "metrics_cell.csv.gz",
    "mac": "metrics_mac.csv.gz",
    "events": "events.csv.gz",
    "mod": "mod_series.csv.gz",
}


def resolve(unit_id, which):
    name = ALIASES.get(which, which)
    if not name.endswith(".csv.gz"):
        name += ".csv.gz"
    p = paths.EXTRACTED / unit_id / name
    if not p.exists():
        sys.exit(f"no such file: {p}\n"
                 f"available: {', '.join(sorted(ALIASES))}")
    return p


def unpack(unit_ids=None):
    n = 0
    for d in sorted(paths.EXTRACTED.iterdir()):
        if not d.is_dir() or (unit_ids and d.name not in unit_ids):
            continue
        out = PLAIN / d.name
        out.mkdir(parents=True, exist_ok=True)
        for f in sorted(d.iterdir()):
            if f.suffix == ".gz":
                with gzip.open(f, "rb") as a, open(out / f.stem, "wb") as b:
                    shutil.copyfileobj(a, b)
            else:
                shutil.copy2(f, out / f.name)          # census.json, phy_summary.json
            n += 1
    print(f"unpacked {n} files -> {PLAIN}")
    return 0


def peek(unit_id, which, limit, cols):
    p = resolve(unit_id, which)
    with gzip.open(p, "rt", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        print(f"{p.name}: empty")
        return 0
    keep = [c for c in (cols.split(",") if cols else rows[0].keys()) if c in rows[0]]
    if cols and not keep:
        sys.exit(f"none of those columns exist. available:\n  " +
                 "\n  ".join(rows[0].keys()))
    show = rows[:limit]
    w = {c: max(len(c), *(len(str(r.get(c, ""))) for r in show)) for c in keep}
    print(f"# {p}  ({len(rows)} rows, {len(rows[0])} columns)")
    print("  ".join(c.ljust(w[c]) for c in keep))
    print("  ".join("-" * w[c] for c in keep))
    for r in show:
        print("  ".join(str(r.get(c, "")).ljust(w[c]) for c in keep))
    if len(rows) > limit:
        print(f"... {len(rows)-limit} more rows (use --head N)")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--unit", action="append", dest="units",
                    help="only this log unit (repeatable)")
    ap.add_argument("--peek", nargs=2, metavar=("UNIT", "WHICH"),
                    help="print to terminal instead of unpacking")
    ap.add_argument("--head", type=int, default=15)
    ap.add_argument("--cols", help="comma-separated subset of columns")
    ap.add_argument("--list", action="store_true", help="list available log units")
    a = ap.parse_args(argv)

    if a.list:
        for d in sorted(paths.EXTRACTED.iterdir()):
            if d.is_dir():
                print(" ", d.name)
        return 0
    if a.peek:
        return peek(a.peek[0], a.peek[1], a.head, a.cols)
    return unpack(set(a.units) if a.units else None)


if __name__ == "__main__":
    raise SystemExit(main())
