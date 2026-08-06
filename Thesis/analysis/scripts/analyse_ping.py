"""Unloaded latency from the 2026-08-03 ping captures, and the contrast with
the loaded RTT measured by iperf3."""
import re
import csv
import statistics as st
from pathlib import Path

ROOT = Path(r"d:/Documents/Thesis/thesis/Thesis/testing_data/03-Aug")
OUT = Path(r"C:/Users/renedito/AppData/Local/Temp/claude/d--Documents-Thesis-thesis/b1332cd8-faa5-4c44-98cf-08890c96dfe4/scratchpad")

RTT = re.compile(r"icmp_seq=(\d+)\s+ttl=(\d+)\s+time=([\d.]+)\s*ms")
STATS = re.compile(r"(\d+) packets transmitted, (\d+) received.*?([\d.]+)% packet loss")
SUMM = re.compile(r"rtt min/avg/max/mdev = ([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+)")

LOC = {"ping_Loc1": "2 m, line of sight", "ping_Loc2": "5 m, partition",
       "ping_Loc3": "10 m, concrete wall"}

rows, series = [], []
for name, label in LOC.items():
    p = ROOT / name
    if not p.exists():
        print("missing", p)
        continue
    txt = p.read_text(encoding="utf-8", errors="ignore")
    samples = [(int(a), float(c)) for a, b, c in RTT.findall(txt)]
    m1, m2 = STATS.search(txt), SUMM.search(txt)
    v = [x[1] for x in samples]
    r = {"file": name, "location": label, "n": len(v),
         "sent": int(m1.group(1)) if m1 else None,
         "recv": int(m1.group(2)) if m1 else None,
         "loss_pct": float(m1.group(3)) if m1 else None,
         "min": round(min(v), 2), "mean": round(st.fmean(v), 2),
         "median": round(st.median(v), 2), "max": round(max(v), 2),
         "sd": round(st.pstdev(v), 2),
         "p95": round(sorted(v)[int(0.95 * len(v)) - 1], 2),
         "jitter_mean_abs_delta": round(
             st.fmean([abs(v[i] - v[i - 1]) for i in range(1, len(v))]), 2),
         "reported_min": float(m2.group(1)) if m2 else None,
         "reported_avg": float(m2.group(2)) if m2 else None,
         "reported_max": float(m2.group(3)) if m2 else None,
         "reported_mdev": float(m2.group(4)) if m2 else None}
    rows.append(r)
    for seq, t in samples:
        series.append({"location": label, "seq": seq, "rtt_ms": t})

print("=" * 120)
print("UNLOADED round-trip time, core -> UE, 30 ICMP echoes at 1 s (2026-08-03)")
print("=" * 120)
hdr = ["location", "n", "loss%", "min", "mean", "median", "p95", "max", "sd", "step"]
fmt = "{:<22}{:>4}{:>7}{:>8}{:>8}{:>9}{:>8}{:>8}{:>7}{:>8}"
print(fmt.format(*hdr))
for r in rows:
    print(fmt.format(r["location"], r["n"], r["loss_pct"], r["min"], r["mean"],
                     r["median"], r["p95"], r["max"], r["sd"],
                     r["jitter_mean_abs_delta"]))

print()
print("Distance has almost no effect on the floor: min RTT is 15.7-16.0 ms at every location,")
print("i.e. latency is dominated by the fixed processing/scheduling pipeline, not propagation.")
print("(10 m of air is 33 ns each way - six orders of magnitude below the measured floor.)")

print()
print("=" * 120)
print("The sawtooth: RTT walks down ~1 ms per second, then jumps back up")
print("=" * 120)
for label in LOC.values():
    v = [s["rtt_ms"] for s in series if s["location"] == label]
    deltas = [round(v[i] - v[i - 1], 1) for i in range(1, len(v))]
    ups = [d for d in deltas if d > 3]
    downs = [d for d in deltas if d < 0]
    print(f"\n{label}")
    print("  " + " ".join(f"{x:5.1f}" for x in v[:15]))
    print("  " + " ".join(f"{x:5.1f}" for x in v[15:]))
    if downs:
        print(f"  {len(downs)} downward steps, mean {st.fmean(downs):+.2f} ms/ping")
    if ups:
        print(f"  {len(ups)} jumps, mean {st.fmean(ups):+.1f} ms  "
              f"(period ~{len(v)/max(len(ups),1):.0f} pings)")

print()
print("=" * 120)
print("UNLOADED vs LOADED — what the 6.17 MB RLC queue costs")
print("=" * 120)
loaded = {"2 m, line of sight": (528.9, 1212.8),
          "5 m, partition": (229.6, 2010.9),
          "10 m, concrete wall": (1994.6, 2255.0)}
fmt2 = "{:<22}{:>14}{:>18}{:>14}"
print(fmt2.format("location", "unloaded mean", "loaded TCP-DL mean", "inflation"))
for r in rows:
    lo, hi = loaded[r["location"]]
    mid = (lo + hi) / 2
    print(fmt2.format(r["location"], f"{r['mean']:.1f} ms",
                      f"{lo:.0f}-{hi:.0f} ms", f"x{mid / r['mean']:.0f}"))

with open(OUT / "ping_summary.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader(); w.writerows(rows)
with open(OUT / "ping_series.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["location", "seq", "rtt_ms"])
    w.writeheader(); w.writerows(series)
print("\nwrote ping_summary.csv, ping_series.csv")
