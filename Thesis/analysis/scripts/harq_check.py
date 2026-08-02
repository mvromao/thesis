"""Do 5G uplink HARQ retransmissions actually happen, given rv=0 on 100% of PUSCH?

Track each HARQ process id: a KO followed by another transmission on the same
h_id is a retransmission. Counts how many attempts each transport block needed.
"""
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(r"d:/Documents/Thesis/thesis/Thesis/testing_data")
PUSCH = re.compile(r"PUSCH: rnti=(\S+) h_id=(\d+).*?tbs=(\d+) crc=(OK|KO)")

for rel in ["5G/Loc_3_10m/TCP/DL/gnb.log", "5G/Loc_1_2m/TCP/DL/gnb.log",
            "5G/Loc_2_5m/TCP/UL/gnb.log"]:
    open_tb = defaultdict(int)          # h_id -> consecutive failed attempts
    attempts_hist = Counter()
    ko_then_same_hid = 0
    ko_total = 0
    prev_hid = None
    prev_ko = False
    with open(ROOT / rel, encoding="utf-8", errors="ignore") as f:
        for line in f:
            m = PUSCH.search(line)
            if not m:
                continue
            _rnti, hid, _tbs, crc = m.groups()
            if prev_ko and hid == prev_hid:
                ko_then_same_hid += 1
            if crc == "KO":
                ko_total += 1
                open_tb[hid] += 1
            else:
                attempts_hist[open_tb[hid] + 1] += 1
                open_tb[hid] = 0
            prev_hid, prev_ko = hid, crc == "KO"

    tot = sum(attempts_hist.values())
    print(f"\n{rel}")
    print(f"  PUSCH CRC=KO: {ko_total}")
    print(f"  KO immediately followed by same h_id (retx on same process): {ko_then_same_hid}")
    print("  attempts needed per successfully decoded TB:")
    for k in sorted(attempts_hist):
        print(f"    {k:2d} attempt(s): {attempts_hist[k]:6d}  ({100*attempts_hist[k]/max(tot,1):5.2f} %)")
