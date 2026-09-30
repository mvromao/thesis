"""MAC bit rate against iperf3 goodput, per repetition and per condition.

Round 1 throughput (4G and 5G) is the RAN console's MAC `brate`, averaged over
the seconds at >= 20 % of the test's peak (`console.active`). Rounds 2-3 report
iperf3 receiver-side goodput. This recomputes Rounds 2-3 from the gNB's own
per-second `[METRICS ]` bit rate under the same 20 % rule, so every round can be
compared with the 4G baseline at the same layer, and gives the MAC/iperf3 ratio
where both exist.

Window per rep: 3 s before the iperf3 start to 35 s after (the gNB keeps
draining its queue after iperf3 stops), cut 3 s before the next rep's start.

Writes data_v2/mac_vs_iperf_reps.csv and data_v2/mac_vs_iperf_summary.csv.
Run from Test_Data/analysis:  python -m pipeline.mac_vs_iperf
"""
import csv
import statistics as st
from collections import defaultdict
from datetime import datetime, timedelta

from . import build_tables as bt
from . import paths

PRE_S, POST_S, FRAC = 3.0, 35.0, 0.20


def _f(v):
    return None if v in ("", None) else float(v)


def _t(iso):
    return datetime.fromisoformat(iso).replace(tzinfo=None)


def per_rep(reps):
    starts = defaultdict(list)
    for r in reps:
        if r["start_utc"]:
            starts[r["unit_id"]].append(_t(r["start_utc"]))
    cache, out = {}, []
    for r in reps:
        row = {k: r[k] for k in ("rep_id", "round", "tech", "location", "protocol",
                                 "direction", "variant", "throughput_src",
                                 "receiver_Mbps", "sender_Mbps")}
        row["iperf3_Mbps"] = _f(r["throughput_Mbps"]) if r["round"] != "1" else None
        if r["round"] == "1":
            row.update(mac_Mbps=_f(r["throughput_Mbps"]), n_active=r["n_samples"])
        elif r["start_utc"]:
            u = r["unit_id"]
            if u not in cache:
                cache[u] = bt.load_metrics(u)
            s = _t(r["start_utc"])
            e = s + timedelta(seconds=POST_S)
            nxt = min((t for t in starts[u] if t > s), default=None)
            if nxt and nxt - timedelta(seconds=PRE_S) < e:
                e = nxt - timedelta(seconds=PRE_S)
            key = "dl_brate_bps" if r["direction"] == "DL" else "ul_brate_bps"
            v = [_f(x.get(key)) for x in cache[u]
                 if s - timedelta(seconds=PRE_S) <= x["_t"] <= e]
            v = [x for x in v if x is not None]
            act = [x for x in v if x >= FRAC * max(v)] if v else []
            row.update(mac_Mbps=round(st.mean(act) / 1e6, 3) if act else None,
                       n_active=len(act))
        mac, ipf = row.get("mac_Mbps"), row["iperf3_Mbps"]
        row["mac_over_iperf3"] = round(mac / ipf, 3) if mac and ipf else None
        out.append(row)
    return out


def summary(rows):
    g = defaultdict(list)
    for r in rows:
        g[(r["tech"], r["round"], r["variant"], r["location"],
           r["protocol"], r["direction"])].append(r)
    out = []
    for (tech, rd, var, loc, p, d), L in sorted(g.items()):
        mac = [r["mac_Mbps"] for r in L if r.get("mac_Mbps") is not None]
        ipf = [r["iperf3_Mbps"] for r in L if r["iperf3_Mbps"] is not None]
        # reps whose iperf3 figure is not receiver-side (stalled or missing receiver)
        fallback = sum(1 for r in L if rd != "1" and r["throughput_src"] != "receiver")
        m = st.mean(mac) if mac else None
        i = st.mean(ipf) if ipf else None
        out.append(dict(tech=tech, round=rd, variant=var, location=loc, protocol=p,
                        direction=d, n=len(L), mac_Mbps=round(m, 2) if m else None,
                        iperf3_Mbps=round(i, 2) if i else None,
                        mac_over_iperf3=round(m / i, 3) if m and i and not fallback else None,
                        n_iperf3_fallback=fallback))
    return out


def _write(path, rows):
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def main():
    reps = list(csv.DictReader(open(paths.DATA_V2 / "reps.csv")))
    rows = per_rep(reps)
    _write(paths.DATA_V2 / "mac_vs_iperf_reps.csv", rows)
    _write(paths.DATA_V2 / "mac_vs_iperf_summary.csv", summary(rows))


if __name__ == "__main__":
    main()
