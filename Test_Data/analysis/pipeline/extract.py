"""Stage 1 driver: stream every stack log once, in parallel.

    python -m pipeline.extract --all
    python -m pipeline.extract --unit R3_5G_A
    python -m pipeline.extract --round 3 --jobs 4

Writes `extracted/<unit_id>/` per log unit plus `extracted/index.csv`, a
one-row-per-log summary that doubles as the provenance table for the thesis
(round, location, rx_gain, TDD pattern, duration, log size, logging rate).
"""
from __future__ import annotations

import argparse
import csv
import sys
import time
from concurrent.futures import ProcessPoolExecutor

from . import paths, logscan

INDEX_COLS = [
    "unit_id", "round", "tech", "location", "distance_m", "variant",
    "rx_gain", "tx_gain", "tdd", "bandwidth_mhz",
    "ts_first", "duration_s", "log_bytes", "lines_total",
    "metrics_lines", "metrics_line_share", "rsrp_ovl_reports",
    "continuation_byte_share", "bytes_per_s", "gb_per_hour", "log",
]


def _one(unit_and_limit):
    unit, limit = unit_and_limit
    t = time.time()
    census = logscan.scan(unit, max_lines=limit)
    census["_elapsed_s"] = round(time.time() - t, 1)
    return census


def _index_row(c):
    cfg = c.get("config", {})
    row = {k: c.get(k) for k in INDEX_COLS}
    row.update(rx_gain=cfg.get("rx_gain"), tx_gain=cfg.get("tx_gain"),
               tdd=cfg.get("tdd"), bandwidth_mhz=cfg.get("bandwidth_mhz"))
    return row


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--all", action="store_true", help="every log unit")
    ap.add_argument("--round", type=int, action="append", dest="rounds")
    ap.add_argument("--unit", action="append", dest="unit_ids")
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--max-lines", type=int, default=None,
                    help="stop each log after N lines (smoke tests)")
    a = ap.parse_args(argv)

    rounds = tuple(a.rounds) if a.rounds else (1, 2, 3)
    unitl = paths.log_units(rounds)
    if a.unit_ids:
        want = set(a.unit_ids)
        unitl = [u for u in unitl if u.unit_id in want]
    if not unitl:
        print("no matching log units", file=sys.stderr)
        return 1

    total_bytes = sum(u.stack_log.stat().st_size for u in unitl)
    print(f"{len(unitl)} log units, {total_bytes/1e9:.2f} GB, {a.jobs} workers")
    paths.EXTRACTED.mkdir(parents=True, exist_ok=True)

    rows, t0 = [], time.time()
    with ProcessPoolExecutor(max_workers=a.jobs) as ex:
        for c in ex.map(_one, [(u, a.max_lines) for u in unitl]):
            rows.append(_index_row(c))
            print(f"  {c['unit_id']:16s} {c['lines_total']:>10,} lines  "
                  f"{c['metrics_lines']:>6,} metrics  "
                  f"{c['rsrp_ovl_reports']:>5,} ovl  {c['_elapsed_s']:>6.1f}s")

    # merge with any previously extracted units so a partial run keeps the index whole
    idx = paths.EXTRACTED / "index.csv"
    existing = {}
    if idx.exists():
        with open(idx, newline="", encoding="utf-8") as f:
            existing = {r["unit_id"]: r for r in csv.DictReader(f)}
    for r in rows:
        existing[r["unit_id"]] = r
    order = {u.unit_id: i for i, u in enumerate(paths.log_units())}
    with open(idx, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=INDEX_COLS, extrasaction="ignore")
        w.writeheader()
        for uid in sorted(existing, key=lambda k: order.get(k, 999)):
            w.writerow(existing[uid])

    print(f"\n{len(rows)} units in {time.time()-t0:.1f}s -> {idx}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
