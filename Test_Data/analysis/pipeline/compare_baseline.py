"""Stage 3: check the rebuilt tables against the pre-rebuild CSVs.

    python -m pipeline.compare_baseline

`analysis/data/` was produced by the 19 superseded scripts and is the source of
every number already written into FINDINGS*.md and DATA_INVENTORY.md. Those
scripts can no longer run (their data root no longer exists), so the old CSVs
are the only witness to what the campaign showed. A rebuild that silently moves
a published number is worse than no rebuild -- this compares the two and prints
what matches, what shifted, and what is newly available.

A shift is not automatically a bug: the old scripts made different aggregation
choices (which repetitions to include, sender vs receiver, ramp handling). The
point is that every difference is visible and explained rather than discovered
in a viva.
"""
from __future__ import annotations

import csv
from pathlib import Path

from . import paths

TOL = 0.02          # 2 % relative


def _read(p: Path):
    if not p.exists():
        return []
    with open(p, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _cmp(label, old, new, tol=TOL):
    if old is None and new is None:
        return ("skip", label, old, new, "")
    if old is None:
        return ("new", label, old, new, "not in baseline")
    if new is None:
        return ("lost", label, old, new, "MISSING in rebuild")
    denom = max(abs(old), 1e-9)
    rel = abs(new - old) / denom
    return ("ok" if rel <= tol else "diff", label, old, new, f"{rel*100:.1f}%")


def compare():
    res = []

    # ---- Round 1 per-test KPIs: data/summary_kpis.csv -> data_v2/reps.csv ----
    old = _read(paths.DATA_BASELINE / "summary_kpis.csv")
    new = {r["rep_id"]: r for r in _read(paths.DATA_V2 / "reps.csv")}
    # old key: tech, distance_m, protocol, direction (distance uses the legacy 5 m for B)
    legacy_d = {"2": "A", "5": "B", "10": "C"}
    for o in old:
        loc = legacy_d.get(o["distance_m"])
        rid = f"R1_{o['tech']}_{loc}_{o['protocol']}_{o['direction']}_r1"
        n = new.get(rid)
        if not n:
            res.append(("lost", f"summary_kpis {rid}", None, None, "no matching rep"))
            continue
        res.append(_cmp(f"{rid} mean_Mbps", _f(o["mean_Mbps"]), _f(n["throughput_Mbps"])))
        res.append(_cmp(f"{rid} ul_snr", _f(o["ul_snr"]), _f(n["pusch_snr_db"])))
        res.append(_cmp(f"{rid} ul_phr", _f(o["ul_phr"]), _f(n["last_phr_db"])))
        res.append(_cmp(f"{rid} n_active", _f(o["n_active"]), _f(n["n_samples"])))

    # ---- ping ----------------------------------------------------------------
    oldp = {r["file"]: r for r in _read(paths.DATA_BASELINE / "ping_summary.csv")}
    newp = {r["file"]: r for r in _read(paths.DATA_V2 / "ping_summary.csv")}
    for k, o in oldp.items():
        n = newp.get(k, {})
        for col in ("min", "mean", "max", "sd", "loss_pct", "jitter_mean_abs_delta"):
            res.append(_cmp(f"ping {k} {col}", _f(o.get(col)), _f(n.get(col))))

    # ---- 03-Aug UE metrics row count ----------------------------------------
    old_rows = len(_read(paths.DATA_BASELINE / "aug03_metrics.csv"))
    new_rows = sum(
        1 for u in paths.log_units((3,))
        for _ in _read_gz(paths.EXTRACTED / u.unit_id / "metrics_ue.csv.gz"))
    res.append(_cmp("aug03 Scheduler-UE rows", float(old_rows), float(new_rows), tol=0.05))

    return res


def _read_gz(p: Path):
    import gzip
    if not p.exists():
        return []
    with gzip.open(p, "rt", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main():
    res = compare()
    order = {"diff": 0, "lost": 1, "new": 2, "ok": 3, "skip": 4}
    res.sort(key=lambda r: (order[r[0]], r[1]))
    counts = {}
    for st, *_ in res:
        counts[st] = counts.get(st, 0) + 1

    print(f"{'status':7} {'metric':46} {'baseline':>12} {'rebuild':>12}  delta")
    print("-" * 96)
    for st, label, o, n, note in res:
        if st == "skip":
            continue
        fo = f"{o:12.3f}" if isinstance(o, float) else f"{'-':>12}"
        fn = f"{n:12.3f}" if isinstance(n, float) else f"{'-':>12}"
        print(f"{st:7} {label[:46]:46} {fo} {fn}  {note}")

    print("\nsummary: " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    if counts.get("diff") or counts.get("lost"):
        print("\nDifferences are expected where the old scripts aggregated differently\n"
              "(sender vs receiver, which repetitions counted). Each one should be\n"
              "explained before a number from it goes into the chapter.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
