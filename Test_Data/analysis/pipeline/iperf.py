"""iperf3 client exports, server-side JSON, and ping captures.

The CellularLab app on the UE writes a decorated transcript (emoji prefixes,
blank lines between records) wrapping ordinary iperf3 output. Only `[SUM]`
lines matter: with `-P 8` the per-stream rows are noise, the aggregate is the
measurement.

Two documented traps are handled here rather than left to the caller:

  * `receiver` is 0.00 Mb/s on the stalled 03-Aug 10 m uplink runs -- the
    results exchange at the end of the test failed even though the link had
    been carrying traffic. `throughput_Mbps` therefore prefers the sender
    figure when the receiver figure is absent or zero but interval data exists.
  * UDP downlink `loss %` is an offered-load artefact: `-b 100M -P 8` offers
    800 Mb/s into a ~40 Mb/s link, so "83 % loss" means the generator outran
    the radio, not that the radio dropped anything. Loss is recorded but
    `loss_is_meaningful` marks when it can be read as a link property.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone

# `[SUM]   5.00-6.00   sec  3.12 MBytes  26.2 Mbits/sec  <tail>`
SUM = re.compile(
    r"\[SUM\]\s+([\d.]+)-([\d.]+)\s+sec\s+([\d.]+)\s+([KMG]?)Bytes\s+"
    r"([\d.]+)\s+([KMG]?)bits/sec(.*)$")
TIME = re.compile(r"Time:\s+\w+,\s+(\d+ \w+ \d+ \d+:\d+:\d+)\s+UTC")
CMD = re.compile(r"^\s*(?:[^\x00-\x7F]\s*)*(iperf3 -c .*)$", re.M)
ITER = re.compile(r"Starting iPerf3 Test (\d+)/(\d+)")
# `10.661 ms  0/8002 (0%)`
UDP_TAIL = re.compile(r"([\d.]+)\s*ms\s+(\d+)/(\d+)\s+\(([\d.e+-]+)%\)")
RETR_TAIL = re.compile(r"^\s*(\d+)\s*$")

UNIT = {"": 1.0, "K": 1e3, "M": 1e6, "G": 1e9}


def condition(cmd: str) -> tuple[str, str]:
    """`-R` is reverse mode: the server sends, so the UE is downloading."""
    return ("UDP" if " -u" in cmd else "TCP", "DL" if " -R" in cmd else "UL")


def _blocks(text: str):
    """Split a transcript into one block per `Starting iPerf3 Test n/N`."""
    marks = [m.start() for m in ITER.finditer(text)]
    if not marks:
        return [text]
    marks.append(len(text))
    return [text[marks[i]:marks[i + 1]] for i in range(len(marks) - 1)]


def parse_export(path, iteration=1):
    """Parse one iperf3 run out of a CellularLab export. Returns a dict or None."""
    text = path.read_text(encoding="utf-8", errors="ignore")
    blocks = _blocks(text)
    if iteration - 1 >= len(blocks):
        return None
    block = blocks[iteration - 1]

    m = CMD.search(block)
    if not m:
        return None
    cmd = m.group(1).strip()
    proto, direction = condition(cmd)

    t0 = None
    if (mt := TIME.search(block)):
        t0 = datetime.strptime(mt.group(1), "%d %b %Y %H:%M:%S").replace(tzinfo=timezone.utc)

    series, summaries = [], []
    for line in block.splitlines():
        ms = SUM.search(line)
        if not ms:
            continue
        a, b, xf, xu, r, ru, tail = ms.groups()
        rec = {"t0": float(a), "t1": float(b),
               "bytes": float(xf) * UNIT[xu], "bps": float(r) * UNIT[ru],
               "role": "receiver" if "receiver" in tail else
                       ("sender" if "sender" in tail else "")}
        if (mu := UDP_TAIL.search(tail)):
            rec.update(jitter_ms=float(mu.group(1)), lost=int(mu.group(2)),
                       total=int(mu.group(3)), loss_pct=float(mu.group(4)))
        (summaries if rec["t1"] - rec["t0"] > 5 else series).append(rec)

    snd = next((s for s in summaries if s["role"] == "sender"), None)
    rcv = next((s for s in summaries if s["role"] == "receiver"), None)

    # steady state: drop the first 5 s so TCP ramp-up is excluded. Same
    # convention as the superseded scripts, so old and new numbers compare.
    mid = [s["bps"] for s in series if s["t0"] >= 5]
    allv = [s["bps"] for s in series]

    out = {
        "file": path.name, "iteration": iteration, "cmd": cmd,
        "protocol": proto, "direction": direction,
        "start_utc": t0.isoformat() if t0 else None,
        "n_intervals": len(series),
        "sender_Mbps": round(snd["bps"] / 1e6, 3) if snd else None,
        "receiver_Mbps": round(rcv["bps"] / 1e6, 3) if rcv else None,
        "mean_Mbps_5s_on": round(sum(mid) / len(mid) / 1e6, 3) if mid else None,
        "mean_Mbps_all": round(sum(allv) / len(allv) / 1e6, 3) if allv else None,
        "min_Mbps": round(min(mid) / 1e6, 3) if mid else None,
        "max_Mbps": round(max(mid) / 1e6, 3) if mid else None,
    }

    # authoritative throughput, with the receiver-stall trap handled
    rx, tx = out["receiver_Mbps"], out["sender_Mbps"]
    if rx and rx > 0:
        out["throughput_Mbps"], out["throughput_src"] = rx, "receiver"
    elif out["mean_Mbps_5s_on"]:
        out["throughput_Mbps"] = out["mean_Mbps_5s_on"]
        out["throughput_src"] = "intervals(receiver stalled)" if rx == 0 else "intervals"
    else:
        out["throughput_Mbps"], out["throughput_src"] = tx, "sender"
    out["receiver_stalled"] = int(rx == 0 and bool(mid))

    if proto == "UDP":
        src = rcv or snd
        if src and "loss_pct" in src:
            out.update(jitter_ms=src.get("jitter_ms"), loss_pct=src.get("loss_pct"),
                       lost=src.get("lost"), total=src.get("total"))
        # offered load is 100 Mb/s per stream; on the downlink that is ~20x the
        # link, so loss reflects the generator, not the radio
        out["loss_is_meaningful"] = int(direction == "UL")
    return out


def parse_series(path, iteration=1):
    """Per-second `[SUM]` interval series for one run, for time-series figures."""
    text = path.read_text(encoding="utf-8", errors="ignore")
    blocks = _blocks(text)
    if iteration - 1 >= len(blocks):
        return []
    rows = []
    for line in blocks[iteration - 1].splitlines():
        m = SUM.search(line)
        if not m:
            continue
        a, b, xf, xu, r, ru, tail = m.groups()
        if float(b) - float(a) > 5:
            continue
        rows.append({"t0": float(a), "t1": float(b), "Mbps": round(float(r) * UNIT[ru] / 1e6, 3)})
    return rows


# ---------------------------------------------------------------------------
# server-side JSON
# ---------------------------------------------------------------------------

def parse_server_json(path):
    """Server-side iperf3 JSON: the receiver's own view, and the RTT record.

    The 02-Aug files are cumulative -- one JSON object per test appended to the
    same file across locations -- so the text is split on object boundaries
    rather than handed to json.load() whole.
    """
    raw = path.read_text(encoding="utf-8", errors="ignore")
    objs, depth, start = [], 0, None
    for i, ch in enumerate(raw):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start is not None:
                try:
                    objs.append(json.loads(raw[start:i + 1]))
                except json.JSONDecodeError:
                    pass
                start = None

    tests = []
    for o in objs:
        end = o.get("end", {})
        start_o = o.get("start", {})
        params = start_o.get("test_start", {})
        sums = end.get("sum") or end.get("sum_received") or {}
        rec = {
            "protocol": params.get("protocol"),
            "num_streams": params.get("num_streams"),
            "duration_s": params.get("duration"),
            "reverse": start_o.get("test_start", {}).get("reverse"),
            "bits_per_second": sums.get("bits_per_second"),
            "Mbps": round(sums.get("bits_per_second", 0) / 1e6, 3) if sums.get("bits_per_second") else None,
            "jitter_ms": sums.get("jitter_ms"),
            "lost_percent": sums.get("lost_percent"),
            "timestamp": start_o.get("timestamp", {}).get("time"),
        }
        # TCP: max RTT and in-flight bytes across streams -- the bufferbloat evidence
        rtts = [s.get("sender", {}).get("max_rtt") for s in end.get("streams", [])
                if s.get("sender", {}).get("max_rtt")]
        if rtts:
            rec["max_rtt_us"] = max(rtts)
            rec["mean_max_rtt_us"] = sum(rtts) / len(rtts)
        tests.append(rec)
    return tests


# ---------------------------------------------------------------------------
# ping
# ---------------------------------------------------------------------------

PING_LINE = re.compile(r"icmp_seq=(\d+)\s+ttl=(\d+)\s+time=([\d.]+)\s*ms")
PING_STATS = re.compile(r"(\d+) packets transmitted, (\d+) received.*?([\d.]+)% packet loss")
PING_RTT = re.compile(r"rtt min/avg/max/mdev = ([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+)")


def parse_ping(path):
    """One ping capture -> (per-echo rows, summary dict)."""
    text = path.read_text(encoding="utf-8", errors="ignore")
    rows = [{"seq": int(m.group(1)), "ttl": int(m.group(2)), "rtt_ms": float(m.group(3))}
            for m in PING_LINE.finditer(text)]
    vals = sorted(r["rtt_ms"] for r in rows)
    n = len(vals)
    summary = {"file": path.name, "n": n}
    if n:
        mean = sum(vals) / n
        summary.update(
            min=vals[0], max=vals[-1], mean=round(mean, 3),
            median=vals[n // 2] if n % 2 else round((vals[n // 2 - 1] + vals[n // 2]) / 2, 3),
            p95=vals[min(n - 1, int(round(0.95 * (n - 1))))],
            # population sd (ddof=0), matching what `ping` itself prints as mdev
            # and what the baseline CSV used -- not the sample sd
            sd=round((sum((v - mean) ** 2 for v in vals) / n) ** 0.5, 3) if n else 0.0,
        )
        # mean absolute successive difference: the sawtooth amplitude
        seq = [r["rtt_ms"] for r in rows]
        if len(seq) > 1:
            summary["jitter_mean_abs_delta"] = round(
                sum(abs(b - a) for a, b in zip(seq, seq[1:])) / (len(seq) - 1), 3)
    if (m := PING_STATS.search(text)):
        summary.update(sent=int(m.group(1)), recv=int(m.group(2)), loss_pct=float(m.group(3)))
    if (m := PING_RTT.search(text)):
        summary.update(reported_min=float(m.group(1)), reported_avg=float(m.group(2)),
                       reported_max=float(m.group(3)), reported_mdev=float(m.group(4)))
    return rows, summary
