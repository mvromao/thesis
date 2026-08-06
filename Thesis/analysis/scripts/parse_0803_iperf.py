"""Parse the 2026-08-03 campaign (rx_gain 60) CellularLab exports.

Differences from the 08-02 parser: new folder layout (Location1/2/3, Location3_TDD)
and one file can hold several iterations ("Starting iPerf3 Test n/N"), as the TDD
isolation run does.
"""
import re
import csv
from pathlib import Path
from datetime import datetime

ROOT = Path(r"d:/Documents/Thesis/thesis/Thesis/testing_data/03-Aug")
OUT = Path(r"C:/Users/renedito/AppData/Local/Temp/claude/d--Documents-Thesis-thesis/b1332cd8-faa5-4c44-98cf-08890c96dfe4/scratchpad")

TIME = re.compile(r"Time:\s+\w+, (\d+ \w+ \d+ \d+:\d+:\d+) UTC")
INTERVAL = re.compile(
    r"\[SUM\]\s+([\d.]+)-([\d.]+)\s+sec\s+([\d.]+)\s+([KMG]?)Bytes\s+([\d.]+)\s+([KMG]?)bits/sec(.*)$")
UNIT = {"": 1, "K": 1e3, "M": 1e6, "G": 1e9}
LOSS = re.compile(r"([\d.]+)\s*ms\s+(\d+)/(\d+)\s+\(([\d.]+e?[-+]?\d*)%\)")
RETR = re.compile(r"^\s*(\d+)\s+(?:sender|receiver)")
ITER = re.compile(r"Starting iPerf3 Test (\d+)/(\d+)")


def clean(l):
    return re.sub(r"^[^\x00-\x7F\s]*\s*", "", l.strip()).strip()


def parse_block(lines, loc, fname, iter_no):
    cmd = next((l for l in lines if l.startswith("iperf3 -c")), "")
    if not cmd:
        return None
    proto = "UDP" if " -u" in cmd else "TCP"
    direction = "DL" if " -R" in cmd else "UL"
    t0 = None
    for l in lines:
        m = TIME.search(l)
        if m:
            t0 = datetime.strptime(m.group(1), "%d %b %Y %H:%M:%S")
            break

    series, summary, in_sum = [], [], False
    for l in lines:
        if "Test Complete" in l:
            in_sum = True
        m = INTERVAL.search(l)
        if not m:
            continue
        s, e, xf, xu, r, ru, tail = m.groups()
        rec = {"t0": float(s), "t1": float(e), "bps": float(r) * UNIT[ru],
               "bytes": float(xf) * UNIT[xu], "tail": tail.strip()}
        (summary if in_sum or float(e) - float(s) > 15 else series).append(rec)

    out = {"location": loc, "protocol": proto, "direction": direction, "file": fname,
           "iter": iter_no, "start_utc": t0.isoformat() if t0 else None,
           "n_intervals": len(series), "cmd": cmd}
    mid = [r["bps"] for r in series if r["t0"] >= 5]
    if mid:
        out["mean_Mbps_5s_on"] = round(sum(mid) / len(mid) / 1e6, 2)
        out["min_Mbps"] = round(min(mid) / 1e6, 2)
        out["max_Mbps"] = round(max(mid) / 1e6, 2)
    if series:
        out["mean_Mbps_full"] = round(sum(r["bps"] for r in series) / len(series) / 1e6, 2)
    for r in summary:
        who = "sender" if "sender" in r["tail"] else ("receiver" if "receiver" in r["tail"] else None)
        if not who:
            continue
        out[f"{who}_Mbps"] = round(r["bps"] / 1e6, 2)
        out[f"{who}_MB"] = round(r["bytes"] / 1e6, 2)
        out[f"{who}_secs"] = round(r["t1"] - r["t0"], 2)
        lm = LOSS.search(r["tail"])
        if lm:
            out[f"{who}_jitter_ms"] = float(lm.group(1))
            out[f"{who}_lost"] = int(lm.group(2))
            out[f"{who}_total_dg"] = int(lm.group(3))
            out[f"{who}_loss_pct"] = float(lm.group(4))
        else:
            rt = RETR.search(r["tail"])
            if rt:
                out[f"{who}_retr"] = int(rt.group(1))
    out["_series"] = series
    return out


rows = []
for f in sorted(ROOT.glob("*/iPerf3_*.txt")):
    lines = [clean(l) for l in f.read_text(encoding="utf-8", errors="ignore").splitlines()]
    # split into iteration blocks
    starts = [i for i, l in enumerate(lines) if ITER.search(l)]
    if not starts:
        starts = [0]
    bounds = starts + [len(lines)]
    for n, (a, b) in enumerate(zip(bounds[:-1], bounds[1:]), 1):
        r = parse_block(lines[a:b], f.parent.name, f.name, n)
        if r:
            rows.append(r)

rows.sort(key=lambda r: (r["location"], r["protocol"], r["direction"], r["start_utc"] or ""))
seen = {}
for r in rows:
    k = (r["location"], r["protocol"], r["direction"])
    seen[k] = seen.get(k, 0) + 1
    r["rep"] = seen[k]

fields = ["location", "protocol", "direction", "rep", "iter", "file", "start_utc",
          "n_intervals", "mean_Mbps_5s_on", "mean_Mbps_full", "min_Mbps", "max_Mbps",
          "sender_Mbps", "receiver_Mbps", "sender_MB", "receiver_MB", "sender_secs",
          "receiver_secs", "sender_retr", "receiver_jitter_ms", "receiver_lost",
          "receiver_total_dg", "receiver_loss_pct", "cmd"]
with open(OUT / "aug03_iperf_reps.csv", "w", newline="", encoding="utf-8") as fh:
    csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore").writeheader()
    w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
    w.writerows(rows)
with open(OUT / "aug03_iperf_series.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh)
    w.writerow(["location", "protocol", "direction", "rep", "sec", "Mbps"])
    for r in rows:
        for s in r["_series"]:
            w.writerow([r["location"], r["protocol"], r["direction"], r["rep"],
                        s["t0"], round(s["bps"] / 1e6, 3)])


def s(v, w=7):
    return f"{'--' if v is None else v:>{w}}"


print(f"parsed {len(rows)} reps\n")
for r in rows:
    print(f"  {r['location']:16s} {r['protocol']} {r['direction']} rep{r['rep']} "
          f"{str(r['start_utc'])[11:]}  steady={s(r.get('mean_Mbps_5s_on'))}  "
          f"rx={s(r.get('receiver_Mbps'))}  dur={s(r.get('receiver_secs'),6)}s  "
          f"retr={s(r.get('sender_retr'),5)}  loss%={s(r.get('receiver_loss_pct'),5)}")
