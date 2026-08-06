"""[METRICS ] Scheduler UE extraction for the 2026-08-03 campaign."""
import re
import csv
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor

ROOT = Path(r"d:/Documents/Thesis/thesis/Thesis/testing_data/03-Aug")
OUT = Path(r"C:/Users/renedito/AppData/Local/Temp/claude/d--Documents-Thesis-thesis/b1332cd8-faa5-4c44-98cf-08890c96dfe4/scratchpad")

LINE = re.compile(r"^(\d{4}-\d\d-\d\dT[\d:.]+)\s+\[METRICS\s*\]\s+Scheduler UE (.*)$")
KV = re.compile(r"(\w+)=(\S+)")
SUF = {"k": 1e3, "M": 1e6, "G": 1e9, "n": 1e-9, "u": 1e-6, "m": 1e-3}
NUM = re.compile(r"^(-?\d+\.?\d*)([kMGnum]?)(bps|%|ns|ms|us|s)?$")

KEEP = ["cqi", "dl_ri", "dl_mcs", "dl_brate", "dl_nof_ok", "dl_nof_nok", "dl_error_rate",
        "dl_bs", "dl_nof_prbs", "dl_olla", "pusch_snr_db", "pusch_rsrp_db", "ul_ri",
        "ul_mcs", "ul_brate", "ul_nof_ok", "ul_nof_nok", "ul_error_rate", "ul_nof_prbs",
        "ul_olla", "bsr", "sr_count", "ta", "last_phr", "pusch_invalid_harqs",
        "pusch_invalid_csis", "f0f1_invalid_harqs", "f2f3f4_invalid_harqs",
        "max_pdsch_distance", "max_pusch_distance", "avg_crc_delay"]


def val(s):
    if s in ("n/a", "ovl", "inf", "nan"):
        return None
    m = NUM.match(s)
    if not m:
        return None
    n, mult, unit = m.groups()
    v = float(n) * (SUF[mult] if mult else 1)
    if unit == "ns": v *= 1e-9
    elif unit == "us": v *= 1e-6
    elif unit == "ms": v *= 1e-3
    return v


def scan(folder: Path):
    log = next(iter(sorted(folder.glob("gnb*.log"))), None)
    rows, n_ovl, n_tot = [], 0, 0
    if log is None:
        return folder.name, rows, n_ovl, n_tot
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
            ovl = kv.get("pusch_rsrp_db") == "ovl"
            n_ovl += ovl
            r = {"location": folder.name, "ts": ts, "rsrp_ovl": int(ovl)}
            for k in KEEP:
                if k in kv:
                    r[k] = val(kv[k])
            rows.append(r)
    return folder.name, rows, n_ovl, n_tot


if __name__ == "__main__":
    folders = sorted(p for p in ROOT.iterdir() if p.is_dir())
    allrows = []
    with ProcessPoolExecutor(max_workers=4) as ex:
        for name, rows, n_ovl, n_tot in ex.map(scan, folders):
            allrows += rows
            print(f"{name:16s} {n_tot:6d} metrics reports, "
                  f"{n_ovl:5d} with pusch_rsrp_db=ovl ({100*n_ovl/max(n_tot,1):5.1f} %)")
    fields = ["location", "ts", "rsrp_ovl"] + KEEP
    with open(OUT / "aug03_metrics.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader(); w.writerows(allrows)
    print(f"\nwrote aug03_metrics.csv ({len(allrows)} rows)")
