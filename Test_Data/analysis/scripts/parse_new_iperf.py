"""Parse the 2026-08-02 re-run campaign (CellularLab iperf3 exports).

Each .txt is one 20 s rep. Condition is read from the iperf3 command line that
CellularLab echoes at the top:  -R => downlink (reverse), -u => UDP.
"""
import re
import csv
from pathlib import Path
from datetime import datetime

ROOT = Path(r"d:/Documents/Thesis/thesis/Thesis/testing_data/5G_new_methodology")
OUT = Path(r"C:/Users/renedito/AppData/Local/Temp/claude/d--Documents-Thesis-thesis/b1332cd8-faa5-4c44-98cf-08890c96dfe4/scratchpad")

CMD = re.compile(r"^iperf3 -c .*$")
TIME = re.compile(r"Time:\s+\w+, (\d+ \w+ \d+ \d+:\d+:\d+) UTC")
# [SUM]   3.00-4.00   sec  2.25 MBytes  18.9 Mbits/sec  ...
INTERVAL = re.compile(
    r"\[SUM\]\s+([\d.]+)-([\d.]+)\s+sec\s+([\d.]+)\s+([KMG]?)Bytes\s+([\d.]+)\s+([KMG]?)bits/sec(.*)$")
UNIT = {"": 1, "K": 1e3, "M": 1e6, "G": 1e9}
LOSS = re.compile(r"([\d.]+)\s*ms\s+(\d+)/(\d+)\s+\(([\d.]+e?[-+]?\d*)%\)")
RETR = re.compile(r"^\s*(\d+)\s+(?:sender|receiver)")


def clean(line):
    """strip CellularLab's emoji prefix"""
    return re.sub(r"^[^\x00-\x7F\s]*\s*", "", line.strip()).strip()


def parse(path: Path):
    txt = [clean(l) for l in path.read_text(encoding="utf-8", errors="ignore").splitlines()]
    cmd = next((l for l in txt if l.startswith("iperf3 -c")), "")
    if not cmd:
        return None
    proto = "UDP" if " -u" in cmd else "TCP"
    direction = "DL" if " -R" in cmd else "UL"

    t0 = None
    for l in txt:
        m = TIME.search(l)
        if m:
            t0 = datetime.strptime(m.group(1), "%d %b %Y %H:%M:%S")
            break

    series, summary = [], []
    in_summary = False
    for l in txt:
        if "Test Complete" in l:
            in_summary = True
        m = INTERVAL.search(l)
        if not m:
            continue
        s, e, xfer, xu, rate, ru, tail = m.groups()
        rec = {"t0": float(s), "t1": float(e),
               "bytes": float(xfer) * UNIT[xu],
               "bps": float(rate) * UNIT[ru], "tail": tail.strip()}
        (summary if in_summary or float(e) - float(s) > 15 else series).append(rec)

    out = {"location": path.parent.name, "protocol": proto, "direction": direction,
           "file": path.name, "start_utc": t0.isoformat() if t0 else None,
           "n_intervals": len(series),
           "cmd": cmd}

    # steady-state: drop first 5 s (TCP ramp-up) per the session-log methodology
    mid = [r["bps"] for r in series if r["t0"] >= 5]
    if mid:
        out["mean_Mbps_5s_on"] = round(sum(mid) / len(mid) / 1e6, 2)
        out["min_Mbps"] = round(min(mid) / 1e6, 2)
        out["max_Mbps"] = round(max(mid) / 1e6, 2)
    allp = [r["bps"] for r in series]
    if allp:
        out["mean_Mbps_full"] = round(sum(allp) / len(allp) / 1e6, 2)

    # final SUM lines: sender then receiver
    for r in summary:
        who = "sender" if "sender" in r["tail"] else ("receiver" if "receiver" in r["tail"] else None)
        if not who:
            continue
        out[f"{who}_Mbps"] = round(r["bps"] / 1e6, 2)
        out[f"{who}_MB"] = round(r["bytes"] / 1e6, 2)
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
for f in sorted(ROOT.glob("*/*.txt")):
    r = parse(f)
    if r:
        rows.append(r)

# assign rep numbers within (location, protocol, direction) ordered by start time
rows.sort(key=lambda r: (r["location"], r["protocol"], r["direction"], r["start_utc"] or ""))
seen = {}
for r in rows:
    k = (r["location"], r["protocol"], r["direction"])
    seen[k] = seen.get(k, 0) + 1
    r["rep"] = seen[k]

fields = ["location", "protocol", "direction", "rep", "file", "start_utc", "n_intervals",
          "mean_Mbps_5s_on", "mean_Mbps_full", "min_Mbps", "max_Mbps",
          "sender_Mbps", "receiver_Mbps", "sender_MB", "receiver_MB", "sender_retr",
          "receiver_jitter_ms", "receiver_lost", "receiver_total_dg", "receiver_loss_pct",
          "sender_jitter_ms", "sender_lost", "sender_total_dg", "sender_loss_pct", "cmd"]
with open(OUT / "new_iperf_reps.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
    w.writeheader()
    w.writerows(rows)

# also dump per-second series
with open(OUT / "new_iperf_series.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh)
    w.writerow(["location", "protocol", "direction", "rep", "sec", "Mbps"])
    for r in rows:
        for s in r["_series"]:
            w.writerow([r["location"], r["protocol"], r["direction"], r["rep"],
                        s["t0"], round(s["bps"] / 1e6, 3)])

def s(v, w=7):
    return f"{'--' if v is None else v:>{w}}"


print(f"parsed {len(rows)} reps")
for r in rows:
    print(f"  {r['location']:9s} {r['protocol']} {r['direction']} rep{r['rep']} "
          f"{r['start_utc']}  steady={s(r.get('mean_Mbps_5s_on'))}  "
          f"rx={s(r.get('receiver_Mbps'))} Mb/s  "
          f"retr={s(r.get('sender_retr'), 5)}  loss%={s(r.get('receiver_loss_pct'), 5)}")
