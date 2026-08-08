"""Mine the server-side iperf3 JSON: RTT, congestion window, retransmissions, UDP jitter.

The three test.json files are CUMULATIVE (the server was never restarted), so
Loc3_10m/test.json holds the whole session. We read that one and assign each test
object to a location by its timestamp.
"""
import json
import csv
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(r"d:/Documents/Thesis/thesis/Thesis/testing_data/5G_new_methodology")
OUT = Path(r"C:/Users/renedito/AppData/Local/Temp/claude/d--Documents-Thesis-thesis/b1332cd8-faa5-4c44-98cf-08890c96dfe4/scratchpad")

# location windows in UTC on 2026-08-02 (from the gNB startup times)
WINDOWS = [("warm-up", "15:00:00", "15:10:00"),
           ("Loc1_2m", "15:10:00", "15:25:00"),
           ("Loc2_5m", "15:30:00", "15:45:00"),
           ("Loc3_10m", "15:48:00", "16:00:00")]


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


def loc_of(hhmmss):
    for name, lo, hi in WINDOWS:
        if lo <= hhmmss < hi:
            return name
    return "?"


tests, intervals = [], []
for o in objects(ROOT / "Loc3_10m" / "test.json"):
    st, end = o.get("start", {}), o.get("end", {})
    ts = st.get("timestamp", {}).get("timesecs")
    tstart = st.get("test_start", {})
    if not ts or not tstart:
        continue
    utc = datetime.fromtimestamp(ts, timezone.utc).strftime("%H:%M:%S")
    proto = tstart.get("protocol")
    rev = bool(tstart.get("reverse"))
    direction = "DL" if rev else "UL"
    loc = loc_of(utc)

    streams = end.get("streams", [])
    row = {"location": loc, "utc": utc, "protocol": proto, "direction": direction,
           "cookie": st.get("cookie", "")[:12]}

    if proto == "TCP" and rev:
        # server is the sender -> it holds RTT / cwnd / retransmits
        snd = [s["sender"] for s in streams if "sender" in s]
        if snd:
            row["server_Mbps"] = round(sum(s["bits_per_second"] for s in snd) / 1e6, 2)
            row["retransmits"] = sum(s.get("retransmits", 0) for s in snd)
            row["mean_rtt_ms"] = round(sum(s["mean_rtt"] for s in snd) / len(snd) / 1000, 1)
            row["min_rtt_ms"] = round(min(s["min_rtt"] for s in snd) / 1000, 1)
            row["max_rtt_ms"] = round(max(s["max_rtt"] for s in snd) / 1000, 1)
            row["max_cwnd_kB"] = round(max(s["max_snd_cwnd"] for s in snd) / 1e3, 1)
            tot_bytes = sum(s["bytes"] for s in snd)
            row["retx_per_MB"] = round(row["retransmits"] / (tot_bytes / 1e6), 1) if tot_bytes else None
    elif proto == "TCP":
        rcv = end.get("sum_received", {})
        row["server_Mbps"] = round(rcv.get("bits_per_second", 0) / 1e6, 2)
    else:  # UDP
        summ = end.get("sum") or end.get("sum_received") or {}
        row["server_Mbps"] = round(summ.get("bits_per_second", 0) / 1e6, 2)
        if "jitter_ms" in summ:
            row["jitter_ms"] = round(summ["jitter_ms"], 2)
            row["lost"] = summ.get("lost_packets")
            row["packets"] = summ.get("packets")
            row["loss_pct"] = round(summ.get("lost_percent", 0), 2)
        # per-stream jitter spread
        js = [s.get("udp", {}).get("jitter_ms") for s in streams if "udp" in s]
        js = [j for j in js if j is not None]
        if js:
            row["jitter_max_ms"] = round(max(js), 2)

    row["cpu_server"] = round(end.get("cpu_utilization_percent", {}).get("host_total", 0), 1)
    row["cpu_ue"] = round(end.get("cpu_utilization_percent", {}).get("remote_total", 0), 1)
    tests.append(row)

    # per-interval RTT/cwnd for TCP DL
    if proto == "TCP" and rev:
        for iv in o.get("intervals", []):
            ss = iv.get("streams", [])
            if not ss:
                continue
            s0 = iv.get("sum", {})
            rtts = [x["rtt"] for x in ss if "rtt" in x]
            cwnds = [x["snd_cwnd"] for x in ss if "snd_cwnd" in x]
            intervals.append({
                "location": loc, "utc": utc, "cookie": row["cookie"],
                "sec": round(s0.get("start", 0), 1),
                "Mbps": round(s0.get("bits_per_second", 0) / 1e6, 2),
                "retransmits": s0.get("retransmits"),
                "rtt_ms": round(sum(rtts) / len(rtts) / 1000, 1) if rtts else None,
                "rtt_max_ms": round(max(rtts) / 1000, 1) if rtts else None,
                "cwnd_kB": round(sum(cwnds) / 1e3, 1) if cwnds else None,
            })

keys = sorted({k for r in tests for k in r})
order = ["location", "utc", "protocol", "direction", "server_Mbps", "retransmits",
         "retx_per_MB", "mean_rtt_ms", "min_rtt_ms", "max_rtt_ms", "max_cwnd_kB",
         "jitter_ms", "jitter_max_ms", "lost", "packets", "loss_pct",
         "cpu_server", "cpu_ue", "cookie"]
order += [k for k in keys if k not in order]
with open(OUT / "server_tests.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=order, extrasaction="ignore")
    w.writeheader(); w.writerows(tests)
with open(OUT / "server_intervals.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["location", "utc", "cookie", "sec", "Mbps",
                                      "retransmits", "rtt_ms", "rtt_max_ms", "cwnd_kB"])
    w.writeheader(); w.writerows(intervals)

print(f"{len(tests)} completed tests, {len(intervals)} TCP-DL intervals\n")
hdr = ["loc", "utc", "pr", "dir", "Mbps", "retr", "/MB", "rtt", "min", "max", "cwnd",
       "jit", "loss%"]
fmt = "{:<9}{:>9}{:>5}{:>4}{:>8}{:>7}{:>7}{:>7}{:>7}{:>7}{:>8}{:>7}{:>7}"
print(fmt.format(*hdr))
for r in tests:
    print(fmt.format(
        r["location"], r["utc"], r["protocol"][:3], r["direction"],
        str(r.get("server_Mbps", "")), str(r.get("retransmits", "")),
        str(r.get("retx_per_MB", "")), str(r.get("mean_rtt_ms", "")),
        str(r.get("min_rtt_ms", "")), str(r.get("max_rtt_ms", "")),
        str(r.get("max_cwnd_kB", "")), str(r.get("jitter_ms", "")),
        str(r.get("loss_pct", ""))))
print("\nwrote server_tests.csv, server_intervals.csv")
