"""Single streaming pass over all 24 srsRAN stack traces.

Counts per test: log-level totals, per-layer volume, normalised WARNING/ERROR
message templates, and specific event classes of interest for the thesis.
"""
import re
import json
import sys
from pathlib import Path
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor

ROOT = Path(r"d:/Documents/Thesis/thesis/Thesis/testing_data")
OUT = Path(r"C:/Users/renedito/AppData/Local/Temp/claude/d--Documents-Thesis-thesis/b1332cd8-faa5-4c44-98cf-08890c96dfe4/scratchpad")

# 2026-07-25T10:24:47.718984 [LAYER   ] [I] message...
LINE = re.compile(r"^(\d{4}-\d\d-\d\dT[\d:.]+)\s+\[([A-Z0-9\-]+)\s*\]\s+\[([IWED])\]\s*(.*)$")
NUMS = re.compile(r"[-+]?\d+\.?\d*")

EVENTS = {
    "phy_dl_late":      re.compile(r"Downlink data late"),
    "phy_ul_late":      re.compile(r"Uplink data late|Late uplink"),
    "phy_rt_failure":   re.compile(r"Real-time failure in lower PHY"),
    "fapi_late":        re.compile(r"Real-time failure in FAPI"),
    "modulator_busy":   re.compile(r"modulator is busy"),
    "rlf":              re.compile(r"RLF detected|Radio link failure|radio link failure"),
    "sched_err_ind":    re.compile(r"Discarding error indication"),
    "rf_overflow":      re.compile(r"\bOverflow\b"),
    "rf_underflow":     re.compile(r"\bUnderflow\b|\bUnderrun\b"),
    "rf_late":          re.compile(r"\bLate\b"),
    "harq_maxretx":     re.compile(r"max.?retx|[Mm]aximum number of retransmissions|max consecutive HARQ"),
    "rlc_drop":         re.compile(r"[Dd]iscard|[Dd]ropp"),
    "rach":             re.compile(r"\bPRACH\b|\bRACH\b|RandomAccess"),
    "reest":            re.compile(r"[Rr]eestablish"),
    "release":          re.compile(r"UEContextRelease|Releasing ue|ue release"),
    "crc_ko":           re.compile(r"crc=KO"),
    "crc_ok":           re.compile(r"crc=OK"),
}


def scan(folder: Path):
    tech, loc, protocol, direction = folder.parts[-4:]
    log = next((folder / f for f in ("gnb.log", "enb.log") if (folder / f).exists()), None)
    res = {
        "tech": tech, "location": loc, "protocol": protocol, "direction": direction,
        "levels": Counter(), "layers": Counter(), "templates": Counter(),
        "events": Counter(), "lines": 0, "hex_lines": 0,
        "t_first": None, "t_last": None,
    }
    if log is None:
        return res

    with open(log, encoding="utf-8", errors="ignore") as f:
        for line in f:
            res["lines"] += 1
            m = LINE.match(line)
            if not m:
                if line.startswith("    "):
                    res["hex_lines"] += 1
                continue
            ts, layer, lvl, msg = m.groups()
            if res["t_first"] is None:
                res["t_first"] = ts
            res["t_last"] = ts
            res["levels"][lvl] += 1
            res["layers"][layer] += 1
            for name, rx in EVENTS.items():
                if rx.search(msg):
                    res["events"][name] += 1
            if lvl in ("W", "E"):
                tmpl = NUMS.sub("#", msg)[:160]
                res["templates"][f"[{lvl}] {layer.strip()}: {tmpl}"] += 1
    return res


def main():
    folders = sorted(p.parent for p in ROOT.glob("*/*/*/*/trace.log"))
    out = []
    with ProcessPoolExecutor(max_workers=6) as ex:
        for r in ex.map(scan, folders):
            for k in ("levels", "layers", "templates", "events"):
                r[k] = dict(r[k])
            out.append(r)
            print(f"done {r['tech']}/{r['location']}/{r['protocol']}/{r['direction']}"
                  f"  {r['lines']:,} lines", flush=True)
    (OUT / "events.json").write_text(json.dumps(out, indent=1))
    print("wrote events.json")


if __name__ == "__main__":
    main()
