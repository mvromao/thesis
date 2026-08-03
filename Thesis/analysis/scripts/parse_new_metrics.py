"""Parse the new `[METRICS ] Scheduler UE` key=value lines out of the 2026-08-02 gnb.logs.

Replaces the old fixed-width trace.log parser (the TODO in SESSION_LOG_2026-08-02.md §3).
Emits one tidy row per metrics report with a real UTC timestamp, so rows can be
sliced against each iperf3 rep's start/end time.
"""
import re
import csv
from pathlib import Path
from datetime import datetime

ROOT = Path(r"d:/Documents/Thesis/thesis/Thesis/testing_data/5G_new_methodology")
OUT = Path(r"C:/Users/renedito/AppData/Local/Temp/claude/d--Documents-Thesis-thesis/b1332cd8-faa5-4c44-98cf-08890c96dfe4/scratchpad")

LINE = re.compile(r"^(\d{4}-\d\d-\d\dT[\d:.]+)\s+\[METRICS\s*\]\s+Scheduler UE (.*)$")
KV = re.compile(r"(\w+)=(\S+)")
SUFFIX = {"k": 1e3, "M": 1e6, "G": 1e9, "n": 1e-9, "u": 1e-6, "m": 1e-3}

# fields we keep, and whether they are numeric
KEEP = ["ue", "rnti", "cqi", "dl_ri", "dl_mcs", "dl_brate", "dl_nof_ok", "dl_nof_nok",
        "dl_error_rate", "dl_bs", "dl_nof_prbs", "dl_olla",
        "pusch_snr_db", "pusch_rsrp_db", "ul_ri", "ul_mcs", "ul_brate", "ul_nof_ok",
        "ul_nof_nok", "ul_error_rate", "ul_nof_prbs", "ul_olla", "bsr", "sr_count",
        "ta", "last_phr", "pusch_invalid_harqs", "pusch_invalid_csis",
        "f0f1_invalid_harqs", "f2f3f4_invalid_harqs", "f2f3f4_invalid_csis",
        "max_pdsch_distance", "max_pusch_distance", "avg_crc_delay",
        "avg_pusch_harq_delay", "avg_pucch_harq_delay", "avg_sr_to_pusch_delay"]

NUM = re.compile(r"^(-?\d+\.?\d*)([kMGnum]?)(bps|%|ns|ms|us|s)?$")


def val(s):
    """'33.1kbps'->33100, '15%'->15, '299ns'->2.99e-7, 'ovl'/'n/a'->None"""
    if s in ("n/a", "ovl", "inf", "nan"):
        return None
    m = NUM.match(s)
    if not m:
        return None
    num, mult, unit = m.groups()
    v = float(num)
    if mult:
        v *= SUFFIX[mult]
    if unit == "ns":
        v *= 1e-9
    elif unit == "us":
        v *= 1e-6
    elif unit == "ms":
        v *= 1e-3
    return v


rows = []
ovl_counts = {}
for d in sorted(p for p in ROOT.iterdir() if p.is_dir()):
    log = d / "gnb.log"
    if not log.exists():
        continue
    n_ovl = n_tot = 0
    with open(log, encoding="utf-8", errors="ignore") as f:
        for line in f:
            if "[METRICS " not in line:
                continue
            m = LINE.match(line)
            if not m:
                continue
            ts, body = m.groups()
            kv = dict(KV.findall(body))
            n_tot += 1
            if kv.get("pusch_rsrp_db") == "ovl":
                n_ovl += 1
            r = {"location": d.name, "ts": ts,
                 "rsrp_ovl": int(kv.get("pusch_rsrp_db") == "ovl")}
            for k in KEEP:
                if k in kv:
                    r[k] = kv[k] if k in ("rnti",) else val(kv[k])
            rows.append(r)
    ovl_counts[d.name] = (n_ovl, n_tot)

fields = ["location", "ts", "rsrp_ovl"] + KEEP
with open(OUT / "new_metrics.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
    w.writeheader()
    w.writerows(rows)

print(f"parsed {len(rows)} [METRICS] Scheduler UE reports -> new_metrics.csv\n")
print("PUSCH RSRP reported as 'ovl' (ADC / receiver overload):")
for k, (n, t) in ovl_counts.items():
    print(f"  {k:10s} {n:6d} / {t:6d} reports  ({100*n/max(t,1):5.1f} %)")
