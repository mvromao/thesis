"""Parse the concatenated server-side iperf3 JSON (`test.json`) per location.

Written without -1, so each completed test appends its own JSON object with no
wrapping array -- json.load() fails on the raw file. Decode with raw_decode.
"""
import json
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(r"d:/Documents/Thesis/thesis/Thesis/testing_data/5G_new_methodology")


def objects(path):
    s = path.read_text(encoding="utf-8", errors="ignore")
    dec = json.JSONDecoder()
    i = 0
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


def summarise(o):
    st, end = o.get("start", {}), o.get("end", {})
    ts = st.get("timestamp", {})
    tstart = st.get("test_start", {})
    sent = end.get("sum_sent", {})
    recv = end.get("sum_received", {})
    # UDP puts the numbers under sum / sum_received differently
    if not sent and "sum" in end:
        sent = end["sum"]
    epoch = ts.get("timesecs")
    return {
        "utc": datetime.fromtimestamp(epoch, timezone.utc).strftime("%H:%M:%S") if epoch else None,
        "epoch": epoch,
        "proto": tstart.get("protocol"),
        "streams": tstart.get("num_streams"),
        "reverse": tstart.get("reverse"),
        "duration": tstart.get("duration"),
        "cookie": st.get("cookie", "")[:12],
        "sent_Mbps": round(sent.get("bits_per_second", 0) / 1e6, 2) if sent else None,
        "recv_Mbps": round(recv.get("bits_per_second", 0) / 1e6, 2) if recv else None,
        "sent_MB": round(sent.get("bytes", 0) / 1e6, 1) if sent else None,
        "retrans": sent.get("retransmits"),
        "jitter_ms": round(recv.get("jitter_ms", 0), 3) if recv and "jitter_ms" in recv else None,
        "lost": recv.get("lost_packets") if recv else None,
        "pkts": recv.get("packets") if recv else None,
        "loss_pct": round(recv.get("lost_percent", 0), 2) if recv and "lost_percent" in recv else None,
        "cpu_local": round(end.get("cpu_utilization_percent", {}).get("host_total", 0), 1),
        "cpu_remote": round(end.get("cpu_utilization_percent", {}).get("remote_total", 0), 1),
        "n_intervals": len(o.get("intervals", [])),
        "cc": end.get("sender_tcp_congestion"),
    }


for d in sorted(p for p in ROOT.iterdir() if p.is_dir()):
    js = d / "test.json"
    if not js.exists():
        continue
    rows = [summarise(o) for o in objects(js)]
    print("=" * 165)
    print(f"{d.name}/test.json — {len(rows)} objects")
    print("=" * 165)
    hdr = ["#", "utc", "proto", "str", "rev", "dur", "ivals", "sent_Mbps", "recv_Mbps",
           "sent_MB", "retr", "jit_ms", "lost", "pkts", "loss%", "cookie"]
    print(("{:>3} {:>9} {:>5} {:>4} {:>6} {:>5} {:>6} {:>10} {:>10} {:>8} {:>7} "
           "{:>7} {:>7} {:>7} {:>6} {:>13}").format(*hdr))
    for i, r in enumerate(rows, 1):
        print(("{:>3} {:>9} {:>5} {:>4} {:>6} {:>5} {:>6} {:>10} {:>10} {:>8} {:>7} "
               "{:>7} {:>7} {:>7} {:>6} {:>13}").format(
            i, str(r["utc"]), str(r["proto"]), str(r["streams"]), str(r["reverse"]),
            str(r["duration"]), r["n_intervals"], str(r["sent_Mbps"]), str(r["recv_Mbps"]),
            str(r["sent_MB"]), str(r["retrans"]), str(r["jitter_ms"]), str(r["lost"]),
            str(r["pkts"]), str(r["loss_pct"]), r["cookie"]))
    print()
