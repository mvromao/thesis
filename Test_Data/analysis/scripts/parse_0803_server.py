"""Server-side iperf3 JSON for the 2026-08-03 campaign (one file per location this time)."""
import json
import csv
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(r"d:/Documents/Thesis/thesis/Thesis/testing_data/03-Aug")
OUT = Path(r"C:/Users/renedito/AppData/Local/Temp/claude/d--Documents-Thesis-thesis/b1332cd8-faa5-4c44-98cf-08890c96dfe4/scratchpad")

FILES = {"Location1": "test1.json", "Location2": "test2.json",
         "Location3": "test3.json", "Location3_TDD": "test3_tdd.json"}


def objects(path):
    s = path.read_text(encoding="utf-8", errors="ignore")
    dec, i = json.JSONDecoder(), 0
    while i < len(s):
        while i < len(s) and s[i] in " \t\r\n":
            i += 1
        if i >= len(s):
            return
        try:
            o, i = dec.raw_decode(s, i)
        except json.JSONDecodeError:
            return
        yield o


rows, ivals = [], []
for loc, fname in FILES.items():
    p = ROOT / loc / fname
    if not p.exists():
        print("missing", p)
        continue
    for o in objects(p):
        st, end = o.get("start", {}), o.get("end", {})
        ts = st.get("timestamp", {}).get("timesecs")
        tstart = st.get("test_start", {})
        if not ts or not tstart:
            continue
        proto, rev = tstart.get("protocol"), bool(tstart.get("reverse"))
        direction = "DL" if rev else "UL"
        r = {"location": loc, "protocol": proto, "direction": direction,
             "utc": datetime.fromtimestamp(ts, timezone.utc).strftime("%H:%M:%S"),
             "cookie": st.get("cookie", "")[:12],
             "duration_s": round(tstart.get("duration", 0), 1)}
        streams = end.get("streams", [])
        if proto == "TCP" and rev:                      # server = sender
            snd = [s["sender"] for s in streams if "sender" in s]
            if snd:
                r["Mbps"] = round(sum(s["bits_per_second"] for s in snd) / 1e6, 2)
                r["retransmits"] = sum(s.get("retransmits", 0) for s in snd)
                r["mean_rtt_ms"] = round(sum(s["mean_rtt"] for s in snd) / len(snd) / 1000, 1)
                r["min_rtt_ms"] = round(min(s["min_rtt"] for s in snd) / 1000, 1)
                r["max_rtt_ms"] = round(max(s["max_rtt"] for s in snd) / 1000, 1)
            for iv in o.get("intervals", []):
                ss, s0 = iv.get("streams", []), iv.get("sum", {})
                rt = [x["rtt"] for x in ss if "rtt" in x]
                cw = [x["snd_cwnd"] for x in ss if "snd_cwnd" in x]
                ivals.append({"location": loc, "cookie": r["cookie"],
                              "sec": round(s0.get("start", 0), 1),
                              "Mbps": round(s0.get("bits_per_second", 0) / 1e6, 2),
                              "rtt_ms": round(sum(rt) / len(rt) / 1000, 1) if rt else None,
                              "cwnd_kB": round(sum(cw) / 1e3, 1) if cw else None})
        elif proto == "TCP":                            # server = receiver (uplink)
            rcv = end.get("sum_received", {})
            r["Mbps"] = round(rcv.get("bits_per_second", 0) / 1e6, 2)
            r["actual_s"] = round(rcv.get("seconds", 0), 1)
            snt = end.get("sum_sent", {})
            r["sender_Mbps"] = round(snt.get("bits_per_second", 0) / 1e6, 2)
            r["retransmits"] = snt.get("retransmits")
        else:                                           # UDP
            summ = end.get("sum") or end.get("sum_received") or {}
            r["Mbps"] = round(summ.get("bits_per_second", 0) / 1e6, 2)
            r["actual_s"] = round(summ.get("seconds", 0), 1)
            if "jitter_ms" in summ:
                r["jitter_ms"] = round(summ["jitter_ms"], 2)
                r["lost"] = summ.get("lost_packets")
                r["packets"] = summ.get("packets")
                r["loss_pct"] = round(summ.get("lost_percent", 0), 2)
        rows.append(r)

order = ["location", "utc", "protocol", "direction", "Mbps", "sender_Mbps", "actual_s",
         "retransmits", "mean_rtt_ms", "min_rtt_ms", "max_rtt_ms", "jitter_ms",
         "lost", "packets", "loss_pct", "duration_s", "cookie"]
with open(OUT / "aug03_server_tests.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=order, extrasaction="ignore")
    w.writeheader(); w.writerows(rows)
with open(OUT / "aug03_server_intervals.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["location", "cookie", "sec", "Mbps", "rtt_ms", "cwnd_kB"])
    w.writeheader(); w.writerows(ivals)

print(f"{len(rows)} completed tests on the server, {len(ivals)} TCP-DL intervals\n")
fmt = "{:<15}{:>9}{:>5}{:>4}{:>9}{:>10}{:>9}{:>7}{:>9}{:>8}{:>7}"
print(fmt.format("loc", "utc", "pr", "dir", "Mbps", "sender", "actual_s", "retr",
                 "meanRTT", "jitter", "loss%"))
for r in rows:
    print(fmt.format(r["location"], r["utc"], r["protocol"][:3], r["direction"],
                     str(r.get("Mbps", "")), str(r.get("sender_Mbps", "")),
                     str(r.get("actual_s", "")), str(r.get("retransmits", "")),
                     str(r.get("mean_rtt_ms", "")), str(r.get("jitter_ms", "")),
                     str(r.get("loss_pct", ""))))
