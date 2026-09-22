"""Cross-check the AMF registration timings against the gNB's NGAP captures.

The control-plane figures in Chapter 6 (Table "registration-time") are measured
inside the core, between the Open5GS AMF's "Registration request" and
"Registration complete" log lines.  This script measures the same procedure from
the outside, in the NGAP captures written by the gNB, and pairs the two.

For every registration that appears in a *_ngap.pcap it measures

    InitialUEMessage (Registration request)  ->  the DownlinkNASTransport with
    which the AMF closes the procedure (the configuration update command)

and matches it, by wall-clock time, to the corresponding AMF log entry.  The two
hosts keep independent clocks, so agreement between the intervals is evidence
that the reported times are a property of the procedure and not of the logging.

Needs tshark (Wireshark).  Run from anywhere; the paths below are absolute.
"""

import glob
import gzip
import os
import re
import statistics as st
import subprocess
from datetime import datetime, timedelta, timezone

TSHARK = r"C:/Program Files/Wireshark/tshark.exe"
ROOT = r"D:/Documents/Thesis/thesis/Test_Data/testing_data"
LOGS = os.path.join(ROOT, "logs")

# The core logs carry no year; the campaign ran in 2026.
YEAR = 2026
# The lab machines run in local time (WEST, UTC+1) during the campaign.
LOCAL = timezone(timedelta(hours=1))

TS = re.compile(r"^(\d\d)/(\d\d) (\d\d):(\d\d):(\d\d)\.(\d\d\d):")


def log_lines(prefix):
    """Every line of an Open5GS log and its rotated .gz siblings."""
    paths = [os.path.join(LOGS, prefix)]
    paths += sorted(glob.glob(os.path.join(LOGS, prefix + ".*.gz")))
    for path in paths:
        if not os.path.exists(path):
            continue
        opener = gzip.open if path.endswith(".gz") else open
        with opener(path, "rt", errors="replace") as fh:
            for line in fh:
                yield line.rstrip("\n")


def stamp(line):
    m = TS.match(line)
    if not m:
        return None
    month, day, hour, minute, sec, ms = map(int, m.groups())
    return datetime(YEAR, month, day, hour, minute, sec, ms * 1000)


def amf_registrations():
    """(start, duration_ms) for every completed registration in the AMF log."""
    out, start = [], None
    for line in log_lines("amf.log"):
        ts = stamp(line)
        if ts is None:
            continue
        if "Registration request" in line:
            start = ts
        elif "Registration complete" in line and start is not None:
            out.append((start, (ts - start).total_seconds() * 1000))
            start = None
    return out


def ngap_registrations():
    """(wall_clock, duration_ms, file) for every registration seen in a capture."""
    out = []
    pattern = os.path.join(ROOT, "**", "*ngap*.pcap")
    for path in sorted(glob.glob(pattern, recursive=True)):
        dump = subprocess.run(
            [TSHARK, "-r", path, "-Y", "ngap", "-T", "fields",
             "-e", "frame.time_epoch", "-e", "_ws.col.Info"],
            capture_output=True, text=True).stdout.strip().splitlines()
        events = [(float(p[0]), p[1])
                  for p in (line.split("\t") for line in dump) if len(p) >= 2]
        for i, (ts, info) in enumerate(events):
            if not ("InitialUEMessage" in info and "Registration request" in info):
                continue
            # The closing message is the first DownlinkNASTransport that follows
            # the InitialContextSetupRequest.  Skipping past that request matters
            # for the one registration that ran a full authentication exchange,
            # where earlier DownlinkNASTransports carry the identity and
            # authentication requests instead.
            tail = events[i + 1:i + 16]
            after_ics = False
            end = None
            for t, inf in tail:
                if inf.startswith("InitialContextSetupResponse"):
                    after_ics = True
                elif after_ics and inf.startswith("DownlinkNASTransport"):
                    end = t
                    break
            if end is None:
                continue
            wall = datetime.fromtimestamp(ts, LOCAL).replace(tzinfo=None)
            out.append((wall, (end - ts) * 1000,
                        os.path.relpath(path, ROOT).replace("\\", "/")))
    return out


def main():
    amf = amf_registrations()
    pcap = ngap_registrations()

    print(f"{'wall clock':<21}{'pcap':>7}{'AMF log':>9}{'diff':>7}  capture")
    pairs = []
    for wall, ms, rel in sorted(pcap):
        best = min(amf, key=lambda a: abs((a[0] - wall).total_seconds()))
        if abs((best[0] - wall).total_seconds()) >= 3:
            print(f"{str(wall)[:21]:<21}{ms:>7.0f}{'-':>9}{'-':>7}  {rel}  (no log match)")
            continue
        pairs.append((ms, best[1]))
        print(f"{str(wall)[:21]:<21}{ms:>7.0f}{best[1]:>9.0f}"
              f"{ms - best[1]:>7.1f}  {rel}")

    if not pairs:
        return
    diffs = [a - b for a, b in pairs]
    print(f"\nmatched registrations: {len(pairs)}")
    print(f"  median from the captures : {st.median(a for a, _ in pairs):.0f} ms")
    print(f"  median from the AMF log  : {st.median(b for _, b in pairs):.0f} ms")
    print(f"  per-pair difference      : median {st.median(diffs):.1f} ms, "
          f"range {min(diffs):.1f} to {max(diffs):.1f} ms")

    full = [d for _, d in amf if d]
    campaign = [d for s, d in amf if s.strftime("%m/%d") != "07/17"]
    print(f"\nAMF log, all registrations      : n={len(full)} "
          f"median={st.median(full):.0f} ms")
    print(f"AMF log, campaign days only     : n={len(campaign)} "
          f"median={st.median(campaign):.0f} ms  (the figure used in Chapter 6)")


if __name__ == "__main__":
    main()
